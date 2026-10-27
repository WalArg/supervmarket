import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import ListScreen from '../ListScreen'
import { CartProvider } from '../../cart/CartContext'
import { LocationProvider } from '../../location/LocationContext'
import { BenefitsProvider } from '../../benefits/BenefitsContext'
import * as api from '../../api'
import type { OptimizePlan, ScenarioPreview } from '../../types'

// Mock API functions
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

const samplePreviews: Record<'ahorro' | 'balanceada' | 'comodidad', ScenarioPreview> = {
  ahorro: {
    mode: 'ahorro',
    title: 'Opción más barata',
    tagline: 'Split óptimo 2 súper',
    total: 35000,
    ahorro_vs_comoda: 5000,
    ahorro_vs_regular: 8000,
    ahorro_pct: 12.5,
    supermercados_count: 2,
    covered_items: 2,
    total_items: 2,
    badge: 'MÁXIMO AHORRO',
    diff: 0,
    stops: 2,
    ahorro_total: 5000,
  },
  balanceada: {
    mode: 'balanceada',
    title: 'Opción equilibrada',
    tagline: 'Ahorro vs conveniencia',
    total: 37000,
    ahorro_vs_comoda: 3000,
    ahorro_vs_regular: 6000,
    ahorro_pct: 7.5,
    supermercados_count: 2,
    covered_items: 2,
    total_items: 2,
    badge: 'RECOMENDADA',
    diff: 2000,
    stops: 2,
    ahorro_total: 3000,
  },
  comodidad: {
    mode: 'comodidad',
    title: 'Opción cómoda',
    tagline: 'Todo en 1 solo súper',
    total: 40000,
    ahorro_vs_comoda: 0,
    ahorro_vs_regular: 3000,
    ahorro_pct: 0,
    supermercados_count: 1,
    covered_items: 2,
    total_items: 2,
    badge: '1 SOLO SÚPER',
    diff: 5000,
    stops: 1,
    ahorro_total: 3000,
  },
}

const planComoda: OptimizePlan = {
  mode: 'comodidad',
  stops: 1,
  total: 40000,
  subtotal_mercaderia: 40000,
  ahorro_total: 3000,
  missing: [],
  carts: [
    {
      supermercado: 'Carrefour',
      supports_cart: true,
      checkout_url: 'https://carrefour.com.ar',
      subtotal: 40000,
      free_shipping_threshold: 50000,
      falta_envio_gratis: 10000,
      items: [
        { ean: '7791234567890', nombre: 'Leche La Serenísima', qty: 2, precio: 1500 },
        { ean: '7799876543210', nombre: 'Galletitas Oreo', qty: 3, precio: 2000 },
      ],
    },
  ],
}

const planBalanceada: OptimizePlan = {
  mode: 'balanceada',
  stops: 2,
  total: 37000,
  subtotal_mercaderia: 37000,
  ahorro_total: 3000,
  missing: [],
  carts: [
    {
      supermercado: 'Carrefour',
      supports_cart: true,
      checkout_url: 'https://carrefour.com.ar',
      subtotal: 20000,
      free_shipping_threshold: 50000,
      falta_envio_gratis: 30000,
      items: [{ ean: '7791234567890', nombre: 'Leche La Serenísima', qty: 2, precio: 1500 }],
    },
    {
      supermercado: 'Coto',
      supports_cart: false,
      checkout_url: null,
      subtotal: 17000,
      free_shipping_threshold: 40000,
      falta_envio_gratis: 23000,
      items: [{ ean: '7799876543210', nombre: 'Galletitas Oreo', qty: 3, precio: 1800 }],
    },
  ],
}

const planAhorro: OptimizePlan = {
  mode: 'ahorro',
  stops: 2,
  total: 35000,
  subtotal_mercaderia: 35000,
  ahorro_total: 5000,
  missing: [],
  carts: [
    {
      supermercado: 'Carrefour',
      supports_cart: true,
      checkout_url: 'https://carrefour.com.ar',
      subtotal: 18000,
      free_shipping_threshold: 50000,
      falta_envio_gratis: 32000,
      items: [{ ean: '7791234567890', nombre: 'Leche La Serenísima', qty: 2, precio: 1400 }],
    },
    {
      supermercado: 'Dia',
      supports_cart: true,
      checkout_url: 'https://diaonline.com.ar',
      subtotal: 17000,
      free_shipping_threshold: 30000,
      falta_envio_gratis: 13000,
      items: [{ ean: '7799876543210', nombre: 'Galletitas Oreo', qty: 3, precio: 1700 }],
    },
  ],
  all_plans: {
    ahorro: null as any, // populated below
    balanceada: planBalanceada,
    comodidad: planComoda,
  },
  mode_previews: samplePreviews,
}
planAhorro.all_plans!.ahorro = planAhorro

function renderListScreen() {
  return render(
    <LocationProvider>
      <BenefitsProvider>
        <CartProvider>
          <ListScreen onGoSearch={vi.fn()} onGoProfile={vi.fn()} />
        </CartProvider>
      </BenefitsProvider>
    </LocationProvider>,
  )
}

describe('ListScreen — Adversarial Stress Testing', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('1. Empty Cart State: displays friendly empty message when 0 items', () => {
    renderListScreen()
    expect(screen.getByText(/Tu (carrito|lista) está vací[ao]/i)).toBeTruthy()
    expect(screen.getByRole('button', { name: /explorar productos/i })).toBeTruthy()
  })

  it('2. Client-Side Mode Switching: Instant 0ms state change WITHOUT network refetch', async () => {
    // Setup 2 items in cart
    const items = [
      { ean: '7791234567890', nombre: 'Leche La Serenísima', qty: 2 },
      { ean: '7799876543210', nombre: 'Galletitas Oreo', qty: 3 },
    ]
    localStorage.setItem('sv_cart_v2', JSON.stringify(items))

    // Mock initial optimize call to return the full 3-mode plan
    const optimizeMock = vi.mocked(api.optimize).mockResolvedValue(planAhorro)

    renderListScreen()

    // Wait for initial plan to load
    await waitFor(() => {
      expect(optimizeMock).toHaveBeenCalledTimes(1)
      expect(screen.getByText(/Opción Más Barata/i)).toBeTruthy()
    })

    // Verify initial total ($35.000) - appears in tab and in hero total
    expect(screen.getAllByText(/\$\s*35\.000/).length).toBeGreaterThanOrEqual(1)

    // Reset mock calls count to verify subsequent mode switches
    optimizeMock.mockClear()

    // 0ms Switch: Click "Equilibrada"
    const balanceadaBtn = screen.getByRole('button', { name: /seleccionar equilibrada/i })
    fireEvent.click(balanceadaBtn)

    // Synchronous immediate update to Equilibrada ($37.000)
    expect(screen.getByText(/Opción Equilibrada/i)).toBeTruthy()
    expect(screen.getAllByText(/\$\s*37\.000/).length).toBeGreaterThanOrEqual(1)

    // 0ms Switch: Click "Cómoda"
    const comodaBtn = screen.getByRole('button', { name: /seleccionar cómoda/i })
    fireEvent.click(comodaBtn)

    // Synchronous immediate update to Cómoda ($40.000)
    expect(screen.getByText(/Opción Cómoda/i)).toBeTruthy()
    expect(screen.getAllByText(/\$\s*40\.000/).length).toBeGreaterThanOrEqual(1)

    // Verify ZERO additional network refetches occurred!
    expect(optimizeMock).not.toHaveBeenCalled()
  })

  it('3. Fallback on Missing Mode: Triggers network fetch when target mode is not in all_plans', async () => {
    const items = [{ ean: '7791234567890', nombre: 'Leche La Serenísima', qty: 2 }]
    localStorage.setItem('sv_cart_v2', JSON.stringify(items))

    // Create a plan with ONLY 'ahorro' in all_plans (missing 'balanceada' and 'comodidad')
    const singleModePlan: OptimizePlan = {
      mode: 'ahorro',
      stops: 1,
      total: 20000,
      missing: [],
      carts: [],
      all_plans: {
        ahorro: null as any,
      } as any, // only ahorro
      mode_previews: {
        ahorro: samplePreviews.ahorro,
      } as any,
    }
    singleModePlan.all_plans!.ahorro = singleModePlan

    const optimizeMock = vi.mocked(api.optimize).mockResolvedValue(singleModePlan)

    renderListScreen()

    await waitFor(() => {
      expect(optimizeMock).toHaveBeenCalledTimes(1)
    })

    // Now mock the response for when balanceada is fetched
    optimizeMock.mockResolvedValueOnce({
      ...planBalanceada,
      total: 22000,
      all_plans: {
        ahorro: singleModePlan,
        balanceada: planBalanceada,
      } as any,
    })

    optimizeMock.mockClear()

    // Click "Equilibrada" (which is NOT in all_plans)
    const balanceadaBtn = screen.getByRole('button', { name: /seleccionar equilibrada/i })
    fireEvent.click(balanceadaBtn)

    // Wait for debounce timer (350ms) to trigger fallback network call
    await waitFor(
      () => {
        expect(optimizeMock).toHaveBeenCalledWith(
          expect.anything(),
          'balanceada',
          expect.anything(),
        )
      },
      { timeout: 1000 },
    )
  })

  it('4. State Preservation: delivery address, drawer state, and shipping toggle persist across mode switches', async () => {
    const items = [
      { ean: '7791234567890', nombre: 'Leche La Serenísima', qty: 2 },
      { ean: '7799876543210', nombre: 'Galletitas Oreo', qty: 3 },
    ]
    localStorage.setItem('sv_cart_v2', JSON.stringify(items))

    vi.mocked(api.optimize).mockResolvedValue(planAhorro)
    renderListScreen()

    await waitFor(() => {
      expect(screen.getAllByText(/\$\s*35\.000/).length).toBeGreaterThanOrEqual(1)
    })

    // A. Type exact address
    const addressInput = screen.getByPlaceholderText(/av\. santa fe 3200/i) as HTMLInputElement
    fireEvent.change(addressInput, { target: { value: 'Av. Corrientes 1234 5B' } })
    expect(addressInput.value).toBe('Av. Corrientes 1234 5B')

    // B. Open collapsible products drawer
    const drawerToggle = screen.getByRole('button', { name: /ver y editar productos agregados/i })
    fireEvent.click(drawerToggle)
    expect(screen.getByText(/Editar cantidades o quitar/i)).toBeTruthy()

    // C. Toggle shipping
    const shippingBtn = screen.getByRole('button', { name: /sumar costo de flete al cálculo/i })
    fireEvent.click(shippingBtn)

    // Now switch modes: 'ahorro' -> 'balanceada' -> 'comodidad' -> 'ahorro'
    const balanceadaBtn = screen.getByRole('button', { name: /seleccionar equilibrada/i })
    fireEvent.click(balanceadaBtn)

    const comodaBtn = screen.getByRole('button', { name: /seleccionar cómoda/i })
    fireEvent.click(comodaBtn)

    const ahorroBtn = screen.getByRole('button', { name: /seleccionar más barata/i })
    fireEvent.click(ahorroBtn)

    // Assert states remained intact:
    // 1. Exact address preserved
    expect((screen.getByPlaceholderText(/av\. santa fe 3200/i) as HTMLInputElement).value).toBe(
      'Av. Corrientes 1234 5B',
    )

    // 2. Drawer remained open
    expect(screen.getByText(/Editar cantidades o quitar/i)).toBeTruthy()

    // 3. Shipping toggle remained active
    expect(screen.getByRole('button', { name: /envío incluido en el cálculo/i })).toBeTruthy()
  })

  it('5. Touch Target Ergonomics: Stepper (+/-), Trash, Mode, and Action buttons meet >= 44x44px standards', async () => {
    const items = [
      { ean: '7791234567890', nombre: 'Leche La Serenísima', qty: 2 },
    ]
    localStorage.setItem('sv_cart_v2', JSON.stringify(items))

    vi.mocked(api.optimize).mockResolvedValue(planAhorro)
    const { container } = renderListScreen()

    await waitFor(() => {
      expect(screen.getAllByText(/\$\s*35\.000/).length).toBeGreaterThanOrEqual(1)
    })

    // Open drawer to expose steppers and trash button
    const drawerToggle = screen.getByRole('button', { name: /ver y editar productos agregados/i })
    fireEvent.click(drawerToggle)

    // Check Stepper Minus button: w-11 h-11 = 44px x 44px
    const minusBtn = screen.getByRole('button', { name: /restar una unidad de leche la serenísima/i })
    expect(minusBtn.className).toContain('w-11')
    expect(minusBtn.className).toContain('h-11')

    // Check Stepper Plus button: w-11 h-11 = 44px x 44px
    const plusBtn = screen.getByRole('button', { name: /sumar una unidad de leche la serenísima/i })
    expect(plusBtn.className).toContain('w-11')
    expect(plusBtn.className).toContain('h-11')

    // Check Trash / Delete button: w-11 h-11 = 44px x 44px
    const trashBtn = screen.getByRole('button', { name: /quitar leche la serenísima de la lista/i })
    expect(trashBtn.className).toContain('w-11')
    expect(trashBtn.className).toContain('h-11')

    // Check Bar Context buttons: min-h-[44px]
    const locationBtn = screen.getByRole('button', { name: /cambiar código postal o dirección/i })
    expect(locationBtn.className).toContain('min-h-[44px]')
    expect(locationBtn.className).toContain('h-11')

    const cardsBtn = screen.getByRole('button', { name: /configurar tarjetas y día de compra/i })
    expect(cardsBtn.className).toContain('min-h-[44px]')
    expect(cardsBtn.className).toContain('h-11')

    // Check Vaciar button: min-h-[44px]
    const clearBtn = screen.getByRole('button', { name: /vaciar/i })
    expect(clearBtn.className).toContain('min-h-[44px]')

    // Check Drawer Toggle: min-h-[48px] h-12 (48px >= 44px)
    expect(drawerToggle.className).toContain('min-h-[48px]')
    expect(drawerToggle.className).toContain('h-12')
  })
})
