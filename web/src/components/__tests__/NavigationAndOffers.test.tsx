import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import App from '../../App'
import OffersScreen from '../OffersScreen'
import SearchScreen from '../SearchScreen'
import { CartProvider } from '../../cart/CartContext'
import { SavedProvider } from '../../saved/SavedContext'
import { LocationProvider } from '../../location/LocationContext'
import { BenefitsProvider } from '../../benefits/BenefitsContext'
import { HabitualListProvider } from '../../cart/HabitualListContext'
import * as api from '../../api'

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

describe('Navigation Structure, Centered Search & Góndolas de Ofertas', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('1. App opens on Buscador as the leftmost bottom tab and renders 4 bottom tabs', () => {
    render(
      <LocationProvider>
        <BenefitsProvider>
          <CartProvider>
            <SavedProvider>
              <HabitualListProvider>
                <App />
              </HabitualListProvider>
            </SavedProvider>
          </CartProvider>
        </BenefitsProvider>
      </LocationProvider>,
    )

    // Check bottom nav has 4 tabs: Buscador, Ofertas, Asistente IA, Perfil
    const nav = screen.getByRole('navigation')
    const buttons = nav.querySelectorAll('button')
    expect(buttons.length).toBe(4)

    // 1st tab (leftmost) is Buscador
    expect(buttons[0].textContent).toContain('Buscador')
    // 2nd tab is Ofertas
    expect(buttons[1].textContent).toContain('Ofertas')
    // 3rd tab is Asistente IA
    expect(buttons[2].textContent).toContain('Asistente IA')
    // 4th tab is Perfil
    expect(buttons[3].textContent).toContain('Perfil')

    // Initial view is Buscador (centered hero)
    expect(screen.getByText('Encontrá el mejor precio')).toBeTruthy()
    expect(screen.getByPlaceholderText(/Buscá o escaneá/i)).toBeTruthy()
  })

  it('2. Floating action buttons for Guardados and Carrito exist outside bottom navigation', () => {
    render(
      <LocationProvider>
        <BenefitsProvider>
          <CartProvider>
            <SavedProvider>
              <HabitualListProvider>
                <App />
              </HabitualListProvider>
            </SavedProvider>
          </CartProvider>
        </BenefitsProvider>
      </LocationProvider>,
    )

    // Carrito and Guardados should exist as floating buttons
    const floatingAside = screen.getByLabelText(/Acciones rápidas de compra/i)
    expect(floatingAside).toBeTruthy()

    const cartFab = screen.getByRole('button', { name: /Ver carrito con 0 productos/i })
    expect(cartFab).toBeTruthy()
    expect(cartFab.textContent).toContain('Carrito')

    const savedFab = screen.getByRole('button', { name: /Ver 0 productos guardados/i })
    expect(savedFab).toBeTruthy()
    expect(savedFab.textContent).toContain('Guardados')

    // Click Carrito floating button: navigates to Carrito view with Volver button
    fireEvent.click(cartFab)
    expect(screen.getByText(/Tu carrito está vacío/i)).toBeTruthy()

    const backButton = screen.getByRole('button', { name: /volver/i })
    expect(backButton).toBeTruthy()

    // Clicking Volver returns to Buscador
    fireEvent.click(backButton)
    expect(screen.getByText('Encontrá el mejor precio')).toBeTruthy()
  })

  it('3. SearchScreen: centered initially, transitions dynamically to top when user searches', async () => {
    const mockProducts = [
      {
        ean: '779123',
        nombre: 'Leche Descremada La Serenísima 1L',
        marca: 'La Serenísima',
        imagen: 'https://example.com/leche.jpg',
        offers: [
          { supermercado: 'Coto', precio: 1200, discount: 15, stock: 10, link: '' },
          { supermercado: 'Carrefour', precio: 1300, discount: 0, stock: 10, link: '' },
        ],
      },
    ]

    vi.mocked(api.searchProducts).mockResolvedValueOnce(mockProducts)

    render(
      <LocationProvider>
        <CartProvider>
          <SavedProvider>
            <SearchScreen />
          </SavedProvider>
        </CartProvider>
      </LocationProvider>,
    )

    // Initially centered
    expect(screen.getByText('Encontrá el mejor precio')).toBeTruthy()
    expect(screen.getByText(/¿Estás en el súper\?/i)).toBeTruthy()

    // No scanner button to the right of input before searching
    expect(screen.queryByRole('button', { name: /escanear código de barras/i })).toBeNull()

    // No habitual searches at the beginning
    expect(screen.queryByText(/Búsquedas recientes/i)).toBeNull()
    expect(screen.queryByText(/Lo más buscado/i)).toBeNull()

    // Type in search input
    const input = screen.getByPlaceholderText(/Buscá o escaneá/i)
    fireEvent.change(input, { target: { value: 'leche' } })

    // Wait for search results
    await waitFor(() => {
      expect(screen.getByText('Leche Descremada La Serenísima 1L')).toBeTruthy()
    })

    // Now barcode button appears to the right of the search input at the top
    expect(screen.getByRole('button', { name: /escanear código de barras/i })).toBeTruthy()

    // Centered hero branding hides when search is active
    expect(screen.queryByText('Encontrá el mejor precio')).toBeNull()

    // Clear search
    const clearBtn = screen.getByRole('button', { name: /borrar/i })
    fireEvent.click(clearBtn)

    // Re-displays centered layout and hides the top scanner button
    expect(screen.getByText('Encontrá el mejor precio')).toBeTruthy()
    expect(screen.queryByRole('button', { name: /escanear código de barras/i })).toBeNull()
  })

  it('4. OffersScreen: renders separated góndolas, top discounts, and always a Mercado Libre sponsored option', () => {
    render(
      <LocationProvider>
        <CartProvider>
          <SavedProvider>
            <OffersScreen />
          </SavedProvider>
        </CartProvider>
      </LocationProvider>,
    )

    // Header title
    expect(screen.getByText('Ofertas y Góndolas')).toBeTruthy()
    expect(screen.getByText('Mayores descuentos del día comparados en vivo')).toBeTruthy()

    // Sponsored Mercado Libre section is ALWAYS present
    expect(screen.getAllByText('PATROCINADO').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Destacado en Mercado Libre')).toBeTruthy()

    // Top discounts banner
    expect(screen.getByText('🔥 Mayores Descuentos del Día')).toBeTruthy()

    // Góndolas separation
    expect(screen.getByText('Ofertas destacadas del día')).toBeTruthy()
    expect(screen.getByText('Lácteos y Frescos')).toBeTruthy()
    expect(screen.getByText('Almacén y Canasta Básica')).toBeTruthy()
    expect(screen.getByText('Limpieza y Hogar')).toBeTruthy()
    expect(screen.getByText('Bebidas y Desayuno')).toBeTruthy()
  })
})
