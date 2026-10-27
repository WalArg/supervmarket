import React from 'react'
import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import MissingItemsBreakdown from '../MissingItemsBreakdown'
import type { MissingItemDetail } from '../../types'

describe('Feature 4: Desglose de Faltantes & Alternativas (MissingItemsBreakdown)', () => {
  const sampleMissingItems: MissingItemDetail[] = [
    {
      ean: '7790895000997',
      nombre: 'Leche Descremada La Serenísima 1L',
      missing_in_assigned_stores: ['Dia', 'Coto'],
      available_in_other_stores: [
        {
          supermercado: 'Carrefour',
          precio: 1450,
          promo_badge: '15% OFF',
        },
        {
          supermercado: 'Jumbo',
          precio: 1650,
          promo_badge: '2x1',
        },
      ],
    },
    {
      ean: '7791234567890',
      nombre: 'Aceite de Girasol Cocinero 1.5L',
      missing_in_assigned_stores: ['Carrefour'],
      available_in_other_stores: [
        {
          supermercado: 'Dia',
          precio: 2300,
        },
      ],
    },
    {
      ean: '7793334445556',
      nombre: 'Café Molido La Virginia 500g',
      missing_in_assigned_stores: ['Vea'],
      available_in_other_stores: [],
    },
    {
      ean: '7799998887771',
      nombre: 'Arroz Doble Carolina Lucchetti 1kg',
      missing_in_assigned_stores: ['Disco'],
      available_in_other_stores: [
        {
          supermercado: 'MercadoLibre',
          precio: 3100,
          promo_badge: 'FULL',
        },
      ],
    },
  ]

  describe('Tier 1: Feature Coverage (F4-T1.1 - F4-T1.5)', () => {
    it('F4-T1.1: Structured Missing Items Header renders item count and alert text', () => {
      render(<MissingItemsBreakdown missing={sampleMissingItems.slice(0, 2)} />)
      expect(screen.getByText(/Productos sin stock en esta opción \(2\)/i)).toBeTruthy()
      expect(
        screen.getByText(/Los siguientes artículos no están disponibles en las tiendas asignadas/i)
      ).toBeTruthy()
    })

    it('F4-T1.2: Item Identity & Missing Chain renders product name, EAN chip, and missing stores', () => {
      render(<MissingItemsBreakdown missing={[sampleMissingItems[0]]} />)

      // Name & EAN
      expect(screen.getByText('Leche Descremada La Serenísima 1L')).toBeTruthy()
      expect(screen.getByText('7790895000997')).toBeTruthy()

      // Missing in assigned stores
      expect(screen.getByText(/Falta en:/i)).toBeTruthy()
      expect(screen.getByText(/Día, Coto/i)).toBeTruthy()
    })

    it('F4-T1.3: Alternative Stores Ranking displays alternatives with formatted prices', () => {
      render(<MissingItemsBreakdown missing={[sampleMissingItems[0]]} />)

      expect(screen.getByText(/Disponible en otras cadenas:/i)).toBeTruthy()
      expect(screen.getByText('Carrefour')).toBeTruthy()
      expect(screen.getByText('Jumbo')).toBeTruthy()

      // Formatted prices in ARS
      expect(screen.getByText(/1\.450/)).toBeTruthy()
      expect(screen.getByText(/1\.650/)).toBeTruthy()
    })

    it('F4-T1.4: Promo Badges on Alternatives highlights active promotions ("15% OFF", "2x1")', () => {
      render(<MissingItemsBreakdown missing={[sampleMissingItems[0]]} />)

      expect(screen.getByText('15% OFF')).toBeTruthy()
      expect(screen.getByText('2x1')).toBeTruthy()
    })

    it('F4-T1.5: Clean Empty State returns null when missing items array is empty or null', () => {
      const { container: containerEmpty } = render(<MissingItemsBreakdown missing={[]} />)
      expect(containerEmpty.firstChild).toBeNull()

      // @ts-expect-error test null safety
      const { container: containerNull } = render(<MissingItemsBreakdown missing={null} />)
      expect(containerNull.firstChild).toBeNull()
    })
  })

  describe('Tier 2: Boundary & Corner Cases (F4-T2.1 - F4-T2.5)', () => {
    it('F4-T2.1: 0 Missing Items renders null with 0 DOM overhead', () => {
      const { container } = render(<MissingItemsBreakdown missing={[]} />)
      expect(container.firstChild).toBeNull()
    })

    it('F4-T2.2: Exactly 1 or 2 Missing Items are rendered directly without accordion toggle', () => {
      render(<MissingItemsBreakdown missing={sampleMissingItems.slice(0, 2)} />)

      expect(screen.getByText('Leche Descremada La Serenísima 1L')).toBeTruthy()
      expect(screen.getByText('Aceite de Girasol Cocinero 1.5L')).toBeTruthy()
      expect(screen.queryByRole('button', { name: /Ver los/i })).toBeNull()
    })

    it('F4-T2.3: 3+ Missing Items shows top 2 items and renders accordion toggle button', () => {
      render(<MissingItemsBreakdown missing={sampleMissingItems} />)

      // Top 2 items are visible
      expect(screen.getByText('Leche Descremada La Serenísima 1L')).toBeTruthy()
      expect(screen.getByText('Aceite de Girasol Cocinero 1.5L')).toBeTruthy()

      // Items 3 and 4 are collapsed initially
      expect(screen.queryByText('Café Molido La Virginia 500g')).toBeNull()
      expect(screen.queryByText('Arroz Doble Carolina Lucchetti 1kg')).toBeNull()

      // Toggle button indicates remaining count (4 - 2 = 2)
      const toggleBtn = screen.getByRole('button', { name: /Ver los 2 productos faltantes restantes/i })
      expect(toggleBtn).toBeTruthy()
      expect(toggleBtn.getAttribute('aria-expanded')).toBe('false')
    })

    it('F4-T2.4: Accordion State Toggle expands remaining items and updates aria-expanded and icon label', () => {
      render(<MissingItemsBreakdown missing={sampleMissingItems} />)

      const toggleBtn = screen.getByRole('button', { name: /Ver los 2 productos faltantes restantes/i })
      fireEvent.click(toggleBtn)

      // Now all 4 items should be visible
      expect(screen.getByText('Café Molido La Virginia 500g')).toBeTruthy()
      expect(screen.getByText('Arroz Doble Carolina Lucchetti 1kg')).toBeTruthy()
      expect(toggleBtn.getAttribute('aria-expanded')).toBe('true')
      expect(screen.getByText('Ver menos faltantes')).toBeTruthy()

      // Clicking again collapses
      fireEvent.click(toggleBtn)
      expect(screen.queryByText('Café Molido La Virginia 500g')).toBeNull()
      expect(toggleBtn.getAttribute('aria-expanded')).toBe('false')
    })

    it('F4-T2.5: No Alternatives Available displays informative fallback notice', () => {
      // 3rd item has empty available_in_other_stores: []
      render(<MissingItemsBreakdown missing={[sampleMissingItems[2]]} />)

      expect(screen.getByText('Café Molido La Virginia 500g')).toBeTruthy()
      expect(
        screen.getByText(/Sin alternativas con stock confirmadas en otras cadenas para tu zona\./i)
      ).toBeTruthy()
    })

    it('F4-T2.6: Accordion toggle meets or exceeds WCAG 2.5.5 AAA touch target requirement (>= 44px)', () => {
      render(<MissingItemsBreakdown missing={sampleMissingItems} />)
      const toggleBtn = screen.getByRole('button', { name: /Ver los 2 productos faltantes restantes/i })
      expect(toggleBtn.className).toContain('h-11') // h-11 = 44px (2.75rem)
    })
  })
})
