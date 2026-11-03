import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { STORES, getStoreMeta, normalizeStoreKey, storeLabel, storeColor, storeVertical, isMarketplaceStore, storeSupportsCart } from '../../lib/stores'
import SearchScreen from '../SearchScreen'
import OffersScreen from '../OffersScreen'
import ProductCard from '../ProductCard'
import GondolaCard from '../GondolaCard'
import OffersSheet from '../OffersSheet'
import { LocationProvider } from '../../location/LocationContext'
import { BenefitsProvider } from '../../benefits/BenefitsContext'
import { CartProvider } from '../../cart/CartContext'
import { SavedProvider } from '../../saved/SavedContext'
import * as api from '../../api'
import type { ProductGroup } from '../../types'

vi.mock('../../api', async () => {
  const actual = await vi.importActual('../../api')
  return {
    ...actual,
    searchProducts: vi.fn(),
    getLiveOffers: vi.fn(),
  }
})

describe('Milestone 4: Differentiated Search, Complete Store Registry & Marketplace Offers Carousels', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('1. Store Registry & Vertical Mapping (All 40 Stores)', () => {
    it('1.1 registers all 40 canonical retail chains and marketplaces', () => {
      const keys = Object.keys(STORES)
      expect(keys.length).toBeGreaterThanOrEqual(40)

      // 13 Supermarkets
      expect(storeVertical('Jumbo')).toBe('supermarket')
      expect(storeVertical('Disco')).toBe('supermarket')
      expect(storeVertical('Vea')).toBe('supermarket')
      expect(storeVertical('Carrefour')).toBe('supermarket')
      expect(storeVertical('Dia')).toBe('supermarket')
      expect(storeVertical('Masonline')).toBe('supermarket')
      expect(storeVertical('Coto')).toBe('supermarket')
      expect(storeVertical('Josimar')).toBe('supermarket')
      expect(storeVertical('Toledo')).toBe('supermarket')
      expect(storeVertical('Cordiez')).toBe('supermarket')
      expect(storeVertical('TheFoodMarket')).toBe('supermarket')
      expect(storeVertical('LaBarata')).toBe('supermarket')
      expect(storeVertical('ArcorEnCasa')).toBe('supermarket')

      // 3 Marketplaces
      expect(storeVertical('Provincia Compras')).toBe('marketplace')
      expect(storeVertical('On City')).toBe('marketplace')
      expect(storeVertical('MercadoLibre')).toBe('marketplace')

      // 12 Electro & Tech
      expect(storeVertical('Fravega')).toBe('electro')
      expect(storeVertical('Cetrogar')).toBe('electro')
      expect(storeVertical('Naldo')).toBe('electro')
      expect(storeVertical('Pardo')).toBe('electro')
      expect(storeVertical('Coppel')).toBe('electro')
      expect(storeVertical('Musimundo')).toBe('electro')
      expect(storeVertical('Samsung')).toBe('electro')
      expect(storeVertical('Philips')).toBe('electro')
      expect(storeVertical('Whirlpool')).toBe('electro')
      expect(storeVertical('Moulinex')).toBe('electro')
      expect(storeVertical('Sony')).toBe('electro')
      expect(storeVertical('Oster')).toBe('electro')

      // Specialty & Pharmacy
      expect(storeVertical('Easy')).toBe('specialty')
      expect(storeVertical('Pigmento')).toBe('pharmacy')
      expect(storeVertical('Farmacity')).toBe('pharmacy')
      expect(storeVertical('Simplicity')).toBe('pharmacy')
      expect(storeVertical('Puppis')).toBe('specialty')
      expect(storeVertical('StyleStore')).toBe('specialty')
    })

    it('1.2 correctly handles store aliases and case/whitespace normalization', () => {
      expect(storeLabel('Frávega')).toBe('Frávega')
      expect(storeVertical('Frávega')).toBe('electro')
      expect(storeVertical('fravega')).toBe('electro')

      expect(storeLabel('ProvinciaCompras')).toBe('Provincia Compras')
      expect(storeVertical('ProvinciaCompras')).toBe('marketplace')

      expect(storeLabel('OnCity')).toBe('On City')
      expect(storeVertical('oncity')).toBe('marketplace')

      expect(storeLabel('Toledo Digital')).toBe('Toledo Digital')
      expect(storeVertical('Toledo Digital')).toBe('supermarket')

      expect(storeLabel('Perfumerías Pigmento')).toBe('Perfumerías Pigmento')
      expect(storeVertical('Perfumerías Pigmento')).toBe('pharmacy')

      // Cart support check
      expect(storeSupportsCart('Carrefour')).toBe(true)
      expect(storeSupportsCart('Coto')).toBe(false)
      expect(storeSupportsCart('Fravega')).toBe(true)
      expect(storeSupportsCart('MercadoLibre')).toBe(false)

      // Marketplace flag check
      expect(isMarketplaceStore('Provincia Compras')).toBe(true)
      expect(isMarketplaceStore('On City')).toBe(true)
      expect(isMarketplaceStore('Fravega')).toBe(true)
      expect(isMarketplaceStore('Coto')).toBe(false)
    })

    it('1.3 normalizes unicode diacritics and aliases for accented store names', () => {
      // normalizeStoreKey behavior
      expect(typeof normalizeStoreKey).toBe('function')
      expect(normalizeStoreKey('  Frávega / Tefal  ')).toBe('fravegatefal')
      expect(normalizeStoreKey('Día')).toBe('dia')
      expect(normalizeStoreKey('Más Online')).toBe('masonline')
      expect(normalizeStoreKey('Perfumerías Pigmento')).toBe('perfumeriaspigmento')

      // Día accent normalization & metadata lookup
      const diaMeta = getStoreMeta('Día')
      expect(diaMeta).toBeDefined()
      expect(diaMeta?.id).toBe('dia')
      expect(diaMeta?.label).toBe('Día')
      expect(storeColor('Día')).toBe('#e11d48')
      expect(storeSupportsCart('Día')).toBe(true)
      expect(storeVertical('Día')).toBe('supermarket')

      // Más Online accent normalization & metadata lookup
      const masMeta = getStoreMeta('Más Online')
      expect(masMeta).toBeDefined()
      expect(masMeta?.id).toBe('masonline')
      expect(masMeta?.label).toBe('Más Online')
      expect(storeColor('Más Online')).toBe('#0d9488')
      expect(isMarketplaceStore('Más Online')).toBe(true)
      expect(storeSupportsCart('Más Online')).toBe(true)

      // Easy and Whirlpool aligned attributes
      const easyMeta = getStoreMeta('Easy')
      expect(easyMeta?.color).toBe('#d6001c')
      expect(easyMeta?.isMarketplace).toBe(false)
      expect(isMarketplaceStore('Easy')).toBe(false)

      const whirlpoolMeta = getStoreMeta('Whirlpool')
      expect(whirlpoolMeta?.color).toBe('#f0b400')
      expect(storeColor('Whirlpool')).toBe('#f0b400')
    })
  })

  describe('2. Differentiated Search UI (`SearchScreen.tsx`)', () => {
    it('2.1 renders vertical chips and initiates filtered search', async () => {
      const mockTvGroup: ProductGroup = {
        id: '8806095483245',
        ean: '8806095483245',
        nombre: 'Smart TV Samsung 50 pulgadas 4K',
        marca: 'Samsung',
        modelo: 'UN50DU7000',
        vertical: 'electro',
        imagen: 'https://example.com/tv.jpg',
        offers: [
          {
            supermercado: 'Provincia Compras',
            precio: 649999,
            precio_lista: 899999,
            stock: 10,
            link: 'https://provinciacompras.com.ar/tv',
            seller_name: 'Samsung Oficial',
            seller_id: '1',
            store_type: 'marketplace',
            cuotas: 24,
            sin_interes: true,
            cuotas_info: '24 cuotas sin interés',
            cuota_monto: 27083,
            discount: 28,
          },
        ],
      }

      vi.mocked(api.searchProducts).mockResolvedValue([mockTvGroup])

      render(
        <LocationProvider>
          <BenefitsProvider>
            <CartProvider>
              <SavedProvider>
                <SearchScreen />
              </SavedProvider>
            </CartProvider>
          </BenefitsProvider>
        </LocationProvider>,
      )

      const input = screen.getByPlaceholderText(/Buscá o escaneá/i)
      fireEvent.change(input, { target: { value: 'televisor' } })

      // Wait for search result
      await waitFor(() => {
        expect(screen.getByText('Smart TV Samsung 50 pulgadas 4K')).toBeTruthy()
      })

      // Vertical filter chip bar must be visible
      expect(screen.getByRole('button', { name: /^Todos$/i })).toBeTruthy()
      expect(screen.getByRole('button', { name: /^Supermercados$/i })).toBeTruthy()
      expect(screen.getByRole('button', { name: /^Marketplaces \/ Electro$/i })).toBeTruthy()

      // Click "Marketplaces / Electro" chip
      const mpChip = screen.getByRole('button', { name: /^Marketplaces \/ Electro$/i })
      fireEvent.click(mpChip)

      await waitFor(() => {
        expect(api.searchProducts).toHaveBeenCalledWith(
          'televisor',
          'unit_price_asc',
          false,
          null,
          expect.objectContaining({
            vertical: 'marketplace,electro',
            grocery_only: false,
          }),
        )
      })

      // Click "Supermercados" chip
      const superChip = screen.getByRole('button', { name: /^Supermercados$/i })
      fireEvent.click(superChip)

      await waitFor(() => {
        expect(api.searchProducts).toHaveBeenCalledWith(
          'televisor',
          'unit_price_asc',
          false,
          null,
          expect.objectContaining({
            vertical: 'supermarket',
            grocery_only: true,
          }),
        )
      })
    })

    it('2.2 categorizes available stores by vertical in the filter dropdown', async () => {
      const mixedProducts: ProductGroup[] = [
        {
          ean: '111',
          nombre: 'Leche Coto',
          marca: 'Coto',
          offers: [{ supermercado: 'Coto', precio: 1000, precio_lista: 1200, stock: 10, link: '' }],
        },
        {
          ean: '222',
          nombre: 'TV Frávega',
          marca: 'Philips',
          offers: [{ supermercado: 'Fravega', precio: 200000, precio_lista: 250000, stock: 5, link: '' }],
        },
        {
          ean: '333',
          nombre: 'Colchón Provincia Compras',
          marca: 'Piero',
          offers: [{ supermercado: 'Provincia Compras', precio: 150000, precio_lista: 180000, stock: 3, link: '' }],
        },
      ]

      vi.mocked(api.searchProducts).mockResolvedValue(mixedProducts)

      render(
        <LocationProvider>
          <BenefitsProvider>
            <CartProvider>
              <SavedProvider>
                <SearchScreen />
              </SavedProvider>
            </CartProvider>
          </BenefitsProvider>
        </LocationProvider>,
      )

      const input = screen.getByPlaceholderText(/Buscá o escaneá/i)
      fireEvent.change(input, { target: { value: 'combo' } })

      await waitFor(() => {
        expect(screen.getByText('Leche Coto')).toBeTruthy()
      })

      // Open store dropdown
      const dropdownBtn = screen.getByRole('button', { name: /Comercio:\s*Todos/i })
      fireEvent.click(dropdownBtn)

      // Category headers should be present inside the listbox
      const listbox = screen.getByRole('listbox')
      expect(within(listbox).getByText('Supermercados')).toBeTruthy()
      expect(within(listbox).getByText('Electro y Tecnología')).toBeTruthy()
      expect(within(listbox).getByText('Marketplaces Generales')).toBeTruthy()

      // Stores should be listed as options
      expect(within(listbox).getByRole('option', { name: /Coto/i })).toBeTruthy()
      expect(within(listbox).getByRole('option', { name: /Frávega/i })).toBeTruthy()
      expect(within(listbox).getByRole('option', { name: /Provincia Compras/i })).toBeTruthy()
    })
  })

  describe('3. ProductCard Badges & Seller Transparency (`ProductCard.tsx`)', () => {
    it('3.1 renders vertical badge, model code, and dynamic seller indicator', () => {
      const product: ProductGroup = {
        id: '123',
        ean: '8806095483245',
        nombre: 'Smart TV Samsung 50" Crystal 4K',
        marca: 'Samsung',
        modelo: 'UN50DU7000',
        vertical: 'electro',
        imagen: 'https://example.com/tv.jpg',
        offers: [
          {
            supermercado: 'Provincia Compras',
            precio: 649999,
            precio_lista: 899999,
            stock: 10,
            link: 'https://provinciacompras.com.ar/tv?seller=diggit',
            seller_name: 'Diggit Electrónica',
            seller_id: 'diggit',
            store_type: 'marketplace',
            cuotas: 24,
            sin_interes: true,
            cuota_monto: 27083,
            discount: 28,
          },
        ],
      }

      render(
        <LocationProvider>
          <BenefitsProvider>
            <CartProvider>
              <SavedProvider>
                <ProductCard group={product} />
              </SavedProvider>
            </CartProvider>
          </BenefitsProvider>
        </LocationProvider>,
      )

      // Vertical badge
      expect(screen.getByText('Electro')).toBeTruthy()

      // Monospace model code
      expect(screen.getByText('UN50DU7000')).toBeTruthy()

      // Dynamic seller indicator
      expect(screen.getByText('Vendido por Diggit Electrónica')).toBeTruthy()

      // Installment financing badge
      expect(screen.getByText(/24 cuotas sin interés/i)).toBeTruthy()
      expect(screen.getByText(/24x\s*\$\s*27\.083/i)).toBeTruthy()
    })

    it('3.2 renders direct retail indicator ("Venta directa") when seller matches store', () => {
      const directProduct: ProductGroup = {
        ean: '779004',
        nombre: 'Fideos Moñito 500g',
        marca: 'Matarazzo',
        vertical: 'supermarket',
        imagen: 'https://example.com/fideos.jpg',
        offers: [
          {
            supermercado: 'Carrefour',
            precio: 1200,
            precio_lista: 1200,
            stock: 20,
            link: 'https://carrefour.com.ar/fideos',
            seller_name: 'Carrefour',
            seller_id: '1',
            store_type: 'supermarket',
            discount: 0,
          },
        ],
      }

      render(
        <LocationProvider>
          <BenefitsProvider>
            <CartProvider>
              <SavedProvider>
                <ProductCard group={directProduct} />
              </SavedProvider>
            </CartProvider>
          </BenefitsProvider>
        </LocationProvider>,
      )

      expect(screen.getByText('Súper')).toBeTruthy()
      expect(screen.getByText('Venta directa')).toBeTruthy()
    })
  })

  describe('4. Dedicated Marketplace Carousels (`OffersScreen.tsx`)', () => {
    it('4.1 renders segmented control tabs and guards against missing meliSponsored', () => {
      render(
        <LocationProvider>
          <BenefitsProvider>
            <CartProvider>
              <SavedProvider>
                <OffersScreen />
              </SavedProvider>
            </CartProvider>
          </BenefitsProvider>
        </LocationProvider>,
      )

      // Segmented control buttons
      expect(screen.getByRole('button', { name: /🌟 Todas las Ofertas/i })).toBeTruthy()
      expect(screen.getByRole('button', { name: /🛒 Supermercados/i })).toBeTruthy()
      expect(screen.getByRole('button', { name: /⚡ Marketplaces & Tech/i })).toBeTruthy()

      // Default view has supermarket tiers AND marketplace tiers stacked
      expect(screen.getByText(/2da Unidad al 70% y 80% OFF/i)).toBeTruthy()
      expect(screen.getByText(/Marketplaces, Electro & Hogar/i)).toBeTruthy()
      expect(screen.getByText(/Electrodomésticos y Tecnología — Hasta 40% OFF y Cuotas/i)).toBeTruthy()

      // Switch to Marketplaces only
      const mpTab = screen.getByRole('button', { name: /⚡ Marketplaces & Tech/i })
      fireEvent.click(mpTab)

      expect(screen.getByText(/Electrodomésticos y Tecnología — Hasta 40% OFF y Cuotas/i)).toBeTruthy()
      expect(screen.queryByText(/2da Unidad al 70% y 80% OFF/i)).toBeNull()

      // Switch to Supermercados only
      const superTab = screen.getByRole('button', { name: /🛒 Supermercados/i })
      fireEvent.click(superTab)

      expect(screen.getByText(/2da Unidad al 70% y 80% OFF/i)).toBeTruthy()
      expect(screen.queryByText(/Marketplaces, Electro & Hogar/i)).toBeNull()
    })
  })

  describe('5. OffersSheet & GondolaCard Financing and Dynamic Seller Links', () => {
    it('5.1 GondolaCard displays financing badge and monthly cuota monto', () => {
      const tvGroup: ProductGroup = {
        id: 'tv1',
        ean: '8806095483245',
        nombre: 'Smart TV Samsung 50" Crystal 4K',
        marca: 'Samsung',
        modelo: 'UN50DU7000',
        imagen: 'https://example.com/tv.jpg',
        offers: [
          {
            supermercado: 'Provincia Compras',
            precio: 649999,
            precio_lista: 899999,
            stock: 10,
            link: 'https://provinciacompras.com.ar/tv',
            seller_name: 'Samsung Oficial',
            seller_id: '1',
            cuotas: 24,
            sin_interes: true,
            cuotas_info: '24 cuotas sin interés de $27.083',
            cuota_monto: 27083,
            discount: 28,
          },
        ],
      }

      render(
        <LocationProvider>
          <BenefitsProvider>
            <CartProvider>
              <SavedProvider>
                <GondolaCard group={tvGroup} />
              </SavedProvider>
            </CartProvider>
          </BenefitsProvider>
        </LocationProvider>,
      )

      expect(screen.getByText(/24 cuotas sin interés/i)).toBeTruthy()
      expect(screen.getByText(/24x\s*\$\s*27\.083/i)).toBeTruthy()
    })

    it('5.2 OffersSheet renders installment financing callout and preserves dynamic seller in links', () => {
      const group: ProductGroup = {
        id: 'tv2',
        ean: '8806095483245',
        nombre: 'Smart TV Samsung 50" Crystal 4K',
        marca: 'Samsung',
        modelo: 'UN50DU7000',
        imagen: 'https://example.com/tv.jpg',
        offers: [
          {
            supermercado: 'Provincia Compras',
            precio: 649999,
            precio_lista: 899999,
            stock: 10,
            link: 'https://provinciacompras.com.ar/tv',
            seller_name: 'AudioStore',
            seller_id: 'audiostore_ar',
            cuotas: 12,
            sin_interes: true,
            cuotas_info: '12 cuotas sin interés de $54.166',
            cuota_monto: 54166,
            discount: 28,
          },
        ],
      }

      const rows = [
        {
          o: group.offers[0],
          eff: 649999,
          unit: null,
          club: null,
          promo: null,
          minQty: 1,
          noDelivery: false,
        },
      ]

      render(
        <CartProvider>
          <OffersSheet open={true} onClose={vi.fn()} group={group} rows={rows} />
        </CartProvider>,
      )

      // Financing callout in sheet
      expect(screen.getByText(/12 cuotas sin interés de \$54\.166/i)).toBeTruthy()

      // Outbound link includes dynamic seller
      const link = screen.getByRole('link', { name: /ver web/i })
      expect(link.getAttribute('href')).toContain('seller=audiostore_ar')
    })
  })
})
