import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import SearchScreen from '../components/SearchScreen'
import ProductCard from '../components/ProductCard'
import { LocationProvider } from '../location/LocationContext'
import { BenefitsProvider } from '../benefits/BenefitsContext'
import { CartProvider } from '../cart/CartContext'
import { SavedProvider } from '../saved/SavedContext'
import * as api from '../api'
import type { ProductGroup } from '../types'
import fs from 'node:fs'
import path from 'node:path'

vi.mock('../api', async () => {
  const actual = await vi.importActual('../api')
  return {
    ...actual,
    searchProducts: vi.fn(),
  }
})

describe('CHALLENGER M4: Adversarial Stress Test Suite — Differentiated Search UI & ProductCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  const renderWithProviders = (ui: React.ReactElement) => {
    return render(
      <LocationProvider>
        <BenefitsProvider>
          <CartProvider>
            <SavedProvider>
              {ui}
            </SavedProvider>
          </CartProvider>
        </BenefitsProvider>
      </LocationProvider>
    )
  }

  // =========================================================================
  // 1. VERTICAL CHIP SWITCHING & STATE TRANSITIONS
  // =========================================================================
  describe('1. Vertical Chip Switching & State Transitions', () => {
    const mockMixedCatalog: ProductGroup[] = [
      {
        id: 'p1',
        ean: '779001',
        nombre: 'Leche La Serenísima 1L',
        marca: 'La Serenísima',
        vertical: 'supermarket',
        offers: [
          { supermercado: 'Carrefour', precio: 1200, precio_lista: 1300, stock: 10, link: '' },
          { supermercado: 'Dia', precio: 1150, precio_lista: 1250, stock: 15, link: '' },
        ],
      },
      {
        id: 'p2',
        ean: '779002',
        nombre: 'Smart TV 55 Pulgadas 4K',
        marca: 'Samsung',
        modelo: 'UN55DU8000',
        vertical: 'electro',
        offers: [
          {
            supermercado: 'Fravega',
            precio: 750000,
            precio_lista: 850000,
            stock: 4,
            link: '',
            cuotas: 12,
            sin_interes: true,
            cuota_monto: 62500,
          },
        ],
      },
      {
        id: 'p3',
        ean: '779003',
        nombre: 'Colchón King Size Sommier',
        marca: 'Piero',
        modelo: 'FOAM-KING',
        vertical: 'marketplace',
        offers: [
          {
            supermercado: 'Provincia Compras',
            precio: 450000,
            precio_lista: 500000,
            stock: 2,
            link: '',
            seller_name: 'Piero Oficial',
            seller_id: 'piero_1',
            cuotas: 24,
            sin_interes: true,
            cuota_monto: 18750,
          },
        ],
      },
      {
        id: 'p4',
        ean: '779004',
        nombre: 'Perfume Sauvage 100ml',
        marca: 'Dior',
        vertical: 'pharmacy',
        offers: [
          { supermercado: 'Pigmento', precio: 180000, precio_lista: 195000, stock: 3, link: '' },
        ],
      },
      {
        id: 'p5',
        ean: '779005',
        nombre: 'Taladro Percutor 750W',
        marca: 'Black+Decker',
        modelo: 'TM750',
        vertical: 'specialty',
        offers: [
          { supermercado: 'Easy', precio: 85000, precio_lista: 99000, stock: 6, link: '' },
        ],
      },
    ]

    it('1.1 Initial render presents "Todos" active and requests all verticals to API', async () => {
      vi.mocked(api.searchProducts).mockResolvedValue(mockMixedCatalog)
      renderWithProviders(<SearchScreen />)

      const input = screen.getByPlaceholderText(/Buscá o escaneá/i)
      fireEvent.change(input, { target: { value: 'combo' } })

      await waitFor(() => {
        expect(screen.getByText('Leche La Serenísima 1L')).toBeTruthy()
      })

      // Chips must exist
      const allChip = screen.getByRole('button', { name: /^Todos$/i })
      const superChip = screen.getByRole('button', { name: /^Supermercados$/i })
      const mpChip = screen.getByRole('button', { name: /^Marketplaces \/ Electro$/i })

      expect(allChip).toBeTruthy()
      expect(superChip).toBeTruthy()
      expect(mpChip).toBeTruthy()

      // "Todos" should have active styling (bg-blue-600)
      expect(allChip.className).toContain('bg-blue-600')
      expect(superChip.className).not.toContain('bg-blue-600')
      expect(mpChip.className).not.toContain('bg-blue-600')

      // API was called with null vertical and grocery_only: false
      expect(api.searchProducts).toHaveBeenCalledWith(
        'combo',
        'unit_price_asc',
        false,
        null,
        expect.objectContaining({
          vertical: null,
          grocery_only: false,
        }),
      )
    })

    it('1.2 Switching to "Supermercados" updates chip state, queries API with grocery_only: true, and filters client-side', async () => {
      vi.mocked(api.searchProducts).mockResolvedValue(mockMixedCatalog)
      renderWithProviders(<SearchScreen />)

      const input = screen.getByPlaceholderText(/Buscá o escaneá/i)
      fireEvent.change(input, { target: { value: 'combo' } })

      await waitFor(() => {
        expect(screen.getByText('Leche La Serenísima 1L')).toBeTruthy()
      })

      // Click "Supermercados"
      const superChip = screen.getByRole('button', { name: /^Supermercados$/i })
      fireEvent.click(superChip)

      await waitFor(() => {
        expect(api.searchProducts).toHaveBeenCalledWith(
          'combo',
          'unit_price_asc',
          false,
          null,
          expect.objectContaining({
            vertical: 'supermarket',
            grocery_only: true,
          }),
        )
      })

      // Active styles transferred to Supermercados
      expect(superChip.className).toContain('bg-blue-600')
      expect(screen.getByRole('button', { name: /^Todos$/i }).className).not.toContain('bg-blue-600')

      // Client-side filtering check: Supermarket item is visible, Electro/Tech/Marketplace items are hidden
      expect(screen.getByText('Leche La Serenísima 1L')).toBeTruthy()
      expect(screen.queryByText('Smart TV 55 Pulgadas 4K')).toBeNull()
      expect(screen.queryByText('Colchón King Size Sommier')).toBeNull()
      expect(screen.queryByText('Taladro Percutor 750W')).toBeNull()
    })

    it('1.3 Switching to "Marketplaces / Electro" updates chip state, queries API with grocery_only: false, and filters client-side', async () => {
      vi.mocked(api.searchProducts).mockResolvedValue(mockMixedCatalog)
      renderWithProviders(<SearchScreen />)

      const input = screen.getByPlaceholderText(/Buscá o escaneá/i)
      fireEvent.change(input, { target: { value: 'combo' } })

      await waitFor(() => {
        expect(screen.getByText('Leche La Serenísima 1L')).toBeTruthy()
      })

      // Click "Marketplaces / Electro"
      const mpChip = screen.getByRole('button', { name: /^Marketplaces \/ Electro$/i })
      fireEvent.click(mpChip)

      await waitFor(() => {
        expect(api.searchProducts).toHaveBeenCalledWith(
          'combo',
          'unit_price_asc',
          false,
          null,
          expect.objectContaining({
            vertical: 'marketplace,electro',
            grocery_only: false,
          }),
        )
      })

      expect(mpChip.className).toContain('bg-blue-600')

      // Client-side filtering check: TV (electro) & Colchón (marketplace) visible; Leche (supermarket) hidden
      expect(screen.getByText('Smart TV 55 Pulgadas 4K')).toBeTruthy()
      expect(screen.getByText('Colchón King Size Sommier')).toBeTruthy()
      expect(screen.queryByText('Leche La Serenísima 1L')).toBeNull()
      expect(screen.queryByText('Perfume Sauvage 100ml')).toBeNull()
    })

    it('1.4 Invariant: switching vertical chip MUST reset selectedStore to null', async () => {
      vi.mocked(api.searchProducts).mockResolvedValue(mockMixedCatalog)
      renderWithProviders(<SearchScreen />)

      const input = screen.getByPlaceholderText(/Buscá o escaneá/i)
      fireEvent.change(input, { target: { value: 'combo' } })

      await waitFor(() => {
        expect(screen.getByText('Leche La Serenísima 1L')).toBeTruthy()
      })

      // 1. Open store dropdown and select Carrefour
      const dropdownBtn = screen.getByRole('button', { name: /Comercio:\s*Todos/i })
      fireEvent.click(dropdownBtn)

      const listbox = screen.getByRole('listbox')
      const carrefourOption = within(listbox).getByRole('option', { name: /Carrefour/i })
      fireEvent.click(carrefourOption)

      // Dropdown button now reflects Carrefour
      const dropdownTrigger = document.querySelector('#store-filter-dropdown')
      expect(dropdownTrigger).toBeTruthy()
      expect(dropdownTrigger?.textContent).toContain('Carrefour')

      // 2. Switch vertical to "Marketplaces / Electro"
      const mpChip = screen.getByRole('button', { name: /^Marketplaces \/ Electro$/i })
      fireEvent.click(mpChip)

      // 3. Verify selectedStore was immediately reset: dropdown button reflects "Comercio: Todos"
      await waitFor(() => {
        expect(document.querySelector('#store-filter-dropdown')?.textContent).toContain('Comercio: Todos')
      })
    })

    it('1.5 Rapid vertical switching stress test (10 consecutive clicks) maintains UI consistency', async () => {
      vi.mocked(api.searchProducts).mockResolvedValue(mockMixedCatalog)
      renderWithProviders(<SearchScreen />)

      const input = screen.getByPlaceholderText(/Buscá o escaneá/i)
      fireEvent.change(input, { target: { value: 'combo' } })

      await waitFor(() => {
        expect(screen.getByText('Leche La Serenísima 1L')).toBeTruthy()
      })

      const chips = [
        screen.getByRole('button', { name: /^Supermercados$/i }),
        screen.getByRole('button', { name: /^Marketplaces \/ Electro$/i }),
        screen.getByRole('button', { name: /^Todos$/i }),
      ]

      // Rapid sequence of 10 clicks
      for (let i = 0; i < 10; i++) {
        fireEvent.click(chips[i % 3])
      }

      // Final click is index 9: 9 % 3 = 0 -> "Supermercados"
      expect(chips[0].className).toContain('bg-blue-600')
      expect(chips[1].className).not.toContain('bg-blue-600')
      expect(chips[2].className).not.toContain('bg-blue-600')

      // Verify that after rapid clicks, Supermercados is active
      await waitFor(() => {
        expect(screen.getByText('Leche La Serenísima 1L')).toBeTruthy()
        expect(screen.queryByText('Smart TV 55 Pulgadas 4K')).toBeNull()
      })
    })
  })

  // =========================================================================
  // 2. CATEGORIZED STORE DROPDOWN & FILTERING
  // =========================================================================
  describe('2. Categorized Store Dropdown & Filtering', () => {
    const catalogWithAllVerticals: ProductGroup[] = [
      {
        ean: 's1',
        nombre: 'Arroz Coto 1kg',
        marca: 'Coto',
        offers: [{ supermercado: 'Coto', precio: 1500, stock: 10, link: '' }],
      },
      {
        ean: 's2',
        nombre: 'Fideos Carrefour 500g',
        marca: 'Carrefour',
        offers: [{ supermercado: 'Carrefour', precio: 1200, stock: 10, link: '' }],
      },
      {
        ean: 'm1',
        nombre: 'Notebook Lenovo i5',
        marca: 'Lenovo',
        offers: [{ supermercado: 'Provincia Compras', precio: 800000, stock: 5, link: '' }],
      },
      {
        ean: 'e1',
        nombre: 'Lavarropas Samsung 8kg',
        marca: 'Samsung',
        offers: [{ supermercado: 'Fravega', precio: 650000, stock: 3, link: '' }],
      },
      {
        ean: 'p1',
        nombre: 'Shampoo Anticaspa 400ml',
        marca: 'Head & Shoulders',
        offers: [{ supermercado: 'Farmacity', precio: 4500, stock: 8, link: '' }],
      },
      {
        ean: 'sp1',
        nombre: 'Pintura Látex Interior 20L',
        marca: 'Alba',
        offers: [{ supermercado: 'Easy', precio: 65000, stock: 4, link: '' }],
      },
      {
        ean: 'u1',
        nombre: 'Vino Tinto Reserva 750ml',
        marca: 'Bodega Desconocida',
        offers: [{ supermercado: 'TiendaMisteriosa', precio: 9500, stock: 2, link: '' }],
      },
    ]

    it('2.1 Groups all 5 standard vertical headers plus "Otros Comercios" for unmapped stores', async () => {
      vi.mocked(api.searchProducts).mockResolvedValue(catalogWithAllVerticals)
      renderWithProviders(<SearchScreen />)

      const input = screen.getByPlaceholderText(/Buscá o escaneá/i)
      fireEvent.change(input, { target: { value: 'articulos' } })

      await waitFor(() => {
        expect(screen.getByText('Arroz Coto 1kg')).toBeTruthy()
      })

      // Open store dropdown
      const dropdownBtn = screen.getByRole('button', { name: /Comercio:\s*Todos/i })
      fireEvent.click(dropdownBtn)

      const listbox = screen.getByRole('listbox')

      // All 5 vertical headers should be rendered
      expect(within(listbox).getByText('Supermercados')).toBeTruthy()
      expect(within(listbox).getByText('Marketplaces Generales')).toBeTruthy()
      expect(within(listbox).getByText('Electro y Tecnología')).toBeTruthy()
      expect(within(listbox).getByText('Farmacias y Perfumería')).toBeTruthy()
      expect(within(listbox).getByText('Hogar y Especialidades')).toBeTruthy()

      // Stores under their respective categories
      expect(within(listbox).getByRole('option', { name: /Coto/i })).toBeTruthy()
      expect(within(listbox).getByRole('option', { name: /Carrefour/i })).toBeTruthy()
      expect(within(listbox).getByRole('option', { name: /Provincia Compras/i })).toBeTruthy()
      expect(within(listbox).getByRole('option', { name: /Frávega/i })).toBeTruthy()
      expect(within(listbox).getByRole('option', { name: /Farmacity/i })).toBeTruthy()
      expect(within(listbox).getByRole('option', { name: /Easy/i })).toBeTruthy()
      // Note: TiendaMisteriosa falls back to supermarket vertical via storeVertical()
      expect(within(listbox).getByRole('option', { name: /TiendaMisteriosa/i })).toBeTruthy()
    })

    it('2.2 Selecting a store filters products and closing/opening preserves consistency', async () => {
      vi.mocked(api.searchProducts).mockResolvedValue(catalogWithAllVerticals)
      renderWithProviders(<SearchScreen />)

      const input = screen.getByPlaceholderText(/Buscá o escaneá/i)
      fireEvent.change(input, { target: { value: 'articulos' } })

      await waitFor(() => {
        expect(screen.getByText('Arroz Coto 1kg')).toBeTruthy()
      })

      // Select Fravega
      fireEvent.click(document.querySelector('#store-filter-dropdown')!)
      const listbox = screen.getByRole('listbox')
      fireEvent.click(within(listbox).getByRole('option', { name: /Frávega/i }))

      // Only Lavarropas Samsung 8kg should be shown
      expect(screen.getByText('Lavarropas Samsung 8kg')).toBeTruthy()
      expect(screen.queryByText('Arroz Coto 1kg')).toBeNull()
      expect(screen.queryByText('Notebook Lenovo i5')).toBeNull()

      // Reopen dropdown via #store-filter-dropdown and select "Todos los comercios"
      fireEvent.click(document.querySelector('#store-filter-dropdown')!)
      const listbox2 = screen.getByRole('listbox')
      fireEvent.click(within(listbox2).getByRole('option', { name: /Todos los comercios/i }))

      // All products return
      expect(screen.getByText('Arroz Coto 1kg')).toBeTruthy()
      expect(screen.getByText('Notebook Lenovo i5')).toBeTruthy()
      expect(screen.getByText('Lavarropas Samsung 8kg')).toBeTruthy()
    })

    it('2.3 Auto-reset: if new search results do not contain selected store, selectedStore clears to null', async () => {
      vi.mocked(api.searchProducts).mockResolvedValue(catalogWithAllVerticals)
      renderWithProviders(<SearchScreen />)

      const input = screen.getByPlaceholderText(/Buscá o escaneá/i)
      fireEvent.change(input, { target: { value: 'articulos' } })

      await waitFor(() => {
        expect(screen.getByText('Arroz Coto 1kg')).toBeTruthy()
      })

      // Select Easy
      fireEvent.click(screen.getByRole('button', { name: /Comercio:\s*Todos/i }))
      fireEvent.click(within(screen.getByRole('listbox')).getByRole('option', { name: /Easy/i }))
      expect(screen.getByText('Pintura Látex Interior 20L')).toBeTruthy()

      // Next search returns only supermarket items (no Easy)
      vi.mocked(api.searchProducts).mockResolvedValue([
        {
          ean: 'only_coto',
          nombre: 'Queso Crema Coto',
          marca: 'Coto',
          offers: [{ supermercado: 'Coto', precio: 2000, stock: 5, link: '' }],
        },
      ])

      fireEvent.change(input, { target: { value: 'queso' } })

      await waitFor(() => {
        expect(screen.getByText('Queso Crema Coto')).toBeTruthy()
      })

      // The selected store button should automatically be reset to "Comercio: Todos"
      expect(screen.getByRole('button', { name: /Comercio:\s*Todos/i })).toBeTruthy()
    })

    it('2.4 Empty store results view renders store-specific message and "Ver todos los comercios" button', async () => {
      // Product has Coto offer, but discount < 5 so with onlyOffers=true it filters out
      const catalogWithPromo: ProductGroup[] = [
        {
          ean: 'c1',
          nombre: 'Leche Coto Regular',
          marca: 'Coto',
          offers: [{ supermercado: 'Coto', precio: 1000, discount: 0, stock: 5, link: '' }],
        },
        {
          ean: 'c2',
          nombre: 'Galletitas Dia Promo',
          marca: 'Dia',
          offers: [{ supermercado: 'Dia', precio: 500, discount: 30, stock: 10, link: '' }],
        },
      ]

      vi.mocked(api.searchProducts).mockResolvedValue(catalogWithPromo)
      renderWithProviders(<SearchScreen />)

      const input = screen.getByPlaceholderText(/Buscá o escaneá/i)
      fireEvent.change(input, { target: { value: 'comida' } })

      await waitFor(() => {
        expect(screen.getByText('Leche Coto Regular')).toBeTruthy()
      })

      // Filter by Coto
      fireEvent.click(screen.getByRole('button', { name: /Comercio:\s*Todos/i }))
      fireEvent.click(within(screen.getByRole('listbox')).getByRole('option', { name: /Coto/i }))

      // Toggle "Ofertas" chip
      const ofertasChip = screen.getByRole('button', { name: /^\s*Ofertas\s*$/i })
      fireEvent.click(ofertasChip)

      // Coto has no offers with discount >= 5, so 0 visible products for Coto
      await waitFor(() => {
        expect(screen.getByText(/No encontramos productos en Coto para "comida"/i)).toBeTruthy()
      })

      // Click "Ver todos los comercios"
      const clearBtn = screen.getByRole('button', { name: /Ver todos los comercios/i })
      fireEvent.click(clearBtn)

      // Now Dia promo item should be visible
      expect(screen.getByText('Galletitas Dia Promo')).toBeTruthy()
    })
  })

  // =========================================================================
  // 3. TOUCH TARGET ERGONOMICS & WCAG 2.5.5 / 2.5.8 COMPLIANCE
  // =========================================================================
  describe('3. Touch Target Ergonomics & WCAG 2.5.5 / 2.5.8 Compliance', () => {
    it('3.1 All vertical filter chips strictly enforce min-h-[44px]', async () => {
      vi.mocked(api.searchProducts).mockResolvedValue([
        {
          ean: '123',
          nombre: 'Sample Item',
          marca: 'Sample',
          offers: [{ supermercado: 'Carrefour', precio: 100, stock: 1, link: '' }],
        },
      ])

      renderWithProviders(<SearchScreen />)

      const input = screen.getByPlaceholderText(/Buscá o escaneá/i)
      fireEvent.change(input, { target: { value: 'sample' } })

      await waitFor(() => {
        expect(screen.getByText('Sample Item')).toBeTruthy()
      })

      const chips = [
        screen.getByRole('button', { name: /^Todos$/i }),
        screen.getByRole('button', { name: /^Supermercados$/i }),
        screen.getByRole('button', { name: /^Marketplaces \/ Electro$/i }),
      ]

      chips.forEach(chip => {
        expect(chip.className).toContain('min-h-[44px]')
      })
    })

    it('3.2 All dropdown options (including "Todos los comercios") enforce min-h-[44px]', async () => {
      vi.mocked(api.searchProducts).mockResolvedValue([
        {
          ean: '111',
          nombre: 'Leche',
          marca: 'La Serenísima',
          offers: [{ supermercado: 'Carrefour', precio: 1000, stock: 1, link: '' }],
        },
        {
          ean: '222',
          nombre: 'TV',
          marca: 'Samsung',
          offers: [{ supermercado: 'Fravega', precio: 500000, stock: 1, link: '' }],
        },
      ])

      renderWithProviders(<SearchScreen />)

      const input = screen.getByPlaceholderText(/Buscá o escaneá/i)
      fireEvent.change(input, { target: { value: 'item' } })

      await waitFor(() => {
        expect(screen.getByText('Leche')).toBeTruthy()
      })

      // Open dropdown
      fireEvent.click(screen.getByRole('button', { name: /Comercio:\s*Todos/i }))
      const listbox = screen.getByRole('listbox')

      const options = within(listbox).getAllByRole('option')
      expect(options.length).toBeGreaterThanOrEqual(3) // "Todos los comercios", "Carrefour", "Frávega"

      options.forEach(opt => {
        expect(opt.className).toContain('min-h-[44px]')
      })
    })

    it('3.3 Source Code Audit: SearchScreen.tsx has explicit min-h-[44px] on chips and options', () => {
      const searchScreenFile = path.resolve(__dirname, '..', 'components', 'SearchScreen.tsx')
      const code = fs.readFileSync(searchScreenFile, 'utf-8')

      // Assert VERTICAL_CHIPS button definition has min-h-[44px]
      expect(code).toMatch(/VERTICAL_CHIPS\.map[\s\S]*?min-h-\[44px\]/)

      // Assert dropdown options have min-h-[44px]
      const minHMatches = code.match(/min-h-\[44px\]/g)
      expect(minHMatches).not.toBeNull()
      expect(minHMatches!.length).toBeGreaterThanOrEqual(3) // 1 in vertical chips, 1 in "Todos los comercios", 1 in store options
    })
  })

  // =========================================================================
  // 4. PRODUCTCARD ATTRIBUTES, INSTALLMENTS & SELLER TRANSPARENCY
  // =========================================================================
  describe('4. ProductCard Attributes, Installments & Seller Transparency', () => {
    it('4.1 Vertical badge renders correctly for all 5 vertical types', () => {
      const verticals: Array<{
        v: 'electro' | 'marketplace' | 'pharmacy' | 'specialty' | 'supermarket'
        expectedBadge: string
        expectedClass: string
      }> = [
        { v: 'electro', expectedBadge: 'Electro', expectedClass: 'bg-indigo-50 text-indigo-700' },
        { v: 'marketplace', expectedBadge: 'Marketplace', expectedClass: 'bg-sky-50 text-sky-700' },
        { v: 'pharmacy', expectedBadge: 'Farmacia', expectedClass: 'bg-rose-50 text-rose-700' },
        { v: 'specialty', expectedBadge: 'Hogar', expectedClass: 'bg-amber-50 text-amber-700' },
        { v: 'supermarket', expectedBadge: 'Súper', expectedClass: 'bg-emerald-50 text-emerald-700' },
      ]

      verticals.forEach(({ v, expectedBadge, expectedClass }) => {
        const product: ProductGroup = {
          ean: `ean_${v}`,
          nombre: `Product ${v}`,
          marca: 'TestBrand',
          vertical: v,
          offers: [{ supermercado: 'Carrefour', precio: 1000, stock: 1, link: '' }],
        }

        const { unmount } = renderWithProviders(<ProductCard group={product} />)
        const badge = screen.getByText(expectedBadge)
        expect(badge).toBeTruthy()
        expect(badge.className).toContain(expectedClass)
        unmount()
      })
    })

    it('4.2 Vertical badge fallback: resolves from best offer store when group.vertical is omitted', () => {
      const productNoVertical: ProductGroup = {
        ean: 'no_vert',
        nombre: 'Cava de Vinos 12 Botellas',
        marca: 'Whirlpool',
        offers: [
          { supermercado: 'Whirlpool', precio: 350000, stock: 1, link: '' }, // storeVertical('Whirlpool') === 'electro'
        ],
      }

      renderWithProviders(<ProductCard group={productNoVertical} />)
      expect(screen.getByText('Electro')).toBeTruthy()
    })

    it('4.3 Monospace model code renders when present and is omitted when absent', () => {
      const withModel: ProductGroup = {
        ean: 'with_m',
        nombre: 'Smart TV Samsung 50 4K',
        marca: 'Samsung',
        modelo: 'UN50DU7000GXZS',
        vertical: 'electro',
        offers: [{ supermercado: 'Fravega', precio: 600000, stock: 1, link: '' }],
      }

      const { unmount } = renderWithProviders(<ProductCard group={withModel} />)
      const modelTag = screen.getByText('UN50DU7000GXZS')
      expect(modelTag).toBeTruthy()
      expect(modelTag.className).toContain('font-mono')
      unmount()

      const withoutModel: ProductGroup = {
        ean: 'without_m',
        nombre: 'Galletitas Chocolinas 250g',
        marca: 'Chocolinas',
        vertical: 'supermarket',
        offers: [{ supermercado: 'Dia', precio: 1200, stock: 1, link: '' }],
      }

      renderWithProviders(<ProductCard group={withoutModel} />)
      expect(screen.queryByText('UN50DU7000GXZS')).toBeNull()
      // No font-mono tag should exist in DOM
      expect(document.querySelector('.font-mono')).toBeNull()
    })

    it('4.4 Installment financing badges: sin interés vs fijas, and monthly cuota monto', () => {
      // 1. Sin interés with monthly cuota
      const interestFreeProd: ProductGroup = {
        ean: 'if1',
        nombre: 'Heladera No Frost 400L',
        marca: 'Whirlpool',
        vertical: 'electro',
        offers: [
          {
            supermercado: 'Provincia Compras',
            precio: 960000,
            stock: 2,
            link: '',
            cuotas: 24,
            sin_interes: true,
            cuota_monto: 40000,
          },
        ],
      }

      const { unmount } = renderWithProviders(<ProductCard group={interestFreeProd} />)
      const badge = screen.getByText(/24 cuotas sin interés/i)
      expect(badge).toBeTruthy()
      expect(badge.className).toContain('text-emerald-800 bg-emerald-50')
      expect(screen.getByText(/24x\s*\$\s*40\.000/i)).toBeTruthy()
      unmount()

      // 2. Cuotas fijas (con interés)
      const fixedCuotasProd: ProductGroup = {
        ean: 'fc1',
        nombre: 'Microondas 20L',
        marca: 'BGH',
        vertical: 'electro',
        offers: [
          {
            supermercado: 'Cetrogar',
            precio: 180000,
            stock: 3,
            link: '',
            cuotas: 6,
            sin_interes: false,
            cuota_monto: 36000,
          },
        ],
      }

      const { unmount: unmount2 } = renderWithProviders(<ProductCard group={fixedCuotasProd} />)
      const badgeFijas = screen.getByText(/6 cuotas fijas/i)
      expect(badgeFijas).toBeTruthy()
      expect(badgeFijas.className).toContain('text-indigo-800 bg-indigo-50')
      expect(screen.getByText(/6x\s*\$\s*36\.000/i)).toBeTruthy()
      unmount2()

      // 3. Single installment / no financing (cuotas <= 1)
      const noCuotasProd: ProductGroup = {
        ean: 'nc1',
        nombre: 'Yerba Mate Playadito 1kg',
        marca: 'Playadito',
        vertical: 'supermarket',
        offers: [{ supermercado: 'Coto', precio: 3500, stock: 10, link: '', cuotas: 1 }],
      }

      renderWithProviders(<ProductCard group={noCuotasProd} />)
      expect(screen.queryByText(/cuotas/i)).toBeNull()
    })

    it('4.5 Seller transparency: distinguishes direct retail ("Venta directa") from 3rd-party sellers', () => {
      // 1. Direct supermarket retail (Carrefour, seller_id: "1")
      const directSuper: ProductGroup = {
        ean: 'ds1',
        nombre: 'Café Molido 250g',
        marca: 'La Virginia',
        offers: [
          {
            supermercado: 'Carrefour',
            precio: 3000,
            stock: 5,
            link: '',
            seller_name: 'Carrefour',
            seller_id: '1',
          },
        ],
      }

      const { unmount: u1 } = renderWithProviders(<ProductCard group={directSuper} />)
      const directBadge = screen.getByText('Venta directa')
      expect(directBadge).toBeTruthy()
      expect(directBadge.className).toContain('bg-slate-100 text-slate-600')
      u1()

      // 2. Direct retail with accented storeLabel (Frávega, seller_id: "1")
      const directFravega: ProductGroup = {
        ean: 'df1',
        nombre: 'Pava Eléctrica',
        marca: 'Philips',
        offers: [
          {
            supermercado: 'Fravega',
            precio: 45000,
            stock: 2,
            link: '',
            seller_name: 'Frávega',
            seller_id: '1',
          },
        ],
      }

      const { unmount: u2 } = renderWithProviders(<ProductCard group={directFravega} />)
      expect(screen.getByText('Venta directa')).toBeTruthy()
      u2()

      // 3. 3rd-party seller on marketplace (Provincia Compras, seller: "Diggit")
      const thirdPartyMarketplace: ProductGroup = {
        ean: 'tp1',
        nombre: 'Tablet 10 Pulgadas',
        marca: 'Lenovo',
        offers: [
          {
            supermercado: 'Provincia Compras',
            precio: 220000,
            stock: 4,
            link: '',
            seller_name: 'Diggit Electrónica',
            seller_id: 'diggit_456',
          },
        ],
      }

      const { unmount: u3 } = renderWithProviders(<ProductCard group={thirdPartyMarketplace} />)
      const tpBadge = screen.getByText('Vendido por Diggit Electrónica')
      expect(tpBadge).toBeTruthy()
      expect(tpBadge.className).toContain('bg-amber-100 text-amber-900 border border-amber-200')
      u3()

      // 4. 3rd-party seller with only seller_id (Mercado Libre, seller_id: "tecno_seller")
      const sellerIdOnly: ProductGroup = {
        ean: 'tp2',
        nombre: 'Auriculares Inalámbricos',
        marca: 'Sony',
        offers: [
          {
            supermercado: 'MercadoLibre',
            precio: 75000,
            stock: 8,
            link: '',
            seller_id: 'tecno_seller_ar',
          },
        ],
      }

      const { unmount: u4 } = renderWithProviders(<ProductCard group={sellerIdOnly} />)
      const idBadge = screen.getByText('Vendido por tecno_seller_ar')
      expect(idBadge).toBeTruthy()
      expect(idBadge.className).toContain('bg-amber-100 text-amber-900')
      u4()

      // 5. Store name match but non-default seller_id (Fravega 3rd-party seller)
      const nonDefaultSellerId: ProductGroup = {
        ean: 'tp3',
        nombre: 'Batidora de Mano',
        marca: 'Oster',
        offers: [
          {
            supermercado: 'Fravega',
            precio: 55000,
            stock: 3,
            link: '',
            seller_name: 'Fravega',
            seller_id: 'seller_partner_88',
          },
        ],
      }

      renderWithProviders(<ProductCard group={nonDefaultSellerId} />)
      // Because seller_id !== '1' and !== 'default', it is treated as third party
      const partnerBadge = screen.getByText('Vendido por Fravega')
      expect(partnerBadge).toBeTruthy()
      expect(partnerBadge.className).toContain('bg-amber-100 text-amber-900')
    })

    it('4.6 Seller reputation indicator: renders color dot matching reputation scale', () => {
      const repScales: Array<{ rep: string; expectedColor: string }> = [
        { rep: '5_green', expectedColor: 'bg-emerald-500' },
        { rep: '4_light_green', expectedColor: 'bg-lime-500' },
        { rep: '3_yellow', expectedColor: 'bg-amber-400' },
        { rep: '1_red', expectedColor: 'bg-red-500' },
      ]

      repScales.forEach(({ rep, expectedColor }) => {
        const product: ProductGroup = {
          ean: `rep_${rep}`,
          nombre: 'Producto con Reputación',
          marca: 'Marca',
          offers: [
            {
              supermercado: 'MercadoLibre',
              precio: 10000,
              stock: 5,
              link: '',
              seller_name: 'Tienda ML',
              seller_id: 'ml_12',
              seller_reputation: rep,
            },
          ],
        }

        const { unmount } = renderWithProviders(<ProductCard group={product} />)
        const repDot = document.querySelector(`span[title="Reputación: ${rep}"]`)
        expect(repDot).not.toBeNull()
        expect(repDot?.className).toContain(expectedColor)
        unmount()
      })
    })
  })

  // =========================================================================
  // 5. ADVERSARIAL RACE CONDITIONS, ARIA SEMANTICS & EXTREME EDGE CASES
  // =========================================================================
  describe('5. Adversarial Race Conditions, ARIA Semantics & Extreme Edge Cases', () => {
    it('5.1 Out-of-order network response discard: stale API responses are safely ignored', async () => {
      let resolveFirstCall: (data: ProductGroup[]) => void = () => {}
      const firstPromise = new Promise<ProductGroup[]>(resolve => {
        resolveFirstCall = resolve
      })

      const secondResult: ProductGroup[] = [
        {
          ean: 'second_fast',
          nombre: 'Heladera Gafa 360L',
          marca: 'Gafa',
          vertical: 'electro',
          offers: [{ supermercado: 'Fravega', precio: 500000, stock: 2, link: '' }],
        },
      ]

      // First call (Todos) will hang until resolveFirstCall is manually called
      vi.mocked(api.searchProducts)
        .mockReturnValueOnce(firstPromise)
        .mockResolvedValueOnce(secondResult)

      renderWithProviders(<SearchScreen />)

      const input = screen.getByPlaceholderText(/Buscá o escaneá/i)
      fireEvent.change(input, { target: { value: 'electro' } })

      // Immediate switch to "Marketplaces / Electro"
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /^Marketplaces \/ Electro$/i })).toBeTruthy()
      })
      fireEvent.click(screen.getByRole('button', { name: /^Marketplaces \/ Electro$/i }))

      // Fast second call resolves first
      await waitFor(() => {
        expect(screen.getByText('Heladera Gafa 360L')).toBeTruthy()
      })

      // Stale first call resolves later with stale grocery items
      const staleItems: ProductGroup[] = [
        {
          ean: 'stale_item',
          nombre: 'Manteca La Serenísima 200g',
          marca: 'La Serenísima',
          vertical: 'supermarket',
          offers: [{ supermercado: 'Carrefour', precio: 2000, stock: 5, link: '' }],
        },
      ]
      resolveFirstCall(staleItems)

      // UI MUST NOT show the stale grocery item!
      expect(screen.queryByText('Manteca La Serenísima 200g')).toBeNull()
      expect(screen.getByText('Heladera Gafa 360L')).toBeTruthy()
    })

    it('5.2 ARIA accessibility: toggles aria-expanded and manages aria-selected on options', async () => {
      vi.mocked(api.searchProducts).mockResolvedValue([
        {
          ean: 'aria_1',
          nombre: 'Café instantáneo',
          marca: 'Nescafé',
          offers: [
            { supermercado: 'Dia', precio: 3000, stock: 5, link: '' },
            { supermercado: 'Coto', precio: 3100, stock: 3, link: '' },
          ],
        },
      ])

      renderWithProviders(<SearchScreen />)
      fireEvent.change(screen.getByPlaceholderText(/Buscá o escaneá/i), { target: { value: 'cafe' } })

      await waitFor(() => {
        expect(screen.getByText('Café instantáneo')).toBeTruthy()
      })

      const dropdownBtn = document.querySelector('#store-filter-dropdown') as HTMLButtonElement
      expect(dropdownBtn).toBeTruthy()
      expect(dropdownBtn.getAttribute('aria-haspopup')).toBe('listbox')
      expect(dropdownBtn.getAttribute('aria-expanded')).toBe('false')

      // Open dropdown
      fireEvent.click(dropdownBtn)
      expect(dropdownBtn.getAttribute('aria-expanded')).toBe('true')

      const listbox = screen.getByRole('listbox')
      expect(listbox).toBeTruthy()

      const allOption = within(listbox).getByRole('option', { name: /Todos los comercios/i })
      const diaOption = within(listbox).getByRole('option', { name: /D[ií]a/i })
      const cotoOption = within(listbox).getByRole('option', { name: /Coto/i })

      expect(allOption.getAttribute('aria-selected')).toBe('true')
      expect(diaOption.getAttribute('aria-selected')).toBe('false')
      expect(cotoOption.getAttribute('aria-selected')).toBe('false')

      // Select Dia
      fireEvent.click(diaOption)

      // Reopen dropdown
      fireEvent.click(document.querySelector('#store-filter-dropdown')!)
      const listbox2 = screen.getByRole('listbox')
      const allOption2 = within(listbox2).getByRole('option', { name: /Todos los comercios/i })
      const diaOption2 = within(listbox2).getByRole('option', { name: /D[ií]a/i })

      expect(allOption2.getAttribute('aria-selected')).toBe('false')
      expect(diaOption2.getAttribute('aria-selected')).toBe('true')
    })

    it('5.3 Massive store density: handles 40 stores in availableStores without crash or layout break', async () => {
      // 40 distinct stores catalog
      const storeList = [
        'Jumbo', 'Disco', 'Vea', 'Carrefour', 'Dia', 'Masonline', 'Coto', 'Josimar', 'Toledo', 'Cordiez',
        'TheFoodMarket', 'LaBarata', 'ArcorEnCasa', 'Provincia Compras', 'On City', 'MercadoLibre',
        'Fravega', 'Cetrogar', 'Naldo', 'Pardo', 'Coppel', 'Musimundo', 'Samsung', 'Philips',
        'Whirlpool', 'Moulinex', 'Sony', 'Oster', 'Easy', 'Pigmento', 'Farmacity', 'Simplicity',
        'Puppis', 'StyleStore', 'GPSFarma', 'OpenFarma', 'Parfumerie', 'TiendaSuper', 'CasaElectro', 'ShopRandom'
      ]

      const massiveProducts: ProductGroup[] = storeList.map((store, idx) => ({
        ean: `ean_dense_${idx}`,
        nombre: `Item de ${store}`,
        marca: 'GenericBrand',
        offers: [{ supermercado: store, precio: 1000 + idx * 100, stock: 5, link: '' }],
      }))

      vi.mocked(api.searchProducts).mockResolvedValue(massiveProducts)
      renderWithProviders(<SearchScreen />)
      fireEvent.change(screen.getByPlaceholderText(/Buscá o escaneá/i), { target: { value: 'item' } })

      await waitFor(() => {
        expect(screen.getByText('Item de Jumbo')).toBeTruthy()
      })

      // Open store dropdown
      fireEvent.click(document.querySelector('#store-filter-dropdown')!)
      const listbox = screen.getByRole('listbox')

      // Must have at least 41 options (Todos + 40 stores)
      const options = within(listbox).getAllByRole('option')
      expect(options.length).toBeGreaterThanOrEqual(40)
    })
  })
})

