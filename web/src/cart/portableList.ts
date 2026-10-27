import type { SharedItem } from '../types'

export interface ShareMessageParams {
  items: { ean: string; nombre?: string; qty: number }[]
  planTotal?: number
  planSaving?: number
  shareUrl: string
}

export interface ShareResult {
  method: 'share' | 'clipboard' | 'cancelled' | 'error'
  success: boolean
}

/**
 * Codifica una lista de ítems en una cadena Base64url compacta (RFC 4648 §5).
 * Formato intermedio: "ean:qty,ean:qty"
 */
export function encodeShareableList(items: { ean: string; qty: number }[]): string {
  if (!items || items.length === 0) return ''

  const clean = items
    .filter(i => i.ean && typeof i.ean === 'string' && i.ean.trim().length >= 8)
    .map(i => `${i.ean.trim()}:${Math.max(1, Math.min(999, Math.floor(i.qty || 1)))}`)

  if (clean.length === 0) return ''

  const raw = clean.join(',')
  // Convertir a Base64url (compatible con browsers y nodejs)
  const b64 =
    typeof btoa !== 'undefined'
      ? btoa(raw)
      : Buffer.from(raw, 'utf-8').toString('base64')

  return b64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

/**
 * Decodifica una cadena Base64url (o raw de compatibilidad) a un array de SharedItem.
 */
export function decodeShareableList(encoded: string): SharedItem[] {
  if (!encoded || typeof encoded !== 'string') return []
  const trimmed = encoded.trim()
  if (!trimmed) return []

  let raw = ''

  // Fallback si viene en formato raw "ean:qty,ean:qty"
  if (trimmed.includes(':') && /^\d{8,14}:\d+/.test(trimmed)) {
    raw = trimmed
  } else {
    try {
      let b64 = trimmed.replace(/-/g, '+').replace(/_/g, '/')
      b64 = b64.replace(/ /g, '+')
      while (b64.length % 4 !== 0) {
        b64 += '='
      }
      raw =
        typeof atob !== 'undefined'
          ? atob(b64)
          : Buffer.from(b64, 'base64').toString('utf-8')
    } catch {
      return []
    }
  }

  const result: SharedItem[] = []
  const parts = raw.split(',')
  const seen = new Map<string, number>()

  for (const part of parts) {
    const [rawEan, rawQty] = part.split(':')
    if (!rawEan) continue
    const ean = rawEan.trim()
    if (!/^\d{8,14}$/.test(ean)) continue

    const qty = Math.max(1, Math.min(999, parseInt(rawQty, 10) || 1))
    seen.set(ean, (seen.get(ean) || 0) + qty)
  }

  for (const [ean, qty] of seen.entries()) {
    result.push({ ean, qty })
  }

  return result
}

/**
 * Genera la URL canónica para compartir una lista.
 */
export function generateShareUrl(
  items: { ean: string; qty: number }[],
  paramKey: 'list' | 'habitual' = 'list',
  baseUrl?: string,
): string {
  const token = encodeShareableList(items)
  if (!token) return ''
  const origin =
    baseUrl ||
    (typeof window !== 'undefined' && window.location?.origin
      ? window.location.origin
      : 'https://vsupermarket.vercel.app')
  return `${origin}/?${paramKey}=${token}`
}

/**
 * Da formato al mensaje amigable optimizado para WhatsApp y mensajería móvil en Argentina.
 */
export function formatShareMessage({
  items,
  planTotal,
  planSaving,
  shareUrl,
}: ShareMessageParams): string {
  const totalUnits = items.reduce((acc, i) => acc + (i.qty || 1), 0)
  const count = items.length

  const lines: string[] = [
    '🛒 *Te comparto mi lista de supermercado en SuperVmarket*',
    `📦 ${count} producto${count === 1 ? '' : 's'} (${totalUnits} unidad${totalUnits === 1 ? '' : 'es'})`,
  ]

  if (planTotal && planTotal > 0) {
    const formattedTotal = Math.round(planTotal).toLocaleString('es-AR')
    const savingBadge =
      planSaving && planSaving > 0
        ? ` (¡Ahorrás $${Math.round(planSaving).toLocaleString('es-AR')}!)`
        : ''
    lines.push(`💰 Total optimizado: *$${formattedTotal}*${savingBadge}`)
  }

  lines.push('')
  lines.push('📋 *Resumen de productos:*')

  const preview = items.slice(0, 4)
  for (const it of preview) {
    const name = it.nombre || `Producto ${it.ean}`
    lines.push(`• ${it.qty}× ${name}`)
  }

  if (items.length > 4) {
    const rem = items.length - 4
    lines.push(`_... y ${rem} producto${rem === 1 ? '' : 's'} más_`)
  }

  lines.push('')
  lines.push('👉 *Abrí la lista y compará precios en vivo acá:*')
  lines.push(shareUrl)

  return lines.join('\n')
}

/**
 * Ejecuta el share utilizando Web Share API con fallback robusto a portapapeles.
 */
export async function executeShare({
  title = 'Mi lista de compras en SuperVmarket',
  text,
  url,
}: {
  title?: string
  text: string
  url: string
}): Promise<ShareResult> {
  if (typeof navigator !== 'undefined' && navigator.share) {
    try {
      await navigator.share({ title, text, url })
      return { method: 'share', success: true }
    } catch (err: unknown) {
      if ((err as { name?: string })?.name === 'AbortError') {
        return { method: 'cancelled', success: false }
      }
    }
  }

  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(`${text}\n\n${url}`)
      return { method: 'clipboard', success: true }
    } catch {
      // Fallback
    }
  }

  return { method: 'error', success: false }
}

/**
 * Limpia los parámetros de query de la URL sin recargar la página.
 */
export function cleanUrlParams(keys: string[]): void {
  if (typeof window === 'undefined') return
  try {
    const url = new URL(window.location.href)
    let dirty = false
    for (const k of keys) {
      if (url.searchParams.has(k)) {
        url.searchParams.delete(k)
        dirty = true
      }
    }
    if (dirty) {
      const newPath = url.pathname + (url.search ? url.search : '') + url.hash
      window.history.replaceState({}, document.title, newPath)
    }
  } catch {
    // Ignore error in test environments
  }
}
