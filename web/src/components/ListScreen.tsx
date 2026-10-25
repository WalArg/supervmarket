import React, { useEffect, useState } from 'react'
import { Trash2, Loader2, Share2, Calendar, CreditCard, ShoppingBasket, TrendingDown, Plus, Minus, Truck } from 'lucide-react'
import type { OptimizeMode, OptimizePlan } from '../types'
import { useCart } from '../cart/CartContext'
import { useLocation } from '../location/LocationContext'
import { useBenefits } from '../benefits/BenefitsContext'
import { optimize } from '../api'
import { formatPrice } from '../lib/pricing'
import { storeLabel } from '../lib/stores'
import StoreCart from './StoreCart'

const MODES: { id: OptimizeMode; label: string }[] = [
  { id: 'ahorro', label: 'Lo más barato' },
  { id: 'balanceada', label: 'Hasta 2 súper' },
  { id: 'comodidad', label: '1 solo súper' },
]

const DAY_LABEL: Record<string, string> = {
  lunes: 'Lunes', martes: 'Martes', miercoles: 'Miércoles', jueves: 'Jueves', viernes: 'Viernes', sabado: 'Sábado', domingo: 'Domingo',
}

const ListScreen: React.FC<{ onGoSearch: () => void; onGoProfile: () => void }> = ({ onGoSearch, onGoProfile }) => {
  const { items, remove, setQty, clear, totalUnits } = useCart()
  const { cp } = useLocation()
  const { selectedCards, selectedDay, setSelectedDay } = useBenefits()
  const [mode, setMode] = useState<OptimizeMode>('ahorro')
  const [includeShipping, setIncludeShipping] = useState(false)
  const [plan, setPlan] = useState<OptimizePlan | null>(null)
  const [loading, setLoading] = useState(false)
  const [editing, setEditing] = useState(false)

  const itemsKey = items.map(i => `${i.ean}:${i.qty}`).join(',')

  useEffect(() => {
    if (!items.length) {
      setPlan(null)
      return
    }
    let alive = true
    const t = setTimeout(() => {
      setLoading(true)
      optimize(items, mode, { cp, includeShipping, selectedCards, day: selectedDay })
        .then(p => alive && setPlan(p))
        .catch(() => {})
        .finally(() => alive && setLoading(false))
    }, 400)
    return () => {
      alive = false
      clearTimeout(t)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [itemsKey, mode, cp, includeShipping, selectedCards.join(','), selectedDay])

  const share = async () => {
    if (!plan) return
    const lines = ['🛒 Mi lista en SuperVmarket', '']
    for (const c of plan.carts) {
      lines.push(`📍 ${storeLabel(c.supermercado)} — ${formatPrice(c.subtotal)}`)
      c.items.forEach(i => lines.push(`  • ${i.qty}× ${i.nombre}`))
      lines.push('')
    }
    lines.push(`Total: ${formatPrice(plan.total)}`)
    const text = lines.join('\n')
    try {
      if (navigator.share) await navigator.share({ title: 'Mi lista', text })
      else {
        await navigator.clipboard.writeText(text)
        alert('Lista copiada al portapapeles')
      }
    } catch {
      /* usuario canceló */
    }
  }

  if (!items.length) {
    return (
      <div className="pt-safe px-6 min-h-[70dvh] flex flex-col items-center justify-center text-center">
        <div className="w-16 h-16 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center">
          <ShoppingBasket size={30} />
        </div>
        <h2 className="mt-4 text-[18px] font-extrabold">Tu lista está vacía</h2>
        <p className="mt-1 text-[14px] text-slate-500 max-w-xs">
          Agregá productos y te decimos en qué súper (o combinación) te sale más barato el changuito.
        </p>
        <button type="button" onClick={onGoSearch} className="mt-5 h-11 px-5 rounded-xl bg-blue-600 text-white font-bold active:bg-blue-700">
          Buscar productos
        </button>
      </div>
    )
  }

  const best = plan?.best_day_suggestion
  const showBestDay = best && best.day !== plan?.day && best.saving > (plan?.reintegro_bancario_total || 0)

  return (
    <div>
      <header className="sticky top-0 z-30 bg-slate-50/95 backdrop-blur-md pt-safe">
        <div className="px-4 pt-3 pb-2 flex items-center justify-between">
          <div>
            <h1 className="text-[20px] font-extrabold tracking-tight">Mi lista</h1>
            <p className="text-[12px] text-slate-500">
              {items.length} productos · {totalUnits} unidades
            </p>
          </div>
          <div className="flex items-center gap-1">
            {plan && (
              <button type="button" onClick={share} aria-label="Compartir" className="p-2.5 rounded-full text-slate-600 active:bg-slate-200">
                <Share2 size={20} />
              </button>
            )}
            <button
              type="button"
              onClick={() => setEditing(v => !v)}
              className="h-9 px-3 rounded-full text-[13px] font-bold text-blue-600 active:bg-blue-50"
            >
              {editing ? 'Listo' : 'Editar'}
            </button>
          </div>
        </div>
        <div className="px-4 pb-2.5">
          <div className="grid grid-cols-3 p-1 bg-slate-200/70 rounded-xl">
            {MODES.map(m => (
              <button
                key={m.id}
                type="button"
                onClick={() => setMode(m.id)}
                className={`h-8 rounded-lg text-[12px] font-bold transition-all ${
                  mode === m.id ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>
      </header>

      <main className="px-4 pb-28 space-y-3">
        {/* Edición de cantidades */}
        {editing && (
          <div className="bg-white rounded-2xl border border-slate-200/80 divide-y divide-slate-100">
            {items.map(i => (
              <div key={i.ean} className="flex items-center gap-3 p-2.5">
                <img src={i.imagen} alt="" className="w-10 h-10 object-contain shrink-0" />
                <span className="flex-1 text-[13px] font-medium leading-snug line-clamp-2">{i.nombre}</span>
                <div className="flex items-center h-9 rounded-xl border border-slate-200">
                  <button type="button" onClick={() => setQty(i.ean, i.qty - 1)} className="w-9 h-full flex items-center justify-center active:bg-slate-100 rounded-l-xl">
                    <Minus size={15} />
                  </button>
                  <span className="w-6 text-center text-[14px] font-bold">{i.qty}</span>
                  <button type="button" onClick={() => setQty(i.ean, i.qty + 1)} className="w-9 h-full flex items-center justify-center active:bg-slate-100 rounded-r-xl">
                    <Plus size={15} />
                  </button>
                </div>
                <button type="button" onClick={() => remove(i.ean)} aria-label="Quitar" className="p-2 text-slate-400 active:text-red-600">
                  <Trash2 size={18} />
                </button>
              </div>
            ))}
            <button type="button" onClick={clear} className="w-full py-3 text-[13px] font-bold text-red-600 active:bg-red-50 rounded-b-2xl">
              Vaciar lista
            </button>
          </div>
        )}

        {/* Resumen total */}
        <div className="rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-700 text-white p-4 relative overflow-hidden">
          {loading && (
            <div className="absolute inset-0 bg-blue-700/40 flex items-center justify-center">
              <Loader2 className="animate-spin" size={26} />
            </div>
          )}
          <p className="text-[12px] font-semibold text-blue-100">
            Total {plan ? `en ${plan.stops} ${plan.stops === 1 ? 'súper' : 'súper'}` : ''}
          </p>
          <p className="text-[32px] font-extrabold tracking-tight leading-tight">{plan ? formatPrice(plan.total) : '—'}</p>
          {plan && (
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px]">
              {(plan.ahorro_total ?? 0) > 0 && (
                <span className="flex items-center gap-1 text-emerald-200 font-bold">
                  <TrendingDown size={14} /> Ahorrás {formatPrice(plan.ahorro_total || 0)}
                </span>
              )}
              {(plan.reintegro_bancario_total ?? 0) > 0 && (
                <span className="text-blue-100">incluye -{formatPrice(plan.reintegro_bancario_total || 0)} de reintegros</span>
              )}
              {(plan.envio_estimado ?? 0) > 0 && <span className="text-blue-100">+ {formatPrice(plan.envio_estimado || 0)} envío</span>}
            </div>
          )}
        </div>

        {/* Día y tarjetas */}
        <button
          type="button"
          onClick={onGoProfile}
          className="w-full bg-white rounded-2xl border border-slate-200/80 p-3 flex items-center gap-3 text-left active:bg-slate-50"
        >
          <div className="w-9 h-9 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center shrink-0">
            <CreditCard size={18} />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[13px] font-bold text-slate-900">
              Comprando el {DAY_LABEL[selectedDay] || selectedDay}
            </p>
            <p className="text-[12px] text-slate-500 truncate">
              {selectedCards.length
                ? `${selectedCards.length} tarjetas/billeteras activas`
                : 'Sumá tus tarjetas y billeteras para ver reintegros'}
            </p>
          </div>
          <span className="text-[13px] font-bold text-blue-600">Cambiar</span>
        </button>

        <label className="flex items-center justify-between bg-white rounded-2xl border border-slate-200/80 px-3 py-3">
          <span className="flex items-center gap-2 text-[13px] font-semibold text-slate-700">
            <Truck size={17} className="text-slate-500" /> Sumar costo de envío
          </span>
          <input
            type="checkbox"
            checked={includeShipping}
            onChange={e => setIncludeShipping(e.target.checked)}
            className="w-5 h-5 rounded accent-blue-600"
          />
        </label>

        {showBestDay && best && (
          <div className="bg-purple-50 border border-purple-200 rounded-2xl p-3 flex items-center gap-3">
            <Calendar size={20} className="text-purple-600 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-[13px] font-extrabold text-purple-950">Conviene el {best.day_label}</p>
              <p className="text-[12px] text-purple-800">
                Ahorrás {formatPrice(best.saving)} con tus tarjetas
              </p>
            </div>
            <button
              type="button"
              onClick={() => setSelectedDay(best.day)}
              className="h-9 px-3 rounded-xl bg-purple-600 text-white text-[12px] font-bold active:bg-purple-700"
            >
              Ver
            </button>
          </div>
        )}

        {plan?.excluded_stores && plan.excluded_stores.length > 0 && (
          <p className="text-[12px] text-amber-800 bg-amber-50 rounded-xl p-2.5">
            No envían a tu CP: {plan.excluded_stores.map(storeLabel).join(', ')}
          </p>
        )}

        {plan?.carts.map(c => <StoreCart key={c.supermercado} plan={c} />)}

        {plan && plan.missing.length > 0 && (
          <p className="text-[12px] text-red-700 bg-red-50 rounded-xl p-2.5">
            Sin stock en ningún súper: {plan.missing.map(m => m.nombre).join(', ')}
          </p>
        )}
      </main>
    </div>
  )
}

export default ListScreen
