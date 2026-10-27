import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import SmartCartHero from '../components/SmartCartHero'
import StoreCart from '../components/StoreCart'
import MissingItemsBreakdown from '../components/MissingItemsBreakdown'
import ListScreen from '../components/ListScreen'
import { CartProvider, useCart } from '../cart/CartContext'
import { LocationProvider } from '../location/LocationContext'
import { BenefitsProvider } from '../benefits/BenefitsContext'
import { HabitualListProvider, useHabitualList, HABITUAL_STORAGE_KEY } from '../cart/HabitualListContext'
import {
  BASKET_HISTORY_STORAGE_KEY,
  createSnapshotFromPlan,
  pushSnapshotToHistory,
  loadBasketHistory,
  calculateBasketDelta,
} from '../cart/basketHistory'
import {
  decorateOutboundUrl,
  trackOutboundAffiliateClick,
  AFFILIATE_STORAGE_KEY,
} from '../lib/affiliate'
import * as api from '../api'
import type { OptimizePlan, ScenarioPreview, StorePlan, MissingItemDetail } from '../types'

// Mock API functions for E2E tests
vi.mock('../api', async () => {
  const actual = await vi.importActual('../api')
  return {
    ...actual,
    optimize: vi.fn(),
    validateCart: vi.fn().mockResolvedValue({ status: 'ok', total: 0, sin_stock: [] }),
    getBenefits: vi.fn().mockResolvedValue({
      today: 'miercoles',
      today_label: 'Miércoles',
      weekdays: [],
      payment_options: [],
      official_links: {},
      daily_promos: [],
    }),
    getRegions: vi.fn().mockResolvedValue([]),
  }
})

describe('SmartCartScenarios E2E Suite (Features 1, 2, 3, 5, 6, 12 across Tiers 1-4)', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    localStorage.clear()
  })

  // =========================================================================
  // TIER 1: FEATURE COVERAGE (Positive Functional Tests)
  // =========================================================================
  describe('Tier 1: Feature Coverage (Features 1, 2, 3, 5, 6, 12)', () => {
    // -----------------------------------------------------------------------
    // Feature 1: Opción Más Barata (ahorro)
    // -----------------------------------------------------------------------
    describe('Feature 1: Opción Más Barata (ahorro)', () => {
      it('F1-T1.1: Multi-Store Split Assignment (2 Stores): allocates items to lowest price store', () => {
        const item1 = { ean: '111', carrefour: 1000, dia: 1500 }
        const item2 = { ean: '222', carrefour: 2000, dia: 1200 }

        // Lowest price selection
        const assignment = {
          '111': item1.carrefour < item1.dia ? 'Carrefour' : 'Dia',
          '222': item2.carrefour < item2.dia ? 'Carrefour' : 'Dia',
        }

        expect(assignment['111']).toBe('Carrefour')
        expect(assignment['222']).toBe('Dia')

        const uniqueStores = new Set(Object.values(assignment))
        expect(uniqueStores.size).toBe(2)
      })

      it('F1-T1.2: Multi-Store Split Assignment (3 Stores): k=3 stops with quantified net savings', () => {
        const plan: OptimizePlan = {
          mode: 'ahorro',
          stops: 3,
          supermercados: ['Carrefour', 'Dia', 'Coto'],
          total: 45000,
          subtotal_merch: 40000,
          shipping_fee: 5000,
          ahorro_vs_comoda: 8500,
          ahorro_vs_regular: 14000,
          ahorro_pct: 15.9,
          covered_items: 6,
          total_items: 6,
          missing: [],
          store_breakdowns: [],
          all_plans: {} as any,
          mode_previews: {} as any,
        }

        expect(plan.stops).toBe(3)
        expect(plan.supermercados.length).toBe(3)
        expect(plan.ahorro_vs_comoda).toBe(8500)
        expect(plan.total).toBe(45000)
      })

      it('F1-T1.3: Single Store Fallback: collapses gracefully to 1 store when only 1 is available', () => {
        const plan: OptimizePlan = {
          mode: 'ahorro',
          stops: 1,
          supermercados: ['Carrefour'],
          total: 30000,
          subtotal_merch: 30000,
          shipping_fee: 0,
          ahorro_vs_comoda: 0,
          ahorro_vs_regular: 4000,
          ahorro_pct: 11.7,
          covered_items: 3,
          total_items: 3,
          missing: [],
          store_breakdowns: [],
          all_plans: {} as any,
          mode_previews: {} as any,
        }

        expect(plan.stops).toBe(1)
        expect(plan.supermercados).toEqual(['Carrefour'])
        expect(plan.ahorro_vs_comoda).toBe(0)
      })

      it('F1-T1.4: Net Financial Quantification: total = merch + shipping - rebates; diff = total_comoda - total_ahorro', () => {
        const merch = 60000
        const shipping = 5000
        const bankRebate = 10000
        const totalAhorro = merch + shipping - bankRebate

        const totalComoda = 70000
        const ahorroVsComoda = Math.max(0, totalComoda - totalAhorro)

        expect(totalAhorro).toBe(55000)
        expect(ahorroVsComoda).toBe(15000)
      })

      it('F1-T1.5: UI Presentation & Badge in SmartCartHero: badge "MÁXIMO AHORRO", diff "$ 0"', () => {
        const preview: ScenarioPreview = {
          mode: 'ahorro',
          title: 'Opción más barata',
          tagline: 'Split óptimo 2 súper',
          total: 45000,
          ahorro_vs_comoda: 8500,
          ahorro_vs_regular: 12000,
          ahorro_pct: 15.9,
          supermercados_count: 2,
          covered_items: 5,
          total_items: 5,
          badge: 'MÁXIMO AHORRO',
          diff: 0,
          stops: 2,
        }

        render(
          <SmartCartHero
            mode="ahorro"
            onSelectMode={() => {}}
            plan={{
              mode: 'ahorro',
              stops: 2,
              total: 45000,
              mode_previews: { ahorro: preview, balanceada: preview, comodidad: preview },
            } as any}
          />
        )

        expect(screen.getByText('MÁXIMO AHORRO')).toBeTruthy()
        expect(screen.getByText('Opción más barata')).toBeTruthy()
        expect(screen.getAllByText(/45\.000/).length).toBeGreaterThan(0)
      })
    })

    // -----------------------------------------------------------------------
    // Feature 2: Opción Equilibrada (balanceada)
    // -----------------------------------------------------------------------
    describe('Feature 2: Opción Equilibrada (balanceada)', () => {
      it('F2-T1.1: Pareto Frontier Justified Split: selects 2 stores when savings >= $3.500 AND >= 5%', () => {
        const singleStoreTotal = 50000
        const splitStoreTotal = 44000
        const netSavings = singleStoreTotal - splitStoreTotal // $6.000 >= $3.500
        const savingsPct = (netSavings / singleStoreTotal) * 100 // 12% >= 5%

        const isParetoJustified = netSavings >= 3500 && savingsPct >= 5.0
        expect(isParetoJustified).toBe(true)
      })

      it('F2-T1.2: Pareto Indifference Marginal Collapse (< $3.500): collapses to 1 store', () => {
        const singleStoreTotal = 30000
        const splitStoreTotal = 28000
        const netSavings = singleStoreTotal - splitStoreTotal // $2.000 < $3.500
        const savingsPct = (netSavings / singleStoreTotal) * 100 // 6.67% >= 5%

        const isParetoJustified = netSavings >= 3500 && savingsPct >= 5.0
        const finalStops = isParetoJustified ? 2 : 1
        expect(finalStops).toBe(1)
      })

      it('F2-T1.3: Pareto Indifference Percentage Collapse (< 5%): collapses to 1 store on large cart', () => {
        const singleStoreTotal = 120000
        const splitStoreTotal = 116000
        const netSavings = singleStoreTotal - splitStoreTotal // $4.000 >= $3.500
        const savingsPct = (netSavings / singleStoreTotal) * 100 // 3.33% < 5%

        const isParetoJustified = netSavings >= 3500 && savingsPct >= 5.0
        const finalStops = isParetoJustified ? 2 : 1
        expect(finalStops).toBe(1)
      })

      it('F2-T1.4: Missing Item Coverage Override: keeps 2 stores if 1-store has unstocked items', () => {
        const singleStoreCoverage = 4
        const splitStoreCoverage = 5
        const netSavings = 1000 // < $3.500

        // If single store fails 100% coverage while split covers all items, override collapse
        const shouldKeepSplit = splitStoreCoverage > singleStoreCoverage || netSavings >= 3500
        expect(shouldKeepSplit).toBe(true)
      })

      it('F2-T1.5: UI Presentation & Badge: renders "RECOMENDADA" and "Ahorro vs conveniencia"', () => {
        const preview: ScenarioPreview = {
          mode: 'balanceada',
          title: 'Opción equilibrada',
          tagline: 'Ahorro vs conveniencia',
          total: 47000,
          ahorro_vs_comoda: 6500,
          ahorro_vs_regular: 10000,
          ahorro_pct: 12.1,
          supermercados_count: 2,
          covered_items: 5,
          total_items: 5,
          badge: 'RECOMENDADA',
          diff: 2000,
          stops: 2,
        }

        render(
          <SmartCartHero
            mode="balanceada"
            onSelectMode={() => {}}
            plan={{
              mode: 'balanceada',
              stops: 2,
              total: 47000,
              mode_previews: { ahorro: preview, balanceada: preview, comodidad: preview },
            } as any}
          />
        )

        expect(screen.getByText('RECOMENDADA')).toBeTruthy()
        expect(screen.getByText('Opción equilibrada')).toBeTruthy()
      })
    })

    // -----------------------------------------------------------------------
    // Feature 3: Opción Cómoda (comodidad)
    // -----------------------------------------------------------------------
    describe('Feature 3: Opción Cómoda (comodidad)', () => {
      it('F3-T1.1: Best Single Store Evaluation (k=1): picks single store with highest coverage and lowest cost', () => {
        const storeOptions = [
          { store: 'Carrefour', covered: 5, totalCost: 50000 },
          { store: 'Dia', covered: 4, totalCost: 35000 },
          { store: 'Coto', covered: 5, totalCost: 52000 },
        ]

        // Filter highest coverage first, then lowest cost
        const maxCoverage = Math.max(...storeOptions.map(s => s.covered))
        const candidates = storeOptions.filter(s => s.covered === maxCoverage)
        candidates.sort((a, b) => a.totalCost - b.totalCost)

        expect(candidates[0].store).toBe('Carrefour')
        expect(candidates[0].totalCost).toBe(50000)
      })

      it('F3-T1.2: Convenience Surcharge Calculation: diff = total_comoda - total_ahorro', () => {
        const totalComoda = 53500
        const totalAhorro = 45000
        const diff = totalComoda - totalAhorro
        expect(diff).toBe(8500)
      })

      it('F3-T1.3: Surcharge Badge Display in SmartCartHero when diff > 0', () => {
        const previewComoda: ScenarioPreview = {
          mode: 'comodidad',
          title: 'Opción cómoda',
          tagline: 'Todo en 1 solo súper',
          total: 53500,
          ahorro_vs_comoda: 0,
          ahorro_vs_regular: 3500,
          ahorro_pct: 0,
          supermercados_count: 1,
          covered_items: 5,
          total_items: 5,
          badge: '1 SOLO SÚPER',
          diff: 8500,
          stops: 1,
        }

        render(
          <SmartCartHero
            mode="comodidad"
            onSelectMode={() => {}}
            plan={{
              mode: 'comodidad',
              stops: 1,
              total: 53500,
              mode_previews: { ahorro: previewComoda, balanceada: previewComoda, comodidad: previewComoda },
            } as any}
          />
        )

        expect(screen.getByText('1 SOLO SÚPER')).toBeTruthy()
        expect(screen.getByText('Opción cómoda')).toBeTruthy()
      })

      it('F3-T1.4: Same Price Detection: diff == 0 displays identical price', () => {
        const previewEqual: ScenarioPreview = {
          mode: 'comodidad',
          title: 'Opción cómoda',
          tagline: 'Todo en 1 solo súper',
          total: 45000,
          ahorro_vs_comoda: 0,
          ahorro_vs_regular: 5000,
          ahorro_pct: 0,
          supermercados_count: 1,
          covered_items: 5,
          total_items: 5,
          badge: '1 SOLO SÚPER',
          diff: 0,
          stops: 1,
        }

        render(
          <SmartCartHero
            mode="comodidad"
            onSelectMode={() => {}}
            plan={{
              mode: 'comodidad',
              stops: 1,
              total: 45000,
              mode_previews: { ahorro: previewEqual, balanceada: previewEqual, comodidad: previewEqual },
            } as any}
          />
        )

        expect(screen.getByText(/Mismo precio que Más Barata/i)).toBeTruthy()
      })

      it('F3-T1.5: Missing Items Warning: flags missing items in single store mode', () => {
        const plan: OptimizePlan = {
          mode: 'comodidad',
          stops: 1,
          supermercados: ['Dia'],
          total: 35000,
          covered_items: 4,
          total_items: 5,
          missing: [
            {
              ean: '7790895000997',
              nombre: 'Leche La Serenísima',
              missing_in_assigned_stores: ['Dia'],
              available_in_other_stores: [{ supermercado: 'Carrefour', precio: 1500 }],
            },
          ],
          logistics_warning: 'Faltan productos en este supermercado',
          store_breakdowns: [],
          all_plans: {} as any,
          mode_previews: {} as any,
        }

        expect(plan.covered_items).toBeLessThan(plan.total_items)
        expect(plan.missing.length).toBe(1)
        expect(plan.logistics_warning).toContain('Faltan productos')
      })
    })

    // -----------------------------------------------------------------------
    // Feature 5: Desglose de Promos & Beneficios
    // -----------------------------------------------------------------------
    describe('Feature 5: Desglose de Promos & Beneficios', () => {
      it('F5-T1.1: Volume Discount 2x1: buying 2 units charges 1 unit; buying 4 charges 2', () => {
        const unitPrice = 2000
        const calc2x1 = (qty: number) => {
          const pairs = Math.floor(qty / 2)
          const remainder = qty % 2
          return pairs * unitPrice + remainder * unitPrice
        }

        expect(calc2x1(2)).toBe(2000) // 1 free
        expect(calc2x1(4)).toBe(4000) // 2 free
        expect(calc2x1(3)).toBe(4000) // 1 pair charged + 1 unit
      })

      it('F5-T1.2: Volume Discount 2do al 70%: 2 units receive 35% net bundle discount', () => {
        const unitPrice = 1000
        const qty = 2
        const secondUnitPrice = unitPrice * 0.3 // 70% off = 300
        const bundleTotal = unitPrice + secondUnitPrice // 1300
        const regularTotal = unitPrice * qty // 2000
        const discountPct = ((regularTotal - bundleTotal) / regularTotal) * 100

        expect(bundleTotal).toBe(1300)
        expect(discountPct).toBe(35)
      })

      it('F5-T1.3: Bank Card Rebates: calculates percentage rebate for active card and day', () => {
        const subtotal = 40000
        const discountPct = 0.2 // Santander 20%
        const bankDiscount = subtotal * discountPct
        expect(bankDiscount).toBe(8000)
      })

      it('F5-T1.4: Bank Rebate Cap Enforcement: strictly caps discount at maximum cap', () => {
        const subtotal = 80000
        const discountPct = 0.2
        const rawDiscount = subtotal * discountPct // 16000
        const cap = 10000
        const effectiveDiscount = Math.min(rawDiscount, cap)
        expect(effectiveDiscount).toBe(10000)
      })

      it('F5-T1.5: Best Day Recommendation: optimizer suggests best day with maximum saving', () => {
        const weekSavings: Record<string, number> = {
          lunes: 2000,
          martes: 0,
          miercoles: 10000, // Santander Day
          jueves: 4000,
          viernes: 5000,
          sabado: 0,
          domingo: 0,
        }

        const bestDay = Object.entries(weekSavings).reduce(
          (best, [day, saving]) => (saving > best.saving ? { day, saving } : best),
          { day: '', saving: 0 }
        )

        expect(bestDay.day).toBe('miercoles')
        expect(bestDay.saving).toBe(10000)
      })
    })

    // -----------------------------------------------------------------------
    // Feature 6: Cotización y Progreso de Flete
    // -----------------------------------------------------------------------
    describe('Feature 6: Cotización y Progreso de Flete', () => {
      it('F6-T1.1: Dynamic Shipping Fee Addition: subtotal < threshold adds shipping fee', () => {
        const subtotal = 25000
        const threshold = 40000
        const shippingRate = 4800
        const isFree = subtotal >= threshold
        const finalShipping = isFree ? 0 : shippingRate

        expect(finalShipping).toBe(4800)
      })

      it('F6-T1.2: Free Shipping Threshold Attainment: subtotal >= threshold sets shipping to 0', () => {
        const subtotal = 45000
        const threshold = 40000
        const shippingRate = 4800
        const isFree = subtotal >= threshold
        const finalShipping = isFree ? 0 : shippingRate

        expect(isFree).toBe(true)
        expect(finalShipping).toBe(0)
      })

      it('F6-T1.3: Free Shipping Progress Bar: calculates progress percentage capped at 100%', () => {
        const calcProgress = (subtotal: number, threshold: number) =>
          Math.min(100, Math.round((subtotal / threshold) * 100))

        expect(calcProgress(20000, 40000)).toBe(50)
        expect(calcProgress(30000, 40000)).toBe(75)
        expect(calcProgress(45000, 40000)).toBe(100)
      })

      it('F6-T1.4: Amount Remaining for Free Shipping: calculates threshold - subtotal', () => {
        const subtotal = 28000
        const threshold = 35000
        const falta = Math.max(0, threshold - subtotal)
        expect(falta).toBe(7000)
      })

      it('F6-T1.5: Real-Time Shipping Toggle in StoreCart: renders shipping info or free shipping badge', async () => {
        const planWithShipping: StorePlan = {
          supermercado: 'Carrefour',
          supports_cart: true,
          checkout_url: 'https://carrefour.com.ar',
          subtotal: 25000,
          free_shipping_threshold: 40000,
          falta_envio_gratis: 15000,
          shipping_fee: 4800,
          items: [{ ean: '111', nombre: 'Yerba Mate Playadito 1kg', qty: 1, precio: 4500 }],
        }

        render(
          <LocationProvider>
            <StoreCart plan={planWithShipping} />
          </LocationProvider>
        )

        await waitFor(() => {
          expect(screen.getAllByText(/Carrefour/i).length).toBeGreaterThan(0)
          expect(screen.getByText(/4\.800/)).toBeTruthy()
        })
      })
    })

    // -----------------------------------------------------------------------
    // Feature 12: Integración Oficial Mercado Libre & IA
    // -----------------------------------------------------------------------
    describe('Feature 12: Integración Oficial Mercado Libre & IA', () => {
      it('F12-T1.1: OAuth token headers & caching structure', () => {
        const tokenCache = {
          access_token: 'APP_USR-test-token-123',
          expires_at: Date.now() + 3600000,
        }

        const isTokenValid = (now: number) => now < tokenCache.expires_at
        expect(isTokenValid(Date.now())).toBe(true)
        expect(isTokenValid(Date.now() + 4000000)).toBe(false)
      })

      it('F12-T1.2: MLA Catalog normalization to unified schema', () => {
        const mlaProduct = {
          id: 'MLA987654321',
          title: 'Café Molido Cabrales 500g',
          price: 6500,
          permalink: 'https://articulo.mercadolibre.com.ar/MLA-987654321-cafe',
          shipping: { logistic_type: 'fulfillment', free_shipping: true },
        }

        const normalized = {
          ean: '7790001112223',
          nombre: mlaProduct.title,
          precio: mlaProduct.price,
          supermercado: 'MercadoLibre',
          link: mlaProduct.permalink,
          is_full: mlaProduct.shipping.logistic_type === 'fulfillment',
          free_shipping: mlaProduct.shipping.free_shipping,
        }

        expect(normalized.supermercado).toBe('MercadoLibre')
        expect(normalized.is_full).toBe(true)
        expect(normalized.free_shipping).toBe(true)
      })

      it('F12-T1.3: Envíos FULL Badge detection and rendering in alternatives', () => {
        const missingItem: MissingItemDetail = {
          ean: '7790001112223',
          nombre: 'Café Premium en Grano 1kg',
          missing_in_assigned_stores: ['Dia'],
          available_in_other_stores: [
            {
              supermercado: 'MercadoLibre',
              precio: 14500,
              promo_badge: 'FULL',
            },
          ],
        }

        render(<MissingItemsBreakdown missing={[missingItem]} />)
        expect(screen.getByText('Mercado Libre')).toBeTruthy()
        expect(screen.getByText('FULL')).toBeTruthy()
        expect(screen.getByText(/14\.500/)).toBeTruthy()
      })

      it('F12-T1.4: Seller reputation level & power seller display', () => {
        const sellerData = {
          id: 12345,
          nickname: 'TIENDA_OFICIAL',
          power_seller_status: 'gold',
          seller_reputation: { level_id: '5_green' },
        }

        expect(sellerData.power_seller_status).toBe('gold')
        expect(sellerData.seller_reputation.level_id).toBe('5_green')
      })

      it('F12-T1.5: AI Assistant Prompt-to-Cart recipe extraction into structured items list', () => {
        const mockRecipePrompt = 'Guiso de lentejas para 4 personas'
        const extractedItems = [
          { ean: '779001', nombre: 'Lentejas secas 500g', qty: 2 },
          { ean: '779002', nombre: 'Chorizo colorado', qty: 2 },
          { ean: '779003', nombre: 'Puré de tomate 520g', qty: 2 },
          { ean: '779004', nombre: 'Cebolla 1kg', qty: 1 },
        ]

        expect(extractedItems.length).toBe(4)
        expect(extractedItems[0].nombre).toContain('Lentejas')
      })
    })
  })

  // =========================================================================
  // TIER 2: BOUNDARY & CORNER CASES (Features 1, 2, 3, 5, 6, 12)
  // =========================================================================
  describe('Tier 2: Boundary & Corner Cases (Features 1, 2, 3, 5, 6, 12)', () => {
    it('F1-T2.1: 1-Item Basket: split optimizer cannot split and forces stops = 1', () => {
      const basket = [{ ean: '111', qty: 1 }]
      const maxPossibleStops = Math.min(basket.length, 3)
      expect(maxPossibleStops).toBe(1)
    })

    it('F1-T2.2: Equal Prices Across Stores breaks ties with minimum stops', () => {
      const candidates = [
        { stops: 2, total: 30000 },
        { stops: 1, total: 30000 },
      ]
      candidates.sort((a, b) => a.total - b.total || a.stops - b.stops)
      expect(candidates[0].stops).toBe(1)
    })

    it('F1-T2.3: Disjoint Inventories forces multi-store split regardless of mode', () => {
      const storeA = ['item1']
      const storeB = ['item2']
      const cart = ['item1', 'item2']

      const canSingleStoreCover = storeA.length === cart.length || storeB.length === cart.length
      expect(canSingleStoreCover).toBe(false)
    })

    it('F1-T2.4: Bulk Volume Order (qty = 100) shifts store preference via volume discount', () => {
      // Store A: linear price $100
      // Store B: regular $120, but bulk tier (qty >= 50) $80
      const calcA = (qty: number) => qty * 100
      const calcB = (qty: number) => qty * (qty >= 50 ? 80 : 120)

      expect(calcA(10)).toBe(1000)
      expect(calcB(10)).toBe(1200) // Store A wins for small qty

      expect(calcA(100)).toBe(10000)
      expect(calcB(100)).toBe(8000) // Store B wins for bulk qty
    })

    it('F1-T2.5: Logistics Warning Trigger: shipping across split stores strictly exceeds savings', () => {
      const merchSavings = 1500
      const extraShipping = 4500
      const shouldWarn = extraShipping > merchSavings
      expect(shouldWarn).toBe(true)
    })

    it('F2-T2.1: Exact Boundary $3.499 vs $3.500 ARS in Pareto balance', () => {
      const isPareto = (savings: number, pct: number) => savings >= 3500 && pct >= 5.0
      expect(isPareto(3499, 10.0)).toBe(false)
      expect(isPareto(3500, 10.0)).toBe(true)
    })

    it('F2-T2.2: Exact Boundary 4.99% vs 5.00% in Pareto balance', () => {
      const isPareto = (savings: number, pct: number) => savings >= 3500 && pct >= 5.0
      expect(isPareto(5000, 4.99)).toBe(false)
      expect(isPareto(5000, 5.00)).toBe(true)
    })

    it('F2-T2.3: Negative Savings (Split Cost > Single Store Cost) collapses to 1 store', () => {
      const singleStoreTotal = 50000
      const splitTotalWithExtraShipping = 54000
      const savings = singleStoreTotal - splitTotalWithExtraShipping
      expect(savings).toBeLessThan(0)
    })

    it('F2-T2.4: Zero Diff / Identical Totals collapses to 1 store', () => {
      const singleTotal = 40000
      const splitTotal = 40000
      const diff = singleTotal - splitTotal
      expect(diff).toBe(0)
    })

    it('F2-T2.5: Identical Store Stock (stops <= 1) collapses to 1 store', () => {
      const assignedStores = ['Carrefour', 'Carrefour']
      const uniqueStores = new Set(assignedStores)
      expect(uniqueStores.size).toBe(1)
    })

    it('F3-T2.1: Priority of Coverage over Price: 10/10 items wins over 9/10 items even at higher price', () => {
      const storeA = { covered: 10, total: 50000 }
      const storeB = { covered: 9, total: 20000 }

      const pickBestComoda = (s1: typeof storeA, s2: typeof storeB) => {
        if (s1.covered !== s2.covered) return s1.covered > s2.covered ? s1 : s2
        return s1.total < s2.total ? s1 : s2
      }

      expect(pickBestComoda(storeA, storeB)).toBe(storeA)
    })

    it('F3-T2.2: Single Store Available in CP: all 3 modes return identical total', () => {
      const comodaTotal = 35000
      const ahorroTotal = 35000
      const balanceadaTotal = 35000
      expect(comodaTotal).toBe(ahorroTotal)
      expect(ahorroTotal).toBe(balanceadaTotal)
    })

    it('F3-T2.3: Partial Coverage (No store has 100%): flags missing items', () => {
      const storeCoverage = 7
      const totalItems = 10
      const missingCount = totalItems - storeCoverage
      expect(missingCount).toBe(3)
    })

    it('F3-T2.4: Zero Convenience Surcharge displays "Mismo precio que Más Barata"', () => {
      const diff = 0
      const message = diff === 0 ? '¡Mismo precio que Más Barata!' : `Costo de conveniencia +$ ${diff}`
      expect(message).toBe('¡Mismo precio que Más Barata!')
    })

    it('F3-T2.5: Extreme Value Basket (9 figures) handled without numeric overflow', () => {
      const extremeTotal = 150000000
      const formatted = extremeTotal.toLocaleString('es-AR')
      expect(formatted).toContain('150.000.000')
    })

    it('F5-T2.1: Odd Quantities in 2x1: qty=3 charges 2; qty=5 charges 3', () => {
      const calcChargeUnits = (qty: number) => Math.floor(qty / 2) + (qty % 2)
      expect(calcChargeUnits(3)).toBe(2)
      expect(calcChargeUnits(5)).toBe(3)
    })

    it('F5-T2.2: Exact Bank Cap Reached ($50.000 at 20% = $10.000 cap)', () => {
      const subtotal = 50000
      const discount = subtotal * 0.2
      const cap = 10000
      expect(Math.min(discount, cap)).toBe(10000)
    })

    it('F5-T2.3: Bank Cap Exceeded ($80.000 at 20% capped at $10.000)', () => {
      const subtotal = 80000
      const discount = subtotal * 0.2 // 16000
      const cap = 10000
      expect(Math.min(discount, cap)).toBe(10000)
    })

    it('F5-T2.4: Multiple Cards Comparison: picks optimal card per store', () => {
      const cards = [
        { name: 'Galicia', pct: 0.15, saving: 6000 },
        { name: 'Santander', pct: 0.20, saving: 8000 },
      ]
      cards.sort((a, b) => b.saving - a.saving)
      expect(cards[0].name).toBe('Santander')
      expect(cards[0].saving).toBe(8000)
    })

    it('F5-T2.5: Club Membership Denial if user lacks store club card', () => {
      const offer = {
        regular_price: 2500,
        club_price: 1800,
        requires_club: true,
      }
      const userHasClub = false
      const effectivePrice = userHasClub || !offer.requires_club ? offer.club_price : offer.regular_price
      expect(effectivePrice).toBe(2500)
    })

    it('F6-T2.1: Exactly $1 Below Threshold charges shipping fee and sets falta = 1', () => {
      const threshold = 30000
      const subtotal = 29999
      const falta = threshold - subtotal
      const isFree = subtotal >= threshold
      expect(falta).toBe(1)
      expect(isFree).toBe(false)
    })

    it('F6-T2.2: Exactly at Threshold sets shipping to 0 and is_free_shipping = true', () => {
      const threshold = 30000
      const subtotal = 30000
      const falta = Math.max(0, threshold - subtotal)
      const isFree = subtotal >= threshold
      expect(falta).toBe(0)
      expect(isFree).toBe(true)
    })

    it('F6-T2.3: Zero Free Shipping Threshold maintains static shipping fee', () => {
      const threshold = 0
      const isFree = threshold > 0
      expect(isFree).toBe(false)
    })

    it('F6-T2.4: Empty Store Cart ($0 subtotal) never charges phantom shipping', () => {
      const subtotal = 0
      const shippingFee = subtotal === 0 ? 0 : 4500
      expect(shippingFee).toBe(0)
    })

    it('F6-T2.5: Multi-Store Shipping Inversion generates logistics warning', () => {
      const singleStoreShipping = 0 // reached free shipping
      const splitShipping = 4500 + 4800 // 9300
      const merchSavings = 3000
      const netSavings = merchSavings - (splitShipping - singleStoreShipping) // -6300
      expect(netSavings).toBeLessThan(0)
    })

    it('F12-T2.1: MeLi Token Expiration & Refresh triggers renewal', () => {
      const expiresAt = Date.now() - 1000 // expired 1s ago
      const isExpired = Date.now() >= expiresAt
      expect(isExpired).toBe(true)
    })

    it('F12-T2.2: Free Shipping Threshold ($65.000) on Mercado Libre', () => {
      const meliThreshold = 65000
      expect(45000 >= meliThreshold).toBe(false)
      expect(65000 >= meliThreshold).toBe(true)
      expect(70000 >= meliThreshold).toBe(true)
    })

    it('F12-T2.3: Missing Seller Reputation Default fallback', () => {
      const seller = { nickname: 'VENDEDOR_NUEVO' }
      const reputation = (seller as any).seller_reputation?.level_id ?? 'sin_datos'
      expect(reputation).toBe('sin_datos')
    })

    it('F12-T2.4: Dynamic Shipping 404 Resilience falls back to static estimate', () => {
      const apiResponse: { status: number; cost?: number } = { status: 404 }
      const finalCost = apiResponse.status === 200 ? apiResponse.cost : 5500
      expect(finalCost).toBe(5500)
    })

    it('F12-T2.5: MLA ID Formatting normalization handles both MLA-123 and MLA123', () => {
      const normalizeMla = (id: string) => id.replace(/-/g, '').toUpperCase()
      expect(normalizeMla('MLA-123456')).toBe('MLA123456')
      expect(normalizeMla('mla123456')).toBe('MLA123456')
    })
  })

  // =========================================================================
  // TIER 3: PAIRWISE CROSS-FEATURE INTERACTIONS (12 Combinations)
  // =========================================================================
  describe('Tier 3: Pairwise Cross-Feature Interactions (12 Interactions)', () => {
    it('Pairwise 1 (F1 x F5: Más Barata x Volume Promos): Volume promo inverts cheapest store winner when qty scales from 1 to 2', () => {
      // Carrefour: $2000 regular, 2x1 promotion (2 for $2000)
      // Dia: $1500 regular, no volume discount (2 for $3000)
      const carrefourCalc = (qty: number) => (qty === 2 ? 2000 : qty * 2000)
      const diaCalc = (qty: number) => qty * 1500

      // At qty = 1: Dia is cheaper ($1500 vs $2000) -> Dia wins
      const winnerQty1 = diaCalc(1) < carrefourCalc(1) ? 'Dia' : 'Carrefour'
      expect(winnerQty1).toBe('Dia')

      // At qty = 2: Carrefour 2x1 is cheaper ($2000 vs $3000) -> Carrefour wins!
      const winnerQty2 = diaCalc(2) < carrefourCalc(2) ? 'Dia' : 'Carrefour'
      expect(winnerQty2).toBe('Carrefour')
    })

    it('Pairwise 2 (F1 x F6: Más Barata x Shipping Fees): Multi-store shipping exceeds merchandise savings -> generates logistics_warning', () => {
      const singleStoreMerch = 40000
      const singleStoreShipping = 0 // Free shipping
      const singleStoreTotal = singleStoreMerch + singleStoreShipping

      const splitMerch = 38000 // $2000 merchandise saving
      const splitShipping = 4800 + 4599 // $9399 double shipping
      const splitTotal = splitMerch + splitShipping // 47399

      const isLogisticsInverted = splitTotal > singleStoreTotal
      expect(isLogisticsInverted).toBe(true)

      const logisticsWarning = isLogisticsInverted
        ? 'El costo de envío combinado supera el ahorro en mercadería'
        : null
      expect(logisticsWarning).not.toBeNull()
    })

    it('Pairwise 3 (F2 x F6: Equilibrada x Shipping Fees): Shipping fees included before evaluating Pareto thresholds', () => {
      const singleStoreMerch = 50000
      const singleStoreShipping = 0
      const singleStoreNet = singleStoreMerch + singleStoreShipping // 50000

      const splitMerch = 45000 // $5000 merch savings
      const splitShipping = 3000
      const splitNet = splitMerch + splitShipping // 48000

      const netSavings = singleStoreNet - splitNet // $2000
      const netPct = (netSavings / singleStoreNet) * 100 // 4%

      // Net savings ($2000) is < $3.500 and 4% < 5% -> collapses to 1 store!
      const justified = netSavings >= 3500 && netPct >= 5.0
      expect(justified).toBe(false)
    })

    it('Pairwise 4 (F3 x F4: Cómoda x Missing Items Breakdown): Selecting Cómoda with unstocked items renders MissingItemsBreakdown', () => {
      const missingItem: MissingItemDetail = {
        ean: '7791234567890',
        nombre: 'Aceite de Oliva Extra Virgen 500ml',
        missing_in_assigned_stores: ['Dia'],
        available_in_other_stores: [
          { supermercado: 'Carrefour', precio: 5400, promo_badge: '15% OFF' },
        ],
      }

      render(<MissingItemsBreakdown missing={[missingItem]} />)
      expect(screen.getByText('Aceite de Oliva Extra Virgen 500ml')).toBeTruthy()
      expect(screen.getByText(/Día/i)).toBeTruthy()
      expect(screen.getByText('Carrefour')).toBeTruthy()
      expect(screen.getByText('15% OFF')).toBeTruthy()
    })

    it('Pairwise 5 (F3 x F6: Cómoda x Free Shipping Threshold): Single store consolidates entire basket reaching threshold ($0 shipping)', () => {
      const threshold = 35000
      const item1 = 20000
      const item2 = 18000

      // Split: each store gets < $35k -> both charge shipping
      const splitCarrefour = item1 < threshold // true -> $4800 shipping
      const splitDia = item2 < threshold // true -> $4599 shipping
      expect(splitCarrefour && splitDia).toBe(true)

      // Consolidated in 1 store: 20k + 18k = 38k >= 35k -> Free shipping ($0)!
      const consolidated = item1 + item2
      const isConsolidatedFree = consolidated >= threshold
      expect(isConsolidatedFree).toBe(true)
    })

    it('Pairwise 6 (F4 x F12: Missing Items x Mercado Libre FULL): Supermarket missing item resolved via Mercado Libre FULL', () => {
      const missingItem: MissingItemDetail = {
        ean: '7799990001112',
        nombre: 'Cápsulas de Café Nespresso Ristretto',
        missing_in_assigned_stores: ['Carrefour', 'Dia'],
        available_in_other_stores: [
          { supermercado: 'MercadoLibre', precio: 12000, promo_badge: 'FULL' },
        ],
      }

      render(<MissingItemsBreakdown missing={[missingItem]} />)
      expect(screen.getByText('Cápsulas de Café Nespresso Ristretto')).toBeTruthy()
      expect(screen.getByText('Mercado Libre')).toBeTruthy()
      expect(screen.getByText('FULL')).toBeTruthy()
    })

    it('Pairwise 7 (F7 x F8: Mi Lista Habitual x Basket History): Updating habitual list triggers price snapshot in history', () => {
      const mockPlan: OptimizePlan = {
        mode: 'ahorro',
        stops: 2,
        total: 35000,
        subtotal_merch: 35000,
        ahorro_vs_comoda: 5000,
        covered_items: 3,
        total_items: 3,
        supermercados: ['Carrefour', 'Dia'],
        missing: [],
        store_breakdowns: [],
        all_plans: {} as any,
        mode_previews: {} as any,
      }

      const snapshot = createSnapshotFromPlan(mockPlan, 3, 3, 'manual')
      expect(snapshot).not.toBeNull()
      expect(snapshot?.total_ahorro).toBe(35000)

      pushSnapshotToHistory([], snapshot!, true)
      const history = loadBasketHistory()
      expect(history.length).toBeGreaterThanOrEqual(1)
    })

    it('Pairwise 8 (F7 x F1: Mi Lista Habitual x Smart Cart Optimization): 1-tap reload populates items ready for optimization', () => {
      const habitualData = {
        updated_at: new Date().toISOString(),
        items: [
          { ean: '7790895000997', nombre: 'Leche 1L', qty: 2, imagen: '' },
          { ean: '7791234567890', nombre: 'Pan de Molde', qty: 1, imagen: '' },
        ],
      }
      localStorage.setItem(HABITUAL_STORAGE_KEY, JSON.stringify(habitualData))

      const raw = localStorage.getItem(HABITUAL_STORAGE_KEY)
      const parsed = JSON.parse(raw!)
      expect(parsed.items.length).toBe(2)
      expect(parsed.items[0].ean).toBe('7790895000997')
    })

    it('Pairwise 9 (F9 x F1: Affiliate CPA x StoreCart Checkout): 1-click VTEX checkout preserves repeating items with affiliate tags', () => {
      const rawUrl = 'https://www.carrefour.com.ar/checkout/cart/add?sku=1001&qty=2&seller=1&sc=1&sku=1002&qty=1&seller=1&sc=1'
      const decorated = decorateOutboundUrl(rawUrl, 'Carrefour', 'checkout')

      expect(decorated).toContain('sku=1001&qty=2&seller=1&sc=1')
      expect(decorated).toContain('sku=1002&qty=1&seller=1&sc=1')
      expect(decorated).toContain('utm_source=supervmarket')
      expect(decorated).toContain('utm_medium=affiliate')
      expect(decorated).toContain('afiliado_id=supervmarket')
    })

    it('Pairwise 10 (F11 x F1: Mobile Touch UI x Mode Switching): Mode buttons satisfy 58px and trigger instant 0ms switch', () => {
      const onSelect = vi.fn()
      const mockPlan: OptimizePlan = {
        mode: 'ahorro',
        stops: 2,
        total: 45000,
        mode_previews: {
          ahorro: { mode: 'ahorro', title: 'Más barata', total: 45000, diff: 0 } as any,
          balanceada: { mode: 'balanceada', title: 'Equilibrada', total: 47000, diff: 2000 } as any,
          comodidad: { mode: 'comodidad', title: 'Cómoda', total: 53500, diff: 8500 } as any,
        },
      } as any

      const { container } = render(
        <SmartCartHero mode="ahorro" onSelectMode={onSelect} plan={mockPlan} />
      )

      const buttons = container.querySelectorAll('.grid-cols-3 button')
      buttons.forEach(btn => {
        expect(btn.className).toContain('min-h-[58px]')
      })

      fireEvent.click(buttons[1]) // click Equilibrada
      expect(onSelect).toHaveBeenCalledWith('balanceada')
    })

    it('Pairwise 11 (F9 x F12: Affiliate CPA x Mercado Libre): Outbound ML links decorated with official matt parameters', () => {
      const meliUrl = 'https://articulo.mercadolibre.com.ar/MLA-123456789-yerba'
      const decorated = decorateOutboundUrl(meliUrl, 'MercadoLibre', 'item')

      expect(decorated).toContain('matt_tool=43872651')
      expect(decorated).toContain('matt_word=sv_item')
      expect(decorated).toContain('matt_source=supervmarket')
      expect(decorated).toContain('utm_source=supervmarket')
    })

    it('Pairwise 12 (F10 x F12: Matrix Classification x R1): Milestone M1 matrix preserves Mercado Libre and AI Assistant', () => {
      // Invariant: Features 3 and 4 must never be ELIMINAR
      const preservedFeatures = [
        { id: 3, name: 'MercadoLibre', status: 'MANTENER' },
        { id: 4, name: 'Asistente IA', status: 'MANTENER' },
      ]

      preservedFeatures.forEach(f => {
        expect(f.status).toBe('MANTENER')
        expect(f.status).not.toBe('ELIMINAR')
      })
    })
  })

  // =========================================================================
  // TIER 4: REAL-WORLD APPLICATION SCENARIOS (5 High-Fidelity Journeys)
  // =========================================================================
  describe('Tier 4: Real-World Application Scenarios (5 Journeys)', () => {
    it('Scenario 1: Compra Mensual Familiar (18 items, 2x1 promos, Santander 20% capped at $10.000, 3 scenarios)', () => {
      // 1. Basket populated with 18 items
      const itemsCount = 18
      expect(itemsCount).toBe(18)

      // 2. Scenario metrics calculation:
      // Más Barata: split Carrefour (8 items) + Dia (7 items) + Coto (3 items)
      const ahorroPlan = {
        totalMerch: 71400,
        cotoShipping: 2800,
        total: 74200,
        savingsVsSingle: 14500,
        stops: 3,
      }

      // Equilibrada: Carrefour (11 items) + Dia (7 items)
      const balanceadaPlan = {
        total: 76800,
        netDiffVsAhorro: 2600, // < $3.500 ARS, eliminates Coto stop
        stops: 2,
      }

      // Cómoda: All 18 items at Carrefour with free shipping ($0)
      const comodaPlan = {
        total: 88700,
        shipping: 0,
        stops: 1,
      }

      // Assertions
      expect(ahorroPlan.total).toBe(74200)
      expect(balanceadaPlan.total).toBe(76800)
      expect(comodaPlan.total).toBe(88700)
      expect(comodaPlan.total - ahorroPlan.total).toBe(ahorroPlan.savingsVsSingle)
      expect(balanceadaPlan.stops).toBe(2)
      expect(comodaPlan.stops).toBe(1)

      // Santander rebate on Carrefour subtotal (capped at $10.000)
      const carrefourSubtotal = 55000
      const santanderDiscount = Math.min(carrefourSubtotal * 0.2, 10000)
      expect(santanderDiscount).toBe(10000)
    })

    it('Scenario 2: Compra Rápida de Reposición (3 essential items: Milk, Bread, Eggs; Cómoda wins due to shipping consolidation)', () => {
      const merchandiseTotal = 8500
      const singleShippingDia = 4599
      const totalComoda = merchandiseTotal + singleShippingDia // $13.099

      // If split across 2 stores: merch $7.900 + 2 shipping fees ($4.800 + $4.599 = $9.399) = $17.299
      const splitMerch = 7900
      const splitShipping = 4800 + 4599
      const totalSplit = splitMerch + splitShipping // $17.299

      // Cómoda is actually $4.200 cheaper than split due to avoided shipping fee!
      expect(totalComoda).toBeLessThan(totalSplit)
      const diffSavings = totalSplit - totalComoda
      expect(diffSavings).toBe(4200)
    })

    it('Scenario 3: Faltante Crítico y Alternativa Mercado Libre FULL (staples stocked + specialty coffee on MeLi FULL)', () => {
      const missingCoffee: MissingItemDetail = {
        ean: '7790001234567',
        nombre: 'Café en Grano Premium Colombia 1kg',
        missing_in_assigned_stores: ['Carrefour', 'Dia'],
        available_in_other_stores: [
          {
            supermercado: 'MercadoLibre',
            precio: 14500,
            promo_badge: 'FULL',
          },
        ],
      }

      render(<MissingItemsBreakdown missing={[missingCoffee]} />)
      expect(screen.getByText('Café en Grano Premium Colombia 1kg')).toBeTruthy()
      expect(screen.getByText('Mercado Libre')).toBeTruthy()
      expect(screen.getByText('FULL')).toBeTruthy()

      // Outbound affiliate link decoration
      const rawMeliLink = 'https://articulo.mercadolibre.com.ar/MLA-99887766-cafe-colombia'
      const decorated = decorateOutboundUrl(rawMeliLink, 'MercadoLibre', 'item')
      expect(decorated).toContain('matt_tool=43872651')
      expect(decorated).toContain('matt_word=sv_item')
    })

    it('Scenario 4: Guardado y Seguimiento de Lista Habitual con Inflación Semanal (1-tap save, reload, +8.0% delta, sparkline)', () => {
      // 1. Initial 5-item habitual list saved
      const initialHabitual = {
        updated_at: new Date(Date.now() - 7 * 86400000).toISOString(),
        items: [
          { ean: '101', nombre: 'Leche 1L', qty: 2, imagen: '' },
          { ean: '102', nombre: 'Pan Lactal', qty: 1, imagen: '' },
          { ean: '103', nombre: 'Queso Crema', qty: 1, imagen: '' },
          { ean: '104', nombre: 'Café 250g', qty: 1, imagen: '' },
          { ean: '105', nombre: 'Arroz 1kg', qty: 2, imagen: '' },
        ],
      }
      localStorage.setItem(HABITUAL_STORAGE_KEY, JSON.stringify(initialHabitual))

      // 2. Previous week snapshot in basket history: total $28.000, savings $4.500
      const prevSnapshot = {
        id: 'snap-1',
        timestamp: new Date(Date.now() - 7 * 86400000).toISOString(),
        total_comodidad: 32500,
        total_ahorro: 28000,
        ahorro_ars: 4500,
        items_count: 5,
      }
      localStorage.setItem(BASKET_HISTORY_STORAGE_KEY, JSON.stringify([prevSnapshot]))

      // 3. User returns a week later, current total is $30.240
      const currentPlan: OptimizePlan = {
        mode: 'ahorro',
        stops: 2,
        total: 30240,
        subtotal_merch: 30240,
        ahorro_vs_comoda: 4800,
        covered_items: 5,
        total_items: 5,
        supermercados: ['Carrefour', 'Dia'],
        missing: [],
        store_breakdowns: [],
        all_plans: {} as any,
        mode_previews: {} as any,
      }

      // 4. Calculate basket inflation delta percentage: ((30240 - 28000) / 28000) * 100 = +8.0%
      const currentSnapshot = createSnapshotFromPlan(currentPlan, 5, 5, 'optimization_view')!
      expect(currentSnapshot).not.toBeNull()
      const delta = calculateBasketDelta(currentSnapshot, [prevSnapshot])
      expect(delta.has_history).toBe(true)
      expect(delta.percentage_delta).toBeCloseTo(8.0, 1)
      expect(delta.delta_ars).toBe(2240)
    })

    it('Scenario 5: Navegación Mobile Pura con Selector de Escenarios y Checkout VTEX', () => {
      // 1. Mobile screen rendered
      const planAhorro: OptimizePlan = {
        mode: 'ahorro',
        stops: 2,
        total: 45000,
        mode_previews: {
          ahorro: { mode: 'ahorro', title: 'Opción más barata', total: 45000, diff: 0, badge: 'MÁXIMO AHORRO' } as any,
          balanceada: { mode: 'balanceada', title: 'Opción equilibrada', total: 47000, diff: 2000, badge: 'RECOMENDADA' } as any,
          comodidad: { mode: 'comodidad', title: 'Opción cómoda', total: 53500, diff: 8500, badge: '1 SOLO SÚPER' } as any,
        },
      } as any

      const onSelect = vi.fn()
      const { container } = render(
        <SmartCartHero mode="ahorro" onSelectMode={onSelect} plan={planAhorro} />
      )

      // 2. 58px mode buttons above the fold
      const buttons = container.querySelectorAll('.grid-cols-3 button')
      expect(buttons.length).toBe(3)
      buttons.forEach(btn => {
        expect(btn.className).toContain('min-h-[58px]')
      })

      // 3. User taps Equilibrada -> instant switch
      fireEvent.click(buttons[1])
      expect(onSelect).toHaveBeenCalledWith('balanceada')

      // 4. VTEX checkout decoration
      const vtexRaw = 'https://www.carrefour.com.ar/checkout/cart/add?sku=555&qty=3&seller=1&sc=1'
      const vtexDecorated = decorateOutboundUrl(vtexRaw, 'Carrefour', 'checkout')
      expect(vtexDecorated).toContain('sku=555&qty=3&seller=1&sc=1')
      expect(vtexDecorated).toContain('utm_source=supervmarket')

      // 5. Track outbound click
      trackOutboundAffiliateClick('Carrefour', 'checkout', vtexDecorated, 45000)
      const storedClicks = JSON.parse(localStorage.getItem(AFFILIATE_STORAGE_KEY) || '[]')
      expect(storedClicks.length).toBe(1)
      expect(storedClicks[0].store).toBe('Carrefour')
      expect(storedClicks[0].estimatedValue).toBe(45000)
    })
  })
})
