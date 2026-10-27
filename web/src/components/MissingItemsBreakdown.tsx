import React, { useState } from 'react'
import {
  PackageX,
  ChevronDown,
  ChevronUp,
  Store,
  Flame,
} from 'lucide-react'
import type { MissingItemDetail } from '../types'
import { storeColor, storeLabel } from '../lib/stores'
import { formatPrice } from '../lib/pricing'

export interface MissingItemsBreakdownProps {
  missing: MissingItemDetail[]
  onSelectAlternative?: (item: MissingItemDetail, store: string) => void
  className?: string
}

export const MissingItemsBreakdown: React.FC<MissingItemsBreakdownProps> = ({
  missing,
  className = '',
}) => {
  const [expanded, setExpanded] = useState(false)

  if (!missing || missing.length === 0) return null

  // If there are more than 2 items, collapse by default on mobile to prevent excessive scroll depth
  const visibleItems = expanded ? missing : missing.slice(0, 2)
  const hasMore = missing.length > 2

  return (
    <div
      className={`bg-amber-50/70 border border-amber-200/80 rounded-2xl p-4 space-y-3 shadow-2xs ${className}`}
    >
      {/* Card Header */}
      <div className="flex items-start gap-2.5">
        <div className="w-8 h-8 rounded-xl bg-amber-100 text-amber-700 flex items-center justify-center shrink-0 mt-0.5">
          <PackageX size={18} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-[13px] font-extrabold text-amber-950">
              Productos sin stock en esta opción ({missing.length})
            </h3>
          </div>
          <p className="text-[12px] text-amber-800 leading-snug mt-0.5">
            Los siguientes artículos no están disponibles en las tiendas asignadas a este escenario, pero podés conseguirlos en estas cadenas alternativas:
          </p>
        </div>
      </div>

      {/* Missing Items List */}
      <div className="space-y-2.5">
        {visibleItems.map(item => {
          const alternatives = item.available_in_other_stores || []

          return (
            <div
              key={item.ean}
              className="bg-white rounded-xl border border-amber-200/60 p-3 shadow-2xs space-y-2"
            >
              {/* Product Info */}
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-[13px] font-bold text-slate-900 leading-snug line-clamp-2">
                    {item.nombre}
                  </p>
                  {item.missing_in_assigned_stores && item.missing_in_assigned_stores.length > 0 && (
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      Falta en:{' '}
                      <span className="font-semibold text-slate-700">
                        {item.missing_in_assigned_stores.map(storeLabel).join(', ')}
                      </span>
                    </p>
                  )}
                </div>
                <span className="text-[10px] font-mono bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded shrink-0">
                  {item.ean}
                </span>
              </div>

              {/* Alternative Stores */}
              {alternatives.length > 0 ? (
                <div className="pt-2 border-t border-slate-100 space-y-1.5">
                  <p className="text-[11px] font-bold text-slate-600 flex items-center gap-1">
                    <Store size={12} className="text-slate-400" />
                    Disponible en otras cadenas:
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                    {alternatives.map(alt => (
                      <div
                        key={alt.supermercado}
                        className="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-200/60 text-[12px]"
                      >
                        <div className="flex items-center gap-1.5 min-w-0">
                          <span
                            className="w-2.5 h-2.5 rounded-full shrink-0"
                            style={{ background: storeColor(alt.supermercado) }}
                          />
                          <span className="font-bold text-slate-800 truncate">
                            {storeLabel(alt.supermercado)}
                          </span>
                          {alt.promo_badge && (
                            <span className="inline-flex items-center gap-0.5 text-[10px] font-extrabold text-orange-700 bg-orange-100/80 px-1.5 py-0.5 rounded shrink-0">
                              <Flame size={10} /> {alt.promo_badge}
                            </span>
                          )}
                        </div>
                        <span className="font-extrabold text-slate-900 whitespace-nowrap ml-2">
                          {formatPrice(alt.precio)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-[11px] text-slate-400 italic pt-1.5 border-t border-slate-100">
                  Sin alternativas con stock confirmadas en otras cadenas para tu zona.
                </p>
              )}
            </div>
          )
        })}
      </div>

      {/* Accordion Toggle for Remaining Items (touch target >= 44px) */}
      {hasMore && (
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="w-full h-11 rounded-xl bg-amber-100/80 hover:bg-amber-200/80 text-amber-950 font-bold text-[12px] flex items-center justify-center gap-1.5 transition-colors active:scale-[0.99]"
          aria-expanded={expanded}
        >
          {expanded ? (
            <>
              <ChevronUp size={15} />
              <span>Ver menos faltantes</span>
            </>
          ) : (
            <>
              <ChevronDown size={15} />
              <span>Ver los {missing.length - 2} productos faltantes restantes</span>
            </>
          )}
        </button>
      )}
    </div>
  )
}

export default MissingItemsBreakdown
