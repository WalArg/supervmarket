import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  decorateOutboundUrl,
  trackOutboundAffiliateClick,
  getOutboundTrackingSummary,
  AFFILIATE_STORAGE_KEY,
  MAX_STORED_CLICKS,
  OutboundLinkType,
} from '../affiliate'

describe('Affiliate Empirical Stress Testing — Challenger M5.1', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  // =========================================================================
  // 1. VTEX 1-CLICK CART REPEATING TUPLES PRESERVATION (20+ ITEMS)
  // =========================================================================
  describe('1. VTEX 1-Click Cart Repeating Tuples (20+ Items)', () => {
    it('preserves exact parameter sequence for 25 repeating item tuples without collapsing or grouping', () => {
      const itemsCount = 25
      const queryParts: string[] = []
      const expectedSkus: string[] = []
      const expectedQtys: string[] = []

      for (let i = 1; i <= itemsCount; i++) {
        const sku = `SKU_${1000 + i}`
        const qty = String((i % 5) + 1)
        expectedSkus.push(sku)
        expectedQtys.push(qty)
        queryParts.push(`sku=${sku}&qty=${qty}&seller=1&sc=1`)
      }

      const rawQuery = queryParts.join('&')
      const rawUrl = `https://www.carrefour.com.ar/checkout/cart/add?${rawQuery}`

      const decorated = decorateOutboundUrl(rawUrl, 'Carrefour', 'checkout')

      // 1. Raw repeating sequence must remain strictly contiguous and identical
      expect(decorated).toContain(rawQuery)

      // 2. Affiliate tracking parameters must be appended at query level
      expect(decorated).toContain('utm_source=supervmarket')
      expect(decorated).toContain('utm_medium=affiliate')
      expect(decorated).toContain('utm_campaign=smart_cart_carrefour')
      expect(decorated).toContain('utm_term=optimizado')
      expect(decorated).toContain('afiliado_id=supervmarket')

      // 3. WHATWG URL parsing verification: 25 skus and 25 qtys in exact order
      const parsed = new URL(decorated)
      const parsedSkus = parsed.searchParams.getAll('sku')
      const parsedQtys = parsed.searchParams.getAll('qty')
      const parsedSellers = parsed.searchParams.getAll('seller')
      const parsedScs = parsed.searchParams.getAll('sc')

      expect(parsedSkus).toHaveLength(25)
      expect(parsedSkus).toEqual(expectedSkus)
      expect(parsedQtys).toHaveLength(25)
      expect(parsedQtys).toEqual(expectedQtys)
      expect(parsedSellers).toHaveLength(25)
      expect(parsedScs).toHaveLength(25)
    })

    it('handles an extreme cart with 100 repeating items and preserves parameter order', () => {
      const itemsCount = 100
      const queryParts: string[] = []
      for (let i = 1; i <= itemsCount; i++) {
        queryParts.push(`sku=${7790000 + i}&qty=${i}&seller=1&sc=32`)
      }
      const rawUrl = `https://www.jumbo.com.ar/checkout/cart/add?${queryParts.join('&')}`
      const decorated = decorateOutboundUrl(rawUrl, 'Jumbo', 'checkout')

      const parsed = new URL(decorated)
      expect(parsed.searchParams.getAll('sku')).toHaveLength(100)
      expect(parsed.searchParams.getAll('sku')[0]).toBe('7790001')
      expect(parsed.searchParams.getAll('sku')[99]).toBe('7790100')
      expect(parsed.searchParams.get('utm_campaign')).toBe('smart_cart_jumbo')
      expect(parsed.searchParams.get('afiliado_id')).toBe('supervmarket')
    })
  })

  // =========================================================================
  // 2. IDEMPOTENCY & MULTI-PASS VERIFICATION
  // =========================================================================
  describe('2. Idempotency & Multi-Pass Decoration', () => {
    it('is strictly idempotent on 2-pass decoration', () => {
      const raw = 'https://diaonline.supermercadosdia.com.ar/checkout/cart/add?sku=991&qty=2&seller=1&sc=1'
      const pass1 = decorateOutboundUrl(raw, 'Dia', 'checkout')
      const pass2 = decorateOutboundUrl(pass1, 'Dia', 'checkout')

      expect(pass2).toBe(pass1)
      const parsed = new URL(pass2)
      expect(parsed.searchParams.getAll('utm_source')).toEqual(['supervmarket'])
      expect(parsed.searchParams.getAll('afiliado_id')).toEqual(['supervmarket'])
    })

    it('withstands 10 consecutive decoration passes without parameter inflation or duplication', () => {
      let current = 'https://www.disco.com.ar/checkout/cart/add?sku=123&qty=1&seller=1&sc=33'
      for (let i = 0; i < 10; i++) {
        current = decorateOutboundUrl(current, 'Disco', 'checkout')
      }

      const parsed = new URL(current)
      expect(parsed.searchParams.getAll('utm_source')).toHaveLength(1)
      expect(parsed.searchParams.getAll('utm_medium')).toHaveLength(1)
      expect(parsed.searchParams.getAll('utm_campaign')).toHaveLength(1)
      expect(parsed.searchParams.getAll('utm_term')).toHaveLength(1)
      expect(parsed.searchParams.getAll('afiliado_id')).toHaveLength(1)
      expect(parsed.searchParams.getAll('sku')).toHaveLength(1)
    })

    it('respects pre-existing tracking or affiliate parameters without overwriting or duplicating', () => {
      const customUrl =
        'https://articulo.mercadolibre.com.ar/MLA-999?matt_tool=custom_tool&utm_source=custom_agency'
      const decorated = decorateOutboundUrl(customUrl, 'MercadoLibre', 'item')

      const parsed = new URL(decorated)
      // Existing parameters must be preserved
      expect(parsed.searchParams.get('matt_tool')).toBe('custom_tool')
      expect(parsed.searchParams.get('utm_source')).toBe('custom_agency')
      // Only missing parameters should be filled
      expect(parsed.searchParams.get('matt_word')).toBe('sv_item')
      expect(parsed.searchParams.get('utm_campaign')).toBe('meli_item')
      // No duplicates
      expect(parsed.searchParams.getAll('matt_tool')).toHaveLength(1)
      expect(parsed.searchParams.getAll('utm_source')).toHaveLength(1)
    })

    it('handles case-insensitive and spacing variations of retailer names uniformly', () => {
      const url1 = decorateOutboundUrl('https://www.carrefour.com.ar/p', 'CARREFOUR', 'item')
      const url2 = decorateOutboundUrl('https://www.carrefour.com.ar/p', 'Carrefour', 'item')
      const url3 = decorateOutboundUrl('https://www.carrefour.com.ar/p', 'carrefour ', 'item')

      const p1 = new URL(url1)
      const p2 = new URL(url2)
      const p3 = new URL(url3)

      expect(p1.searchParams.get('utm_source')).toBe('supervmarket')
      expect(p2.searchParams.get('utm_source')).toBe('supervmarket')
      expect(p3.searchParams.get('utm_source')).toBe('supervmarket')
    })
  })

  // =========================================================================
  // 3. MALFORMED, FRAGMENT, SPECIAL CHARACTERS & UNICODE URLS
  // =========================================================================
  describe('3. Malformed, Fragment, Spaces and Unicode URLs', () => {
    it('preserves hash fragments strictly at the end of the URL with existing query parameters', () => {
      const raw = 'https://www.vea.com.ar/ofertas?categoria=lacteos&order=price#seccion-promociones'
      const decorated = decorateOutboundUrl(raw, 'Vea', 'item')

      expect(decorated.endsWith('#seccion-promociones')).toBe(true)
      const parsed = new URL(decorated)
      expect(parsed.hash).toBe('#seccion-promociones')
      expect(parsed.searchParams.get('categoria')).toBe('lacteos')
      expect(parsed.searchParams.get('utm_campaign')).toBe('item_vea')
    })

    it('preserves hash fragments on URLs that initially have NO query parameters', () => {
      const raw = 'https://www.cotodigital3.com.ar/sitios/cdigi/#top-categories'
      const decorated = decorateOutboundUrl(raw, 'Coto', 'coto')

      expect(decorated.endsWith('#top-categories')).toBe(true)
      const parsed = new URL(decorated)
      expect(parsed.hash).toBe('#top-categories')
      expect(parsed.searchParams.get('utm_campaign')).toBe('coto_smart_cart')
    })

    it('handles complex SPA hash routing fragments', () => {
      const raw = 'https://www.farmacity.com/checkout#/cart/delivery?zone=caba'
      const decorated = decorateOutboundUrl(raw, 'Farmacity', 'checkout')

      const parsed = new URL(decorated)
      expect(parsed.hash).toBe('#/cart/delivery?zone=caba')
      expect(parsed.searchParams.get('utm_source')).toBe('supervmarket')
      expect(parsed.searchParams.get('afiliado_id')).toBe('supervmarket')
    })

    it('handles URLs with unencoded spaces in path and query parameters', () => {
      const raw = 'https://www.jumbo.com.ar/almacen y bebidas/leche entera?marca=la serenisima y sancor'
      const decorated = decorateOutboundUrl(raw, 'Jumbo', 'item')

      expect(decorated).toContain('utm_source=supervmarket')
      const parsed = new URL(decorated)
      expect(parsed.searchParams.get('utm_campaign')).toBe('item_jumbo')
      // URL constructor normalizes spaces to %20
      expect(parsed.searchParams.get('marca')).toBe('la serenisima y sancor')
    })

    it('handles Spanish unicode characters (ñ, á, é, í, ó, ú) in path and query', () => {
      const raw =
        'https://www.disco.com.ar/búsqueda?q=ñoquis+de+papa&categoría=pastas&región=córdoba#opiniones'
      const decorated = decorateOutboundUrl(raw, 'Disco', 'item')

      const parsed = new URL(decorated)
      expect(parsed.hash).toBe('#opiniones')
      expect(parsed.searchParams.get('q')).toBe('ñoquis de papa')
      expect(parsed.searchParams.get('categoría')).toBe('pastas')
      expect(parsed.searchParams.get('utm_source')).toBe('supervmarket')
      expect(parsed.searchParams.get('utm_campaign')).toBe('item_disco')
    })

    it('handles pre-encoded URI components (%20, %2B, %26, %3D) without double encoding', () => {
      const raw = 'https://diaonline.supermercadosdia.com.ar/search?q=sal%26pimienta&filter=brand%3ASerenisima'
      const decorated = decorateOutboundUrl(raw, 'Dia', 'item')

      const parsed = new URL(decorated)
      expect(parsed.searchParams.get('q')).toBe('sal&pimienta')
      expect(parsed.searchParams.get('filter')).toBe('brand:Serenisima')
      expect(parsed.searchParams.get('utm_source')).toBe('supervmarket')
    })

    it('handles invalid or hostile non-HTTP inputs without throwing exceptions', () => {
      expect(decorateOutboundUrl('', 'Carrefour')).toBe('')
      expect(decorateOutboundUrl('   ', 'Carrefour')).toBe('')
      expect(decorateOutboundUrl(null, 'Carrefour')).toBe('')
      expect(decorateOutboundUrl(undefined, 'Carrefour')).toBe('')
      expect(decorateOutboundUrl('javascript:alert(1)', 'Carrefour')).toBe('javascript:alert(1)')
      expect(decorateOutboundUrl('data:text/html,<b>xss</b>', 'Carrefour')).toBe('data:text/html,<b>xss</b>')
      expect(decorateOutboundUrl('mailto:info@supervmarket.com', 'Carrefour')).toBe('mailto:info@supervmarket.com')
      expect(decorateOutboundUrl('/checkout/cart', 'Carrefour')).toBe('/checkout/cart')
      expect(decorateOutboundUrl('//www.carrefour.com.ar/cart', 'Carrefour')).toBe('//www.carrefour.com.ar/cart')
    })

    it('handles trailing query delimiters (? and &) cleanly', () => {
      const trailingQuestion = 'https://www.carrefour.com.ar/cart?'
      const decoratedQ = decorateOutboundUrl(trailingQuestion, 'Carrefour', 'checkout')
      const parsedQ = new URL(decoratedQ)
      expect(parsedQ.searchParams.get('utm_source')).toBe('supervmarket')

      const trailingAmp = 'https://www.carrefour.com.ar/cart?sku=123&'
      const decoratedAmp = decorateOutboundUrl(trailingAmp, 'Carrefour', 'checkout')
      const parsedAmp = new URL(decoratedAmp)
      expect(parsedAmp.searchParams.get('sku')).toBe('123')
      expect(parsedAmp.searchParams.get('utm_source')).toBe('supervmarket')
    })
  })

  // =========================================================================
  // 4. STORAGE STRESS & STRICT FIFO CAP OF 100 ENTRIES
  // =========================================================================
  describe('4. Storage Stress & Strict FIFO Cap of 100 Entries', () => {
    const STORES = [
      'Carrefour',
      'Dia',
      'Jumbo',
      'Disco',
      'Vea',
      'Masonline',
      'Farmacity',
      'Simplicity',
      'Farmaonline',
      'Farmaplus',
      'MercadoLibre',
      'Coto',
    ]

    const LINK_TYPES: OutboundLinkType[] = ['checkout', 'item', 'coto']

    it('simulates 150 consecutive outbound clicks and enforces exact FIFO cap of 100 entries', () => {
      const totalClicks = 150
      const dispatchedEvents: CustomEvent[] = []

      const listener = (e: Event) => {
        dispatchedEvents.push(e as CustomEvent)
      }
      window.addEventListener('sv:affiliate_click', listener)

      // Emit 150 clicks
      for (let i = 1; i <= totalClicks; i++) {
        const store = STORES[(i - 1) % STORES.length]
        const linkType = LINK_TYPES[(i - 1) % LINK_TYPES.length]
        const targetUrl = `https://retailer.example.com/click-${i}`
        const estimatedValue = 1000 + i * 25.5

        trackOutboundAffiliateClick(store, linkType, targetUrl, estimatedValue)
      }

      window.removeEventListener('sv:affiliate_click', listener)

      // 1. Exactly 150 custom events dispatched in real-time
      expect(dispatchedEvents).toHaveLength(150)
      expect(dispatchedEvents[0].detail.targetUrl).toBe('https://retailer.example.com/click-1')
      expect(dispatchedEvents[149].detail.targetUrl).toBe('https://retailer.example.com/click-150')

      // 2. LocalStorage contains exactly 100 items
      const rawStored = localStorage.getItem(AFFILIATE_STORAGE_KEY)
      expect(rawStored).toBeTruthy()
      const storedList = JSON.parse(rawStored!)
      expect(storedList).toHaveLength(MAX_STORED_CLICKS) // 100

      // 3. FIFO eviction verification:
      // Index 0 must be click #150 (the latest)
      expect(storedList[0].targetUrl).toBe('https://retailer.example.com/click-150')
      expect(storedList[0].store).toBe(STORES[149 % STORES.length])
      expect(storedList[0].estimatedValue).toBe(1000 + 150 * 25.5)

      // Index 99 must be click #51 (clicks 1..50 evicted)
      expect(storedList[99].targetUrl).toBe('https://retailer.example.com/click-51')
      expect(storedList[99].store).toBe(STORES[50 % STORES.length])
      expect(storedList[99].estimatedValue).toBe(1000 + 51 * 25.5)

      // None of clicks 1..50 should be present
      for (let i = 1; i <= 50; i++) {
        const evictedUrl = `https://retailer.example.com/click-${i}`
        expect(storedList.some((e: any) => e.targetUrl === evictedUrl)).toBe(false)
      }

      // 4. getOutboundTrackingSummary reflects capped total and last click #150
      const summary = getOutboundTrackingSummary()
      expect(summary.totalClicks).toBe(100)
      expect(summary.lastClick?.targetUrl).toBe('https://retailer.example.com/click-150')
    })

    it('handles numeric edge cases for estimatedValue (NaN, Infinity, undefined, rounding)', () => {
      trackOutboundAffiliateClick('Dia', 'checkout', 'https://example.com/1', NaN)
      trackOutboundAffiliateClick('Dia', 'checkout', 'https://example.com/2', Infinity)
      trackOutboundAffiliateClick('Dia', 'checkout', 'https://example.com/3', undefined)
      trackOutboundAffiliateClick('Dia', 'checkout', 'https://example.com/4', 123.456789)

      const raw = localStorage.getItem(AFFILIATE_STORAGE_KEY)
      const list = JSON.parse(raw!)

      // list[0] is click #4 (unshifting)
      expect(list[0].estimatedValue).toBe(123.46) // Rounded to 2 decimals
      expect(list[1].estimatedValue).toBeUndefined()
      // In JSON, Infinity serializes to null or undefined
      expect(list[2].estimatedValue == null).toBe(true)
      expect(list[3].estimatedValue).toBeUndefined()
    })

    it('survives localStorage QuotaExceededError silently without throwing or crashing', () => {
      const setItemSpy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
        throw new DOMException('QuotaExceededError', 'QuotaExceededError')
      })

      expect(() => {
        trackOutboundAffiliateClick('Carrefour', 'checkout', 'https://example.com/fail', 5000)
      }).not.toThrow()

      expect(setItemSpy).toHaveBeenCalled()
    })

    it('handles corrupted localStorage payload safely without crashing the caller', () => {
      // If localStorage is corrupted with non-array or invalid JSON
      localStorage.setItem(AFFILIATE_STORAGE_KEY, JSON.stringify({ error: 'not an array' }))

      // Tracking a new click should never throw or bubble exceptions to host UI
      expect(() => {
        trackOutboundAffiliateClick('Jumbo', 'item', 'https://example.com/recovered', 1000)
      }).not.toThrow()

      // getOutboundTrackingSummary handles non-array payloads without throwing
      const summary = getOutboundTrackingSummary()
      expect(summary.totalClicks).toBe(0)
      expect(summary.lastClick).toBeUndefined()
    })
  })
})
