import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ImportSharedListModal from '../ImportSharedListModal'
import HabitualListManager from '../HabitualListManager'
import ListScreen from '../ListScreen'
import { CartProvider } from '../../cart/CartContext'
import { HabitualListProvider } from '../../cart/HabitualListContext'
import { LocationProvider } from '../../location/LocationContext'
import { BenefitsProvider } from '../../benefits/BenefitsContext'
import type { SharedItem, HabitualList } from '../../types'

vi.mock('../../api', async () => {
  const actual = await vi.importActual('../../api')
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

describe('Recurrence Components & Import UI', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  afterEach(() => {
    localStorage.clear()
  })

  describe('ImportSharedListModal', () => {
    const sharedItems: SharedItem[] = [
      { ean: '7791234567890', qty: 2 },
      { ean: '7790987654321', qty: 3 },
    ]

    it('1. renders shared list details, current cart warning, and executes callbacks', () => {
      const onMerge = vi.fn()
      const onReplace = vi.fn()
      const onDismiss = vi.fn()

      render(
        <ImportSharedListModal
          isOpen={true}
          sharedItems={sharedItems}
          currentCartCount={4}
          onMerge={onMerge}
          onReplace={onReplace}
          onDismiss={onDismiss}
        />,
      )

      expect(screen.getByText(/¡Lista compartida recibida!/i)).toBeTruthy()
      expect(screen.getByText(/2 productos/i)).toBeTruthy()
      expect(screen.getByText(/5 unidades/i)).toBeTruthy()
      expect(screen.getByText(/Actualmente tenés/i)).toBeTruthy()

      // Click onMerge
      const mergeBtn = screen.getByRole('button', { name: /sumar a mi changuito actual/i })
      expect(mergeBtn.className).toContain('min-h-[48px]')
      fireEvent.click(mergeBtn)
      expect(onMerge).toHaveBeenCalledTimes(1)

      // Click onReplace
      const replaceBtn = screen.getByRole('button', { name: /reemplazar mi changuito/i })
      expect(replaceBtn.className).toContain('min-h-[48px]')
      fireEvent.click(replaceBtn)
      expect(onReplace).toHaveBeenCalledTimes(1)

      // Click onDismiss
      const dismissBtn = screen.getByRole('button', { name: /ignorar y mantener mi lista actual/i })
      expect(dismissBtn.className).toContain('min-h-[44px]')
      fireEvent.click(dismissBtn)
      expect(onDismiss).toHaveBeenCalledTimes(1)
    })

    it('2. hides replace button if active cart is completely empty (0 items)', () => {
      render(
        <ImportSharedListModal
          isOpen={true}
          sharedItems={sharedItems}
          currentCartCount={0}
          onMerge={vi.fn()}
          onReplace={vi.fn()}
          onDismiss={vi.fn()}
        />,
      )

      expect(screen.queryByRole('button', { name: /reemplazar mi changuito/i })).toBeNull()
      expect(screen.getByRole('button', { name: /sumar a mi changuito actual/i })).toBeTruthy()
    })
  })

  describe('HabitualListManager Widget', () => {
    it('3. displays Termómetro de Ahorro, metric pills, and expands controls with >=44px touch targets', () => {
      // Setup saved habitual list and history in localStorage
      const habitual: HabitualList = {
        version: '1.0',
        updated_at: '2026-10-26T12:00:00Z',
        name: 'Mi compra de siempre',
        items: [{ ean: '7791234567890', nombre: 'Leche La Serenísima', imagen: '', qty: 2, added_at: '2026-10-26T12:00:00Z' }],
      }
      localStorage.setItem('sv_habitual_v1', JSON.stringify(habitual))

      const history = [
        {
          id: 's1',
          timestamp: '2026-10-15T12:00:00Z',
          items_count: 1,
          total_units: 2,
          total_comodidad: 25000,
          total_ahorro: 20000,
          ahorro_ars: 5000,
          savings_pct: 20.0,
        },
        {
          id: 's2',
          timestamp: '2026-10-22T12:00:00Z',
          items_count: 1,
          total_units: 2,
          total_comodidad: 26000,
          total_ahorro: 20600,
          ahorro_ars: 5400,
          savings_pct: 20.7,
        },
      ]
      localStorage.setItem('sv_basket_history_v1', JSON.stringify(history))

      render(
        <CartProvider>
          <HabitualListProvider>
            <HabitualListManager />
          </HabitualListProvider>
        </CartProvider>,
      )

      expect(screen.getByText('Termómetro de Ahorro')).toBeTruthy()
      expect(screen.getByText(/2 cotizaciones registradas/i)).toBeTruthy()
      // Cumulative savings ($10.400)
      expect(screen.getByText(/\$\s*10\.400/)).toBeTruthy()

      // Expand details
      const detailsBtn = screen.getByRole('button', { name: /ver detalles del termómetro de ahorro/i })
      expect(detailsBtn.className).toContain('min-h-[44px]')
      fireEvent.click(detailsBtn)

      // Sparkline SVG should be visible
      expect(screen.getByLabelText(/gráfico de evolución histórica de la canasta/i)).toBeTruthy()
    })
  })

  describe('ListScreen Empty Cart State', () => {
    it('4. displays clean empty cart screen without resurrecting deleted items', () => {
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

      expect(screen.getByText('Tu carrito está vacío')).toBeTruthy()
      expect(screen.getByRole('button', { name: /explorar productos/i })).toBeTruthy()
    })
  })
})
