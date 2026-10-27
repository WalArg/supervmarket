import React from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import SmartCartHero from '../SmartCartHero'
import type { OptimizePlan, ScenarioPreview } from '../../types'

const mockPreviews: Record<'ahorro' | 'balanceada' | 'comodidad', ScenarioPreview> = {
  ahorro: {
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
    ahorro_total: 8500,
  },
  balanceada: {
    mode: 'balanceada',
    title: 'Opción equilibrada',
    tagline: 'Ahorro vs logística',
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
    ahorro_total: 6500,
  },
  comodidad: {
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
    ahorro_total: 3500,
  },
}

const mockPlanAhorro: OptimizePlan = {
  mode: 'ahorro',
  stops: 2,
  subtotal_mercaderia: 42000,
  envio_estimado: 4500,
  reintegro_bancario_total: 1500,
  total: 45000,
  ahorro_total: 8500,
  missing: [],
  carts: [],
  mode_previews: mockPreviews,
}

describe('SmartCartHero — Adversarial Stress Testing', () => {
  it('1. Renders all 3 mode buttons with labels, badges, and estimated totals', () => {
    const onSelectMode = vi.fn()
    render(<SmartCartHero mode="ahorro" onSelectMode={onSelectMode} plan={mockPlanAhorro} />)

    expect(screen.getByText('Más Barata')).toBeTruthy()
    expect(screen.getByText('Equilibrada')).toBeTruthy()
    expect(screen.getByText('Cómoda')).toBeTruthy()

    expect(screen.getByText('MÁXIMO AHORRO')).toBeTruthy()
    expect(screen.getByText('RECOMENDADA')).toBeTruthy()
    expect(screen.getByText('1 SOLO SÚPER')).toBeTruthy()

    // Mode buttons exist and have correct accessible names
    const ahorroBtn = screen.getByRole('button', { name: /seleccionar más barata/i })
    const balanceadaBtn = screen.getByRole('button', { name: /seleccionar equilibrada/i })
    const comodaBtn = screen.getByRole('button', { name: /seleccionar cómoda/i })

    expect(ahorroBtn).toBeTruthy()
    expect(balanceadaBtn).toBeTruthy()
    expect(comodaBtn).toBeTruthy()
    expect(ahorroBtn.getAttribute('aria-pressed')).toBe('true')
    expect(balanceadaBtn.getAttribute('aria-pressed')).toBe('false')
  })

  it('2. Synchronous 0ms Mode Switching: triggers onSelectMode with exact mode keys immediately', () => {
    const onSelectMode = vi.fn()
    render(<SmartCartHero mode="ahorro" onSelectMode={onSelectMode} plan={mockPlanAhorro} />)

    const balanceadaBtn = screen.getByRole('button', { name: /seleccionar equilibrada/i })
    fireEvent.click(balanceadaBtn)
    expect(onSelectMode).toHaveBeenCalledTimes(1)
    expect(onSelectMode).toHaveBeenCalledWith('balanceada')

    const comodaBtn = screen.getByRole('button', { name: /seleccionar cómoda/i })
    fireEvent.click(comodaBtn)
    expect(onSelectMode).toHaveBeenCalledTimes(2)
    expect(onSelectMode).toHaveBeenCalledWith('comodidad')

    const ahorroBtn = screen.getByRole('button', { name: /seleccionar más barata/i })
    fireEvent.click(ahorroBtn)
    expect(onSelectMode).toHaveBeenCalledTimes(3)
    expect(onSelectMode).toHaveBeenCalledWith('ahorro')
  })

  it('3. Touch Target Ergonomics: Mode selector buttons satisfy min-h-[58px] (>=44px standard)', () => {
    const onSelectMode = vi.fn()
    const { container } = render(
      <SmartCartHero mode="ahorro" onSelectMode={onSelectMode} plan={mockPlanAhorro} />,
    )

    const buttons = container.querySelectorAll('.grid-cols-3 button')
    expect(buttons.length).toBe(3)
    buttons.forEach(btn => {
      expect(btn.className).toContain('min-h-[58px]')
      // 58px >= 44px touch target requirement
    })
  })

  it('4. Fallback Resilience: Handles plan = null without throwing any exceptions', () => {
    const onSelectMode = vi.fn()
    const { container } = render(
      <SmartCartHero mode="ahorro" onSelectMode={onSelectMode} plan={null} />,
    )

    // Does not crash, shows fallback placeholders
    expect(screen.getByText('Opción Más Barata')).toBeTruthy()
    expect(screen.getByText('Cotizando')).toBeTruthy()
    expect(screen.getByText('—')).toBeTruthy()

    // Clicking mode tabs still functions properly
    const balanceadaBtn = screen.getByRole('button', { name: /seleccionar equilibrada/i })
    fireEvent.click(balanceadaBtn)
    expect(onSelectMode).toHaveBeenCalledWith('balanceada')
  })

  it('5. Fallback Resilience: Handles missing mode_previews or partial 1-mode preview', () => {
    const onSelectMode = vi.fn()
    const partialPlan: OptimizePlan = {
      mode: 'ahorro',
      stops: 1,
      total: 30000,
      missing: [],
      carts: [],
      mode_previews: {
        ahorro: mockPreviews.ahorro,
      } as any, // missing balanceada and comodidad
    }

    // Render with mode="comodidad" when comodidad preview is missing
    const { container } = render(
      <SmartCartHero mode="comodidad" onSelectMode={onSelectMode} plan={partialPlan} />,
    )

    expect(screen.getByText('Opción Cómoda')).toBeTruthy()
    expect(screen.getByText('Toda tu compra en 1 solo súper')).toBeTruthy()
    expect(container).toBeTruthy()
  })

  it('6. Loading State: Displays loading backdrop and spinner when loading=true', () => {
    render(
      <SmartCartHero
        mode="ahorro"
        onSelectMode={vi.fn()}
        plan={mockPlanAhorro}
        loading={true}
      />,
    )

    expect(screen.getByText(/optimizando precios en vivo/i)).toBeTruthy()
  })

  it('7. Financial Metrics & Logistics Warning Display', () => {
    const planWithWarning: OptimizePlan = {
      ...mockPlanAhorro,
      logistics_warning: 'El costo extra de envío supera el ahorro',
      reintegro_bancario_total: 2000,
      envio_estimado: 5000,
    }

    render(
      <SmartCartHero
        mode="ahorro"
        onSelectMode={vi.fn()}
        plan={planWithWarning}
      />,
    )

    expect(screen.getByText(/El costo extra de envío supera el ahorro/i)).toBeTruthy()
    expect(screen.getByText(/2.000 reintegros/i)).toBeTruthy()
    expect(screen.getByText(/5.000 envío/i)).toBeTruthy()
    expect(screen.getByText(/Ahorrás \$ 8.500/i)).toBeTruthy()
    expect(screen.getByText(/15.9% menos vs 1 súper/i)).toBeTruthy()
  })

  it('8. Comodidad Mode: displays convenience surcharge diff when positive', () => {
    const planComodidad: OptimizePlan = {
      ...mockPlanAhorro,
      mode: 'comodidad',
      stops: 1,
      total: 53500,
    }

    render(
      <SmartCartHero
        mode="comodidad"
        onSelectMode={vi.fn()}
        plan={planComodidad}
      />,
    )

    expect(screen.getByText(/Costo de conveniencia/i)).toBeTruthy()
    expect(screen.getByText(/\+\$ 8.500/i)).toBeTruthy()
  })
})
