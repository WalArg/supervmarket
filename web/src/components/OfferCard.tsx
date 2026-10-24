import React from 'react'
import { ExternalLink, Flame, CreditCard, MapPinOff } from 'lucide-react'
import type { Offer } from '../types'
import { useLocation } from '../location/LocationContext'
import { useBenefits } from '../benefits/BenefitsContext'

interface OfferCardProps {
  offer: Offer
  minEffectivePrice: number
  isBestPrice?: boolean
}

export const formatPrice = (price: number) =>
  new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
    maximumFractionDigits: 0,
  }).format(price)

export const STORE_BRANDS: Record<
  string,
  { dot: string; border: string; headerBg: string; text: string }
> = {
  Carrefour: {
    dot: 'bg-blue-600',
    border: 'border-blue-200 hover:border-blue-400',
    headerBg: 'bg-blue-50/70',
    text: 'text-blue-800',
  },
  Coto: {
    dot: 'bg-red-600',
    border: 'border-red-200 hover:border-red-400',
    headerBg: 'bg-red-50/70',
    text: 'text-red-800',
  },
  Dia: {
    dot: 'bg-rose-600',
    border: 'border-rose-200 hover:border-rose-400',
    headerBg: 'bg-rose-50/70',
    text: 'text-rose-800',
  },
  Jumbo: {
    dot: 'bg-emerald-600',
    border: 'border-emerald-200 hover:border-emerald-400',
    headerBg: 'bg-emerald-50/70',
    text: 'text-emerald-800',
  },
  Disco: {
    dot: 'bg-pink-600',
    border: 'border-pink-200 hover:border-pink-400',
    headerBg: 'bg-pink-50/70',
    text: 'text-pink-800',
  },
  Vea: {
    dot: 'bg-green-600',
    border: 'border-green-200 hover:border-green-400',
    headerBg: 'bg-green-50/70',
    text: 'text-green-800',
  },
  Masonline: {
    dot: 'bg-teal-600',
    border: 'border-teal-200 hover:border-teal-400',
    headerBg: 'bg-teal-50/70',
    text: 'text-teal-800',
  },
  Farmacity: {
    dot: 'bg-orange-500',
    border: 'border-orange-200 hover:border-orange-400',
    headerBg: 'bg-orange-50/70',
    text: 'text-orange-800',
  },
  Simplicity: {
    dot: 'bg-fuchsia-600',
    border: 'border-fuchsia-200 hover:border-fuchsia-400',
    headerBg: 'bg-fuchsia-50/70',
    text: 'text-fuchsia-800',
  },
  Farmaonline: {
    dot: 'bg-cyan-600',
    border: 'border-cyan-200 hover:border-cyan-400',
    headerBg: 'bg-cyan-50/70',
    text: 'text-cyan-800',
  },
  Farmaplus: {
    dot: 'bg-sky-600',
    border: 'border-sky-200 hover:border-sky-400',
    headerBg: 'bg-sky-50/70',
    text: 'text-sky-800',
  },
  TheFoodMarket: {
    dot: 'bg-amber-600',
    border: 'border-amber-200 hover:border-amber-400',
    headerBg: 'bg-amber-50/70',
    text: 'text-amber-900',
  },
}

const OfferCard: React.FC<OfferCardProps> = ({
  offer,
  minEffectivePrice,
  isBestPrice,
}) => {
  const { cp, delivers } = useLocation()
  const { hasStoreClub } = useBenefits()
  const userHasClub = hasStoreClub(offer.supermercado)
  const cobertura = cp ? delivers(offer.supermercado) : null
  const noEntrega = cobertura === false

  const brand = STORE_BRANDS[offer.supermercado] || {
    dot: 'bg-slate-500',
    border: 'border-slate-200 hover:border-slate-400',
    headerBg: 'bg-slate-50',
    text: 'text-slate-800',
  }

  const minQty = offer.promo_min_qty || 1
  // Las promos que requieren tarjeta/membresía SOLO se descuentan del precio principal si el usuario marcó esa tarjeta
  const effectivePrice =
    offer.requires_club && !userHasClub
      ? offer.precio
      : (offer.promo_unit_price ?? offer.precio)
  const clubPrice =
    offer.requires_club &&
    !userHasClub &&
    offer.promo_unit_price &&
    offer.promo_unit_price < offer.precio
      ? offer.promo_unit_price
      : null
  const displayUnitPrice =
    offer.unit_price && offer.requires_club && userHasClub && effectivePrice < offer.precio
      ? Math.round(offer.unit_price * (effectivePrice / offer.precio))
      : offer.unit_price
  const referenceStrikePrice =
    effectivePrice < offer.precio
      ? offer.precio
      : offer.precio_lista > offer.precio
        ? offer.precio_lista
        : 0

  const hasPromo = Boolean(
    offer.promo_label || offer.discount >= 5 || effectivePrice < offer.precio,
  )

  const diffPct =
    minEffectivePrice > 0 && effectivePrice > minEffectivePrice
      ? Math.round(((effectivePrice - minEffectivePrice) / minEffectivePrice) * 100)
      : 0

  return (
    <a
      href={offer.link}
      target="_blank"
      rel="noopener noreferrer"
      title={`Abrir en ${offer.supermercado}${offer.promo_label ? ` · ${offer.promo_label}` : ''}`}
      className={`group block w-[164px] h-[116px] rounded-xl border p-2.5 transition-all flex flex-col justify-between select-none ${
        isBestPrice
          ? 'bg-emerald-50/60 border-emerald-400 ring-1 ring-emerald-400 shadow-2xs'
          : `bg-white ${brand.border}`
      } hover:shadow-md ${noEntrega ? 'opacity-55 grayscale-[40%]' : ''}`}
    >
      {/* Fila 1: Cadena + Badge único de MEJOR PRECIO (o diferencia %) */}
      <div className="flex items-center justify-between gap-1">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className={`w-2 h-2 rounded-full shrink-0 ${brand.dot}`} />
          <span className={`text-xs font-extrabold truncate ${brand.text}`}>
            {offer.supermercado}
          </span>
        </div>

        {noEntrega ? (
          <span className="inline-flex items-center gap-0.5 text-[9px] font-bold bg-red-100 text-red-700 px-1.5 py-0.5 rounded shrink-0">
            <MapPinOff size={9} /> S/envío
          </span>
        ) : isBestPrice ? (
          <span className="text-[9px] font-extrabold bg-emerald-600 text-white px-1.5 py-0.5 rounded shrink-0">
            MEJOR PRECIO
          </span>
        ) : diffPct > 0 ? (
          <span className="text-[9px] font-semibold text-slate-400 shrink-0">
            +{diffPct}%
          </span>
        ) : null}
      </div>

      {/* Fila 2: Precio efectivo final (con promo aplicada si tiene) + Precio regular tachado */}
      <div className="my-auto">
        <div className="flex items-baseline gap-1.5">
          <span className="text-lg font-extrabold text-slate-900 leading-none tracking-tight">
            {formatPrice(effectivePrice)}
          </span>
          {minQty > 1 && effectivePrice < offer.precio && (
            <span className="text-[10px] font-bold text-emerald-700 leading-none">
              c/u
            </span>
          )}
          {referenceStrikePrice > effectivePrice && (
            <span className="text-[10px] text-slate-400 line-through leading-none">
              {formatPrice(referenceStrikePrice)}
            </span>
          )}
        </div>

        <div className="text-[10px] text-slate-500 font-medium mt-0.5 flex items-center justify-between">
          <span>
            {displayUnitPrice
              ? `${formatPrice(displayUnitPrice)} / ${offer.unit_measure}`
              : 'Precio unitario'}
          </span>
          <ExternalLink
            size={10}
            className="opacity-0 group-hover:opacity-100 text-slate-400 transition-opacity"
          />
        </div>
      </div>

      {/* Fila 3: Aclaración de la promoción activa (2x1, 2do al 70%, Dto directo, Club) */}
      {hasPromo ? (
        <div
          className={`px-1.5 py-1 rounded-lg border text-[10px] leading-tight flex items-center justify-between gap-1 ${
            offer.requires_club
              ? 'bg-purple-100/80 border-purple-200 text-purple-900'
              : 'bg-orange-100/80 border-orange-200 text-orange-950'
          }`}
        >
          <span className="font-bold flex items-center gap-1 truncate">
            {offer.requires_club ? (
              <CreditCard size={10} className="text-purple-600 shrink-0" />
            ) : (
              <Flame size={10} className="text-orange-600 shrink-0" />
            )}
            <span className="truncate">
              {clubPrice
                ? `${formatPrice(clubPrice)} · ${offer.promo_label}`
                : offer.promo_label || `${Math.round(offer.discount)}% OFF`}
            </span>
          </span>
          {minQty > 1 && (
            <span className="text-[9px] font-extrabold opacity-80 whitespace-nowrap shrink-0">
              llev. {minQty}
            </span>
          )}
        </div>
      ) : (
        <div className="text-[10px] text-slate-400 font-medium truncate border-t border-slate-100 pt-1">
          Precio regular
        </div>
      )}
    </a>
  )
}

export default OfferCard
