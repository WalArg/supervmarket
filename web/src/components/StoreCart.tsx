import React, { useEffect, useState } from 'react'
import {
  ExternalLink,
  CheckCircle2,
  AlertTriangle,
  CreditCard,
  Flame,
  Truck,
  Copy,
  Check,
  Sparkles,
} from 'lucide-react'
import type { StorePlan } from '../types'
import { validateCart } from '../api'
import { useLocation } from '../location/LocationContext'
import { storeColor, storeLabel } from '../lib/stores'
import { formatPrice } from '../lib/pricing'
import { decorateOutboundUrl, trackOutboundAffiliateClick } from '../lib/affiliate'

interface Validation {
  status?: string
  total?: number
  sin_stock?: string[]
  checkout_url?: string
}

export const StoreCart: React.FC<{ plan: StorePlan }> = ({ plan }) => {
  const { cp } = useLocation()
  const [validation, setValidation] = useState<Validation | null>(null)
  const [checking, setChecking] = useState(false)
  const [copied, setCopied] = useState(false)

  // Real-time stock and price validation against store cart API
  useEffect(() => {
    if (!plan.supports_cart || !plan.items.length) return
    let alive = true
    setChecking(true)
    validateCart(
      plan.supermercado,
      plan.items.map(i => ({ sku_id: i.sku_id || '', qty: i.qty, nombre: i.nombre })),
      cp,
    )
      .then(v => {
        if (alive) setValidation(v)
      })
      .catch(() => {})
      .finally(() => {
        if (alive) setChecking(false)
      })
    return () => {
      alive = false
    }
  }, [plan.supermercado, cp, plan.items.map(i => `${i.sku_id}:${i.qty}`).join(',')])

  // Financial metrics calculation
  const subtotalMerch =
    validation?.total && validation.total > 0
      ? validation.total
      : (plan.subtotal_merch ?? plan.subtotal)

  const volumeSavings = plan.volume_discounts_total ?? plan.ahorro ?? 0
  const bankDiscount = plan.bank_discount_amount ?? plan.reintegro_bancario ?? 0
  const bankCardLabel = plan.bank_card_applied || plan.bank_benefit?.label

  const threshold = plan.free_shipping_threshold ?? 0
  const isFreeShipping = Boolean(
    plan.is_free_shipping || (threshold > 0 && subtotalMerch >= threshold),
  )
  const amountForFreeShipping =
    plan.amount_for_free_shipping ??
    plan.falta_envio_gratis ??
    Math.max(0, threshold - subtotalMerch)
  const shippingFee = isFreeShipping ? 0 : (plan.shipping_fee ?? plan.envio_estimado ?? 0)

  const finalTotal =
    plan.final_store_total ?? Math.max(0, subtotalMerch - bankDiscount + shippingFee)
  const sinStock = validation?.sin_stock || []
  const rawCheckout = plan.affiliate_checkout_url || validation?.checkout_url || plan.checkout_url
  const checkout = rawCheckout ? decorateOutboundUrl(rawCheckout, plan.supermercado, 'checkout') : null
  const isCoto = plan.supermercado === 'Coto'

  // Free shipping progress percentage
  const shippingProgressPct =
    threshold > 0
      ? Math.min(100, Math.round((subtotalMerch / threshold) * 100))
      : 100

  const handleCopyList = () => {
    const text = plan.items.map(i => `${i.qty}× ${i.nombre}`).join('\n')
    navigator.clipboard?.writeText?.(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2500)
  }

  const handleCopyAndOpenCoto = () => {
    handleCopyList()
    const targetUrl = decorateOutboundUrl(
      'https://www.cotodigital3.com.ar/sitios/cdigi/',
      'Coto',
      'coto',
    )
    trackOutboundAffiliateClick('Coto', 'coto', targetUrl, finalTotal)
    window.open(targetUrl, '_blank', 'noopener,noreferrer')
  }

  return (
    <div className="bg-white rounded-2xl border border-slate-200/80 shadow-2xs overflow-hidden transition-all">
      {/* Store Header */}
      <div className="px-4 pt-3.5 pb-2.5 flex items-start justify-between gap-3 border-b border-slate-100 bg-slate-50/50">
        <div className="flex items-center gap-2.5 min-w-0">
          <span
            className="w-3.5 h-3.5 rounded-full shrink-0 shadow-2xs"
            style={{ background: storeColor(plan.supermercado) }}
          />
          <div className="min-w-0">
            <h3 className="font-extrabold text-[16px] text-slate-900 truncate">
              {storeLabel(plan.supermercado)}
            </h3>
            <p className="text-[12px] text-slate-500">
              {plan.items.length} {plan.items.length === 1 ? 'producto' : 'productos'}
              {volumeSavings > 0 && (
                <span className="text-emerald-700 font-bold">
                  {' '}· ahorrás {formatPrice(volumeSavings)}
                </span>
              )}
            </p>
          </div>
        </div>

        <div className="text-right shrink-0">
          <div className="text-[18px] font-extrabold text-slate-900 tracking-tight">
            {formatPrice(finalTotal)}
          </div>
          {checking ? (
            <div className="text-[11px] text-slate-400">verificando stock…</div>
          ) : validation?.total ? (
            <div className="text-[11px] text-emerald-700 font-bold flex items-center justify-end gap-1">
              <CheckCircle2 size={12} /> verificado en vivo
            </div>
          ) : null}
        </div>
      </div>

      {/* Items List */}
      <ul className="px-4 divide-y divide-slate-100">
        {plan.items.map(i => {
          const regularPrice = i.precio_regular || i.precio_base || i.precio
          const hasDiscount = regularPrice > i.precio || Boolean(i.applied_promo || i.promo_badge)
          const lineTotal = i.line_total ?? (i.precio * i.qty * (i.unit_multiplier || 1))

          return (
            <li key={i.ean} className="py-2.5 flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                {i.link && i.link.startsWith('http') ? (
                  <a
                    href={decorateOutboundUrl(i.link, plan.supermercado, 'item')}
                    onClick={() => {
                      const itemUrl = decorateOutboundUrl(i.link, plan.supermercado, 'item')
                      trackOutboundAffiliateClick(plan.supermercado, 'item', itemUrl, lineTotal)
                    }}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[13px] text-slate-800 leading-snug line-clamp-2 hover:text-blue-600 transition-colors inline-flex items-center gap-1 group font-medium"
                  >
                    <span>
                      <span className="font-extrabold text-slate-900">
                        {i.qty}×
                        {i.unit_multiplier && i.unit_multiplier !== 1
                          ? ` (~${Math.round(i.qty * i.unit_multiplier * 10) / 10} kg)`
                          : ''}
                      </span>{' '}
                      {i.nombre}
                    </span>
                    <ExternalLink
                      size={12}
                      className="opacity-40 group-hover:opacity-100 text-blue-500 shrink-0 transition-opacity"
                    />
                  </a>
                ) : (
                  <p className="text-[13px] text-slate-800 leading-snug line-clamp-2 font-medium">
                    <span className="font-extrabold text-slate-900">
                      {i.qty}×
                      {i.unit_multiplier && i.unit_multiplier !== 1
                        ? ` (~${Math.round(i.qty * i.unit_multiplier * 10) / 10} kg)`
                        : ''}
                    </span>{' '}
                    {i.nombre}
                  </p>
                )}

                {/* Promo Badge & Price Breakdown */}
                <div className="flex flex-wrap items-center gap-2 mt-1">
                  {(i.applied_promo || i.promo_badge) && (
                    <span className="inline-flex items-center gap-1 text-[11px] font-bold text-orange-700 bg-orange-50 border border-orange-200/60 px-1.5 py-0.5 rounded-md">
                      <Flame size={11} className="text-orange-500" />
                      {i.applied_promo || i.promo_badge}
                    </span>
                  )}
                  {hasDiscount && (
                    <span className="text-[11px] text-slate-400 line-through">
                      {formatPrice(regularPrice * i.qty * (i.unit_multiplier || 1))}
                    </span>
                  )}
                  {(i.ahorro_linea ?? 0) > 0 && (
                    <span className="text-[11px] font-semibold text-emerald-700">
                      ahorrás {formatPrice(i.ahorro_linea!)}
                    </span>
                  )}
                </div>
              </div>

              <span className="text-[13px] font-extrabold text-slate-900 whitespace-nowrap pt-0.5">
                {formatPrice(lineTotal)}
              </span>
            </li>
          )
        })}
      </ul>

      {/* Financial Breakdown Ledger */}
      <div className="px-4 py-3 bg-slate-50/70 border-t border-slate-100 space-y-2 text-[12px]">
        {/* Subtotal Mercadería */}
        <div className="flex items-center justify-between text-slate-600">
          <span>Subtotal mercadería</span>
          <span className="font-semibold text-slate-800">{formatPrice(subtotalMerch)}</span>
        </div>

        {/* Volume Discounts */}
        {volumeSavings > 0 && (
          <div className="flex items-center justify-between text-emerald-700 font-medium">
            <span className="flex items-center gap-1.5">
              <Sparkles size={13} className="text-emerald-600" />
              Descuentos por volumen (2x1, promos)
            </span>
            <span className="font-extrabold">-{formatPrice(volumeSavings)}</span>
          </div>
        )}

        {/* Bank Card Perk */}
        {bankDiscount > 0 && (
          <div className="flex items-center justify-between text-purple-900 bg-purple-50/80 border border-purple-200/60 rounded-xl px-2.5 py-1.5 font-medium">
            <span className="flex items-center gap-1.5 min-w-0">
              <CreditCard size={14} className="text-purple-600 shrink-0" />
              <span className="truncate font-semibold">{bankCardLabel || 'Beneficio bancario'}</span>
            </span>
            <span className="font-extrabold text-emerald-700 whitespace-nowrap ml-2">
              -{formatPrice(bankDiscount)}
            </span>
          </div>
        )}

        {/* Quoted Delivery Fee */}
        <div className="flex items-center justify-between text-slate-600">
          <span className="flex items-center gap-1.5">
            <Truck size={13} className="text-slate-500" />
            Costo de entrega estimado
          </span>
          {isFreeShipping ? (
            <span className="font-extrabold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md">
              ¡Gratis!
            </span>
          ) : shippingFee > 0 ? (
            <span className="font-semibold text-slate-800">+{formatPrice(shippingFee)}</span>
          ) : (
            <span className="text-slate-400 font-medium">$0 (o no cotizado)</span>
          )}
        </div>

        {/* Total Final Store Row */}
        <div className="pt-2 border-t border-slate-200/80 flex items-center justify-between">
          <span className="font-extrabold text-[13px] text-slate-900">
            Total en {storeLabel(plan.supermercado)}
          </span>
          <span className="font-extrabold text-[15px] text-slate-900">
            {formatPrice(finalTotal)}
          </span>
        </div>
      </div>

      {/* Free Shipping Progress Gauge */}
      {threshold > 0 && (
        <div className="px-4 py-2.5 border-t border-slate-100 bg-white">
          {isFreeShipping ? (
            <div className="flex items-center gap-2 text-[12px] font-bold text-emerald-800 bg-emerald-50 border border-emerald-200/60 rounded-xl px-3 py-2">
              <Truck size={15} className="text-emerald-600 shrink-0" />
              <span>✓ ¡Tenés envío gratis en {storeLabel(plan.supermercado)}!</span>
            </div>
          ) : (
            <div className="space-y-1.5 bg-slate-50/80 border border-slate-200/70 rounded-xl p-3">
              <div className="flex items-center justify-between text-[12px]">
                <span className="flex items-center gap-1.5 text-slate-700 font-medium">
                  <Truck size={14} className="text-slate-500" />
                  Progreso a envío gratis
                </span>
                <span className="font-extrabold text-slate-800">{shippingProgressPct}%</span>
              </div>
              {/* Visual Gauge Bar */}
              <div className="w-full bg-slate-200 rounded-full h-2.5 overflow-hidden">
                <div
                  className="bg-emerald-500 h-full rounded-full transition-all duration-500 ease-out"
                  style={{ width: `${shippingProgressPct}%` }}
                />
              </div>
              <div className="flex items-center justify-between text-[11px] text-slate-500 pt-0.5">
                <span>
                  Te faltan{' '}
                  <strong className="text-slate-800 font-extrabold">
                    {formatPrice(amountForFreeShipping)}
                  </strong>
                </span>
                <span>Meta: {formatPrice(threshold)}</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Out of Stock Alert from live validation */}
      {sinStock.length > 0 && (
        <div className="px-4 pt-2">
          <div className="flex items-start gap-2 text-[12px] text-red-700 bg-red-50 border border-red-200/60 rounded-xl p-2.5">
            <AlertTriangle size={15} className="shrink-0 mt-0.5 text-red-600" />
            <span>Sin stock en tu zona: {sinStock.join(', ')}</span>
          </div>
        </div>
      )}

      {/* Actions / Checkout Footer */}
      <div className="p-4 space-y-2.5 bg-white border-t border-slate-100">
        {/* Coto Digital: Streamlined 1-Tap Copy & Open web (touch targets >= 44px) */}
        {isCoto ? (
          <div className="bg-amber-50/80 border border-amber-200/80 rounded-xl p-3 space-y-2.5 text-[12px]">
            <div className="flex items-start gap-2 text-amber-900">
              <AlertTriangle size={15} className="text-amber-600 shrink-0 mt-0.5" />
              <span>
                <strong>Coto Digital:</strong> No permite carga de changuito por URL externa. Podés copiar tu lista y abrir su web en 1 toque.
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <button
                type="button"
                onClick={handleCopyAndOpenCoto}
                className="min-h-[44px] px-3 rounded-xl bg-amber-600 hover:bg-amber-700 text-white font-extrabold text-[12.5px] flex items-center justify-center gap-1.5 transition-all active:scale-[0.98] shadow-xs"
              >
                {copied ? (
                  <>
                    <Check size={14} className="text-white" />
                    <span>¡Copiado! Abriendo Coto...</span>
                  </>
                ) : (
                  <>
                    <Copy size={14} />
                    <span>Copiar lista y abrir web</span>
                  </>
                )}
              </button>
              <button
                type="button"
                onClick={handleCopyList}
                className="min-h-[44px] px-3 rounded-xl bg-white border border-amber-200 hover:bg-amber-50 text-amber-900 font-bold text-[12px] flex items-center justify-center gap-1.5 transition-all active:scale-[0.98]"
              >
                {copied ? (
                  <>
                    <Check size={14} className="text-emerald-700" />
                    <span className="text-emerald-800">¡Copiado al portapapeles!</span>
                  </>
                ) : (
                  <>
                    <Copy size={14} />
                    <span>Solo copiar lista</span>
                  </>
                )}
              </button>
            </div>
          </div>
        ) : null}

        {/* VTEX / Official Retailer Checkout Button (touch target >= 44px: h-12 = 48px) */}
        {checkout && checkout.startsWith('http') && !isCoto ? (
          <a
            href={checkout}
            onClick={() => {
              trackOutboundAffiliateClick(plan.supermercado, 'checkout', checkout, finalTotal)
            }}
            target="_blank"
            rel="noopener noreferrer"
            className="min-h-[48px] h-12 w-full rounded-xl bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white font-extrabold text-[14px] flex items-center justify-center gap-2 transition-colors shadow-sm"
          >
            <span>
              {plan.supports_cart
                ? `Comprar en ${storeLabel(plan.supermercado)} — ${formatPrice(finalTotal)}`
                : `Abrir web de ${storeLabel(plan.supermercado)}`}
            </span>
            <ExternalLink size={16} />
          </a>
        ) : !isCoto ? (
          <p className="text-[12px] text-slate-500 bg-slate-50 rounded-xl p-2.5 text-center">
            {storeLabel(plan.supermercado)}: Tocá cada producto arriba para abrirlo en su web oficial.
          </p>
        ) : null}
      </div>
    </div>
  )
}

export default StoreCart
