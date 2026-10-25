import type { Offer } from '../types'

export const formatPrice = (price: number) =>
  new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
    maximumFractionDigits: 0,
  }).format(price)

/**
 * Precio efectivo por unidad para ESTE usuario:
 * - Promos abiertas (2x1, 3x2, 2do al 50%, % OFF) siempre se aplican.
 * - Promos de tarjeta/club solo si el usuario marcó que tiene esa tarjeta.
 */
export function effPrice(o: Offer, hasClub: boolean): number {
  if (o.requires_club && !hasClub) return o.precio
  return o.promo_unit_price ?? o.precio
}

/** Precio por kg / l / un recalculado sobre el precio efectivo del usuario. */
export function unitPriceFor(o: Offer, eff: number): number | null {
  if (!o.unit_price) return null
  const basis = o.requires_club ? o.precio : (o.promo_unit_price ?? o.precio)
  return basis > 0 ? (o.unit_price * eff) / basis : o.unit_price
}

/** Precio con tarjeta/club que el usuario NO tiene (se muestra solo como dato informativo). */
export function clubPriceHint(o: Offer, hasClub: boolean): number | null {
  if (!o.requires_club || hasClub) return null
  if (o.promo_unit_price && o.promo_unit_price < o.precio) return o.promo_unit_price
  return null
}

/** Etiqueta corta de la promo aplicada (null si no aplica para el usuario). */
export function promoText(o: Offer, hasClub: boolean): string | null {
  if (o.requires_club && !hasClub) return null
  if (o.promo_label) return o.promo_label
  if (o.discount >= 5) return `${Math.round(o.discount)}% OFF`
  return null
}

export const unitSuffix = (u: string | null | undefined) =>
  u === 'kg' ? 'kg' : u === 'l' ? 'litro' : 'unidad'
