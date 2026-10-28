import React, { useEffect, useState } from 'react'
import {
  Trash2,
  Share2,
  Calendar,
  CreditCard,
  ShoppingBasket,
  Plus,
  Minus,
  Truck,
  MapPin,
  ChevronDown,
  AlertCircle,
  Check,
} from 'lucide-react'
import type { OptimizeMode, OptimizePlan } from '../types'
import { useCart } from '../cart/CartContext'
import { useLocation } from '../location/LocationContext'
import { useBenefits } from '../benefits/BenefitsContext'
import { useHabitualList } from '../cart/HabitualListContext'
import { optimize } from '../api'
import { formatPrice } from '../lib/pricing'
import { storeLabel } from '../lib/stores'
import StoreCart from './StoreCart'
import SmartCartHero from './SmartCartHero'
import MissingItemsBreakdown from './MissingItemsBreakdown'
import { generateShareUrl, formatShareMessage, executeShare } from '../cart/portableList'

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
  const { recordSnapshot } = useHabitualList()
  const [mode, setMode] = useState<OptimizeMode>('ahorro')
  const [includeShipping, setIncludeShipping] = useState(false)
  const [plan, setPlan] = useState<OptimizePlan | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState(false)
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
  const [showCopyToast, setShowCopyToast] = useState(false)

  const itemsKey = items.map(i => `${i.ean}:${i.qty}:${i.store || ''}`).join(',')
  const planContextKey = `${itemsKey}|${cp || ''}|${includeShipping}|${selectedCards.join(',')}|${selectedDay}`


  // 0ms Mode Switching: Uses precalculated all_plans from backend
  const handleSelectMode = (newMode: OptimizeMode) => {
    setMode(newMode)
    if (plan?.all_plans?.[newMode]) {
      const selected = plan.all_plans[newMode]
      setPlan({
        ...selected,
        context_key: plan.context_key,
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

    // Instant switch if plan already cached for this exact context
    if (plan && plan.context_key === planContextKey && plan.all_plans?.[mode]) {
      const selected = plan.all_plans[mode]
      setPlan({
        ...selected,
        context_key: planContextKey,
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
            setPlan({
              ...p,
              context_key: planContextKey,
            })
            setLoadError(false)
            recordSnapshot(p, 'optimization_view')
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
    if (!items.length) return
    const shareUrl = generateShareUrl(items, 'list')
    const text = formatShareMessage({
      items,
      planTotal: plan?.total,
      planSaving: plan?.ahorro_total,
      shareUrl,
    })
    const res = await executeShare({
      title: 'Mi lista en SuperVmarket',
      text,
      url: shareUrl,
    })
    if (res.method === 'clipboard') {
      setShowCopyToast(true)
      setTimeout(() => setShowCopyToast(false), 3000)
    }
  }

  if (!items.length) {
    return (
      <div className="pt-safe px-4 py-8 min-h-[75dvh] flex flex-col items-center justify-center text-center max-w-md mx-auto">
        <div className="w-16 h-16 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center shadow-xs">
          <ShoppingBasket size={32} />
        </div>
        <h2 className="mt-4 text-[19px] font-extrabold text-slate-900">Tu carrito está vacío</h2>
        <p className="mt-1.5 text-[14px] text-slate-500 max-w-xs leading-relaxed">
          Agregá productos desde el buscador o desde la pestaña Guardados para comparar precios y optimizar tu compra.
        </p>

        <button
          type="button"
          onClick={onGoSearch}
          className="mt-6 min-h-[44px] h-11 px-6 rounded-2xl bg-blue-600 hover:bg-blue-700 active:scale-95 text-white font-bold transition-all shadow-md shadow-blue-500/20"
        >
          Explorar productos
        </button>
      </div>
    )
  }

  const best = plan?.best_day_suggestion
  const showBestDay =
    best && best.day !== plan?.day && best.saving > (plan?.reintegro_bancario_total || 0)

  return (
    <div>
      {/* HEADER COMPACTO STICKY */}
      <header className="sticky top-0 z-30 bg-slate-50/95 backdrop-blur-md pt-safe border-b border-slate-100/80">
        <div className="px-4 pt-3 pb-2.5 flex items-center justify-between">
          <div className="min-w-0 flex-1 mr-2">
            <h1 className="text-[20px] font-extrabold tracking-tight text-slate-900">Carrito</h1>
            <p className="text-[12px] text-slate-500 font-medium truncate">
              {items.length} producto{items.length === 1 ? '' : 's'} · {totalUnits} unidad{totalUnits === 1 ? '' : 'es'}
            </p>
          </div>
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={share}
              aria-label="Compartir lista o carrito"
              className="w-11 h-11 flex items-center justify-center rounded-xl text-slate-600 hover:bg-slate-200/60 active:scale-95 transition-all"
            >
              <Share2 size={19} />
            </button>
            <button
              type="button"
              onClick={clear}
              className="min-h-[44px] text-[12px] font-bold text-red-600 px-3 py-2 rounded-xl hover:bg-red-50 active:scale-95 transition-all flex items-center justify-center"
            >
              Vaciar
            </button>
          </div>
        </div>

        {/* Toasts Feedback */}
        {showCopyToast && (
          <div className="mx-4 mb-2 p-2 rounded-xl bg-blue-50 border border-blue-200 text-blue-800 text-[11px] font-bold flex items-center gap-2 animate-[fade-in_0.2s_ease-out]">
            <Check size={14} className="text-blue-600 shrink-0" />
            <span>¡Enlace copiado al portapapeles!</span>
          </div>
        )}
      </header>

      <main className="px-4 pt-3 pb-28 space-y-3">
        {/* 1. HÉROE SMART CART: 3 ESCENARIOS EN VIEWPORT SUPERIOR */}
        <SmartCartHero
          mode={mode}
          onSelectMode={handleSelectMode}
          plan={plan}
          loading={loading}
        />

        {/* 2. BARRA CONTEXTUAL COMPACTA (44px de altura, consolida CP, Tarjetas y Flete) */}
        <div className="bg-white rounded-2xl border border-slate-200/80 p-1.5 flex items-center gap-1.5 shadow-2xs">
          {/* CP / Ubicación */}
          <button
            type="button"
            onClick={openModal}
            className="min-h-[44px] h-11 px-2.5 rounded-xl bg-slate-50 hover:bg-slate-100/80 active:scale-[0.98] transition-all flex items-center gap-1.5 min-w-0 flex-1 text-left"
            title="Cambiar código postal o dirección"
            aria-label="Cambiar código postal o dirección"
          >
            <div className="w-7 h-7 rounded-lg bg-blue-100/60 text-blue-700 flex items-center justify-center shrink-0">
              <MapPin size={14} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[12px] font-bold text-slate-800 truncate leading-tight">
                {locationLabel || (cp ? `CP ${cp}` : 'Ubicación')}
              </p>
              <p className="text-[10px] text-slate-400 truncate leading-tight">
                {exactAddress ? exactAddress.split(',')[0] : (cp ? `Zona CP ${cp}` : 'Elegir zona')}
              </p>
            </div>
          </button>

          {/* Tarjetas / Día */}
          <button
            type="button"
            onClick={onGoProfile}
            className="min-h-[44px] h-11 px-2.5 rounded-xl bg-slate-50 hover:bg-slate-100/80 active:scale-[0.98] transition-all flex items-center gap-1.5 min-w-0 flex-1 text-left"
            title="Configurar tarjetas y día de compra"
            aria-label="Configurar tarjetas y día de compra"
          >
            <div className="w-7 h-7 rounded-lg bg-purple-100/60 text-purple-700 flex items-center justify-center shrink-0">
              <CreditCard size={14} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[12px] font-bold text-slate-800 truncate leading-tight">
                {DAY_LABEL[selectedDay]?.slice(0, 3) || selectedDay.slice(0, 3)}
              </p>
              <p className="text-[10px] text-slate-400 truncate leading-tight">
                {selectedCards.length > 0 ? `${selectedCards.length} 💳` : 'Sin tarjetas'}
              </p>
            </div>
          </button>

          {/* Toggle de Flete */}
          <button
            type="button"
            onClick={() => setIncludeShipping(prev => !prev)}
            className={`min-h-[44px] h-11 px-2.5 rounded-xl border transition-all flex items-center gap-1.5 shrink-0 active:scale-95 ${
              includeShipping
                ? 'bg-blue-50 border-blue-200 text-blue-700 font-bold shadow-2xs'
                : 'bg-slate-50 border-slate-200/60 text-slate-500 font-semibold hover:text-slate-700'
            }`}
            title={includeShipping ? 'Envío incluido en el cálculo' : 'Sumar costo de flete al cálculo'}
            aria-label={includeShipping ? 'Envío incluido en el cálculo' : 'Sumar costo de flete al cálculo'}
          >
            <Truck size={15} className={includeShipping ? 'text-blue-600' : 'text-slate-400'} />
            <span className="text-[11px] leading-tight">Envío</span>
            <span
              className={`w-2 h-2 rounded-full transition-colors ${
                includeShipping ? 'bg-blue-600' : 'bg-slate-300'
              }`}
            />
          </button>
        </div>

        {/* 3. MENSAJES DE ERROR / REINTENTO DE COTIZACIÓN */}
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
              className="min-h-[44px] px-3.5 py-1.5 rounded-xl bg-amber-600 text-white font-bold text-[11px] shrink-0 active:scale-95 transition-all shadow-xs flex items-center justify-center"
            >
              Reintentar
            </button>
          </div>
        )}

        {/* 4. BANNER CONDICIONAL DE MEJOR DÍA */}
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
              className="min-h-[44px] h-11 px-3.5 rounded-xl bg-purple-600 text-white text-[12px] font-bold active:bg-purple-700 active:scale-95 transition-all flex items-center justify-center"
            >
              Ver
            </button>
          </div>
        )}

        {/* 5. TIENDAS EXCLUIDAS POR CP */}
        {plan?.excluded_stores && plan.excluded_stores.length > 0 && (
          <p className="text-[12px] text-amber-800 bg-amber-50 rounded-xl p-2.5 border border-amber-200/60">
            No entregan en tu CP: {plan.excluded_stores.map(storeLabel).join(', ')}
          </p>
        )}

        {/* 6. TIENDAS OPTIMIZADAS INMEDIATAMENTE VISIBLES (StoreCart) */}
        {plan?.carts.map(c => (
          <StoreCart key={c.supermercado} plan={c} />
        ))}

        {/* 7. CAJÓN COLAPSABLE DE PRODUCTOS (Expandible para editar cantidades y no tapar las tiendas) */}
        <section className="bg-white rounded-2xl border border-slate-200/80 shadow-2xs overflow-hidden">
          <button
            type="button"
            onClick={() => setIsDrawerOpen(prev => !prev)}
            className="w-full min-h-[48px] h-12 px-4 flex items-center justify-between text-left active:bg-slate-50 transition-colors"
            aria-expanded={isDrawerOpen}
            aria-label="Ver y editar productos agregados"
          >
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-7 h-7 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
                <ShoppingBasket size={15} />
              </div>
              <span className="text-[13px] font-extrabold text-slate-900 truncate">
                {items.length} producto{items.length === 1 ? '' : 's'} en tu lista
              </span>
              <span className="text-[11px] text-slate-500 font-medium shrink-0">
                ({totalUnits} un.)
              </span>
            </div>
            <div className="flex items-center gap-1.5 shrink-0 text-slate-500">
              <span className="text-[11px] font-bold text-blue-600">
                {isDrawerOpen ? 'Ocultar' : 'Ver y editar'}
              </span>
              <ChevronDown
                size={17}
                className={`transition-transform duration-200 text-slate-400 ${
                  isDrawerOpen ? 'rotate-180 text-blue-600' : ''
                }`}
              />
            </div>
          </button>

          {isDrawerOpen && (
            <div className="border-t border-slate-100 divide-y divide-slate-100">
              <div className="px-4 py-2 bg-slate-50/70 flex items-center justify-between">
                <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  Editar cantidades o quitar
                </span>
                <button
                  type="button"
                  onClick={onGoSearch}
                  className="min-h-[44px] px-2 text-[12px] font-bold text-blue-600 hover:text-blue-700 flex items-center gap-1 active:scale-95 transition-transform"
                >
                  <Plus size={13} /> Agregar más
                </button>
              </div>

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

                  {/* Stepper táctil accesible >= 44x44px */}
                  <div className="flex items-center h-11 rounded-xl border border-slate-200 shrink-0 bg-slate-50">
                    <button
                      type="button"
                      onClick={() => setQty(i.ean, i.qty - 1)}
                      className="w-11 h-11 flex items-center justify-center text-slate-600 hover:bg-slate-200/60 rounded-l-xl active:scale-90 transition-transform"
                      aria-label={`Restar una unidad de ${i.nombre}`}
                    >
                      <Minus size={15} />
                    </button>
                    <span className="w-7 text-center text-[13px] font-extrabold text-slate-900">
                      {i.qty}
                    </span>
                    <button
                      type="button"
                      onClick={() => setQty(i.ean, i.qty + 1)}
                      className="w-11 h-11 flex items-center justify-center text-slate-600 hover:bg-slate-200/60 rounded-r-xl active:scale-90 transition-transform"
                      aria-label={`Sumar una unidad de ${i.nombre}`}
                    >
                      <Plus size={15} />
                    </button>
                  </div>

                  {/* Botón eliminar táctil accesible >= 44x44px con separación */}
                  <button
                    type="button"
                    onClick={() => remove(i.ean)}
                    aria-label={`Quitar ${i.nombre} de la lista`}
                    className="w-11 h-11 flex items-center justify-center text-slate-400 hover:text-red-600 active:scale-90 transition-colors shrink-0 rounded-xl hover:bg-red-50 ml-1.5"
                  >
                    <Trash2 size={17} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* 8. DIRECCIÓN EXACTA DE ENTREGA */}
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
              className="w-full min-h-[44px] h-11 px-3 rounded-xl border border-slate-200 text-[13px] placeholder:text-slate-400 focus:outline-none focus:border-blue-500"
            />
          </div>
        )}

        {/* 9. DESGLOSE ESTRUCTURADO DE PRODUCTOS FALTANTES Y ALTERNATIVAS */}
        {plan?.missing && plan.missing.length > 0 && (
          <MissingItemsBreakdown missing={plan.missing} />
        )}
      </main>
    </div>
  )
}

export default ListScreen
