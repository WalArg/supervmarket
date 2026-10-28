import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import OffersSheet from '../OffersSheet'
import { CartProvider } from '../../cart/CartContext'
import type { ProductGroup } from '../../types'
import type { OfferRow } from '../ProductCard'

const mockGroup: ProductGroup = {
  ean: '7790070412345',
  nombre: 'Aceite en aerosol Cañuelas de girasol 187 cc',
  marca: 'Cañuelas',
  imagen: 'https://example.com/oil.jpg',
  offers: [
    {
      supermercado: 'Dia',
      ean: '7790070412345',
      sku_id: 'dia-1',
      nombre: 'Aceite aerosol Cañuelas',
      marca: 'Cañuelas',
      precio: 4390,
      precio_base: 4390,
      line_total: 4390,
    },
    {
      supermercado: 'MercadoLibre',
      ean: '7790070412345',
      sku_id: 'meli-1',
      nombre: 'Aceite en aerosol Cañuelas',
      marca: 'Cañuelas',
      precio: 4934,
      precio_base: 4934,
      line_total: 4934,
      seller_name: 'TIENDAMIPAÑAL',
      link: 'https://articulo.mercadolibre.com.ar/MLA-999',
    },
  ],
}

const mockRows: OfferRow[] = [
  {
    o: mockGroup.offers[0],
    eff: 4390,
    unit: 23476,
    club: null,
    promo: null,
    minQty: 1,
    noDelivery: false,
  },
  {
    o: mockGroup.offers[1],
    eff: 4934,
    unit: 26387,
    club: null,
    promo: null,
    minQty: 1,
    noDelivery: false,
  },
]

describe('OffersSheet Store Selection and Cart Binding', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('1. Initially shows best store (Dia) in bottom bar before anything is added', () => {
    render(
      <CartProvider>
        <OffersSheet open={true} onClose={vi.fn()} group={mockGroup} rows={mockRows} />
      </CartProvider>,
    )

    expect(screen.getByText(/Mejor precio:/)).toBeTruthy()
    expect(screen.getByText('Día')).toBeTruthy()
    expect(screen.getByText('Mercado Libre')).toBeTruthy()
  })

  it('2. Clicking Agregar on Mercado Libre sets store to Mercado Libre and updates bottom bar accordingly', () => {
    render(
      <CartProvider>
        <OffersSheet open={true} onClose={vi.fn()} group={mockGroup} rows={mockRows} />
      </CartProvider>,
    )

    // Find the Agregar button for Mercado Libre
    const meliAddBtn = screen.getByTitle('Agregar oferta de Mercado Libre al carrito')
    expect(meliAddBtn).toBeTruthy()

    fireEvent.click(meliAddBtn)

    // The bottom bar must now explicitly state Mercado Libre is in the cart, NOT Dia!
    expect(screen.getByText(/En changuito:/)).toBeTruthy()
    expect(screen.getByText(/en Mercado Libre/)).toBeTruthy()

    // The Mercado Libre row must show the En changuito badge
    expect(screen.getAllByText(/En changuito/).length).toBeGreaterThan(0)
  })

  it('3. Stepper controls on the selected store row increment and decrement quantity', () => {
    render(
      <CartProvider>
        <OffersSheet open={true} onClose={vi.fn()} group={mockGroup} rows={mockRows} />
      </CartProvider>,
    )

    const meliAddBtn = screen.getByTitle('Agregar oferta de Mercado Libre al carrito')
    fireEvent.click(meliAddBtn)

    // Plus button on Mercado Libre row
    const plusBtn = screen.getByLabelText('Sumar una unidad de Mercado Libre')
    expect(plusBtn).toBeTruthy()
    fireEvent.click(plusBtn)

    // Now quantity is 2
    expect(screen.getByText(/2 un\./)).toBeTruthy()

    // Minus button on Mercado Libre row
    const minusBtn = screen.getByLabelText('Restar una unidad de Mercado Libre')
    fireEvent.click(minusBtn)

    // Back to 1
    expect(screen.getByText(/1 un\./)).toBeTruthy()
  })

  it('4. Switching store from Mercado Libre to Dia switches active store and updates bottom bar', () => {
    render(
      <CartProvider>
        <OffersSheet open={true} onClose={vi.fn()} group={mockGroup} rows={mockRows} />
      </CartProvider>,
    )

    // 1. Add to Mercado Libre
    const meliAddBtn = screen.getByTitle('Agregar oferta de Mercado Libre al carrito')
    fireEvent.click(meliAddBtn)
    expect(screen.getByText(/en Mercado Libre/)).toBeTruthy()

    // 2. Click "Elegir este" on Dia
    const diaChooseBtn = screen.getByTitle('Agregar oferta de Día al carrito')
    fireEvent.click(diaChooseBtn)

    // Now active store is Dia
    expect(screen.getByText(/en Día/)).toBeTruthy()
  })
})
