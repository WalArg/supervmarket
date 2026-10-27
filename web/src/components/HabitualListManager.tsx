import React, { useState } from 'react'
import {
  TrendingUp,
  TrendingDown,
  PiggyBank,
  ChevronDown,
  Bookmark,
  Check,
  RotateCcw,
  Sparkles,
  Info,
} from 'lucide-react'
import { useHabitualList } from '../cart/HabitualListContext'
import { useCart } from '../cart/CartContext'
import { formatPrice } from '../lib/pricing'

export const HabitualListManager: React.FC = () => {
  const {
    habitualList,
    hasHabitualList,
    isCartSavedAsHabitual,
    history,
    comparison,
    stats,
    saveCartAsHabitual,
    loadHabitualIntoCart,
  } = useHabitualList()
  const { items } = useCart()

  const [expanded, setExpanded] = useState(false)
  const [toastMessage, setToastMessage] = useState<string | null>(null)

  const showToast = (msg: string) => {
    setToastMessage(msg)
    setTimeout(() => setToastMessage(null), 3000)
  }

  const handleSave = () => {
    const res = saveCartAsHabitual()
    if (res.success) {
      if (typeof navigator !== 'undefined' && navigator.vibrate) {
        navigator.vibrate(40)
      }
      showToast(`¡Lista habitual guardada con ${res.count} productos!`)
    }
  }

  // Generación matemática de Sparkline SVG puro (0 dependencias)
  const renderSparkline = () => {
    if (history.length < 2) {
      return (
        <div className="mt-3 pt-3 border-t border-slate-100 text-[11px] text-slate-500 bg-slate-50/80 rounded-xl p-3 border border-slate-100">
          <p className="font-bold text-slate-700 mb-0.5">📊 Histórico de Precios en construcción</p>
          <p>
            Registramos la línea base de tu compra hoy. En tus próximas visitas se irá dibujando la curva de inflación y variación de precios de tu changuito.
          </p>
        </div>
      )
    }

    const width = 300
    const height = 55
    const padY = 8
    const pointsData = history.map(s => s.total_ahorro)
    const minVal = Math.min(...pointsData)
    const maxVal = Math.max(...pointsData)
    const range = maxVal - minVal || 1

    const coords = pointsData.map((val, idx) => {
      const x = Number(((idx / (pointsData.length - 1)) * (width - 16) + 8).toFixed(1))
      const y = Number((height - padY - ((val - minVal) / range) * (height - 2 * padY)).toFixed(1))
      return { x, y, val }
    })

    const pathD = coords.reduce((acc, pt, idx) => {
      return idx === 0 ? `M ${pt.x} ${pt.y}` : `${acc} L ${pt.x} ${pt.y}`
    }, '')

    const areaPoints = `${coords[0].x},${height} ${coords.map(c => `${c.x},${c.y}`).join(' ')} ${coords[coords.length - 1].x},${height}`

    const lastCoord = coords[coords.length - 1]

    return (
      <div className="mt-3 pt-3 border-t border-slate-100">
        <div className="flex items-center justify-between text-[11px] font-bold text-slate-500 mb-1">
          <span>Evolución histórico ({history.length} compras)</span>
          <span className="text-blue-600 font-extrabold">{formatPrice(lastCoord.val)}</span>
        </div>
        <div className="w-full bg-slate-50/80 rounded-xl p-2 border border-slate-100 overflow-hidden">
          <svg
            viewBox={`0 0 ${width} ${height}`}
            className="w-full h-14 overflow-visible"
            aria-label="Gráfico de evolución histórica de la canasta"
          >
            <defs>
              <linearGradient id="blueSparkGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#2563EB" stopOpacity="0.25" />
                <stop offset="100%" stopColor="#2563EB" stopOpacity="0.0" />
              </linearGradient>
            </defs>

            {/* Área bajo la curva con gradiente */}
            <polygon points={areaPoints} fill="url(#blueSparkGrad)" />

            {/* Línea de tendencia */}
            <path
              d={pathD}
              fill="none"
              stroke="#2563EB"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            {/* Punto más reciente */}
            <circle cx={lastCoord.x} cy={lastCoord.y} r="4" fill="#2563EB" />
            <circle
              cx={lastCoord.x}
              cy={lastCoord.y}
              r="7"
              fill="#2563EB"
              opacity="0.2"
              className="animate-ping"
            />
          </svg>
          <div className="flex justify-between items-center text-[10px] text-slate-400 font-medium px-1 mt-1">
            <span>Inicio</span>
            <span>Hoy</span>
          </div>
        </div>
      </div>
    )
  }

  // Si no hay historial ni lista habitual ni items en changuito, no mostrar nada
  if (!history.length && !hasHabitualList && !items.length) {
    return null
  }

  return (
    <section className="bg-white rounded-2xl border border-slate-200/80 p-3.5 shadow-2xs space-y-3">
      {/* Toast Feedback */}
      {toastMessage && (
        <div className="p-2.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-[12px] font-bold flex items-center gap-2 animate-[fade-in_0.2s_ease-out]">
          <Check size={16} className="text-emerald-600 shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Header Widget */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
            <PiggyBank size={18} />
          </div>
          <div>
            <div className="flex items-center gap-1.5 flex-wrap">
              <h2 className="text-[13px] font-extrabold text-slate-900 leading-tight">
                Mi Lista Habitual & Histórico de Precios
              </h2>
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-md bg-blue-100 text-blue-800">
                Termómetro de Ahorro
              </span>
            </div>
            <p className="text-[11px] text-slate-500 font-medium leading-tight mt-0.5">
              {stats.total_snapshots > 0
                ? `${stats.total_snapshots} cotizaciones registradas`
                : 'Monitoreo de inflación sin suscripción ni cuenta'}
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setExpanded(prev => !prev)}
          className="min-h-[44px] px-2.5 rounded-xl text-slate-500 hover:text-slate-800 hover:bg-slate-100/60 active:scale-95 transition-all flex items-center gap-1 text-[11px] font-bold"
          aria-expanded={expanded}
          aria-label="Ver detalles del termómetro de ahorro"
        >
          <span>{expanded ? 'Menos' : 'Detalles'}</span>
          <ChevronDown
            size={15}
            className={`transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
          />
        </button>
      </div>

      {/* 1-Tap Direct Habitual Controls (Visible sin necesidad de expandir) */}
      {items.length > 0 && !isCartSavedAsHabitual && (
        <div className="pt-0.5">
          <button
            type="button"
            onClick={handleSave}
            className="w-full min-h-[44px] px-3.5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-[12px] flex items-center justify-center gap-2 active:scale-98 transition-all shadow-xs"
          >
            <Bookmark size={15} />
            <span>⭐ Guardar changuito como Mi Lista Habitual</span>
          </button>
        </div>
      )}

      {isCartSavedAsHabitual && (
        <div className="pt-0.5">
          <div className="min-h-[40px] px-3 py-1.5 rounded-xl bg-emerald-50 text-emerald-800 text-[11px] font-bold border border-emerald-200/80 flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <Check size={15} className="text-emerald-600" />
              <span>Changuito sincronizado con tu Lista Habitual</span>
            </div>
            <span className="text-[10px] font-semibold text-emerald-600">Recurrencia activa</span>
          </div>
        </div>
      )}

      {/* Métricas Principales */}
      <div className="grid grid-cols-2 gap-2">
        {/* Métrica 1: Variación vs última compra */}
        <div className="bg-slate-50/90 rounded-xl p-2.5 border border-slate-100 flex flex-col justify-between">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
            Vs. última compra
          </span>
          {comparison && comparison.has_history ? (
            <div className="mt-1">
              <div className="flex items-center gap-1">
                {comparison.percentage_delta > 0 ? (
                  <span className="inline-flex items-center gap-0.5 text-[13px] font-extrabold text-amber-700 bg-amber-100/80 px-1.5 py-0.5 rounded-md">
                    <TrendingUp size={13} />
                    +{comparison.percentage_delta}%
                  </span>
                ) : comparison.percentage_delta < 0 ? (
                  <span className="inline-flex items-center gap-0.5 text-[13px] font-extrabold text-emerald-700 bg-emerald-100/80 px-1.5 py-0.5 rounded-md">
                    <TrendingDown size={13} />
                    {comparison.percentage_delta}%
                  </span>
                ) : (
                  <span className="text-[13px] font-extrabold text-slate-700">0.0%</span>
                )}
              </div>
              <p className="mt-1 text-[10px] text-slate-400 font-medium">
                {comparison.days_elapsed === 0
                  ? 'Mismo día'
                  : `Hace ${comparison.days_elapsed} día${comparison.days_elapsed === 1 ? '' : 's'}`}
              </p>
            </div>
          ) : (
            <div className="mt-1">
              <span className="text-[12px] font-bold text-slate-700">Línea base</span>
              <p className="text-[10px] text-slate-400">Primer registro</p>
            </div>
          )}
        </div>

        {/* Métrica 2: Ahorro acumulado histórico */}
        <div className="bg-emerald-50/60 rounded-xl p-2.5 border border-emerald-100/80 flex flex-col justify-between">
          <span className="text-[10px] font-bold text-emerald-800 uppercase tracking-wider">
            Ahorro Acumulado
          </span>
          <div className="mt-1">
            <span className="text-[14px] font-black text-emerald-700">
              {formatPrice(stats.cumulative_savings_ars)}
            </span>
            <p className="text-[10px] text-emerald-600/80 font-medium">
              en {stats.total_snapshots} compra{stats.total_snapshots === 1 ? '' : 's'}
            </p>
          </div>
        </div>
      </div>

      {/* Sección Expandida con Gráfico Sparkline e Info de Canasta */}
      {expanded && (
        <div className="space-y-3 pt-1">
          {renderSparkline()}

          {comparison?.is_basket_size_different && (
            <div className="p-2.5 rounded-xl bg-blue-50/70 border border-blue-100 text-[11px] text-blue-900 flex items-start gap-2">
              <Info size={14} className="text-blue-600 shrink-0 mt-0.5" />
              <span>
                El tamaño de tu changuito cambió ({comparison.items_count_diff > 0 ? '+' : ''}
                {comparison.items_count_diff} productos). Variación normalizada por unidad:{' '}
                <strong>
                  {comparison.normalized_unit_delta_pct !== undefined
                    ? `${comparison.normalized_unit_delta_pct > 0 ? '+' : ''}${comparison.normalized_unit_delta_pct}%`
                    : 'N/A'}
                </strong>
                .
              </span>
            </div>
          )}

          {/* Habitual List Controls */}
          <div className="pt-2 border-t border-slate-100 flex flex-wrap gap-2">
            {items.length > 0 && !isCartSavedAsHabitual && (
              <button
                type="button"
                onClick={handleSave}
                className="min-h-[44px] px-3.5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-[12px] flex items-center gap-1.5 active:scale-95 transition-all shadow-xs"
              >
                <Bookmark size={15} />
                <span>Guardar changuito como Habitual</span>
              </button>
            )}

            {hasHabitualList && !isCartSavedAsHabitual && (
              <button
                type="button"
                onClick={() => loadHabitualIntoCart('replace')}
                className="min-h-[44px] px-3.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-[12px] flex items-center gap-1.5 active:scale-95 transition-all"
              >
                <RotateCcw size={15} />
                <span>Cargar lista habitual</span>
              </button>
            )}

            {isCartSavedAsHabitual && (
              <div className="min-h-[44px] px-3 py-2 rounded-xl bg-emerald-50 text-emerald-800 text-[12px] font-bold border border-emerald-200 flex items-center gap-1.5">
                <Check size={16} className="text-emerald-600" />
                <span>Changuito actual sincronizado con Lista Habitual</span>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  )
}

export default HabitualListManager
