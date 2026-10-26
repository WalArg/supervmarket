import React, { useEffect, useState } from 'react'
import {
  Trash2,
  Loader2,
  Share2,
  Calendar,
  CreditCard,
  ShoppingBasket,
  TrendingDown,
  Plus,
  Minus,
  Truck,
  MapPin,
  Sparkles,
  AlertCircle,
} from 'lucide-react'
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
  lunes: 'Lunes',
  martes: 'Martes',
  miercoles: 'Miércoles',
  jueves: 'Jueves',
  viernes: 'Viernes',
  sabado: 'Sábado',
  domingo: 'Domingo',
}

const ListScreen: React.FC<{ onGoSearch: () => void; onGoProfile: () => void }> = ({
  onGoSearch,
  onGoProfile,
}) => {
  const { items, remove, setQty, clear, totalUnits } = useCart()
  const { cp, locationLabel, exactAddress, setExactAddress, openModal } = useLocation()
  const { selectedCards, selectedDay, setSelectedDay } = useBenefits()
  const [mode, setMode] = useState<OptimizeMode>('ahorro')
  const [includeShipping, setIncludeShipping] = useState(false)
  const [plan, setPlan] = useState<OptimizePlan | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState(false)

  const itemsKey = items.map(i => `${i.ean}:${i.qty}`).join(',')

  const handleSelectMode = (newMode: OptimizeMode) => {
    setMode(newMode)
    if (plan?.all_plans?.[newMode]) {
      const selected = plan.all_plans[newMode]
      setPlan({
        ...selected,
        all_plans: plan.all_plans,
        mode_previews: plan.mode_previews,
      })
    }
  }

  useEffect(() => {
    if (!items.length) {
      setPlan(null)
      setLoadError(false)
      return
    }

    // Si ya tenemos el plan precalculado en memoria para este modo, lo aplicamos al instante (0ms)
    if (plan?.all_plans?.[mode]) {
      const selected = plan.all_plans[mode]
      setPlan({
        ...selected,
        all_plans: plan.all_plans,
        mode_previews: plan.mode_previews,
      })
      return
    }

    let alive = true
    const t = setTimeout(() => {
      setLoading(true)
      setLoadError(false)
      optimize(items, mode, { cp, includeShipping, selectedCards, day: selectedDay })
        .then(p => {
          if (alive) {
            setPlan(p)
            setLoadError(false)
          }
        })
        .catch(() => {
          if (alive) setLoadError(true)
        })
        .finally(() => {
          if (alive) setLoading(false)
        })
    }, 350)
    return () => {
      alive = false
      clearTimeout(t)
    }
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
      <div className="pt-safe px-6 min-h-[75dvh] flex flex-col items-center justify-center text-center">
        <div className="w-16 h-16 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center shadow-xs">
          <ShoppingBasket size={32} />
        </div>
        <h2 className="mt-4 text-[19px] font-extrabold text-slate-900">Tu lista está vacía</h2>
        <p className="mt-1.5 text-[14px] text-slate-500 max-w-xs leading-relaxed">
          Agregá productos desde el buscador y te calculamos la combinación más barata entre todos los supermercados.
        </p>
        <button
          type="button"
          onClick={onGoSearch}
          className="mt-6 h-12 px-6 rounded-2xl bg-blue-600 text-white font-bold active:scale-95 transition-all shadow-md shadow-blue-500/20"
        >
          Explorar productos
        </button>
      </div>
    )
  }

  const best = plan?.best_day_suggestion
  const showBestDay = best && best.day !== plan?.day && best.saving > (plan?.reintegro_bancario_total || 0)

  return (
    <div>
      <header className="sticky top-0 z-30 bg-slate-50/95 backdrop-blur-md pt-safe border-b border-slate-100/60">
        <div className="px-4 pt-3 pb-2.5 flex items-center justify-between">
          <div>
            <h1 className="text-[20px] font-extrabold tracking-tight">Mi lista</h1>
            <p className="text-[12px] text-slate-500">
              {items.length} producto{items.length === 1 ? '' : 's'} · {totalUnits} unidad{totalUnits === 1 ? '' : 'es'}
            </p>
          </div>
          <div className="flex items-center gap-1.5">
            {plan && (
              <button
                type="button"
                onClick={share}
                aria-label="Compartir"
                className="p-2 rounded-xl text-slate-600 hover:bg-slate-200/60 active:scale-95 transition-all"
              >
                <Share2 size={19} />
              </button>
            )}
            <button
              type="button"
              onClick={clear}
              className="text-[12px] font-bold text-red-600 px-2.5 py-1.5 rounded-xl hover:bg-red-50 active:scale-95 transition-all"
            >
              Vaciar
            </button>
          </div>
        </div>
      </header>

      <main className="px-4 pt-3 pb-28 space-y-4">
        {/* 1. SECCIÓN: TUS PRODUCTOS (Siempre visible para ver y editar) */}
        <section className="bg-white rounded-2xl border border-slate-200/80 shadow-2xs overflow-hidden">
          <div className="px-4 pt-3 pb-2 border-b border-slate-100 flex items-center justify-between">
            <h2 className="text-[13px] font-extrabold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
              <ShoppingBasket size={15} className="text-blue-600" /> Tus productos
            </h2>
            <button
              type="button"
              onClick={onGoSearch}
              className="text-[12px] font-bold text-blue-600 hover:text-blue-700 flex items-center gap-0.5"
            >
              + Agregar más
            </button>
          </div>

          <div className="divide-y divide-slate-100">
            {items.map(i => (
              <div key={i.ean} className="flex items-center gap-3 p-3">
                {i.imagen ? (
                  <img
                    src={i.imagen}
                    alt=""
                    className="w-12 h-12 object-contain rounded-lg bg-slate-50 p-1 shrink-0 border border-slate-100"
                  />
                ) : (
                  <div className="w-12 h-12 rounded-lg bg-slate-100 flex items-center justify-center shrink-0 text-slate-400">
                    <ShoppingBasket size={20} />
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <span className="text-[13px] font-semibold text-slate-900 leading-snug line-clamp-2">
                    {i.nombre}
                  </span>
                </div>
                <div className="flex items-center h-8 rounded-xl border border-slate-200 shrink-0 bg-slate-50">
                  <button
                    type="button"
                    onClick={() => setQty(i.ean, i.qty - 1)}
                    className="w-8 h-full flex items-center justify-center text-slate-600 hover:bg-slate-200/60 rounded-l-xl active:scale-90"
                    aria-label="Restar unidad"
                  >
                    <Minus size={14} />
                  </button>
                  <span className="w-6 text-center text-[13px] font-extrabold text-slate-900">
                    {i.qty}
                  </span>
                  <button
                    type="button"
                    onClick={() => setQty(i.ean, i.qty + 1)}
                    className="w-8 h-full flex items-center justify-center text-slate-600 hover:bg-slate-200/60 rounded-r-xl active:scale-90"
                    aria-label="Sumar unidad"
                  >
                    <Plus size={14} />
                  </button>
                </div>
                <button
                  type="button"
                  onClick={() => remove(i.ean)}
                  aria-label="Quitar de la lista"
                  className="p-1.5 text-slate-400 hover:text-red-600 active:scale-90 transition-colors shrink-0"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          </div>
        </section>

        {/* 2. SECCIÓN: OPTIMIZACIÓN Y RECOMENDACIÓN INTELIGENTE */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-[13px] font-extrabold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
              <Sparkles size={15} className="text-amber-500" /> Optimización de Changuito
            </h2>
          </div>

          {/* Selector de modo con precios precalculados e instantáneos */}
          <div className="grid grid-cols-3 p-1.5 bg-slate-200/80 rounded-2xl gap-1">
            {MODES.map(m => {
              const isSelected = mode === m.id
              const preview = plan?.mode_previews?.[m.id]
              return (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => handleSelectMode(m.id)}
                  className={`py-2 px-1 rounded-xl flex flex-col items-center justify-center text-center transition-all ${
                    isSelected
                      ? 'bg-white text-slate-900 shadow-sm ring-1 ring-slate-900/5'
                      : 'text-slate-600 hover:text-slate-900 active:scale-[0.98]'
                  }`}
                >
                  <span className="text-[12px] font-extrabold leading-tight">{m.label}</span>
                  {preview ? (
                    <span
                      className={`text-[10px] font-bold mt-0.5 leading-none ${
                        isSelected
                          ? 'text-blue-600 font-extrabold'
                          : preview.diff > 0
                            ? 'text-amber-700 font-semibold'
                            : 'text-emerald-700 font-semibold'
                      }`}
                    >
                      {m.id === 'ahorro'
                        ? `${preview.stops} súper`
                        : preview.covered_items !== undefined && preview.total_items !== undefined && preview.covered_items < preview.total_items
                          ? `${preview.covered_items}/${preview.total_items} items`
                          : preview.diff > 0
                            ? `+${formatPrice(preview.diff)}`
                            : preview.stops === 1
                              ? '1 súper'
                              : `${preview.stops} súper`}
                    </span>
                  ) : (
                    <span className="text-[10px] text-slate-400 mt-0.5 leading-none">—</span>
                  )}
                </button>
              )
            })}
          </div>

          {loadError && !plan && (
            <div className="p-3.5 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 text-[12px] flex items-center justify-between gap-2 shadow-2xs">
              <div className="flex items-center gap-2 min-w-0">
                <AlertCircle size={17} className="text-amber-600 shrink-0" />
                <span className="truncate">Demora al cotizar en vivo. Podés reintentar.</span>
              </div>
              <button
                type="button"
                onClick={() => {
                  setLoading(true)
                  setLoadError(false)
                  optimize(items, mode, { cp, includeShipping, selectedCards, day: selectedDay })
                    .then(p => {
                      setPlan(p)
                      setLoadError(false)
                    })
                    .catch(() => setLoadError(true))
                    .finally(() => setLoading(false))
                }}
                className="px-3 py-1.5 rounded-xl bg-amber-600 text-white font-bold text-[11px] shrink-0 active:scale-95 transition-all shadow-xs"
              >
                Reintentar
              </button>
            </div>
          )}

          {/* Resumen total con ahorro */}
          <div className="rounded-2xl bg-gradient-to-br from-blue-600 via-blue-700 to-indigo-800 text-white p-4 relative overflow-hidden shadow-md shadow-blue-500/10">
            {loading && (
              <div className="absolute inset-0 bg-blue-900/40 backdrop-blur-xs flex items-center justify-center gap-2 text-white font-bold text-[13px] z-10">
                <Loader2 className="animate-spin" size={20} />
                <span>Optimizando precios en vivo…</span>
              </div>
            )}
            <p className="text-[12px] font-semibold text-blue-100">
              Total {plan ? `en ${plan.stops} ${plan.stops === 1 ? 'súper' : 'súper'}` : 'estimado'}
            </p>
            <p className="text-[32px] font-extrabold tracking-tight leading-tight">
              {plan ? formatPrice(plan.total) : '—'}
            </p>
            {plan && (
              <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1 text-[12px]">
                {(plan.ahorro_total ?? 0) > 0 && (
                  <span className="flex items-center gap-1 text-emerald-300 font-extrabold">
                    <TrendingDown size={14} /> Ahorrás {formatPrice(plan.ahorro_total || 0)}
                  </span>
                )}
                {(plan.reintegro_bancario_total ?? 0) > 0 && (
                  <span className="text-blue-100">
                    incluye -{formatPrice(plan.reintegro_bancario_total || 0)} de reintegros
                  </span>
                )}
                {(plan.envio_estimado ?? 0) > 0 && (
                  <span className="text-blue-100">
                    + {formatPrice(plan.envio_estimado || 0)} envío
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Tarjetas y día de compra */}
          <button
            type="button"
            onClick={onGoProfile}
            className="w-full bg-white rounded-2xl border border-slate-200/80 p-3 flex items-center gap-3 text-left active:bg-slate-50 transition-colors shadow-2xs"
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
            <span className="text-[12px] font-bold text-blue-600">Cambiar</span>
          </button>

          {/* Ubicación de entrega */}
          <div className="bg-white rounded-2xl border border-slate-200/80 p-3 flex items-center justify-between shadow-2xs">
            <div className="flex items-center gap-2.5 min-w-0 pr-2">
              <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
                <MapPin size={18} />
              </div>
              <div className="min-w-0">
                <p className="text-[13px] font-extrabold text-slate-900 truncate">
                  {locationLabel || (cp ? `CP ${cp}` : 'Sin ubicación')}
                </p>
                <p className="text-[11px] text-slate-500 truncate">
                  {exactAddress || 'Tocá cambiar para editar zona'}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={openModal}
              className="h-8 px-2.5 rounded-lg bg-blue-50 text-blue-700 text-[12px] font-bold hover:bg-blue-100 active:scale-95 transition-all"
            >
              Cambiar
            </button>
          </div>

          {/* Sumar costo de envío */}
          <label className="flex items-center justify-between bg-white rounded-2xl border border-slate-200/80 px-3 py-3 shadow-2xs">
            <span className="flex items-center gap-2 text-[13px] font-semibold text-slate-700">
              <Truck size={17} className="text-slate-500" /> Sumar costo de envío al cálculo
            </span>
            <input
              type="checkbox"
              checked={includeShipping}
              onChange={e => setIncludeShipping(e.target.checked)}
              className="w-5 h-5 rounded accent-blue-600"
            />
          </label>

          {/* Banner de mejor día */}
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

          {/* Supermercados excluidos por CP */}
          {plan?.excluded_stores && plan.excluded_stores.length > 0 && (
            <p className="text-[12px] text-amber-800 bg-amber-50 rounded-xl p-2.5 border border-amber-200/60">
              No entregan en tu CP: {plan.excluded_stores.map(storeLabel).join(', ')}
            </p>
          )}

          {/* Carritos por supermercado */}
          {plan?.carts.map(c => (
            <StoreCart key={c.supermercado} plan={c} />
          ))}

          {/* Dirección exacta para el envío final */}
          {plan && (
            <div className="bg-white rounded-2xl border border-slate-200/80 p-3.5 space-y-1.5 shadow-2xs">
              <div className="flex items-center justify-between">
                <span className="text-[12px] font-bold text-slate-800 flex items-center gap-1.5">
                  <MapPin size={14} className="text-blue-600" /> Dirección exacta de entrega
                </span>
                <span className="text-[11px] text-slate-400 font-medium">Para el repartidor</span>
              </div>
              <input
                type="text"
                value={exactAddress || ''}
                onChange={e => setExactAddress(e.target.value)}
                placeholder="Ej: Av. Santa Fe 3200, Piso 4 Depto B (opcional)"
                className="w-full h-10 px-3 rounded-xl border border-slate-200 text-[13px] placeholder:text-slate-400 focus:outline-none focus:border-blue-500"
              />
            </div>
          )}

          {/* Items sin stock */}
          {plan && Array.isArray(plan.missing) && plan.missing.length > 0 && (
            <p className="text-[12px] text-red-700 bg-red-50 rounded-xl p-2.5 border border-red-200/60">
              Sin stock en súper con entrega: {plan.missing.map(m => (typeof m === 'object' && m ? m.nombre || m.ean : String(m))).join(', ')}
            </p>
          )}
        </section>
      </main>
    </div>
  )
}

export default ListScreen
