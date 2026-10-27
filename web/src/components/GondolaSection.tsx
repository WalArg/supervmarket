import React from 'react'
import { Flame, Milk, Package, Sparkles, Coffee, ChevronRight } from 'lucide-react'
import type { Gondola } from '../data/gondolasData'
import GondolaCard from './GondolaCard'

interface GondolaSectionProps {
  gondola: Gondola
  onSelectCategory: (searchTerm: string) => void
}

const ICONS = {
  flame: <Flame size={16} className="text-rose-500 fill-rose-500" />,
  milk: <Milk size={16} className="text-blue-500" />,
  package: <Package size={16} className="text-amber-600" />,
  sparkles: <Sparkles size={16} className="text-purple-500" />,
  coffee: <Coffee size={16} className="text-amber-700" />,
}

export const GondolaSection: React.FC<GondolaSectionProps> = ({
  gondola,
  onSelectCategory,
}) => {
  return (
    <section className="space-y-2 pt-1">
      {/* Encabezado de la góndola */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-7 h-7 rounded-lg bg-slate-100 flex items-center justify-center shrink-0">
            {ICONS[gondola.icon] || <Package size={16} />}
          </div>
          <div className="min-w-0">
            <h3 className="text-[15px] font-extrabold text-slate-900 tracking-tight leading-none truncate">
              {gondola.title}
            </h3>
            <p className="text-[11px] text-slate-500 font-medium truncate mt-0.5">
              {gondola.subtitle}
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => onSelectCategory(gondola.searchTerm)}
          className="text-[12px] font-bold text-blue-600 hover:text-blue-700 active:opacity-75 flex items-center gap-0.5 shrink-0 pl-2"
        >
          <span>Ver todo</span>
          <ChevronRight size={13} strokeWidth={2.5} />
        </button>
      </div>

      {/* Carrusel horizontal de productos */}
      <div className="flex gap-2.5 overflow-x-auto no-scrollbar py-1 px-0.5 -mx-0.5 snap-x">
        {gondola.products.map(product => (
          <div key={product.ean} className="snap-start shrink-0">
            <GondolaCard group={product} />
          </div>
        ))}
      </div>
    </section>
  )
}

export default GondolaSection
