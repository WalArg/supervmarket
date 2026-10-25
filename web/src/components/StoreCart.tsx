import React, { useEffect, useState } from 'react'
import { ExternalLink, CheckCircle2, AlertTriangle, CreditCard, Flame, Truck } from 'lucide-react'
import type { StorePlan } from '../types'
import { validateCart } from '../api'
import { useLocation } from '../location/LocationContext'
import { storeColor, storeLabel } from '../lib/stores'
import { formatPrice } from '../lib/pricing'

interface Validation {
  status?: string
  total?: number
  sin_stock?: string[]
  checkout_url?: string
}

const StoreCart: React.FC<{ plan: StorePlan }> = ({ plan }) => {
  const { cp } = useLocation()
  const [validation, setValidation] = useState<Validation | null>(null)
  const [checking, setChecking] = useState(false)

  // Verifica stock y precio final en vivo contra el carrito real del súper
  useEffect(() => {
    if (!plan.supports_cart || !plan.items.length) return
    let alive = true
    setChecking(true)
    validateCart(
      plan.supermercado,
      plan.items.map(i => ({ sku_id: i.sku_id || '', qty: i.qty, nombre: i.nombre })),
      cp,
    )
      .then(v => alive && setValidation(v))
      .catch(() => {})
      .finally(() => alive && setChecking(false))
    return () => {
      alive = false
    }
  }, [plan.supermercado, cp, plan.items.map(i => `${i.sku_id}:${i.qty}`).join(',')])

  const subtotal = validation?.total && validation.total > 0 ? validation.total : plan.subtotal
  const reintegro = plan.reintegro_bancario || 0
  const sinStock = validation?.sin_stock || []
  const checkout = validation?.checkout_url || plan.checkout_url

  return (
    <div className="bg-white rounded-2xl border border-slate-200/80 overflow-hidden">
      <div className="px-4 pt-3.5 pb-2 flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="w-3 h-3 rounded-full shrink-0" style={{ background: storeColor(plan.supermercado) }} />
          <div className="min-w-0">
            <h3 className="font-extrabold text-[16px] text-slate-900">{storeLabel(plan.supermercado)}</h3>
            <p className="text-[12px] text-slate-500">
              {plan.items.length} producto{plan.items.length === 1 ? '' : 's'}
              {(plan.ahorro ?? 0) > 0 && (
                <span className="text-emerald-700 font-semibold"> · ahorrás {formatPrice(plan.ahorro || 0)}</span>
              )}
            </p>
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-[18px] font-extrabold text-slate-900">{formatPrice(subtotal)}</div>
          {checking ? (
            <div className="text-[11px] text-slate-400">verificando…</div>
          ) : validation?.total ? (
            <div className="text-[11px] text-emerald-700 font-semibold flex items-center justify-end gap-0.5">
              <CheckCircle2 size={11} /> verificado
            </div>
          ) : null}
        </div>
      </div>

      <ul className="px-4 divide-y divide-slate-100">
        {plan.items.map(i => (
          <li key={i.ean} className="py-2 flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <p className="text-[13px] text-slate-800 leading-snug line-clamp-2">
                <span className="font-bold">{i.qty}×</span> {i.nombre}
              </p>
              {i.applied_promo && (
                <span className="inline-flex items-center gap-1 mt-0.5 text-[11px] font-semibold text-orange-700">
                  <Flame size={11} /> {i.applied_promo}
                </span>
              )}
            </div>
            <span className="text-[13px] font-bold text-slate-900 whitespace-nowrap">
              {formatPrice(i.line_total ?? i.precio * i.qty)}
            </span>
          </li>
        ))}
      </ul>

      <div className="px-4 pb-4 pt-2 space-y-2">
        {sinStock.length > 0 && (
          <div className="flex gap-2 text-[12px] text-red-700 bg-red-50 rounded-xl p-2.5">
            <AlertTriangle size={14} className="shrink-0 mt-0.5" />
            <span>Sin stock en tu zona: {sinStock.join(', ')}</span>
          </div>
        )}

        {plan.bank_benefit && reintegro > 0 && (
          <div className="flex items-center justify-between gap-2 text-[12px] bg-purple-50 text-purple-900 rounded-xl p-2.5">
            <span className="flex items-center gap-1.5 min-w-0">
              <CreditCard size={14} className="shrink-0" />
              <span className="truncate font-semibold">{plan.bank_benefit.label}</span>
            </span>
            <span className="font-extrabold text-emerald-700 whitespace-nowrap">-{formatPrice(reintegro)}</span>
          </div>
        )}

        {plan.free_shipping_threshold > 0 && (
          plan.falta_envio_gratis > 0 ? (
            <div className="flex items-center gap-1.5 text-[12px] text-slate-500">
              <Truck size={14} /> Te faltan {formatPrice(plan.falta_envio_gratis)} para envío gratis
            </div>
          ) : (
            <div className="flex items-center gap-1.5 text-[12px] font-semibold text-emerald-700 bg-emerald-50 rounded-xl px-2.5 py-1.5">
              <Truck size={14} /> ⚡ ¡Tenés envío gratis en {storeLabel(plan.supermercado)}!
            </div>
          )
        )}

        {checkout ? (
          <a
            href={checkout}
            target="_blank"
            rel="noopener noreferrer"
            className="h-12 w-full rounded-xl bg-slate-900 text-white font-extrabold text-[14px] flex items-center justify-center gap-2 active:bg-slate-800"
          >
            Comprar en {storeLabel(plan.supermercado)} <ExternalLink size={16} />
          </a>
        ) : (
          <p className="text-[12px] text-slate-500 bg-slate-50 rounded-xl p-2.5">
            {storeLabel(plan.supermercado)}: Tocá cada producto arriba para abrirlo en su web.
          </p>
        )}
      </div>
    </div>
  )
}

export default StoreCart
