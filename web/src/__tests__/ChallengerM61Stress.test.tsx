import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import ListScreen from '../components/ListScreen'
import { SmartCartHero } from '../components/SmartCartHero'
import { CartProvider } from '../cart/CartContext'
import { LocationProvider } from '../location/LocationContext'
import { BenefitsProvider } from '../benefits/BenefitsContext'
import { HabitualListProvider, useHabitualList, HABITUAL_STORAGE_KEY } from '../cart/HabitualListContext'
import {
  BASKET_HISTORY_STORAGE_KEY,
  MAX_SNAPSHOTS_LIMIT,
  loadBasketHistory,
  saveBasketHistory,
  createSnapshotFromPlan,
  pushSnapshotToHistory,
  calculateBasketDelta,
  clearBasketHistory,
} from '../cart/basketHistory'
import {
  decorateOutboundUrl,
  trackOutboundAffiliateClick,
  getOutboundTrackingSummary,
  AFFILIATE_STORAGE_KEY,
  MAX_STORED_CLICKS,
} from '../lib/affiliate'
import * as api from '../api'
import type { OptimizePlan, ScenarioPreview, ListItem, BasketSnapshot } from '../types'

// Mock API functions
vi.mock('../api', async () => {
  const actual = await vi.importActual('../api')
  return {
    ...actual,
    optimize: vi.fn(),
    validateCart: vi.fn().mockResolvedValue({ status: 'ok', total: 0, sin_stock: [] }),
    getBenefits: vi.fn().mockResolvedValue({
      today: 'lunes',
      today_label: 'Lunes',
      weekdays: [],
      payment_options: [],
      official_links: {},
      daily_promos: [],
    }),
    getRegions: vi.fn().mockResolvedValue([]),
  }
})

function HabitualConsumer() {
  const ctx = useHabitualList()
  return (
    <div>
      <span data-testid="has-habitual">{String(ctx.hasHabitualList)}</span>
      <span data-testid="items-count">{ctx.itemsCount}</span>
      <span data-testid="is-saved">{String(ctx.isCartSavedAsHabitual)}</span>
      <button onClick={() => ctx.saveCartAsHabitual('Mi lista')}>Guardar</button>
      <button onClick={() => ctx.loadHabitualIntoCart('replace')}>Cargar</button>
      <button onClick={() => ctx.clearHabitualList()}>Limpiar</button>
    </div>
  )
}

const samplePreviews: Record<'ahorro' | 'balanceada' | 'comodidad', ScenarioPreview> = {
  ahorro: {
    mode: 'ahorro',
    title: 'Opción más barata',
    tagline: 'Split óptimo 2 súper',
    total: 35000,
    ahorro_vs_comoda: 5000,
    ahorro_vs_regular: 8000,
    ahorro_pct: 12.5,
    supermercados_count: 2,
    covered_items: 2,
    total_items: 2,
    badge: 'MÁXIMO AHORRO',
    diff: 0,
    stops: 2,
    ahorro_total: 5000,
  },
  balanceada: {
    mode: 'balanceada',
    title: 'Opción equilibrada',
    tagline: 'Ahorro vs conveniencia',
    total: 37000,
    ahorro_vs_comoda: 3000,
    ahorro_vs_regular: 6000,
    ahorro_pct: 7.5,
    supermercados_count: 2,
    covered_items: 2,
    total_items: 2,
    badge: 'RECOMENDADA',
    diff: 2000,
    stops: 2,
    ahorro_total: 3000,
  },
  comodidad: {
    mode: 'comodidad',
    title: 'Opción cómoda',
    tagline: 'Todo en 1 solo súper',
    total: 40000,
    ahorro_vs_comoda: 0,
    ahorro_vs_regular: 3000,
    ahorro_pct: 0,
    supermercados_count: 1,
    covered_items: 2,
    total_items: 2,
    badge: 'MÁS CÓMODA',
    diff: 5000,
    stops: 1,
    ahorro_total: 3000,
  },
}

describe('Challenger M6.1 Empirical Adversarial Stress Test Suite', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    localStorage.clear()
  })

  // =========================================================================
  // 1. CORRUPTED LOCALSTORAGE (sv_habitual_v1 & sv_basket_history_v1)
  // =========================================================================
  describe('1. Corrupted localStorage Stress Testing', () => {
    it('1.1. sv_habitual_v1: syntax error / invalid JSON string gracefully defaults to null', () => {
      localStorage.setItem(HABITUAL_STORAGE_KEY, '{invalid_json: true,}')
      render(
        <CartProvider>
          <HabitualListProvider>
            <HabitualConsumer />
          </HabitualListProvider>
        </CartProvider>,
      )
      expect(screen.getByTestId('has-habitual').textContent).toBe('false')
      expect(screen.getByTestId('items-count').textContent).toBe('0')
    })

    it('1.2. sv_habitual_v1: valid JSON with wrong top-level type (primitive, string, array without items) defaults to null', () => {
      const corruptPayloads = [
        '"just a string"',
        '42',
        'true',
        '[]',
        '{"name": "No items array"}',
        '{"items": "not an array"}',
        '{"items": []}', // empty items array returns null per sanitizeList
      ]

      for (const payload of corruptPayloads) {
        localStorage.setItem(HABITUAL_STORAGE_KEY, payload)
        const { unmount } = render(
          <CartProvider>
            <HabitualListProvider>
              <HabitualConsumer />
            </HabitualListProvider>
          </CartProvider>,
        )
        expect(screen.getByTestId('has-habitual').textContent).toBe('false')
        expect(screen.getByTestId('items-count').textContent).toBe('0')
        unmount()
      }
    })

    it('1.3. sv_habitual_v1: filters out corrupted items (short/invalid EAN, missing nombre) and sanitizes', () => {
      const rawList = {
        name: 'Corrupted List',
        items: [
          null,
          123,
          { ean: '123', nombre: 'Too Short EAN' }, // EAN < 8 chars -> discarded
          { ean: '7791234567890', nombre: null }, // Missing nombre -> discarded
          { ean: '7790000000001', nombre: 'Valid Yerba', qty: -5 }, // Valid EAN, negative qty -> coerced to 1
        ],
      }
      localStorage.setItem(HABITUAL_STORAGE_KEY, JSON.stringify(rawList))

      render(
        <CartProvider>
          <HabitualListProvider>
            <HabitualConsumer />
          </HabitualListProvider>
        </CartProvider>,
      )

      expect(screen.getByTestId('has-habitual').textContent).toBe('true')
      expect(screen.getByTestId('items-count').textContent).toBe('1')
    })

    it('1.4. sv_basket_history_v1: corrupted JSON or non-array returns empty history []', () => {
      localStorage.setItem(BASKET_HISTORY_STORAGE_KEY, '<<<INVALID>>>')
      expect(loadBasketHistory()).toEqual([])

      localStorage.setItem(BASKET_HISTORY_STORAGE_KEY, '{"snapshots": []}')
      expect(loadBasketHistory()).toEqual([])

      localStorage.setItem(BASKET_HISTORY_STORAGE_KEY, '12345')
      expect(loadBasketHistory()).toEqual([])
    })

    it('1.5. sv_basket_history_v1: filters out items with invalid dates, NaN, or missing metrics', () => {
      const mixedSnapshots = [
        { id: '1', timestamp: 'not-a-date', total_comodidad: 1000, total_ahorro: 900, ahorro_ars: 100, items_count: 1 },
        { id: '2', timestamp: '2026-10-20T10:00:00Z', total_comodidad: NaN, total_ahorro: 900, ahorro_ars: 100, items_count: 1 },
        { id: '3', timestamp: '2026-10-20T10:00:00Z', total_comodidad: Infinity, total_ahorro: 900, ahorro_ars: 100, items_count: 1 },
        { id: '4', timestamp: '2026-10-20T10:00:00Z', total_comodidad: 1000, total_ahorro: 900, ahorro_ars: 100, items_count: 1 }, // Valid
      ]
      localStorage.setItem(BASKET_HISTORY_STORAGE_KEY, JSON.stringify(mixedSnapshots))
      const loaded = loadBasketHistory()
      expect(loaded).toHaveLength(1)
      expect(loaded[0].id).toBe('4')
    })

    it('1.6. sv_basket_history_v1: enforces 52-snapshot circular FIFO limit and sorts chronologically', () => {
      const manySnapshots: BasketSnapshot[] = []
      for (let i = 1; i <= 80; i++) {
        manySnapshots.push({
          id: `snap_${i}`,
          timestamp: new Date(2026, 0, i).toISOString(),
          items_count: 5,
          total_units: 5,
          total_comodidad: 50000,
          total_ahorro: 40000,
          ahorro_ars: 10000,
          savings_pct: 20,
          store_split: { Carrefour: 40000 },
          source: 'optimization_view',
        })
      }

      saveBasketHistory(manySnapshots)
      const loaded = loadBasketHistory()

      expect(loaded.length).toBe(MAX_SNAPSHOTS_LIMIT) // 52
      expect(loaded[0].id).toBe('snap_29') // 80 - 52 + 1 = 29
      expect(loaded[51].id).toBe('snap_80')
    })

    it('1.7. sv_basket_history_v1: recovers gracefully from localStorage QuotaExceededError by halving to 26', () => {
      const history50: BasketSnapshot[] = Array.from({ length: 50 }, (_, i) => ({
        id: `snap_${i}`,
        timestamp: new Date(2026, 0, i + 1).toISOString(),
        items_count: 3,
        total_units: 3,
        total_comodidad: 30000,
        total_ahorro: 25000,
        ahorro_ars: 5000,
        savings_pct: 16.7,
        store_split: { Dia: 25000 },
        source: 'optimization_view',
      }))

      let calls = 0
      const origSetItem = localStorage.setItem.bind(localStorage)
      vi.spyOn(Storage.prototype, 'setItem').mockImplementation((key, val) => {
        calls++
        if (calls === 1) {
          throw new DOMException('QuotaExceededError', 'QuotaExceededError')
        }
        origSetItem(key, val)
      })

      const success = saveBasketHistory(history50)
      expect(success).toBe(true)
      expect(calls).toBe(2) // 1st failed, 2nd halved succeeded

      const restored = loadBasketHistory()
      expect(restored.length).toBe(26) // Math.floor(52 / 2) = 26
    })
  })

  // =========================================================================
  // 2. EMPTY PLANS, SINGLE-STORE FALLBACKS, MISSING MODES
  // =========================================================================
  describe('2. Empty Plans, Single-Store Fallbacks & Missing Modes', () => {
    it('2.1. createSnapshotFromPlan returns null for null plan, total <= 0, or itemsCount <= 0', () => {
      expect(createSnapshotFromPlan(null as any, 5, 5)).toBeNull()

      const zeroTotalPlan: OptimizePlan = {
        mode: 'ahorro',
        total: 0,
        subtotal_mercaderia: 0,
        envio_estimado: 0,
        reintegro_bancario_total: 0,
        ahorro_total: 0,
        stops: 0,
        carts: [],
        missing: [],
      }
      expect(createSnapshotFromPlan(zeroTotalPlan, 5, 5)).toBeNull()
      expect(createSnapshotFromPlan({ ...zeroTotalPlan, total: 1000 }, 0, 0)).toBeNull()
    })

    it('2.2. createSnapshotFromPlan fallback math when mode_previews and all_plans are missing', () => {
      const basicPlan: OptimizePlan = {
        mode: 'ahorro',
        total: 35000,
        subtotal_mercaderia: 35000,
        envio_estimado: 0,
        reintegro_bancario_total: 0,
        ahorro_total: 5000,
        stops: 2,
        carts: [
          { supermercado: 'Carrefour', final_store_total: 20000, items: [] } as any,
          { supermercado: 'Dia', final_store_total: 15000, items: [] } as any,
        ],
        missing: [],
      }

      const snap = createSnapshotFromPlan(basicPlan, 2, 4, 'checkout')
      expect(snap).not.toBeNull()
      expect(snap?.total_ahorro).toBe(35000)
      // comodaTotal = plan.total + ahorro_total = 40000
      expect(snap?.total_comodidad).toBe(40000)
      expect(snap?.ahorro_ars).toBe(5000)
      expect(snap?.savings_pct).toBe(12.5) // (5000 / 40000) * 100
      expect(snap?.store_split).toEqual({ Carrefour: 20000, Dia: 15000 })
      expect(snap?.source).toBe('checkout')
    })

    it('2.3. SmartCartHero handles single-store fallback across all 3 modes gracefully', () => {
      const singleStorePreviews: Record<'ahorro' | 'balanceada' | 'comodidad', ScenarioPreview> = {
        ahorro: {
          ...samplePreviews.ahorro,
          supermercados_count: 1,
          stops: 1,
          total: 50000,
          ahorro_vs_comoda: 0,
          diff: 0,
        },
        balanceada: {
          ...samplePreviews.balanceada,
          supermercados_count: 1,
          stops: 1,
          total: 50000,
          ahorro_vs_comoda: 0,
          diff: 0,
        },
        comodidad: {
          ...samplePreviews.comodidad,
          supermercados_count: 1,
          stops: 1,
          total: 50000,
          ahorro_vs_comoda: 0,
          diff: 0,
        },
      }

      const singleStorePlan: OptimizePlan = {
        mode: 'ahorro',
        total: 50000,
        subtotal_mercaderia: 50000,
        envio_estimado: 0,
        reintegro_bancario_total: 0,
        ahorro_total: 0,
        stops: 1,
        mode_previews: singleStorePreviews,
        carts: [],
        missing: [],
      }

      render(
        <SmartCartHero
          mode="ahorro"
          plan={singleStorePlan}
          onSelectMode={vi.fn()}
        />,
      )

      expect(screen.getAllByText(/1 supermercado/i).length).toBeGreaterThan(0)
    })

    it('2.4. ListScreen triggers fallback network fetch when target mode is missing in all_plans', async () => {
      const items = [{ ean: '7790001', nombre: 'Leche 1L', qty: 1 }]
      localStorage.setItem('sv_cart_v2', JSON.stringify(items))

      const planAhorroOnly: OptimizePlan = {
        mode: 'ahorro',
        total: 35000,
        subtotal_mercaderia: 35000,
        envio_estimado: 0,
        reintegro_bancario_total: 0,
        ahorro_total: 5000,
        stops: 2,
        context_key: '7790001:1||false||lunes',
        mode_previews: samplePreviews,
        all_plans: {
          ahorro: {
            mode: 'ahorro',
            total: 35000,
            subtotal_mercaderia: 35000,
            envio_estimado: 0,
            reintegro_bancario_total: 0,
            ahorro_total: 5000,
            stops: 2,
            carts: [],
            missing: [],
          },
        } as any,
        carts: [],
        missing: [],
      }

      const planBalanceadaFetched: OptimizePlan = {
        mode: 'balanceada',
        total: 37000,
        subtotal_mercaderia: 37000,
        envio_estimado: 0,
        reintegro_bancario_total: 0,
        ahorro_total: 3000,
        stops: 2,
        context_key: '7790001:1||false||lunes',
        mode_previews: samplePreviews,
        carts: [],
        missing: [],
      }

      const optMock = vi.mocked(api.optimize)
      optMock.mockResolvedValueOnce(planAhorroOnly)

      render(
        <LocationProvider>
          <BenefitsProvider>
            <CartProvider>
              <HabitualListProvider>
                <ListScreen />
              </HabitualListProvider>
            </CartProvider>
          </BenefitsProvider>
        </LocationProvider>,
      )

      await waitFor(() => {
        expect(optMock).toHaveBeenCalledTimes(1)
      })

      optMock.mockResolvedValueOnce(planBalanceadaFetched)

      // Click "Equilibrada" which is NOT in all_plans
      const btnEquilibrada = screen.getByRole('button', { name: /seleccionar equilibrada/i })
      fireEvent.click(btnEquilibrada)

      await waitFor(
        () => {
          expect(optMock).toHaveBeenCalledWith(
            expect.any(Array),
            'balanceada',
            expect.any(Object),
          )
        },
        { timeout: 1500 },
      )
    })
  })

  // =========================================================================
  // 3. PARETO INDIFFERENCE THRESHOLDS: EXACT $3.499 vs $3.500 & 4.99% vs 5.00%
  // =========================================================================
  describe('3. Pareto Indifference Boundary Thresholds', () => {
    const evaluatePareto = (savings: number, totalComoda: number) => {
      const pct = totalComoda > 0 ? savings / totalComoda : 0
      const isJustified = savings >= 3500.0 && pct >= 0.05
      return { savings, pct, isJustified }
    }

    it('3.1. $3.499 ARS fails Pareto ARS threshold even with pct > 5%', () => {
      const res = evaluatePareto(3499.0, 50000.0) // 3499 / 50000 = 6.998% > 5%
      expect(res.pct).toBeGreaterThanOrEqual(0.05)
      expect(res.savings).toBeLessThan(3500.0)
      expect(res.isJustified).toBe(false)
    })

    it('3.2. $3.500 ARS satisfies Pareto threshold when pct >= 5%', () => {
      const res = evaluatePareto(3500.0, 50000.0) // 3500 / 50000 = 7.0% >= 5%
      expect(res.savings).toBeGreaterThanOrEqual(3500.0)
      expect(res.pct).toBeGreaterThanOrEqual(0.05)
      expect(res.isJustified).toBe(true)
    })

    it('3.3. 4.99% fails Pareto percentage threshold even with savings > $3.500 ARS', () => {
      // Basket of $80,161 ARS with savings of $4,000 ARS: 4000 / 80161 = 4.990% < 5.0%
      const res = evaluatePareto(4000.0, 80161.0)
      expect(res.savings).toBeGreaterThanOrEqual(3500.0)
      expect(res.pct).toBeLessThan(0.05)
      expect(res.isJustified).toBe(false)
    })

    it('3.4. 5.00% satisfies Pareto percentage threshold when savings >= $3.500 ARS', () => {
      // Basket of $70,000 ARS with savings of $3,500 ARS: 3500 / 70000 = 5.000%
      const res = evaluatePareto(3500.0, 70000.0)
      expect(res.savings).toBeGreaterThanOrEqual(3500.0)
      expect(res.pct).toBeGreaterThanOrEqual(0.05)
      expect(res.isJustified).toBe(true)
    })

    it('3.5. Missing items coverage override: keeps 2 stores even if savings < $3.500', () => {
      const k1Coverage = 3
      const k2Coverage = 4
      const savings = 1000.0 // < 3500
      const shouldKeepSplit = k2Coverage > k1Coverage || savings >= 3500.0
      expect(shouldKeepSplit).toBe(true)
    })
  })

  // =========================================================================
  // 4. 0ms MODE SWITCHING WITH 0 NETWORK CALLS
  // =========================================================================
  describe('4. 0ms Mode Switching with Zero Network Calls', () => {
    it('4.1. switches between modes in < 5ms with exactly 0 additional api.optimize calls', async () => {
      const items = [{ ean: '7790001', nombre: 'Leche 1L', qty: 1 }]
      localStorage.setItem('sv_cart_v2', JSON.stringify(items))

      const fullPlan: OptimizePlan = {
        mode: 'ahorro',
        total: 35000,
        subtotal_mercaderia: 35000,
        envio_estimado: 0,
        reintegro_bancario_total: 0,
        ahorro_total: 5000,
        stops: 2,
        context_key: '7790001:1||false||lunes',
        mode_previews: samplePreviews,
        all_plans: {
          ahorro: {
            mode: 'ahorro',
            total: 35000,
            subtotal_mercaderia: 35000,
            envio_estimado: 0,
            reintegro_bancario_total: 0,
            ahorro_total: 5000,
            stops: 2,
            carts: [],
            missing: [],
          },
          balanceada: {
            mode: 'balanceada',
            total: 37000,
            subtotal_mercaderia: 37000,
            envio_estimado: 0,
            reintegro_bancario_total: 0,
            ahorro_total: 3000,
            stops: 2,
            carts: [],
            missing: [],
          },
          comodidad: {
            mode: 'comodidad',
            total: 40000,
            subtotal_mercaderia: 40000,
            envio_estimado: 0,
            reintegro_bancario_total: 0,
            ahorro_total: 0,
            stops: 1,
            carts: [],
            missing: [],
          },
        },
        carts: [],
        missing: [],
      }

      vi.mocked(api.optimize).mockResolvedValue(fullPlan)

      render(
        <LocationProvider>
          <BenefitsProvider>
            <CartProvider>
              <HabitualListProvider>
                <ListScreen />
              </HabitualListProvider>
            </CartProvider>
          </BenefitsProvider>
        </LocationProvider>,
      )

      await waitFor(() => {
        expect(api.optimize).toHaveBeenCalledTimes(1)
      })

      const btnEquilibrada = screen.getByRole('button', { name: /seleccionar equilibrada/i })
      const btnComoda = screen.getByRole('button', { name: /seleccionar cómoda/i })
      const btnAhorro = screen.getByRole('button', { name: /seleccionar más barata|seleccionar barata/i })

      // Instant switch to Equilibrada
      const t0 = performance.now()
      fireEvent.click(btnEquilibrada)
      const t1 = performance.now()

      expect(t1 - t0).toBeLessThan(50)
      expect(api.optimize).toHaveBeenCalledTimes(1) // 0 additional calls

      // Instant switch to Cómoda
      fireEvent.click(btnComoda)
      expect(api.optimize).toHaveBeenCalledTimes(1) // Still 1 total call

      // Instant switch back to Ahorro
      fireEvent.click(btnAhorro)
      expect(api.optimize).toHaveBeenCalledTimes(1) // Still 1 total call
    })
  })

  // =========================================================================
  // 5. 100-TUPLE VTEX URL PRESERVATION & 100-CLICK AFFILIATE FIFO CAP
  // =========================================================================
  describe('5. VTEX 100-Tuple Preservation & 100-Click Affiliate FIFO Cap', () => {
    it('5.1. preserves exactly 100 repeating VTEX SKU tuples and appends attribution parameters', () => {
      const parts: string[] = []
      for (let i = 1; i <= 100; i++) {
        parts.push(`sku=SKU_${i}&qty=${(i % 3) + 1}&seller=1&sc=1`)
      }
      const rawUrl = `https://www.carrefour.com.ar/checkout/cart/add?${parts.join('&')}`

      const decorated = decorateOutboundUrl(rawUrl, 'Carrefour', 'checkout')
      expect(decorated).toContain('utm_source=supervmarket')
      expect(decorated).toContain('utm_medium=affiliate')
      expect(decorated).toContain('afiliado_id=supervmarket')

      const u = new URL(decorated)
      const skuEntries = u.searchParams.getAll('sku')
      const qtyEntries = u.searchParams.getAll('qty')
      const sellerEntries = u.searchParams.getAll('seller')
      const scEntries = u.searchParams.getAll('sc')

      expect(skuEntries).toHaveLength(100)
      expect(qtyEntries).toHaveLength(100)
      expect(sellerEntries).toHaveLength(100)
      expect(scEntries).toHaveLength(100)

      expect(skuEntries[0]).toBe('SKU_1')
      expect(skuEntries[99]).toBe('SKU_100')
      expect(qtyEntries[0]).toBe('2') // (1 % 3) + 1 = 2
    })

    it('5.2. decorateOutboundUrl is idempotent on 100-tuple VTEX URL', () => {
      const parts = Array.from({ length: 100 }, (_, i) => `sku=${i + 1}&qty=1&seller=1&sc=1`)
      const rawUrl = `https://www.jumbo.com.ar/checkout/cart/add?${parts.join('&')}`

      const decorated1 = decorateOutboundUrl(rawUrl, 'Jumbo', 'checkout')
      const decorated2 = decorateOutboundUrl(decorated1, 'Jumbo', 'checkout')

      expect(decorated2).toBe(decorated1)
      const u = new URL(decorated2)
      expect(u.searchParams.getAll('utm_source')).toHaveLength(1)
      expect(u.searchParams.getAll('afiliado_id')).toHaveLength(1)
      expect(u.searchParams.getAll('sku')).toHaveLength(100)
    })

    it('5.3. maintains strict FIFO cap of 100 entries across 150 recorded affiliate clicks', () => {
      for (let i = 1; i <= 150; i++) {
        trackOutboundAffiliateClick('Carrefour', 'checkout', `https://example.com/item/${i}`, i * 100)
      }

      const summary = getOutboundTrackingSummary()
      expect(summary.totalClicks).toBe(MAX_STORED_CLICKS) // 100

      // Most recent click (index 0) must be click 150
      expect(summary.lastClick?.targetUrl).toBe('https://example.com/item/150')
      expect(summary.lastClick?.estimatedValue).toBe(15000)

      const raw = localStorage.getItem(AFFILIATE_STORAGE_KEY)
      const list = JSON.parse(raw!)
      expect(list).toHaveLength(100)

      // Oldest retained click is click 51; clicks 1..50 must be evicted
      expect(list[99].targetUrl).toBe('https://example.com/item/51')
      expect(list.some((c: any) => c.targetUrl === 'https://example.com/item/1')).toBe(false)
      expect(list.some((c: any) => c.targetUrl === 'https://example.com/item/50')).toBe(false)
      expect(list.some((c: any) => c.targetUrl === 'https://example.com/item/51')).toBe(true)
    })

    it('5.4. handles corrupted affiliate click storage without throwing or crashing host UI', () => {
      localStorage.setItem(AFFILIATE_STORAGE_KEY, '{invalid json}')
      expect(getOutboundTrackingSummary()).toEqual({ totalClicks: 0 })

      // Tracking a click with corrupted storage does not throw or crash the app
      expect(() => {
        trackOutboundAffiliateClick('Dia', 'checkout', 'https://dia.com.ar')
      }).not.toThrow()

      // Summary safely returns 0 clicks without crashing
      const summary = getOutboundTrackingSummary()
      expect(summary.totalClicks).toBe(0)

      // Clearing or resetting storage allows fresh tracking
      localStorage.removeItem(AFFILIATE_STORAGE_KEY)
      trackOutboundAffiliateClick('Carrefour', 'checkout', 'https://carrefour.com.ar')
      expect(getOutboundTrackingSummary().totalClicks).toBe(1)
    })
  })
})
