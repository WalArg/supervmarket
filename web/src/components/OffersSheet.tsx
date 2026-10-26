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
                  <li key={`${r.o.supermercado}-${r.o.sku_id}`} className={`px-4 py-3 ${r.noDelivery ? 'opacity-50' : ''}`}>
                    <div className="flex items-center gap-3">
                      <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: storeColor(r.o.supermercado) }} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 flex-wrap">
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

                        {/* Vendedor y semáforo de reputación en Mercado Libre */}
                        {r.o.seller_name && (
                          <div className="flex items-center gap-1.5 mt-0.5 text-[12px] text-slate-600 flex-wrap">
                            <span className="text-slate-400">Vendido por:</span>
                            <span className="font-semibold text-slate-800">{r.o.seller_name}</span>
                            {r.o.seller_reputation && (
                              <span
                                className={`w-2 h-2 rounded-full shrink-0 ${
                                  r.o.seller_reputation === '5_green'
                                    ? 'bg-emerald-500'
                                    : r.o.seller_reputation === '4_light_green'
                                    ? 'bg-lime-500'
                                    : r.o.seller_reputation === '3_yellow'
                                    ? 'bg-amber-400'
                                    : 'bg-red-500'
                                }`}
                                title={
                                  r.o.seller_reputation === '5_green'
                                    ? `Excelente reputación (MercadoLíder ${r.o.power_seller_status || 'Platinum'})`
                                    : r.o.seller_reputation === '3_yellow'
                                    ? 'Termómetro Amarillo (Atención regular / Oficial)'
                                    : 'Reputación en evaluación'
                                }
                              />
                            )}
                            {r.o.power_seller_status && (
                              <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-1 rounded">
                                {r.o.power_seller_status === 'platinum' ? 'Platinum' : r.o.power_seller_status}
                              </span>
                            )}
                            {r.o.is_full && (
                              <span className="text-[10px] font-bold text-emerald-800 bg-emerald-100 px-1 rounded">
                                ⚡ FULL
                              </span>
                            )}
                          </div>
                        )}

                        {/* Umbral de envío gratis para Mercado Libre */}
                        {r.o.supermercado === 'MercadoLibre' && (
                          <div className="text-[11px] text-slate-500 mt-0.5 flex items-center gap-1 flex-wrap">
                            <span>🚚</span>
                            {r.eff >= (r.o.free_shipping_threshold || 33000) ? (
                              <span className="text-emerald-700 font-semibold">¡Envío gratis incluido!</span>
                            ) : (
                              <span>
                                Envío gratis desde $33.000 (o $15.000 c/Meli+)
                                {r.eff * 2 >= 33000 ? (
                                  <strong className="text-emerald-700 font-bold ml-1">· ¡Llevando 2 tenés envío gratis!</strong>
                                ) : (
                                  <span className="text-slate-400 ml-1">· Faltan {formatPrice(33000 - r.eff)}</span>
                                )}
                              </span>
                            )}
                          </div>
                        )}

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
                    </div>

                    {/* Sub-opciones destacadas dentro de Mercado Libre */}
                    {r.o.meli_options && r.o.meli_options.length > 1 && (
                      <div className="mt-2.5 pt-2 border-t border-slate-100">
                        <div className="text-[10.5px] font-bold uppercase tracking-wider text-slate-400 mb-1.5 flex items-center gap-1">
                          <span>Top {r.o.meli_options.length} opciones en Mercado Libre</span>
                        </div>
                        <div className="space-y-1.5">
                          {r.o.meli_options.map((opt, oIdx) => (
                            <div
                              key={opt.item_id || oIdx}
                              className="p-2 rounded-xl bg-slate-50 border border-slate-100/80 flex items-center justify-between gap-2"
                            >
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-1.5 flex-wrap">
                                  <span
                                    className={`w-2 h-2 rounded-full shrink-0 ${
                                      opt.reputation === '5_green'
                                        ? 'bg-emerald-500'
                                        : opt.reputation === '4_light_green'
                                        ? 'bg-lime-500'
                                        : opt.reputation === '3_yellow'
                                        ? 'bg-amber-400'
                                        : 'bg-slate-300'
                                    }`}
                                    title={`Reputación: ${opt.reputation}`}
                                  />
                                  <span className="text-[12px] font-bold text-slate-800 truncate">
                                    {opt.seller_name}
                                  </span>
                                  {opt.power_status && (
                                    <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-100/70 px-1 rounded">
                                      {opt.power_status === 'platinum' ? 'Platinum' : opt.power_status}
                                    </span>
                                  )}
                                  {opt.is_full && (
                                    <span className="text-[10px] font-bold text-emerald-800 bg-emerald-100 px-1 rounded">
                                      ⚡ FULL
                                    </span>
                                  )}
                                </div>
                                <div className="text-[11px] text-slate-500 mt-0.5">
                                  {opt.free_shipping ? '🚚 Envío gratis' : '🚚 Envío a domicilio'}
                                </div>
                              </div>
                              <div className="text-right shrink-0 flex items-center gap-2">
                                <span className="font-extrabold text-slate-900 text-[13px]">
                                  {formatPrice(opt.price)}
                                </span>
                                {opt.link && (
                                  <a
                                    href={opt.link}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex items-center gap-1 h-7 px-2.5 rounded-lg bg-blue-600 text-white text-[11px] font-bold active:bg-blue-700 transition-colors"
                                  >
                                    Ver <ExternalLink size={10} />
                                  </a>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
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
