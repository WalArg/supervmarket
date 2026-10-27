import React, { useState, useEffect } from 'react'
import {
  X,
  ExternalLink,
  CheckCircle2,
  ShoppingCart,
  Zap,
  RotateCcw,
  Copy,
  Check,
  Truck,
  Sparkles,
  ShoppingBag,
} from 'lucide-react'
import type { StorePlan, CartItemDetail } from '../types'
import { formatPrice } from '../lib/pricing'
import { decorateOutboundUrl, trackOutboundAffiliateClick } from '../lib/affiliate'

export interface MeliCartAssistantModalProps {
  isOpen: boolean
  onClose: () => void
  plan: StorePlan
  loadedEans: Record<string, boolean>
  onToggleItem: (ean: string) => void
  onMarkItemLoaded: (ean: string) => void
  onResetProgress: () => void
}

export const MeliCartAssistantModal: React.FC<MeliCartAssistantModalProps> = ({
  isOpen,
  onClose,
  plan,
  loadedEans,
  onToggleItem,
  onMarkItemLoaded,
  onResetProgress,
}) => {
  const [copied, setCopied] = useState(false)

  // Lock body scroll when modal is open
  useEffect(() => {
    if (!isOpen) return
    const originalOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = originalOverflow
    }
  }, [isOpen])

  if (!isOpen) return null

  const items = plan.items || []
  const totalCount = items.length
  const loadedCount = items.filter(i => loadedEans[i.ean]).length
  const progressPct = totalCount > 0 ? Math.round((loadedCount / totalCount) * 100) : 0
  const isAllLoaded = totalCount > 0 && loadedCount === totalCount

  // Find next pending item for 1-click fast track
  const nextItem = items.find(i => !loadedEans[i.ean])

  const subtotalMerch = plan.subtotal_merch ?? plan.subtotal
  const finalTotal = plan.final_store_total ?? plan.subtotal
  const freeShippingThreshold = plan.free_shipping_threshold || 65000
  const hasFreeShipping = subtotalMerch >= freeShippingThreshold
  const missingForFreeShipping = Math.max(0, freeShippingThreshold - subtotalMerch)

  const handleOpenItem = (item: CartItemDetail) => {
    const rawUrl = item.link || 'https://www.mercadolibre.com.ar/supermercado'
    const targetUrl = decorateOutboundUrl(rawUrl, 'MercadoLibre', 'item')
    const lineTotal = (item.precio || 0) * (item.qty || 1) * (item.unit_multiplier || 1)
    trackOutboundAffiliateClick('MercadoLibre', 'item', targetUrl, lineTotal)
    onMarkItemLoaded(item.ean)
    window.open(targetUrl, '_blank', 'noopener,noreferrer')
  }

  const handleOpenCart = () => {
    const rawCart = plan.affiliate_checkout_url || plan.checkout_url || 'https://www.mercadolibre.com.ar/gz/cart'
    const cartUrl = decorateOutboundUrl(rawCart, 'MercadoLibre', 'checkout')
    trackOutboundAffiliateClick('MercadoLibre', 'checkout', cartUrl, finalTotal)
    window.open(cartUrl, '_blank', 'noopener,noreferrer')
  }

  const handleCopyList = () => {
    const text = [
      '🛒 Mi compra de Mercado Libre con SuperVmarket:',
      ...items.map(i => `• ${i.qty}× ${i.nombre || 'Producto'} — ${formatPrice((i.precio || 0) * i.qty)}`),
      `\nTotal estimado: ${formatPrice(finalTotal)}`,
      `Abrir changuito: https://www.mercadolibre.com.ar/gz/cart`,
    ].join('\n')

    navigator.clipboard?.writeText?.(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2500)
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="meli-assistant-title"
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-slate-900/60 backdrop-blur-xs p-0 sm:p-4 animate-[fade-in_0.15s_ease-out]"
    >
      {/* Click outside backdrop */}
      <div className="absolute inset-0" onClick={onClose} aria-hidden="true" />

      {/* Modal / Bottom Sheet Box */}
      <div className="relative w-full max-w-lg bg-white rounded-t-3xl sm:rounded-3xl shadow-2xl flex flex-col max-h-[92dvh] sm:max-h-[88vh] overflow-hidden z-10 border border-slate-200/80">
        {/* Header con identidad Mercado Libre */}
        <div className="bg-yellow-400 px-4 pt-3.5 pb-3 border-b border-yellow-500/30 shrink-0">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-9 h-9 rounded-xl bg-slate-900 text-yellow-400 flex items-center justify-center font-black text-sm shrink-0 shadow-xs">
                <Zap size={18} className="fill-yellow-400" />
              </div>
              <div className="min-w-0">
                <h3 id="meli-assistant-title" className="text-[15px] font-extrabold text-slate-900 leading-tight truncate">
                  Asistente de Changuito Mercado Libre
                </h3>
                <p className="text-[11.5px] text-slate-800 font-semibold truncate">
                  {loadedCount} de {totalCount} agregados · {formatPrice(finalTotal)}
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={onClose}
              aria-label="Cerrar asistente"
              className="w-11 h-11 rounded-full flex items-center justify-center text-slate-900 hover:bg-yellow-500/50 active:scale-95 transition-all shrink-0"
            >
              <X size={20} />
            </button>
          </div>

          {/* Barra de Progreso */}
          <div className="mt-3 bg-yellow-500/40 rounded-full h-2 overflow-hidden">
            <div
              className="bg-slate-900 h-full rounded-full transition-all duration-300 ease-out"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>

        {/* Guía Rápida & Beneficio Envío */}
        <div className="px-4 py-2.5 bg-slate-50 border-b border-slate-100 flex items-center justify-between gap-2 text-[12px] shrink-0">
          {hasFreeShipping ? (
            <div className="flex items-center gap-1.5 text-emerald-800 font-bold min-w-0 truncate">
              <Truck size={14} className="text-emerald-600 shrink-0" />
              <span className="truncate">¡Envío gratis en Full! (Supera {formatPrice(freeShippingThreshold)})</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 text-slate-600 font-medium min-w-0 truncate">
              <Truck size={14} className="text-slate-400 shrink-0" />
              <span className="truncate">
                Faltan <strong className="text-slate-900 font-bold">{formatPrice(missingForFreeShipping)}</strong> para envío gratis
              </span>
            </div>
          )}

          {loadedCount > 0 && (
            <button
              type="button"
              onClick={onResetProgress}
              className="min-h-[36px] px-2 text-[11px] font-bold text-slate-500 hover:text-slate-800 flex items-center gap-1 shrink-0 active:scale-95"
              title="Reiniciar progreso de carga"
            >
              <RotateCcw size={12} />
              <span>Reiniciar</span>
            </button>
          )}
        </div>

        {/* Fast-Track CTA Principal (1 Clic Inteligente) */}
        <div className="p-3 bg-yellow-50/70 border-b border-yellow-200/60 shrink-0">
          {!isAllLoaded && nextItem ? (
            <button
              type="button"
              onClick={() => handleOpenItem(nextItem)}
              className="w-full min-h-[48px] h-12 px-4 rounded-2xl bg-yellow-400 hover:bg-yellow-300 active:bg-yellow-500 text-slate-900 font-extrabold text-[13px] sm:text-[13.5px] flex items-center justify-between gap-2 shadow-sm transition-all active:scale-[0.99]"
            >
              <span className="flex items-center gap-1.5 min-w-0">
                <Zap size={16} className="fill-slate-900 shrink-0" />
                <span className="truncate">
                  Cargar siguiente: {nextItem.qty}× {nextItem.nombre}
                </span>
              </span>
              <span className="text-[11px] bg-slate-900 text-yellow-400 px-2 py-0.5 rounded-lg shrink-0 font-black">
                Abrir ↗
              </span>
            </button>
          ) : (
            <button
              type="button"
              onClick={handleOpenCart}
              className="w-full min-h-[48px] h-12 px-4 rounded-2xl bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white font-extrabold text-[13.5px] flex items-center justify-center gap-2 shadow-sm transition-all active:scale-[0.99]"
            >
              <ShoppingCart size={17} />
              <span>¡Todo cargado! Ir a pagar en Mercado Libre</span>
            </button>
          )}

          <p className="text-[11px] text-slate-500 text-center mt-1.5 leading-tight">
            Tocá el producto, dale <span className="font-bold text-slate-800">"Agregar al carrito"</span> en MeLi y volvé acá.
          </p>
        </div>

        {/* Lista Scrollable de Productos */}
        <div className="flex-1 overflow-y-auto px-4 divide-y divide-slate-100 overscroll-contain">
          {items.map((i, idx) => {
            const isLoaded = Boolean(loadedEans[i.ean])
            const lineTotal = (i.precio || 0) * (i.qty || 1) * (i.unit_multiplier || 1)

            return (
              <div
                key={i.ean || idx}
                className={`py-3 flex items-center gap-3 transition-colors ${
                  isLoaded ? 'opacity-85 bg-emerald-50/20 -mx-4 px-4' : ''
                }`}
              >
                {/* Checkbox / Indicador táctil */}
                <button
                  type="button"
                  onClick={() => onToggleItem(i.ean)}
                  aria-label={isLoaded ? `Marcar ${i.nombre} como no agregado` : `Marcar ${i.nombre} como agregado`}
                  className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 transition-all ${
                    isLoaded
                      ? 'bg-emerald-100 text-emerald-700 border border-emerald-300'
                      : 'bg-slate-100 text-slate-400 hover:bg-slate-200 border border-slate-200'
                  }`}
                >
                  {isLoaded ? <CheckCircle2 size={19} className="text-emerald-600" /> : <span className="text-[12px] font-bold">{idx + 1}</span>}
                </button>

                {/* Imagen del Producto */}
                {i.imagen ? (
                  <img
                    src={i.imagen}
                    alt=""
                    className="w-12 h-12 rounded-xl object-contain bg-white border border-slate-200/80 p-1 shrink-0"
                  />
                ) : (
                  <div className="w-12 h-12 rounded-xl bg-slate-100 border border-slate-200/80 flex items-center justify-center shrink-0 text-slate-400">
                    <ShoppingBag size={18} />
                  </div>
                )}

                {/* Detalle y Precios */}
                <div className="min-w-0 flex-1">
                  <p className="text-[12.5px] font-bold text-slate-900 leading-snug line-clamp-2">
                    {i.qty}× {i.nombre}
                  </p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-[12px] font-extrabold text-slate-900">
                      {formatPrice(lineTotal)}
                    </span>
                    {i.qty > 1 && (
                      <span className="text-[10.5px] text-slate-400 font-medium">
                        ({formatPrice(i.precio)} c/u)
                      </span>
                    )}
                    {isLoaded && (
                      <span className="text-[10px] font-bold text-emerald-700 bg-emerald-100/70 px-1.5 py-0.5 rounded-md">
                        ✓ En changuito
                      </span>
                    )}
                  </div>
                </div>

                {/* Botón de Acción individual (Touch target >= 44x44px) */}
                <div className="shrink-0 flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => handleOpenItem(i)}
                    className={`min-h-[44px] px-3 rounded-xl font-bold text-[11.5px] flex items-center justify-center gap-1.5 transition-all active:scale-95 ${
                      isLoaded
                        ? 'bg-slate-100 hover:bg-slate-200 text-slate-700'
                        : 'bg-yellow-400 hover:bg-yellow-300 text-slate-900 shadow-xs'
                    }`}
                    title={isLoaded ? 'Reabrir publicación en Mercado Libre' : 'Cargar en Mercado Libre'}
                  >
                    <span>{isLoaded ? 'Reabrir' : 'Cargar'}</span>
                    <ExternalLink size={12} className="opacity-70" />
                  </button>
                </div>
              </div>
            )
          })}
        </div>

        {/* Footer Fijo de Acciones Finales */}
        <div className="p-3.5 bg-slate-50 border-t border-slate-200/80 shrink-0 space-y-2">
          <div className="flex items-center justify-between text-[13px] px-1">
            <span className="text-slate-600 font-semibold">Total Mercado Libre:</span>
            <span className="text-[16px] font-extrabold text-slate-900">{formatPrice(finalTotal)}</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {/* Botón Pagar en MeLi (min-h-[48px] h-12 w-full rounded-xl) */}
            <button
              type="button"
              onClick={handleOpenCart}
              className="min-h-[48px] h-12 w-full rounded-xl bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white font-extrabold text-[13.5px] flex items-center justify-center gap-2 transition-all shadow-sm active:scale-[0.98]"
            >
              <ShoppingCart size={16} />
              <span>Ir a pagar a Mercado Libre</span>
              <ExternalLink size={14} className="opacity-80" />
            </button>

            {/* Botón Copiar Lista (min-h-[44px] px-3 rounded-xl) */}
            <button
              type="button"
              onClick={handleCopyList}
              className="min-h-[44px] px-3 rounded-xl bg-white border border-slate-200 hover:bg-slate-100 text-slate-800 font-bold text-[12px] flex items-center justify-center gap-1.5 transition-all active:scale-[0.98]"
            >
              {copied ? (
                <>
                  <Check size={14} className="text-emerald-600" />
                  <span className="text-emerald-700 font-extrabold">¡Copiado al portapapeles!</span>
                </>
              ) : (
                <>
                  <Copy size={14} className="text-slate-500" />
                  <span>Copiar resumen de compra</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default MeliCartAssistantModal
