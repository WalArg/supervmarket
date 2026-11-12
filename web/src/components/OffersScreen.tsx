import React, { useState, useEffect, useRef, useMemo } from 'react'
import { Flame, MapPin, ChevronDown, Plus, Search, RefreshCw, Zap, LayoutGrid, Rows3, ExternalLink } from 'lucide-react'
import { DISCOUNT_TIERS, MARKETPLACE_DISCOUNT_TIERS, type DiscountTier } from '../data/gondolasData'
import { getLiveOffers } from '../api'
import { useLocation } from '../location/LocationContext'
import GondolaCard from './GondolaCard'
import SponsoredGondolaCard from './SponsoredGondolaCard'
import OffersSheet from './OffersSheet'
import { formatPrice } from '../lib/pricing'
import { storeLabel } from '../lib/stores'
import { decorateOutboundUrl, trackOutboundAffiliateClick } from '../lib/affiliate'
import type { ProductGroup, SupermarketOffer } from '../types'

interface OffersScreenProps {
  onGoSearch?: () => void
}

const MOMENT_BADGES: Record<string, { moment: string; icon: string }> = {
  'tier-70-80': { moment: 'Limpieza & Cuidado Personal', icon: '🧼' },
  'tier-clearance': { moment: 'Liquidaciones de Temporada', icon: '🏷️' },
  'tier-50': { moment: 'Llená la Alacena & Bebidas', icon: '🧺' },
  'tier-basket': { moment: 'Canasta Básica y Esenciales', icon: '🥛' },
  'tier-mp-electro': { moment: 'Smart TVs, Celulares y Computación', icon: '📱' },
  'tier-mp-hogar': { moment: 'Sommiers, Colchones y Descanso', icon: '🏠' },
  'tier-mp-destacadas': { moment: 'Marcas Oficiales y Audio', icon: '🎧' },
}

export const OffersScreen: React.FC<OffersScreenProps> = ({ onGoSearch }) => {
  const { cp, locationLabel, openModal } = useLocation()
  const [tiers, setTiers] = useState<DiscountTier[]>(DISCOUNT_TIERS)
  const [marketplaceTiers, setMarketplaceTiers] = useState<DiscountTier[]>(MARKETPLACE_DISCOUNT_TIERS)
  const [selectedVertical, setSelectedVertical] = useState<'all' | 'supermarket' | 'marketplace'>('all')
  const [selectedFilter, setSelectedFilter] = useState<string>('all')
  const [viewMode, setViewMode] = useState<'carousel' | 'grid'>('carousel')
  const [heroSheetGroup, setHeroSheetGroup] = useState<ProductGroup | null>(null)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [isLive, setIsLive] = useState(false)
  const [lastUpdated, setLastUpdated] = useState<string | null>(null)
  // Cantidad de productos visibles por nivel de carrusel (inicialmente 3, expandible con "Cargar más")
  const [visibleCountByTier, setVisibleCountByTier] = useState<Record<string, number>>({})
  const lastFetchTimeRef = useRef<number>(Date.now())

  useEffect(() => {
    let mounted = true
    const fetchOffers = async () => {
      lastFetchTimeRef.current = Date.now()
      try {
        const data = await getLiveOffers(cp)
        if (mounted) {
          if (data?.tiers?.length) {
            setTiers(data.tiers)
          }
          if (data?.marketplace_tiers?.length) {
            setMarketplaceTiers(data.marketplace_tiers)
          }
          setIsLive(!!data?.is_live)
          if (data?.updated_at) {
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

  useEffect(() => {
    const handleVisibilityOrFocus = async () => {
      if (typeof document !== 'undefined' && document.visibilityState && document.visibilityState !== 'visible') {
        return
      }
      if (Date.now() - lastFetchTimeRef.current <= 600_000) {
        return
      }
      lastFetchTimeRef.current = Date.now()
      try {
        const data = await getLiveOffers(cp, false)
        if (data?.tiers?.length) {
          setTiers(data.tiers)
        }
        if (data?.marketplace_tiers?.length) {
          setMarketplaceTiers(data.marketplace_tiers)
        }
        setIsLive(!!data?.is_live)
        if (data?.updated_at) {
          setLastUpdated(data.updated_at)
        }
      } catch {
        // Silencioso en auto-refresh de fondo
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityOrFocus)
    window.addEventListener('focus', handleVisibilityOrFocus)
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityOrFocus)
      window.removeEventListener('focus', handleVisibilityOrFocus)
    }
  }, [cp])

  const handleRefresh = async () => {
    if (isRefreshing) return
    setIsRefreshing(true)
    lastFetchTimeRef.current = Date.now()
    try {
      const data = await getLiveOffers(cp, true)
      if (data?.tiers?.length) {
        setTiers(data.tiers)
      }
      if (data?.marketplace_tiers?.length) {
        setMarketplaceTiers(data.marketplace_tiers)
      }
      setIsLive(!!data?.is_live)
      if (data?.updated_at) {
        setLastUpdated(data.updated_at)
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

  const displayedTiers = useMemo(() => {
    if (selectedVertical === 'supermarket') return tiers
    if (selectedVertical === 'marketplace') return marketplaceTiers
    return [...tiers, ...marketplaceTiers]
  }, [selectedVertical, tiers, marketplaceTiers])

  // La Ganga del Día: Supermercados (Oportunidad verificada de Mercado Libre)
  const topSuperMeliDeal = useMemo(() => {
    const candidates: Array<{ product: ProductGroup; offer: SupermarketOffer }> = []
    for (const t of tiers) {
      if (t.meliSponsored?.product && t.meliSponsored?.offer && t.meliSponsored.offer.precio > 0) {
        candidates.push({ product: t.meliSponsored.product, offer: t.meliSponsored.offer })
      }
      for (const p of t.products || []) {
        const mOffer = p.offers?.find(o => o.supermercado === 'MercadoLibre' && o.precio > 0)
        if (mOffer) {
          candidates.push({ product: p, offer: mOffer })
        }
      }
    }
    if (!candidates.length) return null
    candidates.sort((a, b) => (b.offer.discount || 0) - (a.offer.discount || 0))
    return candidates[0]
  }, [tiers])

  // La Ganga del Día: Marketplaces & Electro (Oportunidad verificada de Mercado Libre)
  const topTechMeliDeal = useMemo(() => {
    const candidates: Array<{ product: ProductGroup; offer: SupermarketOffer }> = []
    for (const t of marketplaceTiers) {
      if (t.meliSponsored?.product && t.meliSponsored?.offer && t.meliSponsored.offer.precio > 0) {
        candidates.push({ product: t.meliSponsored.product, offer: t.meliSponsored.offer })
      }
      for (const p of t.products || []) {
        const mOffer = p.offers?.find(o => o.supermercado === 'MercadoLibre' && o.precio > 0)
        if (mOffer) {
          candidates.push({ product: p, offer: mOffer })
        }
      }
    }
    if (!candidates.length) return null
    candidates.sort((a, b) => (b.offer.discount || 0) - (a.offer.discount || 0))
    return candidates[0]
  }, [marketplaceTiers])

  const renderTier = (tier: DiscountTier, idx: number) => {
    const isMp = tier.id.startsWith('tier-mp-') || tier.vertical === 'electro' || tier.vertical === 'marketplace'
    const validProducts = (tier.products || []).filter(
      p => Array.isArray(p?.offers) && p.offers.length > 0 && p.offers[0].precio > 0,
    )
    const visibleLimit = getVisibleCount(tier.id)
    const visibleProducts = validProducts.slice(0, visibleLimit)
    const hasMore = validProducts.length > visibleLimit

    return (
      <section
        key={tier.id}
        className={`space-y-3 ${idx > 0 ? 'pt-4 border-t border-slate-200/60' : 'pt-1'}`}
      >
        {/* Encabezado del Nivel de Descuento con momento de compra */}
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
            {MOMENT_BADGES[tier.id] && (
              <span className="inline-flex items-center gap-1 text-[10.5px] font-bold px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 mt-1">
                <span>{MOMENT_BADGES[tier.id].icon}</span>
                <span>{MOMENT_BADGES[tier.id].moment}</span>
              </span>
            )}
          </div>
          <span
            className={`shrink-0 px-2.5 py-0.5 rounded-full text-[11px] font-black text-white shadow-2xs ${
              isMp ? 'bg-indigo-600' : 'bg-rose-600'
            }`}
          >
            {tier.badge}
          </span>
        </div>

        {/* Modo Grilla o Modo Carrusel */}
        {viewMode === 'grid' ? (
          <div className="space-y-3">
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2.5 py-1">
              {tier.meliSponsored?.product && tier.meliSponsored?.offer && (
                <div className="w-full">
                  <SponsoredGondolaCard
                    product={tier.meliSponsored.product}
                    offer={tier.meliSponsored.offer}
                  />
                </div>
              )}
              {visibleProducts.map(product => (
                <div key={`tier-${tier.id}-${product.ean || product.id}`} className="w-full">
                  <GondolaCard className="w-full" group={product} />
                </div>
              ))}
            </div>
            {hasMore ? (
              <div className="pt-1 flex justify-center">
                <button
                  type="button"
                  onClick={() => handleLoadMore(tier.id, validProducts.length)}
                  className="px-4 py-2 rounded-xl text-[12px] font-bold bg-slate-100 hover:bg-slate-200 text-slate-700 transition-all flex items-center gap-1.5 shadow-2xs cursor-pointer active:scale-95"
                >
                  <Plus size={14} className="stroke-[2.5]" />
                  <span>Cargar más ofertas (+{validProducts.length - visibleLimit} más)</span>
                </button>
              </div>
            ) : onGoSearch ? (
              <div className="pt-1 flex justify-center">
                <button
                  type="button"
                  onClick={onGoSearch}
                  className="px-4 py-2 rounded-xl text-[12px] font-bold bg-slate-50 hover:bg-slate-100 border border-slate-200 text-slate-700 transition-all flex items-center gap-1.5 cursor-pointer"
                >
                  <Search size={14} />
                  <span>Ver más en el catálogo</span>
                </button>
              </div>
            ) : null}
          </div>
        ) : (
          /* Carrusel horizontal: El patrocinado de Mercado Libre es el PRIMERO DE LA IZQUIERDA (si existe) */
          <div className="flex gap-2.5 overflow-x-auto no-scrollbar py-1 px-0.5 -mx-0.5 snap-x">
            {tier.meliSponsored?.product && tier.meliSponsored?.offer && (
              <div className="snap-start shrink-0">
                <SponsoredGondolaCard
                  product={tier.meliSponsored.product}
                  offer={tier.meliSponsored.offer}
                />
              </div>
            )}
            {visibleProducts.map(product => (
              <div key={`tier-${tier.id}-${product.ean || product.id}`} className="snap-start shrink-0">
                <GondolaCard group={product} />
              </div>
            ))}

            {/* Tarjeta interactiva de Cargar Más al final del carrusel */}
            {hasMore ? (
              <div className="snap-start shrink-0 flex items-stretch">
                <button
                  type="button"
                  onClick={() => handleLoadMore(tier.id, validProducts.length)}
                  aria-label={`Cargar más ofertas en ${tier.title}`}
                  className={`w-[140px] rounded-2xl border-2 border-dashed p-4 flex flex-col items-center justify-center text-center transition-all group active:scale-95 shadow-2xs cursor-pointer ${
                    isMp
                      ? 'border-indigo-300 hover:border-indigo-500 bg-indigo-50/60 hover:bg-indigo-100/70'
                      : 'border-rose-300 hover:border-rose-500 bg-rose-50/60 hover:bg-rose-100/70'
                  }`}
                >
                  <div
                    className={`w-11 h-11 rounded-2xl flex items-center justify-center mb-2.5 transition-all shadow-xs group-hover:scale-105 ${
                      isMp
                        ? 'bg-indigo-100 group-hover:bg-indigo-600 text-indigo-600 group-hover:text-white'
                        : 'bg-rose-100 group-hover:bg-rose-600 text-rose-600 group-hover:text-white'
                    }`}
                  >
                    <Plus size={22} className="stroke-[2.5]" />
                  </div>
                  <span
                    className={`text-[13px] font-black leading-tight ${
                      isMp ? 'text-indigo-950' : 'text-rose-950'
                    }`}
                  >
                    Cargar más ofertas
                  </span>
                  <span
                    className={`text-[10px] font-bold mt-1.5 px-2 py-0.5 rounded-full border ${
                      isMp
                        ? 'text-indigo-700 bg-white/90 border-indigo-200'
                        : 'text-rose-600 bg-white/90 border-rose-200'
                    }`}
                  >
                    +{validProducts.length - visibleLimit} más
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
        )}
      </section>
    )
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

          {/* Segmented Control de Verticales (Todas | Supermercados | Marketplaces) */}
          <div className="flex items-center gap-1 p-1 bg-slate-200/70 rounded-xl mt-2.5">
            <button
              type="button"
              onClick={() => {
                setSelectedVertical('all')
                setSelectedFilter('all')
              }}
              className={`flex-1 py-1.5 px-2 rounded-lg text-[12px] font-bold transition-all text-center ${
                selectedVertical === 'all'
                  ? 'bg-white text-slate-900 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              🌟 Todas las Ofertas
            </button>
            <button
              type="button"
              onClick={() => {
                setSelectedVertical('supermarket')
                setSelectedFilter('all')
              }}
              className={`flex-1 py-1.5 px-2 rounded-lg text-[12px] font-bold transition-all text-center ${
                selectedVertical === 'supermarket'
                  ? 'bg-white text-rose-700 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              🛒 Supermercados
            </button>
            <button
              type="button"
              onClick={() => {
                setSelectedVertical('marketplace')
                setSelectedFilter('all')
              }}
              className={`flex-1 py-1.5 px-2 rounded-lg text-[12px] font-bold transition-all text-center ${
                selectedVertical === 'marketplace'
                  ? 'bg-white text-indigo-700 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              ⚡ Marketplaces & Tech
            </button>
          </div>

          {/* Filtros rápidos por rangos de descuentos y Selector de Vista (Carruseles / Grilla) */}
          <div className="flex items-center justify-between gap-2 pt-2 pb-0.5">
            <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar flex-1 min-w-0">
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
              {displayedTiers.map(tier => {
                const isMp = tier.id.startsWith('tier-mp-') || tier.vertical === 'electro' || tier.vertical === 'marketplace'
                const isSelected = selectedFilter === tier.id
                return (
                  <button
                    key={tier.id}
                    type="button"
                    onClick={() => setSelectedFilter(tier.id)}
                    className={`shrink-0 h-8 px-3 rounded-full text-[12px] font-bold transition-all border flex items-center gap-1 ${
                      isSelected
                        ? isMp
                          ? 'bg-indigo-600 text-white border-indigo-600 shadow-xs'
                          : 'bg-rose-600 text-white border-rose-600 shadow-xs'
                        : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
                    }`}
                  >
                    <span>{tier.percentLabel}</span>
                  </button>
                )
              })}
            </div>

            {/* Alternar Carrusel / Grilla */}
            <div className="flex items-center gap-0.5 p-0.5 bg-slate-200/80 rounded-xl shrink-0">
              <button
                type="button"
                onClick={() => setViewMode('carousel')}
                aria-label="Ver como carruseles"
                title="Vista carruseles horizontales"
                className={`p-1.5 rounded-lg transition-all ${
                  viewMode === 'carousel'
                    ? 'bg-white text-slate-900 shadow-2xs'
                    : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                <Rows3 size={15} />
              </button>
              <button
                type="button"
                onClick={() => setViewMode('grid')}
                aria-label="Ver como grilla"
                title="Vista grilla fluida de 2 columnas"
                className={`p-1.5 rounded-lg transition-all ${
                  viewMode === 'grid'
                    ? 'bg-white text-slate-900 shadow-2xs'
                    : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                <LayoutGrid size={15} />
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="px-4 pt-3 space-y-6">
        {/* HERO: Las Gangas del Día — Supermercados y Marketplaces/Tech (Directo con afiliados) */}
        {selectedFilter === 'all' && (
          <div className="space-y-3">
            {/* Ganga de Supermercado */}
            {(selectedVertical === 'all' || selectedVertical === 'supermarket') && topSuperMeliDeal && (
              <div
                onClick={() => {
                  const url = decorateOutboundUrl(topSuperMeliDeal.offer.link, 'MercadoLibre', 'item')
                  trackOutboundAffiliateClick('MercadoLibre', 'item', url, topSuperMeliDeal.offer.precio)
                  window.open(url, '_blank', 'noopener,noreferrer')
                }}
                className="rounded-3xl p-4 sm:p-5 bg-gradient-to-br from-rose-950 via-rose-900 to-amber-950 text-white shadow-lg cursor-pointer active:scale-[0.99] transition-all relative overflow-hidden group border border-rose-500/30"
              >
                <div className="absolute -right-10 -bottom-10 w-44 h-44 rounded-full bg-rose-500/20 blur-3xl pointer-events-none" />
                <div className="flex items-center justify-between gap-2 mb-2.5">
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-black uppercase tracking-wider bg-rose-600 text-white shadow-xs">
                    <Flame size={13} className="fill-white" /> La Ganga del Día — Supermercado
                  </span>
                  {topSuperMeliDeal.offer.discount > 0 && (
                    <span className="px-2.5 py-0.5 rounded-full text-[12px] font-black bg-amber-400 text-slate-950 shadow-xs">
                      -{Math.round(topSuperMeliDeal.offer.discount)}% OFF
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-4">
                  <div className="w-20 h-20 sm:w-24 sm:h-24 bg-white rounded-2xl p-1.5 shrink-0 flex items-center justify-center border border-white/20 shadow-xs">
                    <img
                      src={topSuperMeliDeal.product.imagen}
                      alt={`Destacado: ${topSuperMeliDeal.product.nombre}`}
                      className="max-h-full max-w-full object-contain"
                      loading="lazy"
                      referrerPolicy="no-referrer"
                    />
                  </div>
                  <div className="flex-1 min-w-0">
                    <span className="text-[11px] font-extrabold uppercase tracking-wider text-rose-200">
                      {topSuperMeliDeal.product.marca}
                    </span>
                    <h4 className="text-[14px] sm:text-[15px] font-black text-white leading-tight line-clamp-2 mt-0.5">
                      {`⚡ Oportunidad: ${topSuperMeliDeal.product.nombre}`}
                    </h4>
                    <div className="mt-1 flex items-center gap-2 flex-wrap">
                      <span className="text-[18px] sm:text-[20px] font-black text-amber-300">
                        {formatPrice(topSuperMeliDeal.offer.precio)}
                      </span>
                      {topSuperMeliDeal.offer.precio_lista > topSuperMeliDeal.offer.precio && (
                        <span className="text-[12px] text-white/50 line-through">
                          {formatPrice(topSuperMeliDeal.offer.precio_lista)}
                        </span>
                      )}
                    </div>
                    <div className="mt-2 flex items-center justify-between gap-2 flex-wrap">
                      <span className="text-[11px] text-amber-200 font-bold flex items-center gap-1">
                        <span>⚡ Envío FULL directo a tu domicilio</span>
                      </span>
                      <span className="inline-flex items-center gap-1 text-[11px] font-extrabold bg-white text-rose-700 px-2.5 py-1 rounded-full shadow-xs group-hover:bg-amber-300 group-hover:text-slate-950 transition-colors">
                        <span>Aprovechar ganga</span>
                        <ExternalLink size={11} />
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Ganga de Marketplaces & Electro */}
            {(selectedVertical === 'all' || selectedVertical === 'marketplace') && topTechMeliDeal && (
              <div
                onClick={() => {
                  const url = decorateOutboundUrl(topTechMeliDeal.offer.link, 'MercadoLibre', 'item')
                  trackOutboundAffiliateClick('MercadoLibre', 'item', url, topTechMeliDeal.offer.precio)
                  window.open(url, '_blank', 'noopener,noreferrer')
                }}
                className="rounded-3xl p-4 sm:p-5 bg-gradient-to-br from-indigo-950 via-slate-900 to-violet-950 text-white shadow-lg cursor-pointer active:scale-[0.99] transition-all relative overflow-hidden group border border-indigo-500/30"
              >
                <div className="absolute -right-10 -bottom-10 w-44 h-44 rounded-full bg-indigo-500/20 blur-3xl pointer-events-none" />
                <div className="flex items-center justify-between gap-2 mb-2.5">
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-black uppercase tracking-wider bg-indigo-600 text-white shadow-xs">
                    <Zap size={13} className="fill-white" /> La Ganga del Día — Electro & Marketplaces
                  </span>
                  {topTechMeliDeal.offer.discount > 0 && (
                    <span className="px-2.5 py-0.5 rounded-full text-[12px] font-black bg-amber-400 text-slate-950 shadow-xs">
                      -{Math.round(topTechMeliDeal.offer.discount)}% OFF
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-4">
                  <div className="w-20 h-20 sm:w-24 sm:h-24 bg-white rounded-2xl p-1.5 shrink-0 flex items-center justify-center border border-white/20 shadow-xs">
                    <img
                      src={topTechMeliDeal.product.imagen}
                      alt={`Destacado: ${topTechMeliDeal.product.nombre}`}
                      className="max-h-full max-w-full object-contain"
                      loading="lazy"
                      referrerPolicy="no-referrer"
                    />
                  </div>
                  <div className="flex-1 min-w-0">
                    <span className="text-[11px] font-extrabold uppercase tracking-wider text-indigo-200">
                      {topTechMeliDeal.product.marca}
                    </span>
                    <h4 className="text-[14px] sm:text-[15px] font-black text-white leading-tight line-clamp-2 mt-0.5">
                      {`⚡ Oportunidad: ${topTechMeliDeal.product.nombre}`}
                    </h4>
                    <div className="mt-1 flex items-center gap-2 flex-wrap">
                      <span className="text-[18px] sm:text-[20px] font-black text-amber-300">
                        {formatPrice(topTechMeliDeal.offer.precio)}
                      </span>
                      {topTechMeliDeal.offer.precio_lista > topTechMeliDeal.offer.precio && (
                        <span className="text-[12px] text-white/50 line-through">
                          {formatPrice(topTechMeliDeal.offer.precio_lista)}
                        </span>
                      )}
                    </div>
                    <div className="mt-2 flex items-center justify-between gap-2 flex-wrap">
                      <span className="text-[11px] text-indigo-200 font-bold flex items-center gap-1">
                        <span>⚡ Envío FULL directo a tu domicilio</span>
                      </span>
                      <span className="inline-flex items-center gap-1 text-[11px] font-extrabold bg-white text-indigo-700 px-2.5 py-1 rounded-full shadow-xs group-hover:bg-amber-300 group-hover:text-slate-950 transition-colors">
                        <span>Aprovechar ganga</span>
                        <ExternalLink size={11} />
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* FEED PRINCIPAL DE TIERS */}
        {selectedVertical === 'all' && selectedFilter === 'all' ? (
          <>
            {/* 1. SECCIONES DE SUPERMERCADOS */}
            {tiers.map((tier, idx) => renderTier(tier, idx))}

            {/* 2. BANNER DEDICADO Y SECCIONES DE MARKETPLACES */}
            {marketplaceTiers.length > 0 && (
              <div className="pt-6 pb-2 border-t-2 border-indigo-100 mt-6">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-700 text-white flex items-center justify-center shadow-xs">
                      <Zap size={18} className="fill-white" />
                    </div>
                    <div>
                      <h2 className="text-[18px] font-black tracking-tight text-slate-900 leading-none">
                        Marketplaces, Electro & Hogar
                      </h2>
                      <p className="text-[11px] text-slate-500 font-medium mt-0.5">
                        Tecnología, electrodomésticos y herramientas comparados con Mercado Libre y tiendas oficiales
                      </p>
                    </div>
                  </div>
                  <span className="text-[10px] font-extrabold px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-800 border border-indigo-200">
                    💳 Financiación Oficial
                  </span>
                </div>
              </div>
            )}
            {marketplaceTiers.map((tier, idx) => renderTier(tier, idx))}
          </>
        ) : (
          displayedTiers
            .filter(tier => selectedFilter === 'all' || selectedFilter === tier.id)
            .map((tier, idx) => renderTier(tier, idx))
        )}

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
                  Comparamos precios y promociones entre todos los supermercados y Mercado Libre al instante.
                </p>
              </div>
              <span className="shrink-0 ml-3 px-3 py-1.5 rounded-xl bg-blue-600 text-white font-bold text-[12px] group-hover:bg-blue-700 shadow-xs">
                Buscar
              </span>
            </button>
          </div>
        )}
      </main>

      {/* Modal Hoja de Ofertas al tocar la Ganga del Día o Guerra de Precios */}
      {heroSheetGroup && (
        <OffersSheet
          open={Boolean(heroSheetGroup)}
          onClose={() => setHeroSheetGroup(null)}
          group={heroSheetGroup}
          rows={heroSheetGroup.offers
            .map(o => ({
              o,
              eff: o.precio,
              unit: o.unit_price ?? null,
              club: null,
              promo: o.promo_label ?? null,
              minQty: o.promo_min_qty || 1,
              noDelivery: false,
            }))
            .sort((a, b) => a.eff - b.eff)}
        />
      )}
    </div>
  )
}

export default OffersScreen
