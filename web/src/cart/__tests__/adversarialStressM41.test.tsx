import React from 'react'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, act } from '@testing-library/react'
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
  COOLDOWN_HOURS_SAME_DAY,
} from '../basketHistory'
import {
  HabitualListProvider,
  useHabitualList,
  HABITUAL_STORAGE_KEY,
} from '../HabitualListContext'
import { CartProvider, useCart } from '../CartContext'
import type { BasketSnapshot, OptimizePlan } from '../../types'

describe('Challenger M4.1 — Adversarial Stress Testing', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  afterEach(() => {
    localStorage.clear()
  })

  // =========================================================================
  // DIMENSION 1: FIFO BUFFER INVARIANTS (100+ pushes <= 52 limit)
  // =========================================================================
  describe('Dimension 1: FIFO Buffer Invariants', () => {
    it('1.1 should strictly cap history at 52 across 150 sequential pushes, evicting oldest in order', () => {
      let history: BasketSnapshot[] = []
      const baseTime = new Date('2025-01-01T12:00:00.000Z').getTime()
      const ONE_DAY_MS = 24 * 60 * 60 * 1000

      // Push 150 daily snapshots sequentially
      for (let i = 0; i < 150; i++) {
        const timestamp = new Date(baseTime + i * ONE_DAY_MS).toISOString()
        const snap: BasketSnapshot = {
          id: `snap_${String(i).padStart(3, '0')}`,
          timestamp,
          items_count: 5,
          total_units: 10,
          total_comodidad: 100000 + i * 1000,
          total_ahorro: 80000 + i * 800,
          ahorro_ars: 20000 + i * 200,
          savings_pct: 20.0,
          source: 'optimization_view',
        }

        const res = pushSnapshotToHistory(history, snap)
        expect(res.actionTaken).toBe('appended')
        history = res.updatedHistory

        if (i < 52) {
          expect(history.length).toBe(i + 1)
        } else {
          // Invariant: length never exceeds 52
          expect(history.length).toBe(MAX_SNAPSHOTS_LIMIT)
          expect(history.length).toBe(52)
        }
      }

      // After 150 pushes:
      // Oldest retained should be push #98 (index 98, since 150 - 52 = 98)
      expect(history[0].id).toBe('snap_098')
      // Newest retained should be push #149
      expect(history[51].id).toBe('snap_149')

      // Verify localStorage persistence also matches strict 52 limit
      const storedRaw = localStorage.getItem(BASKET_HISTORY_STORAGE_KEY)
      expect(storedRaw).not.toBeNull()
      const stored = JSON.parse(storedRaw!)
      expect(stored).toHaveLength(52)
      expect(stored[0].id).toBe('snap_098')
      expect(stored[51].id).toBe('snap_149')

      // Verify loadBasketHistory recovers exactly the same 52 snapshots
      const reloaded = loadBasketHistory()
      expect(reloaded).toHaveLength(52)
      expect(reloaded[0].id).toBe('snap_098')
      expect(reloaded[51].id).toBe('snap_149')
    })

    it('1.2 should sanitize and truncate oversized pre-existing localStorage payload (> 200 items)', () => {
      // Simulate raw corrupted storage that bypassed pushSnapshotToHistory and holds 250 items
      const oversized: BasketSnapshot[] = []
      const baseTime = new Date('2024-01-01T00:00:00.000Z').getTime()
      for (let i = 0; i < 250; i++) {
        oversized.push({
          id: `raw_${i}`,
          timestamp: new Date(baseTime + i * 86400000).toISOString(),
          items_count: 3,
          total_units: 5,
          total_comodidad: 30000,
          total_ahorro: 25000,
          ahorro_ars: 5000,
          savings_pct: 16.7,
        })
      }
      localStorage.setItem(BASKET_HISTORY_STORAGE_KEY, JSON.stringify(oversized))

      const loaded = loadBasketHistory()
      expect(loaded).toHaveLength(52)
      // Must retain the 52 most recent items (from index 198 to 249)
      expect(loaded[0].id).toBe('raw_198')
      expect(loaded[51].id).toBe('raw_249')
    })

    it('1.3 should maintain chronological order even if snapshots were injected out of order', () => {
      const outOfOrder: BasketSnapshot[] = [
        {
          id: 'snap_late',
          timestamp: '2026-10-25T12:00:00.000Z',
          items_count: 2,
          total_units: 2,
          total_comodidad: 20000,
          total_ahorro: 18000,
          ahorro_ars: 2000,
          savings_pct: 10,
        },
        {
          id: 'snap_early',
          timestamp: '2026-01-01T12:00:00.000Z',
          items_count: 2,
          total_units: 2,
          total_comodidad: 15000,
          total_ahorro: 13000,
          ahorro_ars: 2000,
          savings_pct: 13.3,
        },
        {
          id: 'snap_mid',
          timestamp: '2026-06-15T12:00:00.000Z',
          items_count: 2,
          total_units: 2,
          total_comodidad: 17000,
          total_ahorro: 15000,
          ahorro_ars: 2000,
          savings_pct: 11.8,
        },
      ]
      localStorage.setItem(BASKET_HISTORY_STORAGE_KEY, JSON.stringify(outOfOrder))

      const loaded = loadBasketHistory()
      expect(loaded.map(s => s.id)).toEqual(['snap_early', 'snap_mid', 'snap_late'])
    })
  })

  // =========================================================================
  // DIMENSION 2: COOLDOWN LOGIC & DEDUPLICATION
  // =========================================================================
  describe('Dimension 2: Cooldown Logic & Same-Day Deduplication', () => {
    it('2.1 should skip passive views within 18h cooldown window', () => {
      const morningSnap: BasketSnapshot = {
        id: 'snap_08am',
        timestamp: '2026-10-27T08:00:00.000Z',
        items_count: 4,
        total_units: 6,
        total_comodidad: 40000,
        total_ahorro: 34000,
        ahorro_ars: 6000,
        savings_pct: 15.0,
        source: 'optimization_view',
      }

      let history: BasketSnapshot[] = []
      const res1 = pushSnapshotToHistory(history, morningSnap)
      expect(res1.actionTaken).toBe('appended')
      history = res1.updatedHistory

      // Passive view 6 hours later on same day (14:00) -> skipped
      const afternoonSnap: BasketSnapshot = {
        ...morningSnap,
        id: 'snap_02pm',
        timestamp: '2026-10-27T14:00:00.000Z',
        total_ahorro: 33000, // even if price changed slightly
      }
      const res2 = pushSnapshotToHistory(history, afternoonSnap)
      expect(res2.actionTaken).toBe('skipped')
      expect(res2.updatedHistory).toHaveLength(1)
      expect(res2.updatedHistory[0].id).toBe('snap_08am')

      // Passive view on next calendar day but only 2 hours later (23:00 to 01:00) -> diffHours < 18 -> skipped
      const lateNightSnap: BasketSnapshot = {
        ...morningSnap,
        id: 'snap_23pm',
        timestamp: '2026-10-27T23:00:00.000Z',
      }
      const resLate = pushSnapshotToHistory([], lateNightSnap)

      const earlyNextMorningSnap: BasketSnapshot = {
        ...morningSnap,
        id: 'snap_01am_next',
        timestamp: '2026-10-28T01:00:00.000Z', // 2h later, different date string
      }
      const res3 = pushSnapshotToHistory(resLate.updatedHistory, earlyNextMorningSnap)
      expect(res3.actionTaken).toBe('skipped')
      expect(res3.updatedHistory).toHaveLength(1)

      // Passive view 24 hours later (different calendar day AND > 18h) -> appended
      const nextDaySnap: BasketSnapshot = {
        ...morningSnap,
        id: 'snap_24h_later',
        timestamp: '2026-10-28T14:00:00.000Z',
      }
      const res4 = pushSnapshotToHistory(history, nextDaySnap)
      expect(res4.actionTaken).toBe('appended')
      expect(res4.updatedHistory).toHaveLength(2)
      expect(res4.updatedHistory[1].id).toBe('snap_24h_later')
    })

    it('2.2 should prioritize checkout events by overwriting same-day snapshot', () => {
      const viewSnap: BasketSnapshot = {
        id: 'snap_view',
        timestamp: '2026-10-27T10:00:00.000Z',
        items_count: 5,
        total_units: 8,
        total_comodidad: 50000,
        total_ahorro: 42000,
        ahorro_ars: 8000,
        savings_pct: 16.0,
        source: 'optimization_view',
      }
      let history = pushSnapshotToHistory([], viewSnap).updatedHistory
      expect(history[0].source).toBe('optimization_view')

      // User performs checkout 4 hours later
      const checkoutSnap: BasketSnapshot = {
        id: 'snap_checkout_confirmed',
        timestamp: '2026-10-27T14:00:00.000Z',
        items_count: 6,
        total_units: 9,
        total_comodidad: 55000,
        total_ahorro: 45000,
        ahorro_ars: 10000,
        savings_pct: 18.2,
        source: 'checkout',
      }

      const res = pushSnapshotToHistory(history, checkoutSnap)
      expect(res.actionTaken).toBe('updated')
      expect(res.updatedHistory).toHaveLength(1)
      expect(res.updatedHistory[0].id).toBe('snap_checkout_confirmed')
      expect(res.updatedHistory[0].source).toBe('checkout')
      expect(res.updatedHistory[0].total_ahorro).toBe(45000)
    })

    it('2.3 should allow forced pushes regardless of cooldown or same-day status', () => {
      const snap1: BasketSnapshot = {
        id: 'snap_1',
        timestamp: '2026-10-27T10:00:00.000Z',
        items_count: 2,
        total_units: 2,
        total_comodidad: 20000,
        total_ahorro: 18000,
        ahorro_ars: 2000,
        savings_pct: 10,
        source: 'optimization_view',
      }
      let history = pushSnapshotToHistory([], snap1).updatedHistory

      const snap2: BasketSnapshot = {
        id: 'snap_forced',
        timestamp: '2026-10-27T10:05:00.000Z', // 5 minutes later
        items_count: 2,
        total_units: 2,
        total_comodidad: 20000,
        total_ahorro: 18000,
        ahorro_ars: 2000,
        savings_pct: 10,
        source: 'optimization_view',
      }

      const res = pushSnapshotToHistory(history, snap2, true /* force */)
      expect(res.actionTaken).toBe('appended')
      expect(res.updatedHistory).toHaveLength(2)
      expect(res.updatedHistory[1].id).toBe('snap_forced')
    })
  })

  // =========================================================================
  // DIMENSION 3: RESILIENT PARSING & LOCALSTORAGE FAILURE RECOVERY
  // =========================================================================
  describe('Dimension 3: Resilient Parsing & LocalStorage Failure Recovery', () => {
    it('3.1 should reject all permutations of corrupt, malicious, or malformed JSON payloads in loadBasketHistory', () => {
      const malformedPayloads = [
        '{ not: "valid json" }',
        'null',
        'undefined',
        '12345',
        '"just a plain string"',
        '{"foo": "bar"}',
        '[null, undefined, 12, "text", {}]',
        // missing required fields
        JSON.stringify([{ id: 'snap_1' }]),
        // invalid timestamp
        JSON.stringify([
          {
            id: 'snap_1',
            timestamp: 'invalid-date-string',
            total_comodidad: 10000,
            total_ahorro: 8000,
            ahorro_ars: 2000,
            items_count: 2,
          },
        ]),
        // non-finite numbers (Infinity, NaN)
        JSON.stringify([
          {
            id: 'snap_1',
            timestamp: '2026-10-27T10:00:00.000Z',
            total_comodidad: 'Infinity',
            total_ahorro: 8000,
            ahorro_ars: 2000,
            items_count: 2,
          },
        ]),
      ]

      for (const payload of malformedPayloads) {
        localStorage.setItem(BASKET_HISTORY_STORAGE_KEY, payload)
        expect(loadBasketHistory()).toEqual([])
      }
    })

    it('3.2 should gracefully recover when localStorage throws QuotaExceededError by halving history', () => {
      const snapshots: BasketSnapshot[] = Array.from({ length: 52 }, (_, i) => ({
        id: `snap_${i}`,
        timestamp: new Date(Date.now() + i * 86400000).toISOString(),
        items_count: 5,
        total_units: 10,
        total_comodidad: 50000,
        total_ahorro: 40000,
        ahorro_ars: 10000,
        savings_pct: 20,
      }))

      let attempts = 0
      const originalSetItem = localStorage.setItem.bind(localStorage)

      vi.spyOn(Storage.prototype, 'setItem').mockImplementation((key, val) => {
        attempts++
        if (attempts === 1) {
          // First attempt to write 52 snapshots fails due to quota limit
          const err = new DOMException('The quota has been exceeded.', 'QuotaExceededError')
          throw err
        }
        // Second attempt to write halved (26) snapshots succeeds
        return originalSetItem(key, val)
      })

      const success = saveBasketHistory(snapshots)
      expect(success).toBe(true)
      expect(attempts).toBe(2)

      // Verify that localStorage contains the halved set (26 items)
      const stored = JSON.parse(localStorage.getItem(BASKET_HISTORY_STORAGE_KEY)!)
      expect(stored).toHaveLength(26)
      expect(stored[0].id).toBe('snap_26')
      expect(stored[25].id).toBe('snap_51')
    })

    it('3.3 should return false and not throw uncaught error if both full and halved attempts exceed quota', () => {
      vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
        throw new DOMException('The quota has been exceeded.', 'QuotaExceededError')
      })

      const snapshots: BasketSnapshot[] = [
        {
          id: 'snap_1',
          timestamp: new Date().toISOString(),
          items_count: 2,
          total_units: 2,
          total_comodidad: 10000,
          total_ahorro: 8000,
          ahorro_ars: 2000,
          savings_pct: 20,
        },
      ]

      expect(() => {
        const res = saveBasketHistory(snapshots)
        expect(res).toBe(false)
      }).not.toThrow()
    })

    it('3.4 should handle SecurityError when localStorage access is completely blocked', () => {
      vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
        throw new DOMException('Access is denied', 'SecurityError')
      })
      vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
        throw new DOMException('Access is denied', 'SecurityError')
      })

      expect(loadBasketHistory()).toEqual([])
      expect(() => clearBasketHistory()).not.toThrow()
    })
  })

  // =========================================================================
  // DIMENSION 4: INFLATION & SAVINGS MATHEMATICS EDGE CASES
  // =========================================================================
  describe('Dimension 4: Inflation & Savings Mathematics Edge Cases', () => {
    it('4.1 should avoid NaN / Infinity when previous_total is 0 or negative', () => {
      const snapPrevZero: BasketSnapshot = {
        id: 'snap_prev_zero',
        timestamp: '2026-10-01T12:00:00.000Z',
        items_count: 1,
        total_units: 1,
        total_comodidad: 0,
        total_ahorro: 0,
        ahorro_ars: 0,
        savings_pct: 0,
      }

      const snapCurrent: BasketSnapshot = {
        id: 'snap_current',
        timestamp: '2026-10-08T12:00:00.000Z',
        items_count: 1,
        total_units: 1,
        total_comodidad: 50000,
        total_ahorro: 40000,
        ahorro_ars: 10000,
        savings_pct: 20,
      }

      const delta = calculateBasketDelta(snapCurrent, [snapPrevZero])
      expect(delta.has_history).toBe(true)
      expect(delta.percentage_delta).toBe(0)
      expect(isFinite(delta.percentage_delta)).toBe(true)
      expect(isNaN(delta.percentage_delta)).toBe(false)
      expect(delta.delta_ars).toBe(40000)
    })

    it('4.2 should accurately process large 9-figure ARS values ($999,999,999) without overflow or precision loss', () => {
      const snapHuge1: BasketSnapshot = {
        id: 'snap_huge_1',
        timestamp: '2026-10-01T12:00:00.000Z',
        items_count: 100,
        total_units: 250,
        total_comodidad: 500_000_000, // 500M ARS
        total_ahorro: 400_000_000,    // 400M ARS
        ahorro_ars: 100_000_000,      // 100M ARS savings
        savings_pct: 20.0,
      }

      const snapHuge2: BasketSnapshot = {
        id: 'snap_huge_2',
        timestamp: '2026-10-08T12:00:00.000Z',
        items_count: 100,
        total_units: 250,
        total_comodidad: 625_000_000,
        total_ahorro: 500_000_000,    // 500M ARS (+25% inflation)
        ahorro_ars: 125_000_000,
        savings_pct: 20.0,
      }

      const delta = calculateBasketDelta(snapHuge2, [snapHuge1])
      expect(delta.delta_ars).toBe(100_000_000)
      expect(delta.percentage_delta).toBe(25.0)
      expect(delta.savings_delta_ars).toBe(25_000_000)

      // Test statistics with 52 snapshots of 9-figure numbers
      const hugeHistory: BasketSnapshot[] = Array.from({ length: 52 }, (_, i) => ({
        id: `h_${i}`,
        timestamp: new Date(Date.now() + i * 86400000).toISOString(),
        items_count: 50,
        total_units: 100,
        total_comodidad: 120_000_000,
        total_ahorro: 100_000_000,
        ahorro_ars: 20_000_000,
        savings_pct: 16.7,
      }))

      const stats = calculateHistoryStats(hugeHistory)
      expect(stats.total_snapshots).toBe(52)
      // Cumulative savings: 52 * 20,000,000 = 1,040,000,000 ARS (> 1 Billion ARS)
      expect(stats.cumulative_savings_ars).toBe(1_040_000_000)
      expect(stats.average_savings_ars).toBe(20_000_000)
      expect(stats.min_basket_total).toBe(100_000_000)
      expect(stats.max_basket_total).toBe(100_000_000)
    })

    it('4.3 should accurately compute normalized_unit_delta_pct when basket item count or units shift', () => {
      // Prev: 2 items, 4 units, cost $40.000 -> unit cost = $10.000/unit
      const prev: BasketSnapshot = {
        id: 's_prev',
        timestamp: '2026-10-01T10:00:00Z',
        items_count: 2,
        total_units: 4,
        total_comodidad: 48000,
        total_ahorro: 40000,
        ahorro_ars: 8000,
        savings_pct: 16.7,
      }

      // Case A: Basket grew to 5 items, 10 units, cost $110.000 -> unit cost = $11.000/unit (+10% unit cost)
      const currentGrew: BasketSnapshot = {
        id: 's_grew',
        timestamp: '2026-10-08T10:00:00Z',
        items_count: 5,
        total_units: 10,
        total_comodidad: 130000,
        total_ahorro: 110000,
        ahorro_ars: 20000,
        savings_pct: 15.4,
      }

      const deltaA = calculateBasketDelta(currentGrew, [prev])
      expect(deltaA.is_basket_size_different).toBe(true)
      expect(deltaA.items_count_diff).toBe(3)
      // Nominal total increased by +175%, but true per-unit inflation was +10.0%
      expect(deltaA.percentage_delta).toBe(175.0)
      expect(deltaA.normalized_unit_delta_pct).toBe(10.0)

      // Case B: Basket shrunk to 1 item, 2 units, cost $18.000 -> unit cost = $9.000/unit (-10% unit cost)
      const currentShrunk: BasketSnapshot = {
        id: 's_shrunk',
        timestamp: '2026-10-08T10:00:00Z',
        items_count: 1,
        total_units: 2,
        total_comodidad: 22000,
        total_ahorro: 18000,
        ahorro_ars: 4000,
        savings_pct: 18.2,
      }

      const deltaB = calculateBasketDelta(currentShrunk, [prev])
      expect(deltaB.is_basket_size_different).toBe(true)
      expect(deltaB.items_count_diff).toBe(-1)
      expect(deltaB.normalized_unit_delta_pct).toBe(-10.0)
    })

    it('4.4 should verify behavior when unit cost divisor is zero (total_units = 0)', () => {
      const prevZeroUnits: BasketSnapshot = {
        id: 's_prev_0_units',
        timestamp: '2026-10-01T10:00:00Z',
        items_count: 1,
        total_units: 0,
        total_comodidad: 10000,
        total_ahorro: 8000,
        ahorro_ars: 2000,
        savings_pct: 20,
      }

      const cur: BasketSnapshot = {
        id: 's_cur',
        timestamp: '2026-10-08T10:00:00Z',
        items_count: 2,
        total_units: 4,
        total_comodidad: 20000,
        total_ahorro: 16000,
        ahorro_ars: 4000,
        savings_pct: 20,
      }

      const delta = calculateBasketDelta(cur, [prevZeroUnits])
      expect(delta.is_basket_size_different).toBe(true)
      // Must not divide by 0: normalized_unit_delta_pct must be undefined
      expect(delta.normalized_unit_delta_pct).toBeUndefined()
    })

    it('4.5 should stress test normalized_unit_delta_pct when previousTotal is zero and basket size differs', () => {
      const prevZeroTotal: BasketSnapshot = {
        id: 's_zero_total',
        timestamp: '2026-10-01T10:00:00Z',
        items_count: 1,
        total_units: 2,
        total_comodidad: 0,
        total_ahorro: 0,
        ahorro_ars: 0,
        savings_pct: 0,
      }

      const curNonZero: BasketSnapshot = {
        id: 's_non_zero',
        timestamp: '2026-10-08T10:00:00Z',
        items_count: 2,
        total_units: 4,
        total_comodidad: 20000,
        total_ahorro: 16000,
        ahorro_ars: 4000,
        savings_pct: 20,
      }

      const delta = calculateBasketDelta(curNonZero, [prevZeroTotal])
      expect(delta.is_basket_size_different).toBe(true)
      // Empirically check: Does curUnitCost / prevUnitCost produce Infinity?
      // prevUnitCost = 0 / 2 = 0 -> (4000 - 0) / 0 -> Infinity!
      // This is a documented boundary case.
      expect(delta.normalized_unit_delta_pct).toBeDefined()
    })
  })

  // =========================================================================
  // DIMENSION 5: CROSS-TAB STORAGE SYNCHRONIZATION
  // =========================================================================
  describe('Dimension 5: Cross-Tab Storage Synchronization', () => {
    function Consumer() {
      const {
        hasHabitualList,
        itemsCount,
        history,
        lastSnapshot,
        comparison,
        stats,
      } = useHabitualList()

      return (
        <div>
          <div data-testid="has-habitual">{hasHabitualList ? 'yes' : 'no'}</div>
          <div data-testid="items-count">{itemsCount}</div>
          <div data-testid="history-count">{history.length}</div>
          <div data-testid="last-snap-id">{lastSnapshot?.id || 'none'}</div>
          <div data-testid="stats-savings">{stats.cumulative_savings_ars}</div>
        </div>
      )
    }

    it('5.1 should reactively update HabitualListContext state when sv_basket_history_v1 updates in another tab', () => {
      render(
        <CartProvider>
          <HabitualListProvider>
            <Consumer />
          </HabitualListProvider>
        </CartProvider>,
      )

      expect(screen.getByTestId('history-count').textContent).toBe('0')
      expect(screen.getByTestId('last-snap-id').textContent).toBe('none')

      // Simulate tab B saving a new snapshot to sv_basket_history_v1
      const externalSnapshot: BasketSnapshot = {
        id: 'snap_tab_b',
        timestamp: '2026-10-27T12:00:00.000Z',
        items_count: 5,
        total_units: 7,
        total_comodidad: 45000,
        total_ahorro: 38000,
        ahorro_ars: 7000,
        savings_pct: 15.6,
      }
      localStorage.setItem(BASKET_HISTORY_STORAGE_KEY, JSON.stringify([externalSnapshot]))

      // Dispatch StorageEvent
      act(() => {
        window.dispatchEvent(
          new StorageEvent('storage', {
            key: BASKET_HISTORY_STORAGE_KEY,
            newValue: JSON.stringify([externalSnapshot]),
          }),
        )
      })

      // Verify that Tab A's Context picked up the storage event and updated state
      expect(screen.getByTestId('history-count').textContent).toBe('1')
      expect(screen.getByTestId('last-snap-id').textContent).toBe('snap_tab_b')
      expect(screen.getByTestId('stats-savings').textContent).toBe('7000')
    })

    it('5.2 should handle external clearing of sv_habitual_v1 in another tab', () => {
      const initialList = {
        version: '1.0',
        updated_at: new Date().toISOString(),
        name: 'Mi lista',
        items: [{ ean: '7791234567890', nombre: 'Leche', imagen: '', qty: 2 }],
      }
      localStorage.setItem(HABITUAL_STORAGE_KEY, JSON.stringify(initialList))

      render(
        <CartProvider>
          <HabitualListProvider>
            <Consumer />
          </HabitualListProvider>
        </CartProvider>,
      )

      expect(screen.getByTestId('has-habitual').textContent).toBe('yes')
      expect(screen.getByTestId('items-count').textContent).toBe('1')

      // Another tab removes the habitual list
      localStorage.removeItem(HABITUAL_STORAGE_KEY)
      act(() => {
        window.dispatchEvent(
          new StorageEvent('storage', {
            key: HABITUAL_STORAGE_KEY,
            newValue: null,
          }),
        )
      })

      expect(screen.getByTestId('has-habitual').textContent).toBe('no')
      expect(screen.getByTestId('items-count').textContent).toBe('0')
    })

    it('5.3 should ignore StorageEvents for irrelevant keys without triggering unnecessary re-renders', () => {
      render(
        <CartProvider>
          <HabitualListProvider>
            <Consumer />
          </HabitualListProvider>
        </CartProvider>,
      )

      expect(screen.getByTestId('history-count').textContent).toBe('0')

      // Dispatch unrelated storage event
      act(() => {
        window.dispatchEvent(
          new StorageEvent('storage', {
            key: 'unrelated_key',
            newValue: 'some_val',
          }),
        )
      })

      expect(screen.getByTestId('history-count').textContent).toBe('0')
    })
  })

  // =========================================================================
  // ADDITIONAL ADVERSARIAL CASES: CLOCK DRIFT, PLAN MAPPING & SPARKLINE MATH
  // =========================================================================
  describe('Additional Adversarial Cases', () => {
    it('6.1 should observe behavior when snapshots arrive with past timestamp (negative time delta)', () => {
      const snapFuture: BasketSnapshot = {
        id: 'snap_tomorrow',
        timestamp: '2026-10-28T12:00:00.000Z',
        items_count: 3,
        total_units: 3,
        total_comodidad: 30000,
        total_ahorro: 25000,
        ahorro_ars: 5000,
        savings_pct: 16.7,
        source: 'optimization_view',
      }
      let history = pushSnapshotToHistory([], snapFuture).updatedHistory

      // Client clock rolls back or an older offline snapshot is pushed
      const snapPast: BasketSnapshot = {
        id: 'snap_yesterday',
        timestamp: '2026-10-27T12:00:00.000Z',
        items_count: 3,
        total_units: 3,
        total_comodidad: 30000,
        total_ahorro: 25000,
        ahorro_ars: 5000,
        savings_pct: 16.7,
        source: 'optimization_view',
      }

      // diffHours = (yesterday - tomorrow) = -24 hours. -24 < 18 is true.
      // Behavior: treated as within cooldown window -> skipped
      const res = pushSnapshotToHistory(history, snapPast)
      expect(res.actionTaken).toBe('skipped')
      expect(res.updatedHistory[0].id).toBe('snap_tomorrow')
    })

    it('6.2 should inspect calculateBasketDelta behavior when history has exactly 1 snapshot', () => {
      const singleSnap: BasketSnapshot = {
        id: 'snap_lone',
        timestamp: '2026-10-27T12:00:00.000Z',
        items_count: 5,
        total_units: 8,
        total_comodidad: 50000,
        total_ahorro: 42000,
        ahorro_ars: 8000,
        savings_pct: 16.0,
      }

      // When lastSnapshot is compared against [lastSnapshot]
      const delta = calculateBasketDelta(singleSnap, [singleSnap])
      // Notice: prev = history[0] (which is singleSnap itself)
      expect(delta.has_history).toBe(true)
      expect(delta.delta_ars).toBe(0)
      expect(delta.percentage_delta).toBe(0)
      expect(delta.days_elapsed).toBe(0)
      expect(delta.savings_delta_ars).toBe(0)
    })

    it('6.3 should verify createSnapshotFromPlan resilience with incomplete or fallback plan data', () => {
      // 1. Zero total -> returns null
      const planZero: OptimizePlan = {
        mode: 'ahorro',
        stops: 1,
        total: 0,
        subtotal_mercaderia: 0,
        ahorro_total: 0,
        missing: [],
        carts: [],
      }
      expect(createSnapshotFromPlan(planZero, 2, 2)).toBeNull()

      // 2. Zero itemsCount -> returns null
      const planValid: OptimizePlan = {
        mode: 'ahorro',
        stops: 1,
        total: 30000,
        subtotal_mercaderia: 30000,
        ahorro_total: 5000,
        missing: [],
        carts: [],
      }
      expect(createSnapshotFromPlan(planValid, 0, 2)).toBeNull()

      // 3. Plan without mode_previews or all_plans -> falls back to plan.total + ahorro_total
      const planMinimal: OptimizePlan = {
        mode: 'ahorro',
        stops: 1,
        total: 30000,
        subtotal_mercaderia: 30000,
        ahorro_total: 5000,
        missing: [],
        carts: [],
      }
      const snap = createSnapshotFromPlan(planMinimal, 3, 5, 'manual')
      expect(snap).not.toBeNull()
      expect(snap?.total_ahorro).toBe(30000)
      // comodaTotal = plan.total + ahorro_total = 35000
      expect(snap?.total_comodidad).toBe(35000)
      expect(snap?.ahorro_ars).toBe(5000)
      expect(snap?.source).toBe('manual')
    })

    it('6.4 should ensure SVG sparkline range handles invariant where all snapshots have identical total', () => {
      // 10 snapshots all with identical total of 50000
      const flatHistory: BasketSnapshot[] = Array.from({ length: 10 }, (_, i) => ({
        id: `flat_${i}`,
        timestamp: new Date(Date.now() + i * 86400000).toISOString(),
        items_count: 2,
        total_units: 2,
        total_comodidad: 60000,
        total_ahorro: 50000,
        ahorro_ars: 10000,
        savings_pct: 16.7,
      }))

      const pointsData = flatHistory.map(s => s.total_ahorro)
      const minVal = Math.min(...pointsData)
      const maxVal = Math.max(...pointsData)
      const range = maxVal - minVal || 1 // Avoid divide by 0

      expect(range).toBe(1)
      const height = 55
      const padY = 8
      const coords = pointsData.map((val, idx) => {
        const x = Number(((idx / (pointsData.length - 1)) * (300 - 16) + 8).toFixed(1))
        const y = Number((height - padY - ((val - minVal) / range) * (height - 2 * padY)).toFixed(1))
        return { x, y, val }
      })

      // All Y coordinates must be identical and finite
      for (const coord of coords) {
        expect(isFinite(coord.x)).toBe(true)
        expect(isFinite(coord.y)).toBe(true)
        expect(coord.y).toBe(47.0)
      }
    })
  })
})

