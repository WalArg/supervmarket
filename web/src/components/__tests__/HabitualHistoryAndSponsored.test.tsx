import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import SearchScreen from '../SearchScreen'
import ProductCard from '../ProductCard'
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

  it('1. SearchScreen renders the [PATROCINADO] brand offers and Ethical Firewall on home', () => {
    render(
      <LocationProvider>
        <SearchScreen />
      </LocationProvider>,
    )

    // Verify Sponsored header & badge
    expect(screen.getByText('PATROCINADO')).toBeTruthy()
    expect(screen.getByText('Ofertas Destacadas y Cupones de Marca')).toBeTruthy()

    // Verify brand deals
    expect(screen.getByText(/Hellmann's Doypack 15% OFF/i)).toBeTruthy()
    expect(screen.getByText(/Mermeladas La Campagnola 2×1/i)).toBeTruthy()
    expect(screen.getByText(/Pack Quilmes Clásica Lata/i)).toBeTruthy()

    // Verify Ethical Firewall disclaimer
    expect(screen.getByText(/Firewall Ético SuperVmarket/i)).toBeTruthy()
    expect(screen.getByText(/Ley 24\.240/i)).toBeTruthy()
  })

  it('2. ProductCard renders price history indicator and handles [PATROCINADO] badge', () => {
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
      ],
    }

    const { rerender } = render(
      <LocationProvider>
        <BenefitsProvider>
          <CartProvider>
            <ProductCard group={sampleGroup} isSponsored={false} />
          </CartProvider>
        </BenefitsProvider>
      </LocationProvider>,
    )

    // Should render price history indicator (minimum recent)
    expect(screen.getByText(/📉 Mínimo reciente/i)).toBeTruthy()

    // Now re-render with isSponsored=true
    rerender(
      <LocationProvider>
        <BenefitsProvider>
          <CartProvider>
            <ProductCard group={sampleGroup} isSponsored={true} />
          </CartProvider>
        </BenefitsProvider>
      </LocationProvider>,
    )

    expect(screen.getByText('PATROCINADO')).toBeTruthy()
    expect(screen.getByText(/Oferta destacada de marca/i)).toBeTruthy()
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
})
