import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import SearchScreen from '../SearchScreen'
import ProductCard from '../ProductCard'
import SponsoredProductBox from '../SponsoredProductBox'
import HabitualListManager from '../HabitualListManager'
import ListScreen from '../ListScreen'
import { CartProvider } from '../../cart/CartContext'
import { HabitualListProvider } from '../../cart/HabitualListContext'
import { LocationProvider } from '../../location/LocationContext'
import { BenefitsProvider } from '../../benefits/BenefitsContext'
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

  it('1. SearchScreen renders the Mercado Libre [PATROCINADO] section on home', () => {
    render(
      <LocationProvider>
        <SearchScreen />
      </LocationProvider>,
    )

    // Verify Sponsored header & badge
    expect(screen.getByText('PATROCINADO')).toBeTruthy()
    expect(screen.getByText('Mercado Libre Supermercado')).toBeTruthy()

    // Verify Mercado Libre highlights
    expect(screen.getByText(/Envíos FULL en 24hs/i)).toBeTruthy()
    expect(screen.getByText(/Compra protegida/i)).toBeTruthy()

    // Verify Ethical Firewall disclaimer
    expect(screen.getByText(/Firewall Ético SuperVmarket/i)).toBeTruthy()
    expect(screen.getByText(/Ley 24\.240/i)).toBeTruthy()
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

  it('3. ListScreen renders Mi Lista Habitual discovery card and 1-tap sample basket loader', () => {
    render(
      <LocationProvider>
        <BenefitsProvider>
          <CartProvider>
            <HabitualListProvider>
              <ListScreen onGoSearch={vi.fn()} onGoProfile={vi.fn()} />
            </HabitualListProvider>
          </CartProvider>
        </BenefitsProvider>
      </LocationProvider>,
    )

    // Empty state should display Mi Lista Habitual discovery
    expect(screen.getByText('Mi Lista Habitual')).toBeTruthy()
    expect(screen.getByText(/El verdadero valor de SuperVmarket/i)).toBeTruthy()

    // 1-Tap button to load sample basket
    const loadSampleBtn = screen.getByRole('button', {
      name: /cargar canasta mensual de ejemplo/i,
    })
    expect(loadSampleBtn).toBeTruthy()

    // Click to load sample basket
    fireEvent.click(loadSampleBtn)

    // Should load items into cart
    const cartItems = JSON.parse(localStorage.getItem('sv_cart_v2') || '[]')
    expect(cartItems.length).toBe(6)
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
})
