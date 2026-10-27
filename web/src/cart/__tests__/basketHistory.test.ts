import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import {
  loadBasketHistory,
  saveBasketHistory,
  createSnapshotFromPlan,
  pushSnapshotToHistory,
  calculateBasketDelta,
  calculateHistoryStats,
  clearBasketHistory,
  BASKET_HISTORY_STORAGE_KEY,
  MAX_SNAPSHOTS_LIMIT,
} from '../basketHistory'
import type { BasketSnapshot, OptimizePlan } from '../../types'

describe('basketHistory — 52-Week FIFO Storage & Inflation Engine', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('1. should initialize with empty array if localStorage is empty or corrupt', () => {
    expect(loadBasketHistory()).toEqual([])

    localStorage.setItem(BASKET_HISTORY_STORAGE_KEY, 'not valid json')
    expect(loadBasketHistory()).toEqual([])

    localStorage.setItem(BASKET_HISTORY_STORAGE_KEY, JSON.stringify({ not: 'an array' }))
    expect(loadBasketHistory()).toEqual([])

    localStorage.setItem(
      BASKET_HISTORY_STORAGE_KEY,
      JSON.stringify([{ invalid: 'entry' }, null, 123]),
    )
    expect(loadBasketHistory()).toEqual([])
  })

  it('2. should cap history at 52 snapshots with strict circular FIFO eviction', () => {
    const baseDate = new Date('2025-01-01T12:00:00Z').getTime()
    const snapshots: BasketSnapshot[] = []

    // Generate 60 snapshots, 1 per week
    for (let i = 0; i < 60; i++) {
      const timestamp = new Date(baseDate + i * 7 * 24 * 60 * 60 * 1000).toISOString()
      snapshots.push({
        id: `snap_${i}`,
        timestamp,
        items_count: 5,
        total_units: 10,
        total_comodidad: 50000 + i * 500,
        total_ahorro: 40000 + i * 400,
        ahorro_ars: 10000 + i * 100,
        savings_pct: 20,
      })
    }

    saveBasketHistory(snapshots)
    const loaded = loadBasketHistory()

    expect(loaded).toHaveLength(MAX_SNAPSHOTS_LIMIT)
    expect(loaded.length).toBe(52)
    // Oldest 8 snapshots (0 to 7) must have been evicted
    expect(loaded[0].id).toBe('snap_8')
    // Most recent snapshot (59) must be retained at the end
    expect(loaded[51].id).toBe('snap_59')
  })

  it('3. should respect same-day cooldown (18h window) for passive views and allow checkout overwrite', () => {
    const today = '2026-10-27T10:00:00.000Z'
    const snap1: BasketSnapshot = {
      id: 'snap_morning',
      timestamp: today,
      items_count: 4,
      total_units: 6,
      total_comodidad: 45000,
      total_ahorro: 38000,
      ahorro_ars: 7000,
      savings_pct: 15.6,
      source: 'optimization_view',
    }

    let history: BasketSnapshot[] = []
    const res1 = pushSnapshotToHistory(history, snap1)
    expect(res1.actionTaken).toBe('appended')
    expect(res1.updatedHistory).toHaveLength(1)
    history = res1.updatedHistory

    // Second passive view on same day (4 hours later) -> skipped to prevent saturation
    const snap2: BasketSnapshot = {
      id: 'snap_afternoon',
      timestamp: '2026-10-27T14:00:00.000Z',
      items_count: 4,
      total_units: 6,
      total_comodidad: 45000,
      total_ahorro: 38000,
      ahorro_ars: 7000,
      savings_pct: 15.6,
      source: 'optimization_view',
    }
    const res2 = pushSnapshotToHistory(history, snap2)
    expect(res2.actionTaken).toBe('skipped')
    expect(res2.updatedHistory).toHaveLength(1)

    // User completes checkout on same day -> must update existing snapshot
    const snapCheckout: BasketSnapshot = {
      id: 'snap_checkout',
      timestamp: '2026-10-27T18:00:00.000Z',
      items_count: 5,
      total_units: 8,
      total_comodidad: 52000,
      total_ahorro: 43000,
      ahorro_ars: 9000,
      savings_pct: 17.3,
      source: 'checkout',
    }
    const res3 = pushSnapshotToHistory(history, snapCheckout)
    expect(res3.actionTaken).toBe('updated')
    expect(res3.updatedHistory).toHaveLength(1)
    expect(res3.updatedHistory[0].id).toBe('snap_checkout')
    expect(res3.updatedHistory[0].total_ahorro).toBe(43000)

    // Next day (24 hours later) -> must append
    const snapNextDay: BasketSnapshot = {
      id: 'snap_next_day',
      timestamp: '2026-10-28T19:00:00.000Z',
      items_count: 5,
      total_units: 8,
      total_comodidad: 53000,
      total_ahorro: 44000,
      ahorro_ars: 9000,
      savings_pct: 17.0,
      source: 'optimization_view',
    }
    const res4 = pushSnapshotToHistory(res3.updatedHistory, snapNextDay)
    expect(res4.actionTaken).toBe('appended')
    expect(res4.updatedHistory).toHaveLength(2)
  })

  it('4. should correctly compute personal inflation percentage and savings delta', () => {
    const prevSnap: BasketSnapshot = {
      id: 'snap_week1',
      timestamp: '2026-10-01T12:00:00Z',
      items_count: 10,
      total_units: 15,
      total_comodidad: 60000,
      total_ahorro: 50000,
      ahorro_ars: 10000,
      savings_pct: 16.7,
    }

    // Case A: Price increased from $50.000 to $52.500 (+5.0% inflation)
    const currentSnapInflation: BasketSnapshot = {
      id: 'snap_week2',
      timestamp: '2026-10-08T12:00:00Z',
      items_count: 10,
      total_units: 15,
      total_comodidad: 64000,
      total_ahorro: 52500,
      ahorro_ars: 11500,
      savings_pct: 18.0,
    }

    const deltaA = calculateBasketDelta(currentSnapInflation, [prevSnap])
    expect(deltaA.has_history).toBe(true)
    expect(deltaA.delta_ars).toBe(2500)
    expect(deltaA.percentage_delta).toBe(5.0)
    expect(deltaA.savings_delta_ars).toBe(1500) // 11500 - 10000
    expect(deltaA.is_basket_size_different).toBe(false)
    expect(deltaA.days_elapsed).toBe(7)

    // Case B: Price dropped from $50.000 to $48.000 (-4.0% deflation/better deal)
    const currentSnapDeflation: BasketSnapshot = {
      id: 'snap_week2_cheap',
      timestamp: '2026-10-08T12:00:00Z',
      items_count: 10,
      total_units: 15,
      total_comodidad: 58000,
      total_ahorro: 48000,
      ahorro_ars: 10000,
      savings_pct: 17.2,
    }

    const deltaB = calculateBasketDelta(currentSnapDeflation, [prevSnap])
    expect(deltaB.delta_ars).toBe(-2000)
    expect(deltaB.percentage_delta).toBe(-4.0)
  })

  it('5. should calculate cumulative historical savings and statistics', () => {
    const history: BasketSnapshot[] = [
      {
        id: 's1',
        timestamp: '2026-09-01T10:00:00Z',
        items_count: 8,
        total_units: 10,
        total_comodidad: 40000,
        total_ahorro: 35000,
        ahorro_ars: 5000,
        savings_pct: 12.5,
      },
      {
        id: 's2',
        timestamp: '2026-09-15T10:00:00Z',
        items_count: 8,
        total_units: 10,
        total_comodidad: 48000,
        total_ahorro: 40000,
        ahorro_ars: 8000,
        savings_pct: 16.7,
      },
      {
        id: 's3',
        timestamp: '2026-10-01T10:00:00Z',
        items_count: 8,
        total_units: 10,
        total_comodidad: 52000,
        total_ahorro: 45000,
        ahorro_ars: 7000,
        savings_pct: 13.5,
      },
    ]

    const stats = calculateHistoryStats(history)
    expect(stats.total_snapshots).toBe(3)
    expect(stats.cumulative_savings_ars).toBe(20000) // 5000 + 8000 + 7000
    expect(stats.average_savings_ars).toBe(6667)
    expect(stats.min_basket_total).toBe(35000)
    expect(stats.max_basket_total).toBe(45000)
    // Overall period inflation: ((45000 - 35000) / 35000) * 100 = 28.6%
    expect(stats.overall_period_inflation_pct).toBe(28.6)
  })

  it('6. should detect basket size differences and compute normalized unit delta %', () => {
    const prev: BasketSnapshot = {
      id: 'snap_small',
      timestamp: '2026-10-01T10:00:00Z',
      items_count: 2,
      total_units: 4, // 4 units, cost $20.000 -> $5.000 / unit
      total_comodidad: 24000,
      total_ahorro: 20000,
      ahorro_ars: 4000,
      savings_pct: 16.7,
    }

    const current: BasketSnapshot = {
      id: 'snap_large',
      timestamp: '2026-10-08T10:00:00Z',
      items_count: 5,
      total_units: 10, // 10 units, cost $55.000 -> $5.500 / unit (+10% per unit)
      total_comodidad: 65000,
      total_ahorro: 55000,
      ahorro_ars: 10000,
      savings_pct: 15.4,
    }

    const delta = calculateBasketDelta(current, [prev])
    expect(delta.is_basket_size_different).toBe(true)
    expect(delta.items_count_diff).toBe(3)
    // Nominal delta is +$35.000, but normalized unit cost delta is only +10%
    expect(delta.normalized_unit_delta_pct).toBe(10.0)
  })

  it('7. should create typed snapshot from OptimizePlan with store splits', () => {
    const plan: OptimizePlan = {
      mode: 'ahorro',
      stops: 2,
      total: 35000,
      subtotal_mercaderia: 35000,
      ahorro_total: 5000,
      missing: [],
      carts: [
        {
          supermercado: 'Carrefour',
          supports_cart: true,
          checkout_url: 'https://carrefour.com.ar',
          subtotal: 18000,
          final_store_total: 18000,
          free_shipping_threshold: 30000,
          falta_envio_gratis: 12000,
          items: [],
        },
        {
          supermercado: 'Dia',
          supports_cart: true,
          checkout_url: 'https://diaonline.com.ar',
          subtotal: 17000,
          final_store_total: 17000,
          free_shipping_threshold: 25000,
          falta_envio_gratis: 8000,
          items: [],
        },
      ],
      mode_previews: {
        ahorro: {
          mode: 'ahorro',
          title: 'Opción más barata',
          tagline: 'Split 2',
          total: 35000,
          ahorro_vs_comoda: 5000,
          ahorro_vs_regular: 8000,
          ahorro_pct: 12.5,
          supermercados_count: 2,
          covered_items: 2,
          total_items: 2,
        },
        balanceada: {
          mode: 'balanceada',
          title: 'Opción equilibrada',
          tagline: 'Balance',
          total: 37000,
          ahorro_vs_comoda: 3000,
          ahorro_vs_regular: 6000,
          ahorro_pct: 7.5,
          supermercados_count: 2,
          covered_items: 2,
          total_items: 2,
        },
        comodidad: {
          mode: 'comodidad',
          title: 'Opción cómoda',
          tagline: '1 súper',
          total: 40000,
          ahorro_vs_comoda: 0,
          ahorro_vs_regular: 3000,
          ahorro_pct: 0,
          supermercados_count: 1,
          covered_items: 2,
          total_items: 2,
        },
      },
    }

    const snap = createSnapshotFromPlan(plan, 4, 7, 'checkout')
    expect(snap).not.toBeNull()
    expect(snap?.total_ahorro).toBe(35000)
    expect(snap?.total_comodidad).toBe(40000)
    expect(snap?.ahorro_ars).toBe(5000)
    expect(snap?.savings_pct).toBe(12.5)
    expect(snap?.items_count).toBe(4)
    expect(snap?.total_units).toBe(7)
    expect(snap?.source).toBe('checkout')
    expect(snap?.store_split).toEqual({
      Carrefour: 18000,
      Dia: 17000,
    })

    clearBasketHistory()
    expect(loadBasketHistory()).toEqual([])
  })
})
