import React, { useState, useEffect } from 'react'
import { X, Trash2, Loader2, Sparkles, CreditCard, Truck, TrendingDown, Calendar } from 'lucide-react'
import type { OptimizeMode, OptimizePlan } from '../types'
import { useCart } from '../cart/CartContext'
import { useLocation } from '../location/LocationContext'
import { useBenefits } from '../benefits/BenefitsContext'
import { optimize } from '../api'
import { formatPrice } from './OfferCard'
import StoreCart from './StoreCart'

const MODES: { id: OptimizeMode; label: string; desc: string }[] = [
  { id: 'ahorro', label: 'Ahorro', desc: 'Mínimo costo (varias paradas)' },
  { id: 'comodidad', label: 'Comodidad', desc: 'Un solo súper' },
  { id: 'balanceada', label: 'Balanceada', desc: 'Hasta 2 súper' },
]

const SmartCart: React.FC<{
  open: boolean
  onClose: () => void
  onOpenBenefits?: () => void
}> = ({ open, onClose, onOpenBenefits }) => {
  const { items, remove, setQty, clear, totalUnits } = useCart()
  const { cp } = useLocation()
  const { selectedCards, selectedDay, setSelectedDay } = useBenefits()
  const [mode, setMode] = useState<OptimizeMode>('ahorro')
  const [includeShipping, setIncludeShipping] = useState(false)
  const [plan, setPlan] = useState<OptimizePlan | null>(null)
  const [loading, setLoading] = useState(false)

  const run = async () => {
    if (!items.length) {
      setPlan(null)
      return
    }
    setLoading(true)
    try {
      setPlan(
        await optimize(items, mode, {
          cp,
          includeClubs: false,
          includeShipping,
          selectedCards,
          day: selectedDay,
        }),
      )
    } finally {
      setLoading(false)
    }
  }

  // Re-optimizar automáticamente cuando se abre el carrito o cambian ítems/opciones
  useEffect(() => {
    if (open && items.length > 0) {
      run()
    } else if (items.length === 0) {
      setPlan(null)
    }
  }, [open, items, mode, cp, includeShipping, selectedCards, selectedDay])

  return (
    <div className={`fixed inset-0 z-50 ${open ? '' : 'pointer-events-none'}`}>
      <div
        className={`absolute inset-0 bg-black/40 transition-opacity ${open ? 'opacity-100' : 'opacity-0'}`}
        onClick={onClose}
      />
      <aside
        className={`absolute right-0 top-0 h-full w-full max-w-lg bg-gray-50 shadow-2xl flex flex-col transition-transform ${
          open ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <header className="flex items-center justify-between p-4 border-b bg-white">
          <div>
            <h2 className="text-lg font-bold flex items-center gap-2">
              <Sparkles size={18} className="text-blue-600" /> Mi Smart Cart
            </h2>
            <p className="text-xs text-gray-500">
              {items.length} producto(s) · {totalUnits} unidad(es)
              {cp ? ` · CP ${cp}` : ''}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {items.length > 0 && (
              <button
                onClick={clear}
                className="text-xs text-gray-400 hover:text-red-600 px-2 py-1 rounded hover:bg-red-50"
              >
                Vaciar
              </button>
            )}
            <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded">
              <X size={20} />
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {items.length === 0 && (
            <div className="text-center text-gray-400 mt-14 space-y-2">
              <p className="font-medium text-gray-600">Tu lista de compras está vacía</p>
              <p className="text-xs max-w-xs mx-auto">
                Buscá productos, sumalos a tu lista (en 1 o más unidades para activar ofertas 2x1 / 2do al 70%) y compará dónde te conviene comprar.
              </p>
            </div>
          )}

          {items.length > 0 && (
            <>
              <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                {items.map(i => (
                  <div
                    key={i.ean}
                    className="flex items-center gap-3 bg-white rounded-lg p-2 border border-gray-200"
                  >
                    <img src={i.imagen} alt="" className="w-10 h-10 object-contain" />
                    <span className="flex-1 text-xs font-medium leading-snug line-clamp-2">
                      {i.nombre}
                    </span>
                    <div className="flex items-center border rounded-lg overflow-hidden">
                      <button
                        onClick={() => setQty(i.ean, i.qty - 1)}
                        className="px-2 py-1 bg-gray-50 hover:bg-gray-100 text-xs font-bold"
                      >
                        -
                      </button>
                      <span className="px-2.5 text-xs font-bold">{i.qty}</span>
                      <button
                        onClick={() => setQty(i.ean, i.qty + 1)}
                        className="px-2 py-1 bg-gray-50 hover:bg-gray-100 text-xs font-bold"
                      >
                        +
                      </button>
                    </div>
                    <button
                      onClick={() => remove(i.ean)}
                      className="text-gray-400 hover:text-red-500 p-1"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-3 gap-2">
                {MODES.map(m => (
                  <button
                    key={m.id}
                    onClick={() => setMode(m.id)}
                    className={`p-2.5 rounded-lg border text-left transition-colors ${
                      mode === m.id
                        ? 'border-blue-600 bg-blue-50 ring-1 ring-blue-500'
                        : 'border-gray-200 bg-white hover:bg-gray-50'
                    }`}
                  >
                    <div className="font-bold text-sm">{m.label}</div>
                    <div className="text-[11px] text-gray-500 leading-tight">{m.desc}</div>
                  </button>
                ))}
              </div>

              <div className="bg-white rounded-xl border border-gray-200 p-3 space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-gray-800 font-semibold">
                    <CreditCard size={15} className="text-purple-600" />
                    <span>
                      Día: <strong className="capitalize">{selectedDay}</strong> ·{' '}
                      <strong>{selectedCards.length}</strong> tarjeta(s)/billetera(s)
                    </span>
                  </span>
                  {onOpenBenefits && (
                    <button
                      type="button"
                      onClick={onOpenBenefits}
                      className="px-2.5 py-1 rounded-lg bg-purple-50 text-purple-700 border border-purple-200 font-bold hover:bg-purple-100"
                    >
                      Configurar
                    </button>
                  )}
                </div>

                <label className="flex items-center justify-between cursor-pointer pt-1 border-t border-gray-100">
                  <span className="flex items-center gap-2 text-gray-700 font-medium">
                    <Truck size={15} className="text-blue-600" />
                    Considerar costo de envío si no llego al mínimo gratis
                  </span>
                  <input
                    type="checkbox"
                    checked={includeShipping}
                    onChange={e => setIncludeShipping(e.target.checked)}
                    className="rounded text-blue-600 focus:ring-blue-500 h-4 w-4"
                  />
                </label>
              </div>
            </>
          )}

          {loading && (
            <div className="flex items-center justify-center gap-2 py-6 text-sm text-blue-600 font-medium">
              <Loader2 className="animate-spin" size={18} />
              Calculando la mejor combinación...
            </div>
          )}

          {plan && !loading && (
            <div className="space-y-3 pt-1">
              <div className="bg-gradient-to-br from-blue-600 to-indigo-700 text-white rounded-xl p-4 shadow-md">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs text-blue-100 uppercase font-semibold">
                      Total optimizado · {plan.stops} {plan.stops === 1 ? 'supermercado' : 'supermercados'}
                    </div>
                    <div className="text-3xl font-extrabold mt-0.5">
                      {formatPrice(plan.total)}
                    </div>
                  </div>
                  {(plan.ahorro_total ?? 0) > 0 && (
                    <div className="bg-green-400/20 border border-green-300/40 rounded-lg px-3 py-1.5 text-right">
                      <div className="text-[11px] text-green-100 flex items-center justify-end gap-1">
                        <TrendingDown size={13} /> Ahorrás en promos
                      </div>
                      <div className="text-base font-extrabold text-green-200">
                        {formatPrice(plan.ahorro_total || 0)}
                      </div>
                    </div>
                  )}
                </div>

                {includeShipping && (plan.envio_estimado ?? 0) > 0 && (
                  <div className="text-xs text-blue-100 mt-2 pt-2 border-t border-white/15 flex justify-between">
                    <span>Mercadería: {formatPrice(plan.subtotal_mercaderia || 0)}</span>
                    <span>Envío estimado: {formatPrice(plan.envio_estimado || 0)}</span>
                  </div>
                )}

                {(plan.reintegro_bancario_total ?? 0) > 0 && (
                  <div className="text-xs text-emerald-200 mt-2 pt-2 border-t border-white/15 flex justify-between font-bold">
                    <span>Reintegro tarjetas/billeteras ({plan.day_label}):</span>
                    <span>-{formatPrice(plan.reintegro_bancario_total || 0)}</span>
                  </div>
                )}
              </div>

              {plan.best_day_suggestion &&
                plan.best_day_suggestion.day !== plan.day &&
                plan.best_day_suggestion.saving > (plan.reintegro_bancario_total || 0) && (
                  <div className="bg-purple-50 border border-purple-200 rounded-xl p-3 text-xs flex items-center justify-between gap-2">
                    <div>
                      <div className="font-extrabold text-purple-950 flex items-center gap-1">
                        <Calendar size={13} className="text-purple-600" />
                        Mejor día para comprar con tus tarjetas:{' '}
                        <span className="underline">{plan.best_day_suggestion.day_label}</span>
                      </div>
                      <div className="text-[11px] text-purple-800 mt-0.5">
                        Ahorrás <strong>{formatPrice(plan.best_day_suggestion.saving)}</strong> en reintegros (
                        {plan.best_day_suggestion.details.join(' · ')})
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => setSelectedDay(plan.best_day_suggestion!.day)}
                      className="px-2.5 py-1.5 rounded-lg bg-purple-600 text-white font-extrabold whitespace-nowrap hover:bg-purple-700"
                    >
                      Ver {plan.best_day_suggestion.day_label}
                    </button>
                  </div>
                )}

              {plan.excluded_stores && plan.excluded_stores.length > 0 && (
                <div className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-2.5">
                  📍 Se excluyeron por no entregar en tu CP ({cp}):{' '}
                  <strong>{plan.excluded_stores.join(', ')}</strong>
                </div>
              )}

              {plan.carts.map(c => (
                <StoreCart key={c.supermercado} plan={c} />
              ))}

              {plan.missing.length > 0 && (
                <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg p-2.5">
                  No encontramos stock para: {plan.missing.map(m => m.nombre).join(', ')}
                </div>
              )}
            </div>
          )}
        </div>
      </aside>
    </div>
  )
}

export default SmartCart
