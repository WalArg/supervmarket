import React, { useState, useEffect } from 'react'
import { Flame, MapPin, ChevronDown, Plus, Search, RefreshCw } from 'lucide-react'
import { DISCOUNT_TIERS, type DiscountTier } from '../data/gondolasData'
import { getLiveOffers } from '../api'
import { useLocation } from '../location/LocationContext'
import GondolaCard from './GondolaCard'
import SponsoredGondolaCard from './SponsoredGondolaCard'

interface OffersScreenProps {
  onGoSearch?: () => void
}

export const OffersScreen: React.FC<OffersScreenProps> = ({ onGoSearch }) => {
  const { cp, locationLabel, openModal } = useLocation()
  const [tiers, setTiers] = useState<DiscountTier[]>(DISCOUNT_TIERS)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [isLive, setIsLive] = useState(false)
  const [lastUpdated, setLastUpdated] = useState<string | null>(null)
  const [selectedFilter, setSelectedFilter] = useState<string>('all')
  // Cantidad de productos visibles por nivel de carrusel (inicialmente 3, expandible con "Cargar más")
  const [visibleCountByTier, setVisibleCountByTier] = useState<Record<string, number>>({})

  useEffect(() => {
    let mounted = true
    const fetchOffers = async () => {
      try {
        const data = await getLiveOffers(cp)
        if (mounted && data?.tiers?.length) {
          setTiers(data.tiers)
          setIsLive(!!data.is_live)
          if (data.updated_at) {
            setLastUpdated(data.updated_at)
          }
        }
      } catch (err) {
        // Fallback al baseline curado si la API no está disponible
      }
    }
    fetchOffers()
    return () => {
      mounted = false
    }
  }, [cp])

  const handleRefresh = async () => {
    if (isRefreshing) return
    setIsRefreshing(true)
    try {
      const data = await getLiveOffers(cp, true)
      if (data?.tiers?.length) {
        setTiers(data.tiers)
        setIsLive(!!data.is_live)
        if (data.updated_at) {
          setLastUpdated(data.updated_at)
        }
      }
    } catch (err) {
      // Silencioso en error
    } finally {
      setIsRefreshing(false)
    }
  }

  const getVisibleCount = (tierId: string) => visibleCountByTier[tierId] ?? 3

  const handleLoadMore = (tierId: string, total: number) => {
    setVisibleCountByTier(prev => ({
      ...prev,
      [tierId]: Math.min((prev[tierId] ?? 3) + 3, total),
    }))
  }

  return (
    <div className="pb-28">
      {/* Header Sticky */}
      <header className="sticky top-0 z-30 bg-slate-50/95 backdrop-blur-md pt-safe border-b border-slate-100 shadow-2xs">
        <div className="px-4 pt-3 pb-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-rose-600 to-amber-500 text-white flex items-center justify-center shadow-xs">
                <Flame size={18} className="fill-white" />
              </div>
              <div>
                <h1 className="text-[19px] font-extrabold tracking-tight text-slate-900 leading-none">
                  Ofertas
                </h1>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <p className="text-[11px] text-slate-500 font-medium">
                    Mayores descuentos del día comparados en vivo
                  </p>
                  {isLive && (
                    <span className="inline-flex items-center gap-1 px-1.5 py-0.2 rounded-full text-[9px] font-black bg-emerald-100 text-emerald-800">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                      Hoy
                    </span>
                  )}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={handleRefresh}
                disabled={isRefreshing}
                aria-label="Actualizar ofertas en vivo"
                title="Actualizar ofertas de hoy en vivo"
                className="w-7 h-7 rounded-full bg-slate-100/90 hover:bg-slate-200/90 text-slate-600 hover:text-slate-900 flex items-center justify-center transition-all active:scale-95 disabled:opacity-50 shadow-2xs cursor-pointer"
              >
                <RefreshCw size={12} className={isRefreshing ? 'animate-spin text-rose-600' : ''} />
              </button>

              <button
                type="button"
                onClick={openModal}
                className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-blue-50/90 hover:bg-blue-100/80 border border-blue-200/80 text-blue-700 text-[11px] font-bold active:scale-95 transition-all max-w-[145px] shadow-2xs"
              >
                <MapPin size={12} className="text-blue-600 shrink-0" />
                <span className="truncate">{locationLabel || (cp ? `CP ${cp}` : 'Elegir zona')}</span>
                <ChevronDown size={11} className="text-blue-500 shrink-0" />
              </button>
            </div>
          </div>

          {/* Filtros rápidos exclusivamente por rangos de descuentos grandes */}
          <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar pt-3 pb-0.5">
            <button
              type="button"
              onClick={() => setSelectedFilter('all')}
              className={`shrink-0 h-8 px-3 rounded-full text-[12px] font-bold transition-all border ${
                selectedFilter === 'all'
                  ? 'bg-slate-900 text-white border-slate-900 shadow-xs'
                  : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
              }`}
            >
              Todos los Descuentos
            </button>
            {tiers.map(tier => (
              <button
                key={tier.id}
                type="button"
                onClick={() => setSelectedFilter(tier.id)}
                className={`shrink-0 h-8 px-3 rounded-full text-[12px] font-bold transition-all border flex items-center gap-1 ${
                  selectedFilter === tier.id
                    ? 'bg-rose-600 text-white border-rose-600 shadow-xs'
                    : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
                }`}
              >
                <span>{tier.percentLabel}</span>
              </button>
            ))}
          </div>
        </div>
      </header>

      <main className="px-4 pt-3 space-y-6">
        {/* SECCIONES POR RANGOS DE DESCUENTOS GRANDES (70%-80%, Liquidaciones, 50% y 2x1, Canasta Básica) */}
        {tiers.filter(
          tier => selectedFilter === 'all' || selectedFilter === tier.id,
        ).map((tier, idx) => {
          const visibleLimit = getVisibleCount(tier.id)
          const visibleProducts = tier.products.slice(0, visibleLimit)
          const hasMore = tier.products.length > visibleLimit

          return (
            <section
              key={tier.id}
              className={`space-y-3 ${idx > 0 ? 'pt-4 border-t border-slate-200/60' : 'pt-1'}`}
            >
              {/* Encabezado del Nivel de Descuento */}
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-[16px] font-black text-slate-900 tracking-tight">
                      {tier.title}
                    </h3>
                  </div>
                  <p className="text-[12px] text-slate-500 font-medium mt-0.5">
                    {tier.subtitle}
                  </p>
                </div>
                <span className="shrink-0 px-2.5 py-0.5 rounded-full text-[11px] font-black bg-rose-600 text-white shadow-2xs">
                  {tier.badge}
                </span>
              </div>

              {/* Carrusel horizontal: El patrocinado de Mercado Libre es el PRIMERO DE LA IZQUIERDA */}
              <div className="flex gap-2.5 overflow-x-auto no-scrollbar py-1 px-0.5 -mx-0.5 snap-x">
                <div className="snap-start shrink-0">
                  <SponsoredGondolaCard
                    product={tier.meliSponsored.product}
                    offer={tier.meliSponsored.offer}
                  />
                </div>
                {visibleProducts.map(product => (
                  <div key={`tier-${tier.id}-${product.ean}`} className="snap-start shrink-0">
                    <GondolaCard group={product} />
                  </div>
                ))}

                {/* Tarjeta interactiva de Cargar Más al final del carrusel */}
                {hasMore ? (
                  <div className="snap-start shrink-0 flex items-stretch">
                    <button
                      type="button"
                      onClick={() => handleLoadMore(tier.id, tier.products.length)}
                      aria-label={`Cargar más ofertas en ${tier.title}`}
                      className="w-[140px] rounded-2xl border-2 border-dashed border-rose-300 hover:border-rose-500 bg-rose-50/60 hover:bg-rose-100/70 p-4 flex flex-col items-center justify-center text-center transition-all group active:scale-95 shadow-2xs cursor-pointer"
                    >
                      <div className="w-11 h-11 rounded-2xl bg-rose-100 group-hover:bg-rose-600 text-rose-600 group-hover:text-white flex items-center justify-center mb-2.5 transition-all shadow-xs group-hover:scale-105">
                        <Plus size={22} className="stroke-[2.5]" />
                      </div>
                      <span className="text-[13px] font-black text-rose-950 leading-tight">
                        Cargar más ofertas
                      </span>
                      <span className="text-[10px] text-rose-600 font-bold mt-1.5 bg-white/90 px-2 py-0.5 rounded-full border border-rose-200">
                        +{tier.products.length - visibleLimit} más
                      </span>
                    </button>
                  </div>
                ) : onGoSearch ? (
                  <div className="snap-start shrink-0 flex items-stretch">
                    <button
                      type="button"
                      onClick={onGoSearch}
                      aria-label="Ver más ofertas en el catálogo"
                      className="w-[140px] rounded-2xl border border-slate-200 bg-slate-50/70 hover:bg-slate-100 p-4 flex flex-col items-center justify-center text-center transition-all group active:scale-95 shadow-2xs cursor-pointer"
                    >
                      <div className="w-11 h-11 rounded-2xl bg-white border border-slate-200 text-slate-700 group-hover:text-blue-600 flex items-center justify-center mb-2.5 transition-all shadow-2xs group-hover:scale-105">
                        <Search size={20} className="stroke-[2.2]" />
                      </div>
                      <span className="text-[13px] font-black text-slate-800 leading-tight">
                        Ver más ofertas
                      </span>
                      <span className="text-[10px] text-slate-500 font-medium mt-1.5">
                        Ir al Buscador
                      </span>
                    </button>
                  </div>
                ) : null}
              </div>
            </section>
          )
        })}

        {/* Banner buscador complementario */}
        {onGoSearch && (
          <div className="pt-2">
            <button
              type="button"
              onClick={onGoSearch}
              className="w-full p-4 rounded-2xl bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200/80 text-left flex items-center justify-between group active:scale-[0.99] transition-all"
            >
              <div>
                <h3 className="text-[14px] font-extrabold text-blue-950">
                  ¿Buscás otro producto en específico?
                </h3>
                <p className="text-[12px] text-blue-700 font-medium mt-0.5">
                  Comparamos precios y promociones entre todos los supermercados al instante.
                </p>
              </div>
              <span className="shrink-0 ml-3 px-3 py-1.5 rounded-xl bg-blue-600 text-white font-bold text-[12px] group-hover:bg-blue-700 shadow-xs">
                Buscar
              </span>
            </button>
          </div>
        )}
      </main>
    </div>
  )
}

export default OffersScreen
