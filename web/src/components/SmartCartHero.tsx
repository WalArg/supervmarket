import React from 'react'
import {
  TrendingDown,
  Sparkles,
  AlertTriangle,
  Loader2,
  Store,
  CheckCircle2,
  Info,
} from 'lucide-react'
import type { OptimizeMode, OptimizePlan } from '../types'
import { formatPrice } from '../lib/pricing'

export interface SmartCartHeroProps {
  mode: OptimizeMode
  onSelectMode: (mode: OptimizeMode) => void
  plan: OptimizePlan | null
  loading?: boolean
}

interface ScenarioMeta {
  id: OptimizeMode
  label: string
  defaultTagline: string
  badgeLabel: string
  badgeBg: string
  badgeText: string
  icon: React.FC<{ size?: number; className?: string }>
}

const SCENARIOS: ScenarioMeta[] = [
  {
    id: 'ahorro',
    label: 'Más Barata',
    defaultTagline: 'Split óptimo 2-3 súper',
    badgeLabel: 'MÁXIMO AHORRO',
    badgeBg: 'bg-emerald-100',
    badgeText: 'text-emerald-800',
    icon: TrendingDown,
  },
  {
    id: 'balanceada',
    label: 'Equilibrada',
    defaultTagline: 'Balance ahorro vs logística',
    badgeLabel: 'RECOMENDADA',
    badgeBg: 'bg-blue-100',
    badgeText: 'text-blue-800',
    icon: Sparkles,
  },
  {
    id: 'comodidad',
    label: 'Cómoda',
    defaultTagline: 'Todo en 1 solo súper',
    badgeLabel: '1 SOLO SÚPER',
    badgeBg: 'bg-slate-200',
    badgeText: 'text-slate-800',
    icon: Store,
  },
]

export const SmartCartHero: React.FC<SmartCartHeroProps> = ({
  mode,
  onSelectMode,
  plan,
  loading = false,
}) => {
  const previews = plan?.mode_previews
  const activePreview = previews?.[mode]
  const activePlan = plan

  // Total savings vs cómoda or regular price
  const savingsVsComoda = activePreview?.ahorro_vs_comoda ?? 0
  const savingsVsRegular = activePreview?.ahorro_vs_regular ?? 0
  const savingsPct = activePreview?.ahorro_pct ?? 0
  const totalSavings =
    savingsVsComoda > 0
      ? savingsVsComoda
      : (activePlan?.ahorro_total ?? 0)

  const logisticsWarning = activePlan?.logistics_warning || activePreview?.logistics_warning

  return (
    <div className="space-y-2.5">
      {/* 1. Selector de 3 Escenarios (Tabs touch-friendly >= 44px con 0ms switching) */}
      <div className="grid grid-cols-3 gap-1.5 p-1 bg-slate-200/75 rounded-2xl">
        {SCENARIOS.map(sc => {
          const isSelected = mode === sc.id
          const preview = previews?.[sc.id]
          const isAhorro = sc.id === 'ahorro'
          const isBalanceada = sc.id === 'balanceada'

          // Subtext calculation for each tab
          let subText = sc.defaultTagline
          if (preview) {
            if (isAhorro) {
              subText = `${preview.supermercados_count || preview.stops || 2} súper`
            } else if (isBalanceada) {
              const diffVal = preview.diff ?? 0
              subText =
                diffVal > 0
                  ? `+${formatPrice(diffVal)}`
                  : `${preview.supermercados_count || preview.stops || 1} súper`
            } else {
              const diffVal = preview.diff ?? 0
              subText =
                diffVal > 0
                  ? `+${formatPrice(diffVal)}`
                  : '1 súper'
            }
          }

          return (
            <button
              key={sc.id}
              type="button"
              onClick={() => onSelectMode(sc.id)}
              className={`min-h-[58px] p-2 rounded-xl flex flex-col items-center justify-center text-center transition-all active:scale-[0.98] select-none ${
                isSelected
                  ? 'bg-white text-slate-900 shadow-xs ring-1 ring-slate-900/10 font-bold'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-white/50'
              }`}
              aria-pressed={isSelected}
              aria-label={`Seleccionar ${sc.label}`}
            >
              {/* Badge superior */}
              <span
                className={`text-[9px] font-extrabold uppercase tracking-wider px-1.5 py-0.5 rounded-full mb-1 leading-none ${
                  isSelected ? `${sc.badgeBg} ${sc.badgeText}` : 'bg-slate-300/60 text-slate-600'
                }`}
              >
                {sc.badgeLabel}
              </span>

              {/* Título de escenario */}
              <span className="text-[12px] font-extrabold leading-tight">{sc.label}</span>

              {/* Total estimado o diferencial */}
              <span
                className={`text-[11px] font-bold mt-0.5 leading-none ${
                  isSelected
                    ? isAhorro
                      ? 'text-emerald-700 font-extrabold'
                      : isBalanceada
                        ? 'text-blue-700 font-extrabold'
                        : 'text-slate-900 font-extrabold'
                    : 'text-slate-500'
                }`}
              >
                {preview ? formatPrice(preview.total) : subText}
              </span>
            </button>
          )
        })}
      </div>

      {/* 2. Tarjeta Héroe del Escenario Activo */}
      <div className="relative rounded-2xl bg-white border border-slate-200/90 p-4 shadow-2xs overflow-hidden">
        {loading && (
          <div className="absolute inset-0 bg-white/75 backdrop-blur-xs flex items-center justify-center gap-2 text-slate-700 font-bold text-[13px] z-10 transition-opacity">
            <Loader2 className="animate-spin text-blue-600" size={18} />
            <span>Optimizando precios en vivo…</span>
          </div>
        )}

        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-[11px] font-extrabold text-slate-500 uppercase tracking-wider">
                {activePreview?.title ||
                  (mode === 'ahorro'
                    ? 'Opción Más Barata'
                    : mode === 'balanceada'
                      ? 'Opción Equilibrada'
                      : 'Opción Cómoda')}
              </span>
              <span className="text-[11px] text-slate-300">·</span>
              <span className="text-[11px] font-semibold text-slate-600">
                {activePlan
                  ? `${activePlan.stops} ${activePlan.stops === 1 ? 'supermercado' : 'supermercados'}`
                  : 'Cotizando'}
              </span>
            </div>

            {/* Gran Total */}
            <div className="text-[32px] font-black text-slate-900 tracking-tight leading-none mt-1">
              {activePlan ? formatPrice(activePlan.total) : '—'}
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5 font-medium">
              {activePreview?.tagline ||
                (mode === 'ahorro'
                  ? 'Split óptimo 2-3 supermercados'
                  : mode === 'balanceada'
                    ? 'Balance Pareto: ahorro vs comodidad'
                    : 'Toda tu compra en 1 solo súper')}
            </p>
          </div>

          {/* Badge de Ahorro Cuantificado o Costo de Comodidad */}
          {mode === 'ahorro' && totalSavings > 0 && (
            <div className="text-right shrink-0">
              <div className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-[12px] font-extrabold shadow-2xs">
                <TrendingDown size={14} className="text-emerald-600 shrink-0" />
                <span>Ahorrás {formatPrice(totalSavings)}</span>
              </div>
              {savingsPct > 0 && (
                <p className="text-[10px] font-bold text-emerald-700 mt-0.5">
                  ({savingsPct}% menos vs 1 súper)
                </p>
              )}
              {savingsVsRegular > totalSavings && (
                <p className="text-[9.5px] text-slate-400 mt-0.5">
                  -{formatPrice(savingsVsRegular)} vs precio regular
                </p>
              )}
            </div>
          )}

          {mode === 'balanceada' && (
            <div className="text-right shrink-0">
              {totalSavings > 0 ? (
                <>
                  <div className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl bg-blue-50 border border-blue-200 text-blue-800 text-[12px] font-extrabold shadow-2xs">
                    <Sparkles size={13} className="text-blue-600 shrink-0" />
                    <span>Ahorrás {formatPrice(totalSavings)}</span>
                  </div>
                  <p className="text-[10px] font-bold text-blue-700 mt-0.5">
                    {activePlan && activePlan.stops <= 1
                      ? 'Recomendado 1 súper (Pareto)'
                      : `Con solo ${activePlan?.stops || 2} súper`}
                  </p>
                </>
              ) : (
                <div className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl bg-slate-100 text-slate-700 text-[11px] font-bold">
                  <CheckCircle2 size={13} className="text-slate-500 shrink-0" />
                  <span>Sin split necesario</span>
                </div>
              )}
            </div>
          )}

          {mode === 'comodidad' && (
            <div className="text-right shrink-0">
              {(activePreview?.diff ?? 0) > 0 ? (
                <>
                  <div className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl bg-slate-100 border border-slate-200 text-slate-800 text-[11.5px] font-extrabold">
                    <span>+{formatPrice(activePreview!.diff!)}</span>
                  </div>
                  <p className="text-[10px] font-semibold text-slate-500 mt-0.5">
                    Costo de conveniencia
                  </p>
                </>
              ) : (
                <div className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl bg-emerald-50 text-emerald-800 text-[11px] font-bold">
                  <span>¡Mismo precio que Más Barata!</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Desglose Contextual de Reintegros y Envíos */}
        {activePlan && (
          <div className="mt-3 pt-2.5 border-t border-slate-100 flex flex-wrap items-center gap-x-2.5 gap-y-1.5 text-[11.5px] text-slate-600">
            {(activePlan.reintegro_bancario_total ?? 0) > 0 && (
              <span className="inline-flex items-center gap-1 text-purple-700 font-bold bg-purple-50 border border-purple-100 px-2 py-0.5 rounded-lg">
                💳 -{formatPrice(activePlan.reintegro_bancario_total!)} reintegros
              </span>
            )}
            {(activePlan.envio_estimado ?? 0) > 0 ? (
              <span className="inline-flex items-center gap-1 text-slate-700 font-medium bg-slate-100 px-2 py-0.5 rounded-lg">
                🚚 +{formatPrice(activePlan.envio_estimado!)} envío
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-emerald-700 font-semibold bg-emerald-50 px-2 py-0.5 rounded-lg">
                🚚 Envío bonificado / no sumado
              </span>
            )}
            {activePreview?.covered_items !== undefined &&
              activePreview.total_items !== undefined &&
              activePreview.covered_items < activePreview.total_items && (
                <span className="inline-flex items-center gap-1 text-amber-800 font-semibold bg-amber-50 border border-amber-200/60 px-2 py-0.5 rounded-lg">
                  <Info size={12} className="text-amber-600 shrink-0" />
                  {activePreview.covered_items}/{activePreview.total_items} productos cubiertos
                </span>
              )}
          </div>
        )}

        {/* Advertencia Logística si corresponde */}
        {logisticsWarning && (
          <div className="mt-2.5 p-2 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-[11px] flex items-center gap-2">
            <AlertTriangle size={15} className="text-amber-600 shrink-0" />
            <span className="leading-snug">{logisticsWarning}</span>
          </div>
        )}
      </div>
    </div>
  )
}

export default SmartCartHero
