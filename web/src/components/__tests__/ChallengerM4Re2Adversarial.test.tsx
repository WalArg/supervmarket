import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within, act } from '@testing-library/react'
import OffersScreen from '../OffersScreen'
import GondolaCard from '../GondolaCard'
import ProductCard from '../ProductCard'
import OffersSheet from '../OffersSheet'
import { DISCOUNT_TIERS, MARKETPLACE_DISCOUNT_TIERS, type DiscountTier } from '../../data/gondolasData'
import * as api from '../../api'
import { LocationProvider } from '../../location/LocationContext'
import { BenefitsProvider } from '../../benefits/BenefitsContext'
import { CartProvider } from '../../cart/CartContext'
import { SavedProvider } from '../../saved/SavedContext'
import type { ProductGroup, SupermarketOffer } from '../../types'

vi.mock('../../api', async () => {
  const actual = await vi.importActual('../../api')
  return {
    ...actual,
    getLiveOffers: vi.fn(),
    searchProducts: vi.fn(),
  }
})

describe('CHALLENGER M4 RE 2: Adversarial Stress & Verification Suite', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  const renderWithProviders = (ui: React.ReactElement) => {
    return render(
      <LocationProvider>
        <BenefitsProvider>
          <CartProvider>
            <SavedProvider>{ui}</SavedProvider>
          </CartProvider>
        </BenefitsProvider>
      </LocationProvider>,
    )
  }

  // =========================================================================
  // 1. OffersScreen Tabs & Category Stacking & Sponsored Card Invariant
  // =========================================================================
  describe('1. OffersScreen Tabs & Sponsored Card Invariants', () => {
    it('1.1. Default mode "all" stacks both supermarket & marketplace tiers and maintains exactly 4 sponsored cards', async () => {
      vi.mocked(api.getLiveOffers).mockResolvedValue({
        tiers: DISCOUNT_TIERS,
        marketplace_tiers: MARKETPLACE_DISCOUNT_TIERS,
        is_live: true,
        updated_at: '2026-11-03T10:00:00Z',
      })

      renderWithProviders(<OffersScreen />)

      await waitFor(() => {
        expect(screen.getByText(/Mayores descuentos del día/i)).toBeTruthy()
      })

      // In 'all' mode: supermarket tiers are rendered
      expect(screen.getByRole('heading', { name: /2da Unidad al 70% y 80% OFF/i })).toBeTruthy()
      expect(screen.getByRole('heading', { name: /Liquidaciones Directas/i })).toBeTruthy()
      expect(screen.getByRole('heading', { name: /50% OFF y 2x1/i })).toBeTruthy()
      expect(screen.getByRole('heading', { name: /Canasta Básica y Esenciales/i })).toBeTruthy()

      // In 'all' mode: marketplace section header and tiers are stacked below
      expect(screen.getByText(/Marketplaces, Electro & Hogar/i)).toBeTruthy()
      expect(screen.getByText(/Electrodomésticos y Tecnología — Hasta 40% OFF y Cuotas/i)).toBeTruthy()
      expect(screen.getByText(/Hogar, Herramientas y Climatización — Gran Ahorro/i)).toBeTruthy()
      expect(screen.getByText(/Ofertas Destacadas de Marketplaces — Precios Bomba/i)).toBeTruthy()

      // Sponsored card invariant: exactly 4 PATROCINADO cards present
      const sponsoredBadges = screen.getAllByText('PATROCINADO')
      expect(sponsoredBadges).toHaveLength(4)
    })

    it('1.2. Switching to "supermarket" displays only grocery tiers and maintains 4 sponsored cards, hiding tech banner', async () => {
      vi.mocked(api.getLiveOffers).mockResolvedValue({
        tiers: DISCOUNT_TIERS,
        marketplace_tiers: MARKETPLACE_DISCOUNT_TIERS,
        is_live: true,
        updated_at: '2026-11-03T10:00:00Z',
      })

      renderWithProviders(<OffersScreen />)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /🛒 Supermercados/i })).toBeTruthy()
      })

      // Click "Supermercados"
      const superTab = screen.getByRole('button', { name: /🛒 Supermercados/i })
      fireEvent.click(superTab)

      // Supermarket tiers present
      expect(screen.getByText(/2da Unidad al 70% y 80% OFF/i)).toBeTruthy()
      expect(screen.getByText(/Canasta Básica y Esenciales/i)).toBeTruthy()

      // Marketplace sections and banner must be cleanly removed from DOM
      expect(screen.queryByText(/Marketplaces, Electro & Hogar/i)).toBeNull()
      expect(screen.queryByText(/Electrodomésticos y Tecnología — Hasta 40% OFF y Cuotas/i)).toBeNull()
      expect(screen.queryByText(/Hogar, Herramientas y Climatización — Gran Ahorro/i)).toBeNull()

      // Sponsored cards remain 4 in supermarket mode
      expect(screen.getAllByText('PATROCINADO')).toHaveLength(4)
    })

    it('1.3. Switching to "marketplace" displays ONLY marketplace tiers with 0 crashes, 0 supermarket tiers, and 0 sponsored cards', async () => {
      vi.mocked(api.getLiveOffers).mockResolvedValue({
        tiers: DISCOUNT_TIERS,
        marketplace_tiers: MARKETPLACE_DISCOUNT_TIERS,
        is_live: true,
        updated_at: '2026-11-03T10:00:00Z',
      })

      renderWithProviders(<OffersScreen />)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /⚡ Marketplaces & Tech/i })).toBeTruthy()
      })

      // Click "Marketplaces & Tech"
      const mpTab = screen.getByRole('button', { name: /⚡ Marketplaces & Tech/i })
      fireEvent.click(mpTab)

      // Marketplace tiers present
      expect(screen.getByText(/Electrodomésticos y Tecnología — Hasta 40% OFF y Cuotas/i)).toBeTruthy()
      expect(screen.getByText(/Hogar, Herramientas y Climatización — Gran Ahorro/i)).toBeTruthy()
      expect(screen.getByText(/Ofertas Destacadas de Marketplaces — Precios Bomba/i)).toBeTruthy()

      // Supermarket tiers suppressed
      expect(screen.queryByText(/2da Unidad al 70% y 80% OFF/i)).toBeNull()
      expect(screen.queryByText(/Canasta Básica y Esenciales/i)).toBeNull()

      // Marketplace tiers have no meliSponsored -> 0 PATROCINADO cards without crash
      expect(screen.queryByText('PATROCINADO')).toBeNull()
    })

    it('1.4. Rapid round-trip tab switching (all -> supermarket -> marketplace -> all) preserves state and renders smoothly', async () => {
      vi.mocked(api.getLiveOffers).mockResolvedValue({
        tiers: DISCOUNT_TIERS,
        marketplace_tiers: MARKETPLACE_DISCOUNT_TIERS,
        is_live: true,
        updated_at: '2026-11-03T10:00:00Z',
      })

      renderWithProviders(<OffersScreen />)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /🌟 Todas las Ofertas/i })).toBeTruthy()
      })

      const allTab = screen.getByRole('button', { name: /🌟 Todas las Ofertas/i })
      const superTab = screen.getByRole('button', { name: /🛒 Supermercados/i })
      const mpTab = screen.getByRole('button', { name: /⚡ Marketplaces & Tech/i })

      // Rapid sequence
      for (let i = 0; i < 5; i++) {
        fireEvent.click(superTab)
        expect(screen.queryByText(/Marketplaces, Electro & Hogar/i)).toBeNull()
        fireEvent.click(mpTab)
        expect(screen.queryByText(/2da Unidad al 70% y 80% OFF/i)).toBeNull()
        fireEvent.click(allTab)
        expect(screen.getByText(/Marketplaces, Electro & Hogar/i)).toBeTruthy()
      }

      // Check final state integrity
      expect(screen.getAllByText('PATROCINADO')).toHaveLength(4)
      expect(screen.getByText(/Smart TV Samsung 55'' Qled 4K Q6F/i)).toBeTruthy()
    })
  })

  // =========================================================================
  // 2. Missing meliSponsored & Malformed Tier Data Resilience (0 Crashes)
  // =========================================================================
  describe('2. Missing meliSponsored & Malformed Data Resilience', () => {
    it('2.1. Passes tiers with meliSponsored: undefined and verifies 0 crashes and clean rendering', async () => {
      const strippedTiers: DiscountTier[] = [
        {
          id: 'tier-test-no-sponsored',
          title: 'Tier Sin Patrocinado',
          subtitle: 'Probando tolerancia a sponsored ausente',
          badge: 'Test 0 Sponsored',
          percentLabel: '40% OFF',
          icon: 'tag',
          meliSponsored: undefined, // Explicit undefined
          products: [
            {
              id: 'p1',
              ean: '7790001',
              nombre: 'Producto Ordinario Sin Patrocinado',
              marca: 'Generica',
              offers: [
                {
                  supermercado: 'Carrefour',
                  precio: 2500,
                  precio_lista: 3500,
                  stock: 10,
                  link: 'https://carrefour.com.ar/p1',
                },
              ],
            },
          ],
        },
      ]

      vi.mocked(api.getLiveOffers).mockResolvedValue({
        tiers: strippedTiers,
        marketplace_tiers: [],
        is_live: true,
        updated_at: '2026-11-03T10:00:00Z',
      })

      renderWithProviders(<OffersScreen />)

      await waitFor(() => {
        expect(screen.getByText('Tier Sin Patrocinado')).toBeTruthy()
      })

      // Zero crashes, 0 PATROCINADO cards, product rendered normally
      expect(screen.queryByText('PATROCINADO')).toBeNull()
      expect(screen.getByText('Producto Ordinario Sin Patrocinado')).toBeTruthy()
    })

    it('2.2. Passes tiers with partially null meliSponsored objects without throwing TypeError', async () => {
      const malformedTiers: any[] = [
        {
          id: 'tier-malformed-1',
          title: 'Tier Con Sponsored Parcialmente Nulo',
          subtitle: 'product es null, offer es valido',
          badge: 'Edge 1',
          percentLabel: '30%',
          icon: 'zap',
          meliSponsored: {
            product: null,
            offer: { supermercado: 'MercadoLibre', precio: 1000 },
          },
          products: [
            {
              ean: '7799991',
              nombre: 'Item de prueba 1',
              marca: 'Marca',
              offers: [{ supermercado: 'Dia', precio: 1500, link: 'https://dia.com/1' }],
            },
          ],
        },
        {
          id: 'tier-malformed-2',
          title: 'Tier Con Offer Nulo',
          subtitle: 'product valido pero offer null',
          badge: 'Edge 2',
          percentLabel: '50%',
          icon: 'flame',
          meliSponsored: {
            product: { ean: '999', nombre: 'Ghost Product' },
            offer: null,
          },
          products: [
            {
              ean: '7799992',
              nombre: 'Item de prueba 2',
              marca: 'Marca',
              offers: [{ supermercado: 'Coto', precio: 2200, link: 'https://coto.com/2' }],
            },
          ],
        },
      ]

      vi.mocked(api.getLiveOffers).mockResolvedValue({
        tiers: malformedTiers,
        marketplace_tiers: [],
        is_live: true,
      })

      renderWithProviders(<OffersScreen />)

      await waitFor(() => {
        expect(screen.getByText('Tier Con Sponsored Parcialmente Nulo')).toBeTruthy()
      })

      // Neither malformed sponsored card should render, but standard items must survive
      expect(screen.queryByText('PATROCINADO')).toBeNull()
      expect(screen.getByText('Item de prueba 1')).toBeTruthy()
      expect(screen.getByText('Item de prueba 2')).toBeTruthy()
    })

    it('2.3. Handles tiers with empty or null products array without crashing', async () => {
      const emptyProductTiers: any[] = [
        {
          id: 'tier-empty-products',
          title: 'Tier Con Lista Vacia',
          subtitle: 'Subtitulo',
          badge: 'Vacio',
          percentLabel: '0%',
          icon: 'tag',
          products: [],
        },
        {
          id: 'tier-null-products',
          title: 'Tier Con Products Null',
          subtitle: 'Subtitulo 2',
          badge: 'Null',
          percentLabel: '0%',
          icon: 'tag',
          products: null,
        },
      ]

      vi.mocked(api.getLiveOffers).mockResolvedValue({
        tiers: emptyProductTiers,
        marketplace_tiers: [],
        is_live: true,
      })

      renderWithProviders(<OffersScreen />)

      await waitFor(() => {
        expect(screen.getByText('Tier Con Lista Vacia')).toBeTruthy()
        expect(screen.getByText('Tier Con Products Null')).toBeTruthy()
      })

      // Verified 0 unhandled exceptions
    })
  })

  // =========================================================================
  // 3. Financing Math: Cuotas Display vs Clean Suppression
  // =========================================================================
  describe('3. Financing Math & Cuotas Display / Suppression', () => {
    it('3.1. When cuotas > 1 and sin_interes=true: displays "💳 N cuotas sin interés" and cuota_monto in GondolaCard', () => {
      const group: ProductGroup = {
        id: 'tech-tv',
        ean: '8806095000000',
        nombre: 'Smart TV 55" OLED 4K',
        marca: 'LG',
        modelo: 'OLED55C3',
        offers: [
          {
            supermercado: 'Provincia Compras',
            precio: 1200000,
            precio_lista: 1500000,
            stock: 5,
            link: 'https://provinciacompras.com.ar/lg-55',
            cuotas: 12,
            sin_interes: true,
            cuota_monto: 100000,
          },
        ],
      }

      renderWithProviders(<GondolaCard group={group} />)

      expect(screen.getByText(/💳 12 cuotas sin interés/i)).toBeTruthy()
      expect(screen.getByText(/12x\s*\$\s*100\.000/i)).toBeTruthy()
    })

    it('3.2. When cuotas > 1 and sin_interes=false (or missing): displays "💳 N cuotas fijas" in GondolaCard', () => {
      const group: ProductGroup = {
        id: 'tech-fijas',
        ean: '8806095000001',
        nombre: 'Heladera No Frost 400L',
        marca: 'Whirlpool',
        modelo: 'WRM45',
        offers: [
          {
            supermercado: 'Cetrogar',
            precio: 950000,
            precio_lista: 950000,
            stock: 8,
            link: 'https://cetrogar.com.ar/heladera',
            cuotas: 6,
            sin_interes: false, // Fijas
            cuota_monto: 195000,
          },
        ],
      }

      renderWithProviders(<GondolaCard group={group} />)

      expect(screen.getByText(/💳 6 cuotas fijas/i)).toBeTruthy()
      expect(screen.getByText(/6x\s*\$\s*195\.000/i)).toBeTruthy()
    })

    it('3.3. When cuotas === 1: CLEANLY SUPPRESSES installment badge (no "1 cuotas")', () => {
      const groupSingleInstallment: ProductGroup = {
        id: 'tech-cuota-1',
        ean: '8806095000002',
        nombre: 'Cafetera Expreso',
        marca: 'Oster',
        offers: [
          {
            supermercado: 'Fravega',
            precio: 150000,
            precio_lista: 180000,
            stock: 12,
            link: 'https://fravega.com.ar/cafetera',
            cuotas: 1, // Single payment -> should NOT show installment badge
            sin_interes: true,
          },
        ],
      }

      renderWithProviders(<GondolaCard group={groupSingleInstallment} />)

      expect(screen.queryByText(/cuota/i)).toBeNull()
      expect(screen.queryByText(/💳/)).toBeNull()
    })

    it('3.4. When cuotas <= 0, negative, null, or undefined: CLEANLY SUPPRESSES installment badge', () => {
      const edgeCases = [0, -1, -6, null, undefined]

      for (const edgeCuota of edgeCases) {
        const group: ProductGroup = {
          ean: `77900000000${String(edgeCuota)}`,
          nombre: `Item Test ${edgeCuota}`,
          marca: 'Marca',
          offers: [
            {
              supermercado: 'Carrefour',
              precio: 10000,
              stock: 10,
              link: 'https://carrefour.com.ar/p',
              cuotas: edgeCuota as any,
              sin_interes: true,
            },
          ],
        }

        const { unmount } = renderWithProviders(<GondolaCard group={group} />)
        expect(screen.queryByText(/cuota/i)).toBeNull()
        expect(screen.queryByText(/💳/)).toBeNull()
        unmount()
      }
    })

    it('3.5. ProductCard also respects cuotas financing formatting and clean suppression', () => {
      const groupWithInterest: ProductGroup = {
        ean: '8806095000003',
        nombre: 'Lavarropas Automático 8kg',
        marca: 'Samsung',
        modelo: 'WW80A40',
        offers: [
          {
            supermercado: 'Naldo',
            precio: 720000,
            stock: 5,
            link: 'https://naldo.com.ar/lavarropas',
            cuotas: 18,
            sin_interes: false,
          },
        ],
      }

      const { unmount } = renderWithProviders(<ProductCard group={groupWithInterest} />)
      expect(screen.getByText(/18 cuotas fijas/i)).toBeTruthy()
      unmount()

      const groupNullCuotas: ProductGroup = {
        ean: '8806095000004',
        nombre: 'Aceite de Girasol 1.5L',
        marca: 'Natura',
        offers: [
          {
            supermercado: 'Dia',
            precio: 2500,
            stock: 50,
            link: 'https://dia.com.ar/aceite',
            cuotas: undefined,
          },
        ],
      }

      renderWithProviders(<ProductCard group={groupNullCuotas} />)
      expect(screen.queryByText(/cuota/i)).toBeNull()
    })
  })

  // =========================================================================
  // 4. OffersSheet Outbound Link Propagation (buildOutboundOfferUrl)
  // =========================================================================
  describe('4. OffersSheet Outbound Links & Seller Propagation', () => {
    it('4.1. Appends ?seller={seller_id} when link has no parameters and seller_id is 3rd-party', () => {
      const group: ProductGroup = {
        id: 'p-link-1',
        ean: '8800000001',
        nombre: 'Notebook Gamer Asus ROG',
        marca: 'Asus',
        offers: [
          {
            supermercado: 'Provincia Compras',
            precio: 1800000,
            stock: 4,
            link: 'https://provinciacompras.com.ar/notebook-asus',
            seller_id: 'asus_store_oficial',
            seller_name: 'Asus Store',
          },
        ],
      }

      const rows = [{ o: group.offers[0], eff: 1800000, minQty: 1 } as any]

      renderWithProviders(<OffersSheet open={true} onClose={vi.fn()} group={group} rows={rows} />)

      const link = screen.getByRole('link', { name: /ver web/i })
      expect(link.getAttribute('href')).toBe(
        'https://provinciacompras.com.ar/notebook-asus?seller=asus_store_oficial',
      )
    })

    it('4.2. Appends &seller={seller_id} when link already contains other query parameters', () => {
      const group: ProductGroup = {
        id: 'p-link-2',
        ean: '8800000002',
        nombre: 'Monitor Gamer 27 165Hz',
        marca: 'Samsung',
        offers: [
          {
            supermercado: 'On City',
            precio: 350000,
            stock: 7,
            link: 'https://oncity.com/monitor-27/p?sc=2&color=negro',
            seller_id: 'megastore_digital',
            seller_name: 'MegaStore',
          },
        ],
      }

      const rows = [{ o: group.offers[0], eff: 350000, minQty: 1 } as any]

      renderWithProviders(<OffersSheet open={true} onClose={vi.fn()} group={group} rows={rows} />)

      const link = screen.getByRole('link', { name: /ver web/i })
      expect(link.getAttribute('href')).toBe(
        'https://oncity.com/monitor-27/p?sc=2&color=negro&seller=megastore_digital',
      )
    })

    it('4.3. Does NOT duplicate seller parameter if URL already includes seller=', () => {
      const group: ProductGroup = {
        id: 'p-link-3',
        ean: '8800000003',
        nombre: 'Consola PlayStation 5 Slim',
        marca: 'Sony',
        offers: [
          {
            supermercado: 'Fravega',
            precio: 1200000,
            stock: 3,
            link: 'https://fravega.com.ar/p/ps5?seller=sonystorear',
            seller_id: 'sonystorear',
            seller_name: 'Sony Store',
          },
        ],
      }

      const rows = [{ o: group.offers[0], eff: 1200000, minQty: 1 } as any]

      renderWithProviders(<OffersSheet open={true} onClose={vi.fn()} group={group} rows={rows} />)

      const link = screen.getByRole('link', { name: /ver web/i })
      const href = link.getAttribute('href') || ''
      expect(href).toBe('https://fravega.com.ar/p/ps5?seller=sonystorear')
      // Count occurrences of 'seller='
      const count = (href.match(/seller=/g) || []).length
      expect(count).toBe(1)
    })

    it('4.4. Does NOT append seller when seller_id is "1" (direct retail store)', () => {
      const group: ProductGroup = {
        id: 'p-link-4',
        ean: '8800000004',
        nombre: 'Lavarropas Drean Next 8kg',
        marca: 'Drean',
        offers: [
          {
            supermercado: 'Naldo',
            precio: 650000,
            stock: 10,
            link: 'https://naldo.com.ar/lavarropas-drean/p',
            seller_id: '1', // Direct store
            seller_name: 'Naldo',
          },
        ],
      }

      const rows = [{ o: group.offers[0], eff: 650000, minQty: 1 } as any]

      renderWithProviders(<OffersSheet open={true} onClose={vi.fn()} group={group} rows={rows} />)

      const link = screen.getByRole('link', { name: /ver web/i })
      expect(link.getAttribute('href')).toBe('https://naldo.com.ar/lavarropas-drean/p')
      expect(link.getAttribute('href')).not.toContain('seller=')
    })

    it('4.5. Correctly URI encodes special characters in seller_id without breaking URL syntax', () => {
      const group: ProductGroup = {
        id: 'p-link-5',
        ean: '8800000005',
        nombre: 'Taladro Atornillador',
        marca: 'Bosch',
        offers: [
          {
            supermercado: 'Provincia Compras',
            precio: 120000,
            stock: 15,
            link: 'https://provinciacompras.com.ar/taladro',
            seller_id: 'ferreteria & herramientas + cia',
            seller_name: 'Ferreteria Central',
          },
        ],
      }

      const rows = [{ o: group.offers[0], eff: 120000, minQty: 1 } as any]

      renderWithProviders(<OffersSheet open={true} onClose={vi.fn()} group={group} rows={rows} />)

      const link = screen.getByRole('link', { name: /ver web/i })
      expect(link.getAttribute('href')).toBe(
        'https://provinciacompras.com.ar/taladro?seller=ferreteria%20%26%20herramientas%20%2B%20cia',
      )
    })
  })

  // =========================================================================
  // 5. Fallback Resilience to MARKETPLACE_DISCOUNT_TIERS when API is Unavailable
  // =========================================================================
  describe('5. Fallback Resilience & Error Recovery', () => {
    it('5.1. Falls back seamlessly to MARKETPLACE_DISCOUNT_TIERS when getLiveOffers throws network error', async () => {
      vi.mocked(api.getLiveOffers).mockRejectedValue(new Error('Network Error 503 Service Unavailable'))

      renderWithProviders(<OffersScreen />)

      // Verified: despite network rejection, fallback tiers render without crash
      await waitFor(() => {
        expect(screen.getByText(/2da Unidad al 70% y 80% OFF/i)).toBeTruthy()
      })

      // Marketplace fallback tiers must be present
      expect(screen.getByText(/Electrodomésticos y Tecnología — Hasta 40% OFF y Cuotas/i)).toBeTruthy()
      expect(screen.getByText(/Hogar, Herramientas y Climatización — Gran Ahorro/i)).toBeTruthy()
      expect(screen.getByText(/Ofertas Destacadas de Marketplaces — Precios Bomba/i)).toBeTruthy()

      // Invariant: 4 sponsored cards preserved on fallback
      expect(screen.getAllByText('PATROCINADO')).toHaveLength(4)
    })

    it('5.2. Falls back to MARKETPLACE_DISCOUNT_TIERS when live API returns empty marketplace_tiers', async () => {
      vi.mocked(api.getLiveOffers).mockResolvedValue({
        tiers: DISCOUNT_TIERS,
        marketplace_tiers: [], // Empty from backend
        is_live: true,
      })

      renderWithProviders(<OffersScreen />)

      await waitFor(() => {
        expect(screen.getByText(/2da Unidad al 70% y 80% OFF/i)).toBeTruthy()
      })

      // When live marketplace_tiers is empty, the initial state MARKETPLACE_DISCOUNT_TIERS remains active
      expect(screen.getByText(/Marketplaces, Electro & Hogar/i)).toBeTruthy()
      expect(screen.getByText(/Electrodomésticos y Tecnología — Hasta 40% OFF y Cuotas/i)).toBeTruthy()
    })

    it('5.3. Refresh button handles transient error gracefully and resets spinner (disabled=false)', async () => {
      vi.mocked(api.getLiveOffers)
        .mockResolvedValueOnce({
          tiers: DISCOUNT_TIERS,
          marketplace_tiers: MARKETPLACE_DISCOUNT_TIERS,
          is_live: true,
        })
        .mockRejectedValueOnce(new Error('Timeout 504 Gateway Timeout'))

      renderWithProviders(<OffersScreen />)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /actualizar ofertas en vivo/i })).toBeTruthy()
      })

      const refreshBtn = screen.getByRole('button', { name: /actualizar ofertas en vivo/i })
      expect(refreshBtn.hasAttribute('disabled')).toBe(false)

      // Trigger manual refresh
      fireEvent.click(refreshBtn)

      // Should recover and re-enable button after error caught
      await waitFor(() => {
        expect(refreshBtn.hasAttribute('disabled')).toBe(false)
      })

      // UI remains functional and responsive
      expect(screen.getByText(/Marketplaces, Electro & Hogar/i)).toBeTruthy()
    })
  })

  // =========================================================================
  // 6. Fast Discount Filter Chips Across Supermarket & Marketplace Tiers
  // =========================================================================
  describe('6. Fast Discount Filter Chips Functionality', () => {
    it('6.1. Clicking a marketplace discount chip isolates only that marketplace tier', async () => {
      vi.mocked(api.getLiveOffers).mockResolvedValue({
        tiers: DISCOUNT_TIERS,
        marketplace_tiers: MARKETPLACE_DISCOUNT_TIERS,
        is_live: true,
      })

      renderWithProviders(<OffersScreen />)

      await waitFor(() => {
        expect(screen.getByText(/Hasta 40% OFF \+ Cuotas/i)).toBeTruthy()
      })

      // Click marketplace filter chip
      const electroChip = screen.getByRole('button', { name: /Hasta 40% OFF \+ Cuotas/i })
      fireEvent.click(electroChip)

      // Only the selected tier should be rendered
      expect(screen.getByText(/Electrodomésticos y Tecnología — Hasta 40% OFF y Cuotas/i)).toBeTruthy()
      expect(screen.queryByText(/2da Unidad al 70% y 80% OFF/i)).toBeNull()
      expect(screen.queryByText(/Hogar, Herramientas y Climatización/i)).toBeNull()

      // Click "Todos los Descuentos" to restore
      const allFilterChip = screen.getByRole('button', { name: /Todos los Descuentos/i })
      fireEvent.click(allFilterChip)

      expect(screen.getByText(/2da Unidad al 70% y 80% OFF/i)).toBeTruthy()
      expect(screen.getByText(/Electrodomésticos y Tecnología — Hasta 40% OFF y Cuotas/i)).toBeTruthy()
    })
  })
})
