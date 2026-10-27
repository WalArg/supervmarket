import React, { useMemo, useState } from 'react'
import { ChevronUp, CreditCard, Flame, Bookmark } from 'lucide-react'
import type { Offer, ProductGroup } from '../types'
import { useBenefits } from '../benefits/BenefitsContext'
import { useLocation } from '../location/LocationContext'
import { useSaved, getCanonicalProductId } from '../saved/SavedContext'
import { storeColor, storeLabel } from '../lib/stores'
import { effPrice, unitPriceFor, clubPriceHint, promoText, formatPrice } from '../lib/pricing'
import OffersSheet from './OffersSheet'
import QtyControl from './QtyControl'

export interface OfferRow {
  o: Offer
  eff: number
  unit: number | null
  club: number | null
  promo: string | null
  minQty: number
  noDelivery: boolean
}

/**
 * Tarjeta compacta: muestra SOLO la mejor oferta (precio, súper, precio por kg/l/un y promo)
 * y un botón "Ver N ofertas" que abre la hoja con todas las opciones (patrón Turismocity).
 */
const ProductCard: React.FC<{ group: ProductGroup; isSponsored?: boolean }> = ({ group, isSponsored }) => {
  const { hasStoreClub, selectedCards } = useBenefits()
  const { cp, coverage } = useLocation()
  const { isSaved, toggleSave } = useSaved()
  const [sheet, setSheet] = useState(false)

  const prodId = getCanonicalProductId(group)
  const saved = isSaved(prodId)

  const rows: OfferRow[] = useMemo(() => {
    return group.offers
      .map(o => {
        const has = hasStoreClub(o.supermercado)
        const eff = effPrice(o, has)
        const cov = coverage.find(c => c.supermercado === o.supermercado)
        return {
          o,
          eff,
          unit: unitPriceFor(o, eff),
          club: clubPriceHint(o, has),
          promo: promoText(o, has),
          minQty: o.requires_club && !has ? 1 : o.promo_min_qty || 1,
          noDelivery: Boolean(cp && cov && cov.delivers === false),
        }
      })
      .sort((a, b) => Number(a.noDelivery) - Number(b.noDelivery) || a.eff - b.eff)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [group.offers, selectedCards, cp, coverage])

  if (!rows.length) return null
  const best = rows[0]
  const maxEff = Math.max(...rows.map(r => r.eff))
  const savePct = rows.length > 1 && maxEff > best.eff ? Math.round(((maxEff - best.eff) / maxEff) * 100) : 0

  return (
    <article
      className={`rounded-2xl border shadow-[0_1px_2px_rgba(15,23,42,0.04)] ${
        isSponsored
          ? 'bg-amber-50/25 border-amber-200/90'
          : 'bg-white border-slate-200/80'
      }`}
    >
      {isSponsored && (
        <div className="px-3 pt-2.5 -mb-1 flex items-center justify-between">
          <span className="inline-block text-[10px] font-black tracking-wider uppercase text-amber-900 bg-amber-100 border border-amber-300 px-2 py-0.5 rounded-full">
            PATROCINADO
          </span>
          <span className="text-[10px] text-amber-800/80 font-medium">Oferta destacada de marca</span>
        </div>
      )}

      {rows.length > 1 && savePct >= 5 && (
        <div className="px-3 pt-2.5 -mb-1">
          <span className="inline-block text-[10px] font-extrabold tracking-wide uppercase text-emerald-800 bg-emerald-100/80 px-2 py-0.5 rounded-full">
            Más barato en {storeLabel(best.o.supermercado)} · ahorrás {savePct}%
          </span>
        </div>
      )}

      <div className="p-3 pb-2.5 flex gap-3">
        <button
          type="button"
          onClick={() => setSheet(true)}
          className="w-14 h-14 shrink-0 rounded-xl bg-white border border-slate-100 p-1 flex items-center justify-center"
          aria-label="Ver ofertas"
        >
          <img
            src={group.imagen}
            alt=""
            loading="lazy"
            className="max-w-full max-h-full object-contain"
            onError={e => ((e.target as HTMLImageElement).style.visibility = 'hidden')}
          />
        </button>

        {/* Info del producto */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-1">
            <div className="min-w-0 flex-1">
              <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400 truncate">{group.marca}</p>
              <h3 className="text-[13.5px] leading-snug font-semibold text-slate-900 line-clamp-2">{group.nombre}</h3>
            </div>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation()
                toggleSave(group)
              }}
              className={`w-8 h-8 min-w-[32px] min-h-[32px] rounded-lg flex items-center justify-center transition-all shrink-0 active:scale-90 ${
                saved
                  ? 'text-amber-500 bg-amber-50 hover:bg-amber-100'
                  : 'text-slate-300 hover:text-amber-500 hover:bg-slate-50'
              }`}
              title={saved ? 'Quitar de guardados' : 'Guardar producto'}
              aria-label={saved ? 'Quitar de guardados' : 'Guardar producto'}
            >
              <Bookmark size={16} className={saved ? 'fill-amber-500' : ''} />
            </button>
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-1">
            {best.unit && (
              <span className="text-[11px] font-semibold text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded-md">
                {formatPrice(best.unit)}/{best.o.unit_measure}
              </span>
            )}

            {/* Descuento verificado vs precio regular de góndola */}
            {(best.eff < best.o.precio || best.o.discount >= 5) && (
              <span
                className="inline-flex items-center gap-0.5 text-[11px] font-bold text-emerald-800 bg-emerald-50 px-1.5 py-0.5 rounded-md"
                title="Precio con rebaja verificada vs precio regular"
              >
                📉 Mínimo reciente (-{best.o.discount || Math.round(((best.o.precio - best.eff) / best.o.precio) * 100)}%)
              </span>
            )}

            {best.promo && (
              <span className="inline-flex items-center gap-0.5 text-[11px] font-bold text-orange-800 bg-orange-50 px-1.5 py-0.5 rounded-md">
                <Flame size={10} /> {best.promo}
              </span>
            )}
            {!best.promo && best.club && (
              <span className="inline-flex items-center gap-0.5 text-[11px] font-semibold text-purple-700 bg-purple-50 px-1.5 py-0.5 rounded-md">
                <CreditCard size={10} /> {formatPrice(best.club)} c/tarjeta
              </span>
            )}
          </div>
        </div>

      </div>

      {/* Mejor precio + acciones (como "Precio total / Ver oferta" de Turismocity) */}
      <div className="mx-3 mb-3 pt-2.5 border-t border-slate-100 flex items-center gap-2">
        <button type="button" onClick={() => setSheet(true)} className="flex-1 min-w-0 text-left">
          <span className="flex items-center gap-1 text-[11px] font-semibold text-slate-500">
            <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: storeColor(best.o.supermercado) }} />
            <span className="truncate">
              {rows.length > 1 ? 'Mejor en ' : 'En '}
              <b className="text-slate-700">{storeLabel(best.o.supermercado)}</b>
              {best.o.seller_name && (
                <span className="text-slate-500 font-normal"> · {best.o.seller_name}</span>
              )}
            </span>
            {best.o.seller_reputation && (
              <span
                className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                  best.o.seller_reputation === '5_green'
                    ? 'bg-emerald-500'
                    : best.o.seller_reputation === '4_light_green'
                    ? 'bg-lime-500'
                    : best.o.seller_reputation === '3_yellow'
                    ? 'bg-amber-400'
                    : 'bg-red-500'
                }`}
                title={`Reputación: ${best.o.seller_reputation}`}
              />
            )}
          </span>
          <span className="flex items-baseline gap-1">
            <span className="text-[20px] font-extrabold tracking-tight text-slate-900 leading-tight">{formatPrice(best.eff)}</span>
            {best.minQty > 1 ? (
              <span className="text-[10px] font-bold text-orange-700">c/u x{best.minQty}</span>
            ) : best.eff < best.o.precio ? (
              <span className="text-[10px] text-slate-400 line-through">{formatPrice(best.o.precio)}</span>
            ) : null}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setSheet(true)}
          className="h-9 px-3 shrink-0 rounded-xl border border-blue-200 bg-blue-50 text-blue-700 text-[13px] font-bold flex items-center gap-1 active:bg-blue-100"
        >
          <ChevronUp size={15} />
          {rows.length > 1 ? `${rows.length} ofertas` : 'Ver'}
        </button>
        <QtyControl group={group} compact />
      </div>

      <OffersSheet open={sheet} onClose={() => setSheet(false)} group={group} rows={rows} />
    </article>
  )
}

export default ProductCard
