import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import MeliCartAssistantModal from '../MeliCartAssistantModal'
import StoreCart from '../StoreCart'
import type { StorePlan } from '../../types'
import { LocationProvider } from '../../location/LocationContext'

const mockPlan: StorePlan = {
  supermercado: 'MercadoLibre',
  supports_cart: false,
  checkout_url: 'https://www.mercadolibre.com.ar/gz/cart',
  subtotal: 72000,
  subtotal_merch: 72000,
  final_store_total: 72000,
  free_shipping_threshold: 65000,
  is_free_shipping: true,
  falta_envio_gratis: 0,
  items: [
    {
      ean: '7798338291803',
      nombre: 'Leche Con Proteina La Serenisima 1L',
      qty: 2,
      precio: 2300,
      link: 'https://articulo.mercadolibre.com.ar/MLA-140001',
    },
    {
      ean: '7791234567890',
      nombre: 'Cafe Molido Cabrales 500g',
      qty: 1,
      precio: 67400,
      link: 'https://articulo.mercadolibre.com.ar/MLA-140002',
    },
  ],
}

describe('MeliCartAssistantModal Component', () => {
  let openSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    vi.clearAllMocks()
    openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)
  })

  it('1. Does not render in DOM when isOpen is false', () => {
    const { container } = render(
      <MeliCartAssistantModal
        isOpen={false}
        onClose={vi.fn()}
        plan={mockPlan}
        loadedEans={{}}
        onToggleItem={vi.fn()}
        onMarkItemLoaded={vi.fn()}
        onResetProgress={vi.fn()}
      />,
    )
    expect(container.firstChild).toBeNull()
  })

  it('2. Renders title, progress and free shipping status when isOpen is true', () => {
    render(
      <MeliCartAssistantModal
        isOpen={true}
        onClose={vi.fn()}
        plan={mockPlan}
        loadedEans={{}}
        onToggleItem={vi.fn()}
        onMarkItemLoaded={vi.fn()}
        onResetProgress={vi.fn()}
      />,
    )

    expect(screen.getByText('Asistente de Changuito Mercado Libre')).toBeTruthy()
    expect(screen.getByText(/0 de 2 agregados/)).toBeTruthy()
    expect(screen.getByText(/¡Envío gratis en Full!/)).toBeTruthy()
    expect(screen.getAllByText(/Leche Con Proteina La Serenisima 1L/).length).toBeGreaterThan(0)
    expect(screen.getByText(/Cafe Molido Cabrales 500g/)).toBeTruthy()
  })

  it('3. Fast-Track button points to the first pending item and opens link with affiliate attribution', () => {
    const onMarkItemLoaded = vi.fn()
    render(
      <MeliCartAssistantModal
        isOpen={true}
        onClose={vi.fn()}
        plan={mockPlan}
        loadedEans={{}}
        onToggleItem={vi.fn()}
        onMarkItemLoaded={onMarkItemLoaded}
        onResetProgress={vi.fn()}
      />,
    )

    const fastTrackBtn = screen.getByRole('button', { name: /Cargar siguiente: 2× Leche Con Proteina/i })
    expect(fastTrackBtn).toBeTruthy()

    fireEvent.click(fastTrackBtn)

    expect(openSpy).toHaveBeenCalledTimes(1)
    const openedUrl = openSpy.mock.calls[0][0] as string
    expect(openedUrl).toContain('articulo.mercadolibre.com.ar/MLA-140001')
    expect(openedUrl).toContain('matt_tool=43872651')
    expect(openedUrl).toContain('matt_word=sv_item')
    expect(onMarkItemLoaded).toHaveBeenCalledWith('7798338291803')
  })

  it('4. Fast-Track button switches to the second item once the first is loaded', () => {
    render(
      <MeliCartAssistantModal
        isOpen={true}
        onClose={vi.fn()}
        plan={mockPlan}
        loadedEans={{ '7798338291803': true }}
        onToggleItem={vi.fn()}
        onMarkItemLoaded={vi.fn()}
        onResetProgress={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: /Cargar siguiente: 1× Cafe Molido Cabrales/i })).toBeTruthy()
    expect(screen.getByText(/1 de 2 agregados/)).toBeTruthy()
  })

  it('5. When all items are loaded, shows completion banner and direct checkout CTA', () => {
    render(
      <MeliCartAssistantModal
        isOpen={true}
        onClose={vi.fn()}
        plan={mockPlan}
        loadedEans={{ '7798338291803': true, '7791234567890': true }}
        onToggleItem={vi.fn()}
        onMarkItemLoaded={vi.fn()}
        onResetProgress={vi.fn()}
      />,
    )

    const allLoadedBtn = screen.getByRole('button', { name: /¡Todo cargado! Ir a pagar en Mercado Libre/i })
    expect(allLoadedBtn).toBeTruthy()

    fireEvent.click(allLoadedBtn)
    expect(openSpy).toHaveBeenCalledTimes(1)
    const openedUrl = openSpy.mock.calls[0][0] as string
    expect(openedUrl).toContain('mercadolibre.com.ar/gz/cart')
    expect(openedUrl).toContain('matt_word=sv_smart_cart')
  })

  it('6. Clicking individual item Cargar button triggers onMarkItemLoaded and opens URL', () => {
    const onMarkItemLoaded = vi.fn()
    render(
      <MeliCartAssistantModal
        isOpen={true}
        onClose={vi.fn()}
        plan={mockPlan}
        loadedEans={{}}
        onToggleItem={vi.fn()}
        onMarkItemLoaded={onMarkItemLoaded}
        onResetProgress={vi.fn()}
      />,
    )

    const cargarBtns = screen.getAllByRole('button', { name: /Cargar/i })
    expect(cargarBtns.length).toBeGreaterThan(0)

    fireEvent.click(cargarBtns[1]) // Second item in list
    expect(onMarkItemLoaded).toHaveBeenCalledWith('7798338291803')
  })

  it('7. Clicking Reset calls onResetProgress', () => {
    const onResetProgress = vi.fn()
    render(
      <MeliCartAssistantModal
        isOpen={true}
        onClose={vi.fn()}
        plan={mockPlan}
        loadedEans={{ '7798338291803': true }}
        onToggleItem={vi.fn()}
        onMarkItemLoaded={vi.fn()}
        onResetProgress={onResetProgress}
      />,
    )

    const resetBtn = screen.getByRole('button', { name: /Reiniciar/i })
    fireEvent.click(resetBtn)
    expect(onResetProgress).toHaveBeenCalledTimes(1)
  })

  it('8. StoreCart integrates Mercado Libre assistant banner and opens modal on click', () => {
    render(
      <LocationProvider>
        <StoreCart plan={mockPlan} />
      </LocationProvider>,
    )

    expect(screen.getByText('Asistente de Carrito Mercado Libre')).toBeTruthy()
    const openAssistantBtn = screen.getByRole('button', { name: /Abrir Asistente/i })
    expect(openAssistantBtn).toBeTruthy()

    // Clicking Abrir Asistente opens the modal
    fireEvent.click(openAssistantBtn)
    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(screen.getByText('Asistente de Changuito Mercado Libre')).toBeTruthy()
  })
})
