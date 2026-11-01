import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import OffersScreen from '../OffersScreen'
import { DISCOUNT_TIERS } from '../../data/gondolasData'
import { formatPrice } from '../../lib/pricing'
import { CartProvider } from '../../cart/CartContext'
import { SavedProvider } from '../../saved/SavedContext'
import { LocationProvider } from '../../location/LocationContext'

const normalizePriceText = (price: number) =>
  formatPrice(price).replace(/\s+/g, ' ').trim()

vi.mock('../../api', async () => {
  const actual = await vi.importActual('../../api')
  const { DISCOUNT_TIERS: tiersData } = await vi.importActual<
    typeof import('../../data/gondolasData')
  >('../../data/gondolasData')
  return {
    ...actual,
    getLiveOffers: vi.fn().mockResolvedValue({
      tiers: tiersData,
      is_live: true,
      updated_at: new Date().toISOString(),
    }),
  }
})

const BLACKLISTED_IMAGE_PATTERNS = [
  '607590',
  '879659',
  '843734',
  'ids/314352',
  'ids/345227',
]

describe('OffersIntegrity — Mathematical Price, Link, Image & Sponsored Integrity', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('1. Mathematical Price & Discount Integrity across all DISCOUNT_TIERS', () => {
    expect(DISCOUNT_TIERS.length).toBe(4)

    for (const tier of DISCOUNT_TIERS) {
      expect(tier.products.length).toBeGreaterThanOrEqual(1)

      for (const product of tier.products) {
        expect(product.offers.length).toBeGreaterThanOrEqual(1)

        for (const offer of product.offers) {
          expect(offer.precio).toBeGreaterThan(0)
          const listPrice = offer.precio_lista ?? offer.precio
          expect(listPrice).toBeGreaterThanOrEqual(offer.precio)

          const label = offer.promo_label || ''
          const isMultiUnitPromo =
            (offer.promo_min_qty !== undefined && offer.promo_min_qty >= 2) ||
            /^(2d[oa]\s+al|2x1|3x2)/i.test(label.trim())

          if (isMultiUnitPromo) {
            expect(offer.promo_min_qty).toBeGreaterThanOrEqual(2)
            expect(label).toContain('$')
            expect(label.toLowerCase()).toContain('c/u')
          }

          const isDirectDiscount =
            (offer.discount ?? 0) > 0 &&
            (!offer.promo_min_qty || offer.promo_min_qty === 1) &&
            listPrice > offer.precio

          if (isDirectDiscount) {
            const calculatedPct = Math.round((1 - offer.precio / listPrice) * 100)
            expect(Math.abs(calculatedPct - (offer.discount ?? 0))).toBeLessThanOrEqual(2)
          }
        }
      }
    }
  })

  it('2. Link & Image Integrity across all DISCOUNT_TIERS', () => {
    for (const tier of DISCOUNT_TIERS) {
      for (const product of tier.products) {
        expect(product.imagen.startsWith('https://')).toBe(true)
        for (const badId of BLACKLISTED_IMAGE_PATTERNS) {
          expect(product.imagen).not.toContain(badId)
        }

        for (const offer of product.offers) {
          expect(offer.link.startsWith('https://')).toBe(true)
          const parsed = new URL(offer.link)
          expect(parsed.pathname).not.toBe('/')
          expect(parsed.pathname.length).toBeGreaterThan(1)
          const isDeepProductLink =
            offer.link.includes('/p') ||
            offer.link.includes('/p/MLA') ||
            offer.link.includes('MLA-')
          expect(isDeepProductLink).toBe(true)
        }
      }
    }
  })

  it('3. Mercado Libre Sponsored Offers Integrity across all 4 tiers', () => {
    const seenEans = new Set<string>()
    const seenNames = new Set<string>()

    for (const tier of DISCOUNT_TIERS) {
      const { product, offer } = tier.meliSponsored
      expect(product).toBeDefined()
      expect(offer).toBeDefined()

      const normName = product.nombre.trim().toLowerCase()
      expect(seenEans.has(product.ean)).toBe(false)
      expect(seenNames.has(normName)).toBe(false)
      seenEans.add(product.ean)
      seenNames.add(normName)

      expect(product.imagen.startsWith('https://')).toBe(true)
      for (const badId of BLACKLISTED_IMAGE_PATTERNS) {
        expect(product.imagen).not.toContain(badId)
      }

      expect(offer.supermercado).toBe('MercadoLibre')
      expect(offer.is_full).toBe(true)
      expect(offer.precio).toBeGreaterThan(0)
      expect(offer.precio_lista ?? offer.precio).toBeGreaterThanOrEqual(offer.precio)
      expect(offer.discount ?? 0).toBeGreaterThan(0)
      expect(offer.link.startsWith('https://')).toBe(true)
      expect(
        offer.link.includes('/p/MLA') || offer.link.includes('MLA-'),
      ).toBe(true)
    }

    expect(seenEans.size).toBe(4)
    expect(seenNames.size).toBe(4)
  })

  it('4. UI Rendering & Image Fallback Resilience in <OffersScreen />', async () => {
    render(
      <LocationProvider>
        <CartProvider>
          <SavedProvider>
            <OffersScreen />
          </SavedProvider>
        </CartProvider>
      </LocationProvider>,
    )

    await waitFor(() => {
      expect(screen.getAllByText('PATROCINADO').length).toBe(4)
    })

    // Verify all 4 tier titles, sponsored cards, and shelf prices are displayed
    for (const tier of DISCOUNT_TIERS) {
      expect(screen.getByText(tier.title)).toBeTruthy()
      expect(screen.getByText(tier.meliSponsored.product.nombre)).toBeTruthy()
      expect(
        screen.getAllByText(normalizePriceText(tier.meliSponsored.offer.precio)).length,
      ).toBeGreaterThanOrEqual(1)

      const firstVisibleProduct = tier.products[0]
      expect(screen.getByText(firstVisibleProduct.nombre)).toBeTruthy()
      const bestPrice = Math.min(...firstVisibleProduct.offers.map(o => o.precio))
      expect(
        screen.getAllByText(normalizePriceText(bestPrice)).length,
      ).toBeGreaterThanOrEqual(1)
    }

    // Verify image fallback resilience on error
    const firstProductName = DISCOUNT_TIERS[0].products[0].nombre
    const firstProductImg = screen.getByAltText(firstProductName) as HTMLImageElement
    expect(firstProductImg).toBeTruthy()
    fireEvent.error(firstProductImg)
    const handledCleanly =
      !firstProductImg.isConnected ||
      firstProductImg.style.visibility === 'hidden' ||
      firstProductImg.src.startsWith('data:image/') ||
      Boolean(screen.getByLabelText(firstProductName))
    expect(handledCleanly).toBe(true)
  })
})
