import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import SmartCartHero from '../SmartCartHero'
import ListScreen from '../ListScreen'
import { CartProvider } from '../../cart/CartContext'
import { LocationProvider } from '../../location/LocationContext'
import { BenefitsProvider } from '../../benefits/BenefitsContext'
import * as api from '../../api'
import type { OptimizePlan, ScenarioPreview } from '../../types'

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

describe('Adversarial Stress Test Suite: Extreme Edge Cases & Race Conditions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('A1. Extreme financial values: handles 9-figure numbers, 0, and fractional values without overflow', () => {
    const extremePreview: ScenarioPreview = {
      mode: 'ahorro',
      title: 'Opción más barata con título excesivamente largo para testear desbordes tipográficos',
      tagline: 'Tagline extraordinariamente extensa para verificar contención flexbox',
      total: 999999999.75,
      ahorro_vs_comoda: 150000000,
      ahorro_vs_regular: 200000000,
      ahorro_pct: 15.0,
      supermercados_count: 3,
      covered_items: 2,
      total_items: 10,
      badge: 'MÁXIMO AHORRO',
      diff: 0,
    }

    const extremePlan: OptimizePlan = {
      mode: 'ahorro',
      stops: 3,
      total: 999999999.75,
      ahorro_total: 150000000,
      reintegro_bancario_total: 50000000,
      envio_estimado: 2500000,
      missing: [],
      carts: [],
      mode_previews: {
        ahorro: extremePreview,
      } as any,
    }

    const { container } = render(
      <SmartCartHero
        mode="ahorro"
        onSelectMode={vi.fn()}
        plan={extremePlan}
      />,
    )

    // Check that large formatted numbers appear properly formatted
    expect(screen.getAllByText(/\$\s*1\.000\.000\.000/).length).toBeGreaterThanOrEqual(1)
    // Check covered items badge (2/10 productos cubiertos)
    expect(screen.getByText(/2\/10 productos cubiertos/i)).toBeTruthy()
    // Check reintegros
    expect(screen.getByText(/50\.000\.000 reintegros/i)).toBeTruthy()
  })

  it('A2. Negative difference and zero savings: handles edge conditions cleanly', () => {
    const zeroPreview: ScenarioPreview = {
      mode: 'comodidad',
      title: 'Opción cómoda',
      tagline: 'Todo en 1 solo súper',
      total: 10000,
      ahorro_vs_comoda: 0,
      ahorro_vs_regular: 0,
      ahorro_pct: 0,
      supermercados_count: 1,
      covered_items: 1,
      total_items: 1,
      diff: 0, // No extra cost vs más barata
    }

    const zeroPlan: OptimizePlan = {
      mode: 'comodidad',
      stops: 1,
      total: 10000,
      missing: [],
      carts: [],
      mode_previews: {
        comodidad: zeroPreview,
      } as any,
    }

    render(
      <SmartCartHero
        mode="comodidad"
        onSelectMode={vi.fn()}
        plan={zeroPlan}
      />,
    )

    // When diff is 0 or missing, it should display "¡Mismo precio que Más Barata!"
    expect(screen.getByText(/¡Mismo precio que Más Barata!/i)).toBeTruthy()
  })

  it('A3. Rapid Mode Switching Race Condition: withstands 10 rapid switches in milliseconds without desync', async () => {
    const items = [{ ean: '7791234567890', nombre: 'Leche La Serenísima', qty: 2 }]
    localStorage.setItem('sv_cart_v2', JSON.stringify(items))

    const previews: Record<string, ScenarioPreview> = {
      ahorro: {
        mode: 'ahorro',
        title: 'Opción más barata',
        tagline: 'Split 2 súper',
        total: 35000,
        ahorro_vs_comoda: 5000,
        ahorro_vs_regular: 5000,
        ahorro_pct: 10,
        supermercados_count: 2,
        covered_items: 1,
        total_items: 1,
      },
      balanceada: {
        mode: 'balanceada',
        title: 'Opción equilibrada',
        tagline: 'Equilibrada',
        total: 37000,
        ahorro_vs_comoda: 3000,
        ahorro_vs_regular: 3000,
        ahorro_pct: 7,
        supermercados_count: 2,
        covered_items: 1,
        total_items: 1,
      },
      comodidad: {
        mode: 'comodidad',
        title: 'Opción cómoda',
        tagline: '1 súper',
        total: 40000,
        ahorro_vs_comoda: 0,
        ahorro_vs_regular: 0,
        ahorro_pct: 0,
        supermercados_count: 1,
        covered_items: 1,
        total_items: 1,
      },
    }

    const mockPlan: OptimizePlan = {
      mode: 'ahorro',
      stops: 2,
      total: 35000,
      missing: [],
      carts: [],
      all_plans: {
        ahorro: { mode: 'ahorro', stops: 2, total: 35000, missing: [], carts: [] },
        balanceada: { mode: 'balanceada', stops: 2, total: 37000, missing: [], carts: [] },
        comodidad: { mode: 'comodidad', stops: 1, total: 40000, missing: [], carts: [] },
      },
      mode_previews: previews as any,
    }

    const optimizeMock = vi.mocked(api.optimize).mockResolvedValue(mockPlan)

    render(
      <LocationProvider>
        <BenefitsProvider>
          <CartProvider>
            <ListScreen onGoSearch={vi.fn()} onGoProfile={vi.fn()} />
          </CartProvider>
        </BenefitsProvider>
      </LocationProvider>,
    )

    // Wait until plan renders with total
    await waitFor(() => {
      expect(screen.getAllByText(/\$\s*35\.000/).length).toBeGreaterThanOrEqual(1)
    })
    optimizeMock.mockClear()

    const ahorroBtn = screen.getByRole('button', { name: /seleccionar más barata/i })
    const balanceadaBtn = screen.getByRole('button', { name: /seleccionar equilibrada/i })
    const comodaBtn = screen.getByRole('button', { name: /seleccionar cómoda/i })

    // Rapid switches across modes
    for (let i = 0; i < 5; i++) {
      fireEvent.click(balanceadaBtn)
      fireEvent.click(comodaBtn)
      fireEvent.click(ahorroBtn)
    }

    // Verify system ended up in 'ahorro' consistently with 0 network calls
    expect(screen.getByText(/Opción Más Barata/i)).toBeTruthy()
    expect(screen.getAllByText(/\$\s*35\.000/).length).toBeGreaterThanOrEqual(1)
    expect(optimizeMock).not.toHaveBeenCalled()
  })

  it('A4. Cart Item Stepper Decrement to 0 and Trash Removal: immediately transitions correctly', async () => {
    const items = [
      { ean: '7791234567890', nombre: 'Leche La Serenísima', qty: 1 },
      { ean: '7799876543210', nombre: 'Galletitas Oreo', qty: 2 },
    ]
    localStorage.setItem('sv_cart_v2', JSON.stringify(items))

    const mockPlan: OptimizePlan = {
      mode: 'ahorro',
      stops: 1,
      total: 10000,
      missing: [],
      carts: [],
    }

    vi.mocked(api.optimize).mockResolvedValue(mockPlan)

    render(
      <LocationProvider>
        <BenefitsProvider>
          <CartProvider>
            <ListScreen onGoSearch={vi.fn()} onGoProfile={vi.fn()} />
          </CartProvider>
        </BenefitsProvider>
      </LocationProvider>,
    )

    await waitFor(() => {
      expect(screen.getByText(/2 productos en tu lista/i)).toBeTruthy()
    })

    // Open drawer
    const drawerToggle = screen.getByRole('button', { name: /ver y editar productos agregados/i })
    fireEvent.click(drawerToggle)

    // Decrement Leche (qty: 1 -> 0): should remove it
    const minusBtn = screen.getByRole('button', { name: /restar una unidad de leche la serenísima/i })
    fireEvent.click(minusBtn)

    // Should now have 1 product
    expect(screen.getByText(/1 producto en tu lista/i)).toBeTruthy()

    // Remove remaining Oreo via Trash button
    const trashBtn = screen.getByRole('button', { name: /quitar galletitas oreo de la lista/i })
    fireEvent.click(trashBtn)

    // Should now show empty cart screen
    expect(screen.getByText('Tu lista está vacía')).toBeTruthy()
  })
})
