import React, { useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { X, ExternalLink, Flame, CreditCard, MapPinOff } from 'lucide-react'
import type { ProductGroup } from '../types'
import { storeColor, storeLabel } from '../lib/stores'
import { formatPrice } from '../lib/pricing'
import type { OfferRow } from './ProductCard'
import QtyControl from './QtyControl'

/** Hoja inferior con todas las opciones de compra (estilo "Ver oferta" de Turismocity). */
const OffersSheet: React.FC<{
  open: boolean
  onClose: () => void
  group: ProductGroup
  rows: OfferRow[]
}> = ({ open, onClose, group, rows }) => {
  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [open])

  const best = rows[0]

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50">
          <motion.div
            className="absolute inset-0 bg-slate-900/50"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            role="dialog"
            aria-label="Opciones de compra"
            className="absolute inset-x-0 bottom-0 mx-auto max-w-xl bg-white rounded-t-3xl max-h-[88dvh] flex flex-col shadow-2xl"
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ type: 'spring', damping: 32, stiffness: 340 }}
            drag="y"
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={{ top: 0, bottom: 0.5 }}
            onDragEnd={(_, info) => {
              if (info.offset.y > 120 || info.velocity.y > 600) onClose()
            }}
          >
            <div className="pt-2.5 pb-1 flex justify-center">
              <span className="w-10 h-1.5 rounded-full bg-slate-200" />
            </div>

            <div className="px-4 pb-3 flex items-center gap-3 border-b border-slate-100">
              <img src={group.imagen} alt="" className="w-12 h-12 object-contain shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400">Opciones de compra</p>
                <h3 className="text-[14px] font-semibold text-slate-900 leading-snug line-clamp-2">{group.nombre}</h3>
              </div>
              <button type="button" onClick={onClose} aria-label="Cerrar" className="p-2 -mr-2 rounded-full text-slate-400 active:bg-slate-100">
                <X size={22} />
              </button>
            </div>

            <ul className="flex-1 overflow-y-auto overscroll-contain divide-y divide-slate-100">
              {rows.map((r, idx) => {
                const diff = idx > 0 && best.eff > 0 ? Math.round(((r.eff - best.eff) / best.eff) * 100) : 0
                return (
                  <li key={`${r.o.supermercado}-${r.o.sku_id}`} className={`px-4 py-3 flex items-center gap-3 ${r.noDelivery ? 'opacity-50' : ''}`}>
                    <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: storeColor(r.o.supermercado) }} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[14px] font-bold text-slate-900">{storeLabel(r.o.supermercado)}</span>
                        {idx === 0 && rows.length > 1 && (
                          <span className="text-[10px] font-extrabold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded">MEJOR</span>
                        )}
                        {r.noDelivery && (
                          <span className="inline-flex items-center gap-0.5 text-[10px] text-red-600 font-semibold">
                            <MapPinOff size={10} /> no envía a tu CP
                          </span>
                        )}
                      </div>
                      {r.promo && (
                        <div className="text-[12px] text-orange-700 font-semibold flex items-center gap-1 mt-0.5">
                          <Flame size={12} /> {r.promo}
                          {r.minQty > 1 ? ` · llevando ${r.minQty}` : ''}
                        </div>
                      )}
                      {r.club && (
                        <div className="text-[12px] text-purple-700 font-medium flex items-center gap-1 mt-0.5">
                          <CreditCard size={12} /> {formatPrice(r.club)} con {r.o.promo_label}
                        </div>
                      )}
                      <div className="text-[12px] text-slate-400 mt-0.5">
                        {r.unit ? `${formatPrice(r.unit)}/${r.o.unit_measure}` : ''}
                        {diff > 0 ? ` · +${diff}% que el mejor` : ''}
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className={`text-[16px] font-extrabold ${idx === 0 ? 'text-emerald-700' : 'text-slate-900'}`}>
                        {formatPrice(r.eff)}
                        {r.minQty > 1 && <span className="text-[11px] font-bold text-slate-400"> c/u</span>}
                      </div>
                      {r.o.link && r.o.link.startsWith('http') && (
                        <a
                          href={r.o.link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="mt-1 inline-flex items-center gap-1 h-8 px-3 rounded-full bg-blue-600 text-white text-[12px] font-bold active:bg-blue-700"
                        >
                          Ver <ExternalLink size={12} />
                        </a>
                      )}
                    </div>
                  </li>
                )
              })}
            </ul>

            <div className="px-4 pt-3 pb-safe border-t border-slate-100 bg-white">
              <div className="pb-3 flex items-center justify-between gap-3">
                <div className="text-[13px] text-slate-500">
                  Mejor: <span className="font-extrabold text-slate-900">{formatPrice(best.eff)}</span> en {storeLabel(best.o.supermercado)}
                </div>
                <QtyControl group={group} bulkQty={best.minQty} />
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}

export default OffersSheet
