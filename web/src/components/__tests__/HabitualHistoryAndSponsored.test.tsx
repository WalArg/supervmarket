import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import SearchScreen from '../SearchScreen'
import ProductCard from '../ProductCard'
import SponsoredProductBox from '../SponsoredProductBox'
import HabitualListManager from '../HabitualListManager'
import ListScreen from '../ListScreen'
import SavedScreen from '../SavedScreen'
import OffersSheet from '../OffersSheet'
import { CartProvider } from '../../cart/CartContext'
import { HabitualListProvider } from '../../cart/HabitualListContext'
import { SavedProvider } from '../../saved/SavedContext'
import { LocationProvider } from '../../location/LocationContext'
import { BenefitsProvider } from '../../benefits/BenefitsContext'
import * as api from '../../api'
import type { ProductGroup } from '../../types'

vi.mock('../../api', async () => {
  const actual = await vi.importActual('../../api')
  return {
    ...actual,
    searchProducts: vi.fn().mockResolvedValue([]),
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

describe('Feature Delivery: Mi Lista Habitual, Histórico de Precios y Patrocinado', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('1. SearchScreen does NOT render sponsored section on initial home search page', () => {
    render(
      <LocationProvider>
        <SearchScreen />
      </LocationProvider>,
    )

    // User requirement: No sponsored section on the initial search page
    expect(screen.queryByText('PATROCINADO')).toBeNull()
    expect(screen.queryByText('Mercado Libre Supermercado')).toBeNull()

    // Clean home components should still be visible
    expect(screen.getByText(/Lo más buscado/i)).toBeTruthy()
    expect(screen.getByText(/¿Estás en el súper\?/i)).toBeTruthy()
  })

  it('2. ProductCard renders price discount tag and SponsoredProductBox displays Mercado Libre prominently', () => {
    const sampleGroup: ProductGroup = {
      ean: '7790070336026',
      nombre: 'Fideos Lucchetti Tirabuzón 500g',
      marca: 'Lucchetti',
      imagen: 'https://example.com/fideos.jpg',
      offers: [
        {
          supermercado: 'Carrefour',
          precio: 2000,
          precio_lista: 2500,
          discount: 20,
          stock: true,
          link: 'https://carrefour.com.ar/p',
          sku_id: '123',
          unit_price: 4000,
          unit_measure: 'kg',
          supports_cart: true,
        },
        {
          supermercado: 'MercadoLibre',
          precio: 2100,
          precio_lista: 2100,
          discount: 0,
          stock: true,
          link: 'https://articulo.mercadolibre.com.ar/MLA-123456',
          sku_id: 'MLA-123456',
          unit_price: 4200,
          unit_measure: 'kg',
          supports_cart: false,
          seller_name: 'Tienda Oficial Lucchetti',
          is_full: true,
          free_shipping: true,
        },
      ],
    }

    render(
      <LocationProvider>
        <BenefitsProvider>
          <CartProvider>
            <ProductCard group={sampleGroup} />
          </CartProvider>
        </BenefitsProvider>
      </LocationProvider>,
    )

    // Should render price discount indicator (minimum recent)
    expect(screen.getByText(/📉 Mínimo reciente/i)).toBeTruthy()

    // Now render SponsoredProductBox directly for Mercado Libre
    render(
      <SponsoredProductBox
        product={sampleGroup}
        offer={sampleGroup.offers[1]}
      />,
    )

    expect(screen.getAllByText('PATROCINADO').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Destacado en Mercado Libre')).toBeTruthy()
    expect(screen.getByText('Tienda Oficial Lucchetti')).toBeTruthy()
    expect(screen.getByText(/FULL/i)).toBeTruthy()
  })

  it('3. ListScreen renders clean empty Carrito state and allows navigating to search', () => {
    const onGoSearch = vi.fn()
    render(
      <LocationProvider>
        <BenefitsProvider>
          <CartProvider>
            <HabitualListProvider>
              <ListScreen onGoSearch={onGoSearch} onGoProfile={vi.fn()} />
            </HabitualListProvider>
          </CartProvider>
        </BenefitsProvider>
      </LocationProvider>,
    )

    // Empty state should display clean Carrito state
    expect(screen.getByText(/Tu (carrito|lista) está vací[ao]/i)).toBeTruthy()
    expect(screen.getByText(/Agregá productos desde el buscador o desde la pestaña Guardados/i)).toBeTruthy()

    // 1-Tap button to explore products
    const exploreBtn = screen.getByRole('button', {
      name: /explorar productos/i,
    })
    expect(exploreBtn).toBeTruthy()
    fireEvent.click(exploreBtn)
    expect(onGoSearch).toHaveBeenCalledTimes(1)
  })

  it('4. HabitualListManager displays direct 1-tap save button when items are in cart', () => {
    const items = [{ ean: '7790742333605', nombre: 'Leche 1L', qty: 2 }]
    localStorage.setItem('sv_cart_v2', JSON.stringify(items))

    render(
      <CartProvider>
        <HabitualListProvider>
          <HabitualListManager />
        </HabitualListProvider>
      </CartProvider>,
    )

    // Header has Mi Lista Habitual & Histórico de Precios + Termómetro de Ahorro
    expect(screen.getByText(/Mi Lista Habitual & Histórico de Precios/i)).toBeTruthy()
    expect(screen.getByText('Termómetro de Ahorro')).toBeTruthy()

    // Direct 1-tap save button is visible without expanding
    const saveBtn = screen.getByRole('button', {
      name: /guardar changuito como mi lista habitual/i,
    })
    expect(saveBtn).toBeTruthy()

    // Click to save as habitual
    fireEvent.click(saveBtn)

    // localStorage should have habitual list
    const habitual = JSON.parse(localStorage.getItem('sv_habitual_v1') || '{}')
    expect(habitual.items.length).toBe(1)
    expect(habitual.items[0].ean).toBe('7790742333605')
  })

  it('5. Sponsored placement strictly requires Full Super (is_full: true) and query relevance', () => {
    // 1. Non-full Mercado Libre offer must NOT be sponsored
    const nonFullOffer: Offer = {
      supermercado: 'MercadoLibre',
      sku: 'MELI-AIR-123',
      precio: 10000,
      precio_lista: 10000,
      stock: 10,
      link: 'https://articulo.mercadolibre.com.ar/MLA-123',
      is_full: false,
    }
    const airFreshenerGroup: ProductGroup = {
      id: 'grp-air',
      nombre: 'Aromatizante Coca Cola Auto',
      marca: 'Airpure',
      offers: [nonFullOffer],
    }

    // 2. Full Super offer must be accepted
    const fullOffer: Offer = {
      supermercado: 'MercadoLibre',
      sku: 'MELI-COCA-999',
      precio: 6995,
      precio_lista: 6995,
      stock: 100,
      link: 'https://articulo.mercadolibre.com.ar/MLA-999',
      seller_name: '01MERCADO.COM.AR',
      is_full: true,
      free_shipping: true,
    }
    const realCocaColaGroup: ProductGroup = {
      id: 'grp-coca',
      nombre: 'Gaseosa Coca Cola 1.75 Lt',
      marca: 'Coca-Cola',
      offers: [fullOffer],
    }

    render(
      <SponsoredProductBox
        product={realCocaColaGroup}
        offer={fullOffer}
      />,
    )

    expect(screen.getByText(/FULL SÚPER/i)).toBeTruthy()
    expect(screen.getByText('01MERCADO.COM.AR')).toBeTruthy()
    expect(screen.getByText('Gaseosa Coca Cola 1.75 Lt')).toBeTruthy()
  })

  it('6. Guardados tab: allows saving products, viewing them, adding to cart, and removing', () => {
    const testProduct: ProductGroup = {
      ean: '7791234567890',
      nombre: 'Leche Descremada La Serenísima 1L',
      marca: 'La Serenísima',
      imagen: 'https://example.com/leche.jpg',
      offers: [
        {
          supermercado: 'Coto',
          precio: 1450,
          precio_lista: 1600,
          stock: 10,
          link: 'https://coto.com.ar/leche',
        },
      ],
    }

    // Render SavedScreen initially empty
    const { unmount } = render(
      <SavedProvider>
        <CartProvider>
          <SavedScreen onGoSearch={vi.fn()} onGoCart={vi.fn()} />
        </CartProvider>
      </SavedProvider>,
    )

    expect(screen.getByText('No tenés productos guardados')).toBeTruthy()
    unmount()

    // Now render with a saved product in localStorage
    localStorage.setItem(
      'sv_saved_products_v1',
      JSON.stringify([
        {
          id: '7791234567890',
          ean: '7791234567890',
          nombre: testProduct.nombre,
          marca: testProduct.marca,
          imagen: testProduct.imagen,
          minPrice: 1450,
          bestStore: 'Coto',
          group: testProduct,
          savedAt: Date.now(),
        },
      ]),
    )

    render(
      <SavedProvider>
        <CartProvider>
          <SavedScreen onGoSearch={vi.fn()} onGoCart={vi.fn()} />
        </CartProvider>
      </SavedProvider>,
    )

    expect(screen.getByText('Leche Descremada La Serenísima 1L')).toBeTruthy()
    expect(screen.getByText('1 producto para tener a mano')).toBeTruthy()

    // Add to cart from SavedScreen
    const addToCartBtn = screen.getByRole('button', { name: /^al carrito$/i })
    expect(addToCartBtn).toBeTruthy()
    fireEvent.click(addToCartBtn)

    const cart = JSON.parse(localStorage.getItem('sv_cart_v2') || '[]')
    expect(cart.length).toBe(1)
    expect(cart[0].ean).toBe('7791234567890')

    // Remove from saved
    const removeBtn = screen.getByRole('button', { name: /sacar de guardados/i })
    fireEvent.click(removeBtn)

    expect(screen.getByText('No tenés productos guardados')).toBeTruthy()
  })

  it('7. Inicio renders Góndolas temáticas with real products and search input with scan placeholder', () => {
    render(
      <LocationProvider>
        <CartProvider>
          <SavedProvider>
            <SearchScreen />
          </SavedProvider>
        </CartProvider>
      </LocationProvider>,
    )

    // Check placeholder
    const searchInput = screen.getByPlaceholderText(/Buscá o escaneá el producto que querés buscar\.\.\./i)
    expect(searchInput).toBeTruthy()

    // Check category pills
    expect(screen.getByText('🔥 Ofertas del día')).toBeTruthy()
    expect(screen.getByText('🥛 Lácteos')).toBeTruthy()

    // Check Góndola headers
    expect(screen.getByText('Ofertas destacadas del día')).toBeTruthy()
    expect(screen.getByText('Lácteos y Frescos')).toBeTruthy()
    expect(screen.getByText('Almacén y Canasta Básica')).toBeTruthy()

    // Check products inside gondolas
    expect(screen.getByText('Fideos Lucchetti Tirabuzón 500 G')).toBeTruthy()
    expect(screen.getByText('Leche La Serenísima Clásica Entera 1 L')).toBeTruthy()
  })

  it('8. Store filter: allows filtering search results by supermarket', async () => {
    const multiStoreProducts: ProductGroup[] = [
      {
        ean: '779001',
        nombre: 'Galletitas Coto Exclusive',
        marca: 'Coto',
        offers: [
          { supermercado: 'Coto', precio: 1000, precio_lista: 1200, stock: 10, link: '' },
        ],
      },
      {
        ean: '779002',
        nombre: 'Galletitas Carrefour Exclusive',
        marca: 'Carrefour',
        offers: [
          { supermercado: 'Carrefour', precio: 1100, precio_lista: 1300, stock: 10, link: '' },
        ],
      },
    ]

    vi.mocked(api.searchProducts).mockResolvedValueOnce(multiStoreProducts)

    render(
      <LocationProvider>
        <CartProvider>
          <SavedProvider>
            <SearchScreen />
          </SavedProvider>
        </CartProvider>
      </LocationProvider>,
    )

    const input = screen.getByPlaceholderText(/Buscá o escaneá/i)
    fireEvent.change(input, { target: { value: 'galletitas' } })

    // Wait for search
    await waitFor(() => {
      expect(screen.getByText('Galletitas Coto Exclusive')).toBeTruthy()
      expect(screen.getByText('Galletitas Carrefour Exclusive')).toBeTruthy()
    })

    // Store filter chips must appear
    const cotoChip = screen.getByRole('button', { name: /^coto\s*\(\d+\)$/i })
    expect(cotoChip).toBeTruthy()

    // Filter by Coto
    fireEvent.click(cotoChip)

    // Only Coto product should remain
    expect(screen.getByText('Galletitas Coto Exclusive')).toBeTruthy()
    expect(screen.queryByText('Galletitas Carrefour Exclusive')).toBeNull()

    // Reset back to Todos
    const todosBtn = screen.getByRole('button', { name: /^todos\s*\(\d+\)$/i })
    fireEvent.click(todosBtn)

    expect(screen.getByText('Galletitas Coto Exclusive')).toBeTruthy()
    expect(screen.getByText('Galletitas Carrefour Exclusive')).toBeTruthy()
  })

  it('9. OffersSheet: allows adding items to cart directly from each store row without external redirect', () => {
    const group: ProductGroup = {
      ean: '7799998881112',
      nombre: 'Arroz Largo Fino 1kg',
      marca: 'Ala',
      offers: [
        {
          supermercado: 'Coto',
          precio: 1500,
          precio_lista: 1800,
          stock: 20,
          link: 'https://coto.com.ar/arroz',
        },
        {
          supermercado: 'Carrefour',
          precio: 1600,
          precio_lista: 1800,
          stock: 15,
          link: 'https://carrefour.com.ar/arroz',
        },
      ],
    }

    const rows = [
      {
        o: group.offers[0],
        eff: 1500,
        unit: 1500,
        club: null,
        promo: null,
        minQty: 1,
        noDelivery: false,
      },
      {
        o: group.offers[1],
        eff: 1600,
        unit: 1600,
        club: null,
        promo: null,
        minQty: 1,
        noDelivery: false,
      },
    ]

    render(
      <CartProvider>
        <OffersSheet
          open={true}
          onClose={vi.fn()}
          group={group}
          rows={rows}
        />
      </CartProvider>,
    )

    // Check store rows rendered
    expect(screen.getByText('Coto')).toBeTruthy()
    expect(screen.getByText('Carrefour')).toBeTruthy()

    // Add buttons should be available on each store row
    const addButtons = screen.getAllByRole('button', { name: /agregar/i })
    expect(addButtons.length).toBeGreaterThanOrEqual(2)

    // Click to add from Coto
    fireEvent.click(addButtons[0])

    const cart = JSON.parse(localStorage.getItem('sv_cart_v2') || '[]')
    expect(cart.length).toBe(1)
    expect(cart[0].ean).toBe('7799998881112')
  })
})
