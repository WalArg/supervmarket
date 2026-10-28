import React, { useMemo, useState } from 'react'
import { Flame, MapPin, ChevronDown, Sparkles, Zap, ExternalLink, ShoppingCart, Percent, ArrowUpDown } from 'lucide-react'
import { GONDOLAS, type Gondola } from '../data/gondolasData'
import { useLocation } from '../location/LocationContext'
import { useCart } from '../cart/CartContext'
import { formatPrice } from '../lib/pricing'
import { storeLabel, storeColor } from '../lib/stores'
import { decorateOutboundUrl, trackOutboundAffiliateClick } from '../lib/affiliate'
import GondolaSection from './GondolaSection'
import GondolaCard from './GondolaCard'
import SponsoredProductBox from './SponsoredProductBox'
import type { ProductGroup, Offer } from '../types'

interface OffersScreenProps {
  onGoSearch?: () => void
}

export const OffersScreen: React.FC<OffersScreenProps> = ({ onGoSearch }) => {
  const { cp, locationLabel, openModal } = useLocation()
  const { add } = useCart()
  const [selectedCategory, setSelectedCategory] = useState<string>('all')

  // Encuentra la mejor oferta patrocinada de Mercado Libre (la de mayor descuento)
  const meliSponsored = useMemo(() => {
    let candidate: { product: ProductGroup; offer: Offer } | null = null
    let maxDiscount = -1

    for (const g of GONDOLAS) {
      for (const prod of g.products) {
        const mlOffer = prod.offers.find(
          o => (o.supermercado === 'MercadoLibre' || o.supermercado === 'meli') && (o.discount || 0) > maxDiscount,
        )
        if (mlOffer && (mlOffer.discount || 0) > maxDiscount) {
          maxDiscount = mlOffer.discount || 0
          candidate = { product: prod, offer: mlOffer }
        }
      }
    }
    return candidate
  }, [])

  // Góndolas con productos ordenados de mayor a menor descuento
  const sortedGondolas = useMemo(() => {
    return GONDOLAS.map(g => {
      const sortedProducts = [...g.products].sort((a, b) => {
        const maxA = Math.max(...a.offers.map(o => o.discount || 0))
        const maxB = Math.max(...b.offers.map(o => o.discount || 0))
        return maxB - maxA
      })
      return {
        ...g,
        products: sortedProducts,
      }
    })
  }, [])

  // Selección de los mayores descuentos globales (Top bombazos del día)
  const topDiscountProducts = useMemo(() => {
    const allProducts: { product: ProductGroup; maxDiscount: number }[] = []
    const seenEans = new Set<string>()

    for (const g of GONDOLAS) {
      for (const prod of g.products) {
        if (!seenEans.has(prod.ean)) {
          seenEans.add(prod.ean)
          const maxDiscount = Math.max(...prod.offers.map(o => o.discount || 0))
          allProducts.push({ product: prod, maxDiscount })
        }
      }
    }

    return allProducts
      .sort((a, b) => b.maxDiscount - a.maxDiscount)
      .slice(0, 6)
      .map(item => item.product)
  }, [])

  const filteredGondolas = useMemo(() => {
    if (selectedCategory === 'all') return sortedGondolas
    return sortedGondolas.filter(g => g.id === selectedCategory)
  }, [selectedCategory, sortedGondolas])

  return (
    <div className="pb-28">
      {/* Header Sticky */}
      <header className="sticky top-0 z-30 bg-slate-50/95 backdrop-blur-md pt-safe border-b border-slate-100">
        <div className="px-4 pt-3 pb-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-xl bg-rose-500 text-white flex items-center justify-center shadow-xs">
                <Flame size={18} className="fill-white" />
              </div>
              <div>
                <h1 className="text-[19px] font-extrabold tracking-tight text-slate-900 leading-none">
                  Ofertas y Góndolas
                </h1>
                <p className="text-[11px] text-slate-500 font-medium mt-0.5">
                  Mayores descuentos del día comparados en vivo
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={openModal}
              className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-blue-50/90 hover:bg-blue-100/80 border border-blue-200/80 text-blue-700 text-[11px] font-bold active:scale-95 transition-all max-w-[170px] shadow-2xs"
            >
              <MapPin size={12} className="text-blue-600 shrink-0" />
              <span className="truncate">{locationLabel || (cp ? `CP ${cp}` : 'Elegir zona')}</span>
              <ChevronDown size={11} className="text-blue-500 shrink-0" />
            </button>
          </div>

          {/* Filtros rápidos de góndolas */}
          <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar pt-3 pb-0.5">
            <button
              type="button"
              onClick={() => setSelectedCategory('all')}
              className={`shrink-0 h-8 px-3 rounded-full text-[12px] font-bold transition-all border ${
                selectedCategory === 'all'
                  ? 'bg-slate-900 text-white border-slate-900 shadow-xs'
                  : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
              }`}
            >
              Todas las góndolas
            </button>
            {sortedGondolas.map(g => (
              <button
                key={g.id}
                type="button"
                onClick={() => setSelectedCategory(g.id)}
                className={`shrink-0 h-8 px-3 rounded-full text-[12px] font-bold transition-all border ${
                  selectedCategory === g.id
                    ? 'bg-rose-600 text-white border-rose-600 shadow-xs'
                    : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
                }`}
              >
                {g.title.split(' ')[0]} {g.title.split(' ')[1] || ''}
              </button>
            ))}
          </div>
        </div>
      </header>

      <main className="px-4 pt-3 space-y-6">
        {/* OPCIÓN PATROCINADA SIEMPRE PRESENTE: MERCADO LIBRE */}
        {meliSponsored && (
          <section className="space-y-1.5">
            <SponsoredProductBox
              product={meliSponsored.product}
              offer={meliSponsored.offer}
            />
          </section>
        )}

        {/* TOP BOMBAZOS DEL DÍA (Mayores descuentos globales) */}
        {selectedCategory === 'all' && (
          <section className="space-y-2.5 pt-1">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-pulse" />
                <h2 className="text-[15px] font-extrabold text-slate-900 tracking-tight">
                  🔥 Mayores Descuentos del Día
                </h2>
              </div>
              <span className="text-[11px] font-bold text-rose-600 bg-rose-50 px-2 py-0.5 rounded-full">
                Hasta -30% OFF
              </span>
            </div>

            <div className="flex gap-2.5 overflow-x-auto no-scrollbar py-1 px-0.5 -mx-0.5 snap-x">
              {topDiscountProducts.map(product => (
                <div key={`top-${product.ean}`} className="snap-start shrink-0">
                  <GondolaCard group={product} />
                </div>
              ))}
            </div>
          </section>
        )}

        {/* GÓNDOLAS DE PRODUCTOS SEPARADAS */}
        <div className="space-y-6">
          {filteredGondolas.map(gondola => (
            <GondolaSection
              key={gondola.id}
              gondola={gondola}
            />
          ))}
        </div>

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
                  ¿Buscás un producto en específico?
                </h3>
                <p className="text-[12px] text-blue-700 font-medium mt-0.5">
                  Usá el buscador en vivo para comparar entre todos los supermercados.
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
