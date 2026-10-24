import React, { useState, useEffect } from 'react'
import { ExternalLink, Loader2, Info, MapPin, MapPinOff, Flame, CheckCircle2 } from 'lucide-react'
import type { StorePlan } from '../types'
import { formatPrice } from './OfferCard'
import { validateCart } from '../api'
import { useLocation } from '../location/LocationContext'

const StoreCart: React.FC<{ plan: StorePlan }> = ({ plan }) => {
  const { cp, delivers } = useLocation()
  const [validation, setValidation] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const cobertura = delivers(plan.supermercado)
  const effectiveSubtotal = validation?.total != null && validation.total > 0 ? validation.total : plan.subtotal
  const pct = plan.free_shipping_threshold
    ? Math.min(100, (effectiveSubtotal / plan.free_shipping_threshold) * 100)
    : 100

  const runValidate = async () => {
    if (!plan.supports_cart) return
    setLoading(true)
    try {
      setValidation(
        await validateCart(
          plan.supermercado,
          plan.items.map(i => ({ sku_id: i.sku_id || '', qty: i.qty, nombre: i.nombre })),
          cp,
        ),
      )
    } finally {
      setLoading(false)
    }
  }

  // Verificar stock y promociones automáticamente en vivo al armar/actualizar el carrito
  useEffect(() => {
    if (plan.supports_cart && plan.items.length > 0) {
      runValidate()
    }
  }, [plan.supermercado, cp, JSON.stringify(plan.items.map(i => `${i.sku_id}:${i.qty}`))])

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <h4 className="font-bold text-lg text-gray-900">{plan.supermercado}</h4>
          {(plan.ahorro ?? 0) > 0 && (
            <span className="text-[11px] font-bold bg-green-100 text-green-800 px-2 py-0.5 rounded-full">
              Ahorrás {formatPrice(plan.ahorro || 0)}
            </span>
          )}
        </div>
        <div className="text-right">
          <span className="text-xl font-extrabold text-gray-900">
            {formatPrice(effectiveSubtotal)}
          </span>
          {validation?.total != null && validation.total > 0 && (
            <div className="text-[10px] text-green-700 font-semibold flex items-center justify-end gap-0.5">
              <CheckCircle2 size={11} /> Precio verificado en vivo
            </div>
          )}
        </div>
      </div>

      {cp && cobertura === true && (
        <p className="text-xs text-green-700 flex items-center gap-1 mb-2">
          <MapPin size={13} /> Entrega disponible en tu zona (CP {cp})
        </p>
      )}
      {cp && cobertura === false && (
        <p className="text-xs text-red-600 flex items-center gap-1 mb-2">
          <MapPinOff size={13} /> No entrega en tu zona — probá otro súper
        </p>
      )}

      <ul className="text-sm text-gray-700 mb-3 divide-y divide-gray-100">
        {plan.items.map(i => (
          <li key={i.ean} className="py-1.5 flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium">
                {i.qty}× {i.nombre}
              </div>
              {i.applied_promo && (
                <span className="inline-flex items-center gap-1 text-[11px] text-orange-700 bg-orange-50 border border-orange-200 px-1.5 py-0.2 rounded font-semibold mt-0.5">
                  <Flame size={11} /> {i.applied_promo} ({formatPrice(i.precio)} c/u)
                </span>
              )}
            </div>
            <div className="text-right whitespace-nowrap">
              <span className="font-bold">
                {formatPrice(i.line_total ?? i.precio * i.qty)}
              </span>
              {i.precio_base && i.precio < i.precio_base && (
                <div className="text-[11px] text-gray-400 line-through">
                  {formatPrice(i.precio_base * i.qty)}
                </div>
              )}
            </div>
          </li>
        ))}
      </ul>

      {plan.free_shipping_threshold > 0 && (
        <div className="mb-3">
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all ${
                plan.falta_envio_gratis === 0 ? 'bg-green-500' : 'bg-blue-500'
              }`}
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="text-xs mt-1 text-gray-500">
            {plan.falta_envio_gratis === 0
              ? '✅ Alcanzás el mínimo para envío gratis'
              : `Te faltan ${formatPrice(plan.falta_envio_gratis)} para envío gratis (mín. ${formatPrice(plan.free_shipping_threshold)})`}
          </p>
        </div>
      )}

      {/* Resultados de la simulación en vivo de VTEX */}
      {validation?.status === 'ok' && validation?.sin_stock?.length === 0 && (
        <div className="mb-2 text-xs text-green-800 bg-green-50 border border-green-200 rounded-lg p-2">
          ✅ Todos los productos tienen stock disponible en {plan.supermercado}.
          {validation.promos_aplicadas?.length > 0 && (
            <div className="mt-1 font-semibold">
              Promos activas en carrito: {validation.promos_aplicadas.join(', ')}
            </div>
          )}
        </div>
      )}

      {validation?.sin_stock?.length > 0 && (
        <div className="mb-2 text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg p-2">
          ⚠️ Sin stock en tu zona: {validation.sin_stock.join(', ')}
        </div>
      )}

      {validation?.mensajes?.length > 0 && (
        <div className="mb-2 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-2 space-y-0.5">
          {validation.mensajes.map((m: string, idx: number) => (
            <div key={idx}>ℹ️ {m}</div>
          ))}
        </div>
      )}

      {(validation?.envio != null || validation?.retiro_gratis) && (
        <div className="text-xs text-gray-600 mb-2 flex flex-wrap gap-3 bg-gray-50 p-2 rounded-lg">
          {validation.envio != null && (
            <span>
              🚚 Envío a domicilio:{' '}
              <strong>{validation.envio === 0 ? 'Gratis' : formatPrice(validation.envio)}</strong>
            </span>
          )}
          {validation.retiro_gratis && (
            <span className="text-green-700 font-medium">🏪 Retiro en sucursal: Gratis</span>
          )}
        </div>
      )}

      {plan.supports_cart ? (
        <div className="flex gap-2">
          <button
            onClick={runValidate}
            disabled={loading}
            className="flex-1 flex items-center justify-center gap-1.5 text-xs font-semibold py-2.5 px-3 rounded-lg border border-gray-300 hover:bg-gray-50 transition-colors"
            title={cp ? `Simula el carrito en vivo en ${plan.supermercado} para CP ${cp}` : 'Simula stock y promociones en vivo'}
          >
            {loading ? <Loader2 className="animate-spin" size={15} /> : 'Verificar stock y promos'}
          </button>
          <a
            href={validation?.checkout_url || plan.checkout_url || '#'}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-1 flex items-center justify-center gap-1.5 text-xs font-bold py-2.5 px-3 rounded-lg bg-gray-900 text-white hover:bg-gray-800 transition-colors"
          >
            Armar carrito en {plan.supermercado} <ExternalLink size={13} />
          </a>
        </div>
      ) : (
        <div className="flex items-center gap-2 text-xs text-gray-600 bg-gray-100 rounded-lg p-2.5">
          <Info size={15} className="shrink-0 text-gray-500" />
          <span>
            <strong>{plan.supermercado}</strong> no usa checkout VTEX. Podés abrir cada producto desde la lista de arriba.
          </span>
        </div>
      )}
    </div>
  )
}

export default StoreCart
