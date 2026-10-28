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
    expect(screen.getByText(/En Mercado Libre/i)).toBeTruthy()

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

  it('4. Adding multiple distinct offers (Dia and Mercado Libre) retains both without replacing or overwriting', () => {
    render(
      <CartProvider>
        <OffersSheet open={true} onClose={vi.fn()} group={mockGroup} rows={mockRows} />
      </CartProvider>,
    )

    // 1. Add to Mercado Libre
    const meliAddBtn = screen.getByTitle('Agregar oferta de Mercado Libre al carrito')
    fireEvent.click(meliAddBtn)
    expect(screen.getByText(/En Mercado Libre/i)).toBeTruthy()

    // 2. Add to Dia
    const diaAddBtn = screen.getByTitle('Agregar oferta de Día al carrito')
    fireEvent.click(diaAddBtn)

    // Now both stores have items in cart, showing total 2 units and 2 distinct offers added
    expect(screen.getByText(/2 un\./)).toBeTruthy()
    expect(screen.getByText(/2 ofertas distintas agregadas/)).toBeTruthy()

    // Both steppers are visible
    expect(screen.getByLabelText('Sumar una unidad de Mercado Libre')).toBeTruthy()
    expect(screen.getByLabelText('Sumar una unidad de Día')).toBeTruthy()
  })

  it('5. Sub-options of Mercado Libre can be added independently with their own steppers', () => {
    const mockMeliRowWithSubOptions: OfferRow[] = [
      {
        o: {
          supermercado: 'MercadoLibre',
          ean: '7790070412345',
          sku_id: 'meli-main',
          nombre: 'Aceite en aerosol Cañuelas',
          marca: 'Cañuelas',
          precio: 4934,
          precio_base: 4934,
          line_total: 4934,
          seller_name: 'TIENDAMIPAÑAL',
          meli_options: [
            {
              item_id: 'MLA-SELLER-1',
              title: 'Aceite Cañuelas TIENDAMIPAÑAL',
              price: 4934,
              seller_name: 'TIENDAMIPAÑAL',
              link: 'https://articulo.mercadolibre.com.ar/MLA-1',
            },
            {
              item_id: 'MLA-SELLER-2',
              title: 'Aceite Cañuelas OTRO VENDEDOR',
              price: 5100,
              seller_name: 'OTROVENDEDOR',
              link: 'https://articulo.mercadolibre.com.ar/MLA-2',
            },
          ],
        },
        eff: 4934,
        unit: 26387,
        club: null,
        promo: null,
        minQty: 1,
        noDelivery: false,
      },
    ]

    render(
      <CartProvider>
        <OffersSheet
          open={true}
          onClose={vi.fn()}
          group={mockGroup}
          rows={mockMeliRowWithSubOptions}
        />
      </CartProvider>,
    )

    // Initially sub-options have their own Agregar buttons
    const addSeller1Btn = screen.getByTitle('Agregar opción de TIENDAMIPAÑAL')
    const addSeller2Btn = screen.getByTitle('Agregar opción de OTROVENDEDOR')
    expect(addSeller1Btn).toBeTruthy()
    expect(addSeller2Btn).toBeTruthy()

    // Add first seller option
    fireEvent.click(addSeller1Btn)
    expect(screen.getByText(/1 un\./)).toBeTruthy()

    // Now seller 1 shows stepper
    expect(screen.getByLabelText('Sumar una unidad de TIENDAMIPAÑAL')).toBeTruthy()

    // Add second seller option
    fireEvent.click(addSeller2Btn)
    expect(screen.getByText(/2 un\./)).toBeTruthy()
    expect(screen.getByText(/2 ofertas distintas agregadas/)).toBeTruthy()

    // Both seller options now have their own steppers!
    expect(screen.getByLabelText('Sumar una unidad de TIENDAMIPAÑAL')).toBeTruthy()
    expect(screen.getByLabelText('Sumar una unidad de OTROVENDEDOR')).toBeTruthy()
  })
})
