import React, { useState } from 'react'
import { Flame, MapPin, ChevronDown, Sparkles } from 'lucide-react'
import { GONDOLAS, DISCOUNT_TIERS } from '../data/gondolasData'
import { useLocation } from '../location/LocationContext'
import GondolaSection from './GondolaSection'
import GondolaCard from './GondolaCard'
import SponsoredGondolaCard from './SponsoredGondolaCard'

interface OffersScreenProps {
  onGoSearch?: () => void
}

export const OffersScreen: React.FC<OffersScreenProps> = ({ onGoSearch }) => {
  const { cp, locationLabel, openModal } = useLocation()
  const [selectedFilter, setSelectedFilter] = useState<string>('all')

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

          {/* Filtros rápidos por rangos de descuento y categorías */}
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
            {DISCOUNT_TIERS.map(tier => (
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
                <span>{tier.percentLabel} OFF</span>
              </button>
            ))}
            {GONDOLAS.map(g => (
              <button
                key={g.id}
                type="button"
                onClick={() => setSelectedFilter(g.id)}
                className={`shrink-0 h-8 px-3 rounded-full text-[12px] font-bold transition-all border ${
                  selectedFilter === g.id
                    ? 'bg-blue-600 text-white border-blue-600 shadow-xs'
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
        {/* SECCIONES POR RANGOS DE DESCUENTOS GRANDES (70%-80%, 60%, 50%, 40%) */}
        {/* Cada uno contiene su producto patrocinado de Mercado Libre como PRIMERA TARJETA A LA IZQUIERDA con descuento acorde */}
        {DISCOUNT_TIERS.filter(
          tier => selectedFilter === 'all' || selectedFilter === tier.id,
        ).map((tier, idx) => (
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

            {/* Carrusel horizontal: El patrocinado de Mercado Libre es el PRIMERO DE LA IZQUIERDA con su descuento correspondiente */}
            <div className="flex gap-2.5 overflow-x-auto no-scrollbar py-1 px-0.5 -mx-0.5 snap-x">
              <div className="snap-start shrink-0">
                <SponsoredGondolaCard
                  product={tier.meliSponsored.product}
                  offer={tier.meliSponsored.offer}
                />
              </div>
              {tier.products.map(product => (
                <div key={`tier-${tier.id}-${product.ean}`} className="snap-start shrink-0">
                  <GondolaCard group={product} />
                </div>
              ))}
            </div>
          </section>
        ))}

        {/* GÓNDOLAS POR CATEGORÍA CON SUPER OFERTAS */}
        {(selectedFilter === 'all' || GONDOLAS.some(g => g.id === selectedFilter)) && (
          <div className="space-y-6 pt-2 border-t border-slate-200/60">
            <div className="flex items-center gap-2">
              <Sparkles size={16} className="text-blue-600" />
              <h2 className="text-[15px] font-extrabold text-slate-900 tracking-tight">
                Góndolas de Ofertas por Rubro
              </h2>
            </div>

            {GONDOLAS.filter(
              g => selectedFilter === 'all' || selectedFilter === g.id,
            ).map(gondola => (
              <GondolaSection
                key={gondola.id}
                gondola={gondola}
              />
            ))}
          </div>
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
