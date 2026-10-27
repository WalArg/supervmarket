/**
 * SuperVmarket — Outbound CPA & Affiliate Tracking Helper
 *
 * Provides non-intrusive URL decoration and client-side outbound click telemetry.
 * Pure TypeScript, zero external dependencies.
 *
 * Rules:
 * 1. Preserves repeating query tuples (VTEX sku=...&qty=...&seller=...&sc=...).
 * 2. Idempotent: does not duplicate parameters if already present.
 * 3. Preserves hash fragments (#).
 * 4. Client-side click tracking stored in localStorage with FIFO cap of 100 entries.
 */

export type OutboundLinkType = 'checkout' | 'item' | 'coto'

export interface AffiliateClickEvent {
  timestamp: string
  store: string
  linkType: OutboundLinkType
  targetUrl?: string
  estimatedValue?: number
}

export const AFFILIATE_STORAGE_KEY = 'sv_affiliate_clicks_v1'
export const MAX_STORED_CLICKS = 100

/**
 * Decorates an outbound retailer or marketplace URL with official CPA/affiliate
 * and UTM attribution parameters.
 */
export function decorateOutboundUrl(
  url: string | null | undefined,
  store: string,
  linkType: OutboundLinkType = 'checkout',
): string {
  if (!url) return ''
  const trimmed = url.trim()
  if (!trimmed.startsWith('http://') && !trimmed.startsWith('https://')) {
    return trimmed
  }

  try {
    const u = new URL(trimmed)
    const storeKey = (store || '').toLowerCase().replace(/[\s_]/g, '')
    const isMeli = storeKey.includes('mercadolibre') || u.hostname.includes('mercadolibre.com')
    const isCoto = storeKey.includes('coto') || u.hostname.includes('cotodigital')

    const paramsToSet: Record<string, string> = {}

    if (isMeli) {
      paramsToSet['matt_tool'] = '43872651'
      paramsToSet['matt_word'] = linkType === 'item' ? 'sv_item' : 'sv_smart_cart'
      paramsToSet['matt_source'] = 'supervmarket'
      paramsToSet['utm_source'] = 'supervmarket'
      paramsToSet['utm_medium'] = 'affiliate'
      paramsToSet['utm_campaign'] = linkType === 'item' ? 'meli_item' : 'meli_smart_cart'
    } else if (isCoto) {
      paramsToSet['utm_source'] = 'supervmarket'
      paramsToSet['utm_medium'] = 'affiliate'
      paramsToSet['utm_campaign'] = linkType === 'item' ? 'coto_item' : 'coto_smart_cart'
      paramsToSet['utm_term'] = linkType === 'item' ? 'item' : 'copiar_lista'
    } else {
      const storeSlug = (store || 'retailer').toLowerCase().replace(/\s+/g, '_')
      paramsToSet['utm_source'] = 'supervmarket'
      paramsToSet['utm_medium'] = 'affiliate'
      paramsToSet['utm_campaign'] = linkType === 'item' ? `item_${storeSlug}` : `smart_cart_${storeSlug}`
      paramsToSet['utm_term'] = linkType === 'item' ? 'item' : 'optimizado'
      paramsToSet['afiliado_id'] = 'supervmarket'
    }

    for (const [key, value] of Object.entries(paramsToSet)) {
      if (!u.searchParams.has(key)) {
        u.searchParams.set(key, value)
      }
    }

    return u.toString()
  } catch {
    return trimmed
  }
}

/**
 * Persists an outbound affiliate click to localStorage under sv_affiliate_clicks_v1.
 * Maintains a strict FIFO cap of 100 entries.
 */
export function trackOutboundAffiliateClick(
  store: string,
  linkType: OutboundLinkType,
  targetUrl?: string,
  estimatedValue?: number,
): void {
  try {
    if (typeof window === 'undefined' || !window.localStorage) return

    const event: AffiliateClickEvent = {
      timestamp: new Date().toISOString(),
      store,
      linkType,
      targetUrl,
      estimatedValue: estimatedValue != null && !isNaN(estimatedValue) ? Number(estimatedValue.toFixed(2)) : undefined,
    }

    const raw = localStorage.getItem(AFFILIATE_STORAGE_KEY)
    const list: AffiliateClickEvent[] = raw ? JSON.parse(raw) : []

    // Prepend latest event
    list.unshift(event)

    // FIFO cap at 100 items
    if (list.length > MAX_STORED_CLICKS) {
      list.length = MAX_STORED_CLICKS
    }

    localStorage.setItem(AFFILIATE_STORAGE_KEY, JSON.stringify(list))

    // Dispatch custom browser event for reactive UI/telemetry listeners
    window.dispatchEvent(new CustomEvent('sv:affiliate_click', { detail: event }))
  } catch {
    // Fail silently in private browsing or storage-restricted sandboxes
  }
}

/**
 * Retrieves a summary of recorded outbound clicks from localStorage.
 */
export function getOutboundTrackingSummary(): {
  totalClicks: number
  lastClick?: AffiliateClickEvent
} {
  try {
    if (typeof window === 'undefined' || !window.localStorage) {
      return { totalClicks: 0 }
    }
    const raw = localStorage.getItem(AFFILIATE_STORAGE_KEY)
    if (!raw) return { totalClicks: 0 }
    const list: AffiliateClickEvent[] = JSON.parse(raw)
    return {
      totalClicks: Array.isArray(list) ? list.length : 0,
      lastClick: Array.isArray(list) && list.length > 0 ? list[0] : undefined,
    }
  } catch {
    return { totalClicks: 0 }
  }
}
