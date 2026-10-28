import React, { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { X, ExternalLink, Flame, CreditCard, MapPinOff, Plus, Minus, Check } from 'lucide-react'
import type { ProductGroup } from '../types'
import { storeColor, storeLabel } from '../lib/stores'
import { formatPrice } from '../lib/pricing'
import { useCart, getItemKey } from '../cart/CartContext'
import type { OfferRow } from './ProductCard'

/** Hoja inferior con todas las opciones de compra y agregado directo al changuito. */
const OffersSheet: React.FC<{
  open: boolean
  onClose: () => void
  group: ProductGroup
  rows: OfferRow[]
}> = ({ open, onClose, group, rows }) => {
  const { add, setQty, qtyOf, items } = useCart()
  const [justAddedKey, setJustAddedKey] = useState<string | null>(null)

  const ean = group.ean || group.offers?.[0]?.ean || (group as any).id || group.nombre
  const totalInCart = qtyOf(ean)
  const cartItemsForThisProduct = items.filter(
    i => i.ean === ean || (i.id && i.id.startsWith(`${ean}::`)),
  )

  const best = rows[0]

  const handleAddOffer = (
    key: string,
    qty: number = 1,
    store?: string,
    extra?: { link?: string; precio?: number; sku_id?: string },
  ) => {
    add(group, qty, store, extra)
    setJustAddedKey(key)
    navigator.vibrate?.(10)
    setTimeout(() => {
      setJustAddedKey(prev => (prev === key ? null : prev))
    }, 1800)
  }

  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [open])

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
                <p className="text-[10.5px] text-blue-700 font-semibold mt-0.5">
                  🔍 Comparativa en vivo de precios y stock entre supermercados
                </p>
              </div>
              <button type="button" onClick={onClose} aria-label="Cerrar" className="p-2 -mr-2 rounded-full text-slate-400 active:bg-slate-100">
                <X size={22} />
              </button>
            </div>

            <ul className="flex-1 overflow-y-auto overscroll-contain divide-y divide-slate-100">
              {rows.map((r, idx) => {
                const diff = idx > 0 && best.eff > 0 ? Math.round(((r.eff - best.eff) / best.eff) * 100) : 0
                const rowKey = getItemKey(ean, r.o.supermercado, r.o.sku_id)
                const rowQty = qtyOf(rowKey)
                const isJustAdded = justAddedKey === rowKey

                return (
                  <li
                    key={`${r.o.supermercado}-${r.o.sku_id || idx}`}
                    className={`px-4 py-3 transition-colors ${
                      rowQty > 0 ? 'bg-blue-50/40' : ''
                    } ${r.noDelivery ? 'opacity-50' : ''}`}
                  >
                    <div className="flex items-center gap-3">
                      <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: storeColor(r.o.supermercado) }} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="text-[14px] font-bold text-slate-900">{storeLabel(r.o.supermercado)}</span>
                          {idx === 0 && rows.length > 1 && (
                            <span className="text-[10px] font-extrabold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded">MEJOR</span>
                          )}
                          {rowQty > 0 && (
                            <span className="text-[10px] font-extrabold text-blue-700 bg-blue-100/80 px-1.5 py-0.5 rounded flex items-center gap-0.5">
                              <Check size={10} strokeWidth={3} /> {rowQty} en changuito
                            </span>
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
                                title={`Reputación: ${r.o.seller_reputation}`}
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

                        {/* Estado oficial de envío desde la API de Mercado Libre */}
                        {r.o.supermercado === 'MercadoLibre' && (
                          <div className="text-[11px] text-slate-500 mt-0.5 flex items-center gap-1 flex-wrap">
                            {r.o.free_shipping ? (
                              <span className="text-emerald-700 font-semibold flex items-center gap-1">
                                🚚 ¡Envío gratis oficial en esta publicación!
                              </span>
                            ) : r.o.is_full ? (
                              <span className="text-slate-600 flex items-center gap-1">
                                <span>⚡</span>
                                <span>Envío FULL · Acumulable en changuito (Envío gratis superando $65.000)</span>
                              </span>
                            ) : (
                              <span className="text-slate-500 flex items-center gap-1">
                                <span>🚚</span>
                                <span>Envío con costo según destino</span>
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
                      <div className="text-right shrink-0 flex flex-col items-end">
                        <div className={`text-[16px] font-extrabold ${idx === 0 ? 'text-emerald-700' : 'text-slate-900'}`}>
                          {formatPrice(r.eff)}
                          {r.minQty > 1 && <span className="text-[11px] font-bold text-slate-400"> c/u</span>}
                        </div>

                        {/* Botón principal: AGREGAR O CONTROLAR CANTIDAD INDEPENDIENTE */}
                        {rowQty > 0 ? (
                          <div className="mt-1 flex items-center h-[34px] rounded-xl border border-blue-600 bg-blue-600 text-white shadow-2xs">
                            <button
                              type="button"
                              onClick={() => {
                                navigator.vibrate?.(8)
                                setQty(rowKey, rowQty - 1)
                              }}
                              className="w-8 h-full flex items-center justify-center hover:bg-blue-700 active:bg-blue-800 rounded-l-xl transition-colors"
                              aria-label={`Restar una unidad de ${storeLabel(r.o.supermercado)}`}
                            >
                              <Minus size={13} strokeWidth={3} />
                            </button>
                            <span className="w-6 text-center text-[12px] font-extrabold">{rowQty}</span>
                            <button
                              type="button"
                              onClick={() => {
                                navigator.vibrate?.(8)
                                handleAddOffer(rowKey, 1, r.o.supermercado, {
                                  link: r.o.link,
                                  precio: r.eff,
                                  sku_id: r.o.sku_id,
                                })
                              }}
                              className="w-8 h-full flex items-center justify-center hover:bg-blue-700 active:bg-blue-800 rounded-r-xl transition-colors"
                              aria-label={`Sumar una unidad de ${storeLabel(r.o.supermercado)}`}
                            >
                              <Plus size={13} strokeWidth={3} />
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() =>
                              handleAddOffer(
                                rowKey,
                                r.minQty || 1,
                                r.o.supermercado,
                                {
                                  link: r.o.link,
                                  precio: r.eff,
                                  sku_id: r.o.sku_id,
                                },
                              )
                            }
                            className={`mt-1 min-h-[34px] h-[34px] px-3 rounded-xl font-bold text-[12px] flex items-center justify-center gap-1 transition-all active:scale-95 shadow-2xs ${
                              isJustAdded
                                ? 'bg-emerald-600 text-white'
                                : 'bg-blue-600 hover:bg-blue-700 text-white'
                            }`}
                            title={`Agregar oferta de ${storeLabel(r.o.supermercado)} al carrito`}
                          >
                            {isJustAdded ? (
                              <>
                                <Check size={13} strokeWidth={3} />
                                <span>Agregado</span>
                              </>
                            ) : (
                              <>
                                <Plus size={14} strokeWidth={3} />
                                <span>{r.minQty > 1 ? `Sumar (${r.minQty})` : 'Agregar'}</span>
                              </>
                            )}
                          </button>
                        )}

                        {/* Enlace secundario opcional y discreto hacia la web oficial */}
                        {r.o.link && r.o.link.startsWith('http') && (
                          <a
                            href={r.o.link}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="mt-1 text-[11px] text-slate-400 hover:text-blue-600 flex items-center gap-0.5"
                            title={`Abrir página oficial de ${storeLabel(r.o.supermercado)}`}
                          >
                            <span>Ver web</span>
                            <ExternalLink size={10} />
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
                          {[...r.o.meli_options]
                            .sort((a, b) => a.price - b.price)
                            .map((opt, oIdx) => {
                              const optKey = getItemKey(ean, 'MercadoLibre', opt.item_id)
                              const optQty = qtyOf(optKey)
                              const isJustAddedOpt = justAddedKey === optKey

                              return (
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
                                      {opt.free_shipping ? '🚚 Envío gratis oficial' : opt.is_full ? '⚡ FULL · Acumulable' : '🚚 Envío a domicilio'}
                                    </div>
                                  </div>
                                  <div className="text-right shrink-0 flex items-center gap-2">
                                    <span className="font-extrabold text-slate-900 text-[13px]">
                                      {formatPrice(opt.price)}
                                    </span>

                                    {optQty > 0 ? (
                                      <div className="flex items-center h-7 rounded-lg border border-blue-600 bg-blue-600 text-white shadow-2xs">
                                        <button
                                          type="button"
                                          onClick={() => {
                                            navigator.vibrate?.(8)
                                            setQty(optKey, optQty - 1)
                                          }}
                                          className="w-6 h-full flex items-center justify-center hover:bg-blue-700 active:bg-blue-800 rounded-l-lg"
                                          aria-label={`Restar una unidad de ${opt.seller_name}`}
                                        >
                                          <Minus size={11} strokeWidth={3} />
                                        </button>
                                        <span className="w-5 text-center text-[11px] font-extrabold">{optQty}</span>
                                        <button
                                          type="button"
                                          onClick={() => {
                                            navigator.vibrate?.(8)
                                            handleAddOffer(
                                              optKey,
                                              1,
                                              'MercadoLibre',
                                              {
                                                link: opt.link,
                                                precio: opt.price,
                                                sku_id: opt.item_id,
                                              },
                                            )
                                          }}
                                          className="w-6 h-full flex items-center justify-center hover:bg-blue-700 active:bg-blue-800 rounded-r-lg"
                                          aria-label={`Sumar una unidad de ${opt.seller_name}`}
                                        >
                                          <Plus size={11} strokeWidth={3} />
                                        </button>
                                      </div>
                                    ) : (
                                      <button
                                        type="button"
                                        title={`Agregar opción de ${opt.seller_name}`}
                                        onClick={() =>
                                          handleAddOffer(
                                            optKey,
                                            1,
                                            'MercadoLibre',
                                            {
                                              link: opt.link,
                                              precio: opt.price,
                                              sku_id: opt.item_id,
                                            },
                                          )
                                        }
                                        className={`h-7 px-2.5 rounded-lg text-[11px] font-bold flex items-center gap-1 transition-all active:scale-95 ${
                                          isJustAddedOpt
                                            ? 'bg-emerald-600 text-white'
                                            : 'bg-blue-600 hover:bg-blue-700 text-white'
                                        }`}
                                      >
                                        {isJustAddedOpt ? (
                                          <>
                                            <Check size={12} strokeWidth={3} />
                                            <span>Agregado</span>
                                          </>
                                        ) : (
                                          <>
                                            <Plus size={12} strokeWidth={3} />
                                            <span>Agregar</span>
                                          </>
                                        )}
                                      </button>
                                    )}

                                    {opt.link && (
                                      <a
                                        href={opt.link}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="p-1 text-slate-400 hover:text-blue-600"
                                        title="Ver en Mercado Libre"
                                      >
                                        <ExternalLink size={11} />
                                      </a>
                                    )}
                                  </div>
                                </div>
                              )
                            })}
                        </div>
                      </div>
                    )}
                  </li>
                )
              })}
            </ul>

            {/* BARRA INFERIOR DINÁMICA: Refleja con precisión la tienda y precio elegidos */}
            <div className="px-4 pt-3 pb-safe border-t border-slate-100 bg-white">
              <div className="pb-3 flex items-center justify-between gap-3">
                <div className="min-w-0 flex-1">
                  {totalInCart > 0 ? (
                    <div>
                      <p className="text-[13px] font-extrabold text-slate-900 leading-tight truncate">
                        En changuito: <span className="text-blue-700">{totalInCart} un.</span> en total
                      </p>
                      <p className="text-[11px] text-slate-500 mt-0.5 truncate">
                        {cartItemsForThisProduct.length > 1
                          ? `${cartItemsForThisProduct.length} ofertas distintas agregadas`
                          : `En ${storeLabel(cartItemsForThisProduct[0]?.store || best.o.supermercado)}`}
                      </p>
                    </div>
                  ) : (
                    <div>
                      <p className="text-[13px] text-slate-600 leading-tight">
                        Mejor precio: <span className="font-extrabold text-slate-900">{formatPrice(best.eff)}</span> en {storeLabel(best.o.supermercado)}
                      </p>
                      <p className="text-[11px] text-slate-400 mt-0.5">Elegí tu opción preferida arriba</p>
                    </div>
                  )}
                </div>

                {totalInCart > 0 ? (
                  <button
                    type="button"
                    onClick={onClose}
                    className="h-10 px-4 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-[13px] font-extrabold flex items-center gap-1 active:scale-95 transition-all shadow-xs shrink-0"
                  >
                    <Check size={16} strokeWidth={3} /> Listo
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() =>
                      handleAddOffer(
                        getItemKey(ean, best.o.supermercado, best.o.sku_id),
                        best.minQty || 1,
                        best.o.supermercado,
                        { link: best.o.link, precio: best.eff, sku_id: best.o.sku_id },
                      )
                    }
                    className="h-10 px-3.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-[13px] font-extrabold flex items-center gap-1 active:scale-95 transition-all shadow-xs shrink-0"
                  >
                    <Plus size={16} strokeWidth={3} /> Agregar mejor
                  </button>
                )}
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}

export default OffersSheet
