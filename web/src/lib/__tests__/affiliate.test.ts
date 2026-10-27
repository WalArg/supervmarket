import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  decorateOutboundUrl,
  trackOutboundAffiliateClick,
  getOutboundTrackingSummary,
  AFFILIATE_STORAGE_KEY,
  MAX_STORED_CLICKS,
} from '../affiliate'

describe('Affiliate & Outbound Link Decoration', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('preserves repeating VTEX query tuples in exact order while appending affiliate tags', () => {
    const rawVtex =
      'https://www.carrefour.com.ar/checkout/cart/add?sku=779123&qty=2&seller=1&sc=1&sku=779456&qty=1&seller=1&sc=1'
    const decorated = decorateOutboundUrl(rawVtex, 'Carrefour', 'checkout')

    // Must preserve original query substring with multi-value items
    expect(decorated).toContain('sku=779123&qty=2&seller=1&sc=1&sku=779456&qty=1&seller=1&sc=1')
    expect(decorated).toContain('utm_source=supervmarket')
    expect(decorated).toContain('utm_medium=affiliate')
    expect(decorated).toContain('utm_campaign=smart_cart_carrefour')
    expect(decorated).toContain('utm_term=optimizado')
    expect(decorated).toContain('afiliado_id=supervmarket')

    // Verify WHATWG parsing
    const parsed = new URL(decorated)
    expect(parsed.searchParams.getAll('sku')).toEqual(['779123', '779456'])
    expect(parsed.searchParams.getAll('qty')).toEqual(['2', '1'])
    expect(parsed.searchParams.get('utm_source')).toBe('supervmarket')
    expect(parsed.searchParams.get('afiliado_id')).toBe('supervmarket')
  })

  it('decorates Mercado Libre item permalinks with matt_tool and official UTM params', () => {
    const rawMeliItem = 'https://articulo.mercadolibre.com.ar/MLA-1428592381'
    const decorated = decorateOutboundUrl(rawMeliItem, 'MercadoLibre', 'item')

    const parsed = new URL(decorated)
    expect(parsed.origin).toBe('https://articulo.mercadolibre.com.ar')
    expect(parsed.pathname).toBe('/MLA-1428592381')
    expect(parsed.searchParams.get('matt_tool')).toBe('43872651')
    expect(parsed.searchParams.get('matt_word')).toBe('sv_item')
    expect(parsed.searchParams.get('matt_source')).toBe('supervmarket')
    expect(parsed.searchParams.get('utm_source')).toBe('supervmarket')
    expect(parsed.searchParams.get('utm_medium')).toBe('affiliate')
    expect(parsed.searchParams.get('utm_campaign')).toBe('meli_item')
  })

  it('decorates Mercado Libre general supermarket checkout link with sv_smart_cart', () => {
    const rawMeliCart = 'https://www.mercadolibre.com.ar/supermercado'
    const decorated = decorateOutboundUrl(rawMeliCart, 'MercadoLibre', 'checkout')

    const parsed = new URL(decorated)
    expect(parsed.searchParams.get('matt_tool')).toBe('43872651')
    expect(parsed.searchParams.get('matt_word')).toBe('sv_smart_cart')
    expect(parsed.searchParams.get('utm_campaign')).toBe('meli_smart_cart')
  })

  it('decorates Coto Digital destination URL with copier_lista UTM parameters', () => {
    const rawCoto = 'https://www.cotodigital3.com.ar/sitios/cdigi/'
    const decorated = decorateOutboundUrl(rawCoto, 'Coto', 'coto')

    const parsed = new URL(decorated)
    expect(parsed.searchParams.get('utm_source')).toBe('supervmarket')
    expect(parsed.searchParams.get('utm_medium')).toBe('affiliate')
    expect(parsed.searchParams.get('utm_campaign')).toBe('coto_smart_cart')
    expect(parsed.searchParams.get('utm_term')).toBe('copiar_lista')
  })

  it('is idempotent: decorating an already decorated URL produces no duplicate parameters', () => {
    const rawUrl = 'https://diaonline.supermercadosdia.com.ar/checkout/cart/add?sku=555&qty=1&seller=1&sc=1'
    const firstPass = decorateOutboundUrl(rawUrl, 'Dia', 'checkout')
    const secondPass = decorateOutboundUrl(firstPass, 'Dia', 'checkout')

    expect(secondPass).toBe(firstPass)

    const parsed = new URL(secondPass)
    expect(parsed.searchParams.getAll('utm_source')).toHaveLength(1)
    expect(parsed.searchParams.getAll('afiliado_id')).toHaveLength(1)
  })

  it('preserves hash fragments at the end of the URL', () => {
    const rawUrl = 'https://www.jumbo.com.ar/lacteos#ofertas-semanales'
    const decorated = decorateOutboundUrl(rawUrl, 'Jumbo', 'item')

    expect(decorated).toContain('#ofertas-semanales')
    const parsed = new URL(decorated)
    expect(parsed.hash).toBe('#ofertas-semanales')
    expect(parsed.searchParams.get('utm_source')).toBe('supervmarket')
    expect(parsed.searchParams.get('utm_campaign')).toBe('item_jumbo')
  })

  it('handles null, undefined, empty, and invalid URLs gracefully', () => {
    expect(decorateOutboundUrl(null, 'Carrefour')).toBe('')
    expect(decorateOutboundUrl(undefined, 'Carrefour')).toBe('')
    expect(decorateOutboundUrl('', 'Carrefour')).toBe('')
    expect(decorateOutboundUrl('javascript:void(0)', 'Carrefour')).toBe('javascript:void(0)')
    expect(decorateOutboundUrl('/relative/path', 'Carrefour')).toBe('/relative/path')
  })
})

describe('Affiliate Click Tracking & FIFO LocalStorage Persistence', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('records an outbound click with timestamp, store, linkType, and estimated value', () => {
    const dispatchSpy = vi.spyOn(window, 'dispatchEvent')

    trackOutboundAffiliateClick('Carrefour', 'checkout', 'https://www.carrefour.com.ar/checkout', 85400.5)

    const summary = getOutboundTrackingSummary()
    expect(summary.totalClicks).toBe(1)
    expect(summary.lastClick).toBeDefined()
    expect(summary.lastClick?.store).toBe('Carrefour')
    expect(summary.lastClick?.linkType).toBe('checkout')
    expect(summary.lastClick?.estimatedValue).toBe(85400.5)
    expect(summary.lastClick?.targetUrl).toBe('https://www.carrefour.com.ar/checkout')
    expect(new Date(summary.lastClick!.timestamp).getTime()).toBeGreaterThan(0)

    expect(dispatchSpy).toHaveBeenCalledTimes(1)
  })

  it('enforces a strict FIFO cap of 100 entries when more than 100 clicks are tracked', () => {
    // Generate 105 clicks
    for (let i = 1; i <= 105; i++) {
      trackOutboundAffiliateClick('Dia', 'item', `https://diaonline.supermercadosdia.com.ar/item-${i}`, i * 100)
    }

    const summary = getOutboundTrackingSummary()
    expect(summary.totalClicks).toBe(MAX_STORED_CLICKS) // Exactly 100

    const raw = localStorage.getItem(AFFILIATE_STORAGE_KEY)
    expect(raw).toBeTruthy()
    const stored = JSON.parse(raw!)
    expect(stored).toHaveLength(100)

    // The most recent click is #105
    expect(stored[0].targetUrl).toBe('https://diaonline.supermercadosdia.com.ar/item-105')
    expect(stored[0].estimatedValue).toBe(10500)

    // The oldest kept click is #6 (items 1 to 5 were evicted by FIFO)
    expect(stored[99].targetUrl).toBe('https://diaonline.supermercadosdia.com.ar/item-6')
    expect(stored[99].estimatedValue).toBe(600)
  })

  it('getOutboundTrackingSummary returns empty stats when no clicks exist', () => {
    const summary = getOutboundTrackingSummary()
    expect(summary.totalClicks).toBe(0)
    expect(summary.lastClick).toBeUndefined()
  })

  it('handles corrupted localStorage payload safely', () => {
    localStorage.setItem(AFFILIATE_STORAGE_KEY, 'invalid-json-{}')
    const summary = getOutboundTrackingSummary()
    expect(summary.totalClicks).toBe(0)
    expect(summary.lastClick).toBeUndefined()
  })
})
