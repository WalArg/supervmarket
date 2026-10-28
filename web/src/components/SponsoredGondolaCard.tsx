import React from 'react'
import { Flame, Zap, ExternalLink } from 'lucide-react'
import type { ProductGroup, Offer } from '../types'
import { formatPrice } from '../lib/pricing'
import { decorateOutboundUrl, trackOutboundAffiliateClick } from '../lib/affiliate'

interface SponsoredGondolaCardProps {
  product: ProductGroup
  offer: Offer
}

export const SponsoredGondolaCard: React.FC<SponsoredGondolaCardProps> = ({ product, offer }) => {
  const store = offer.supermercado || 'MercadoLibre'
  const decoratedUrl = decorateOutboundUrl(offer.link, store, 'item')

  const handleClick = () => {
    trackOutboundAffiliateClick(
      product.nombre,
      store,
      decoratedUrl,
      offer.precio,
      'sponsored_carousel_card',
    )
    window.open(decoratedUrl, '_blank', 'noopener,noreferrer')
  }

  const handleLinkClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    trackOutboundAffiliateClick(
      product.nombre,
      store,
      decoratedUrl,
      offer.precio,
      'sponsored_carousel_card',
    )
  }

  return (
    <article
      onClick={handleClick}
      className="w-[168px] shrink-0 bg-gradient-to-b from-amber-50/90 via-white to-yellow-50/40 rounded-2xl border-2 border-amber-300 p-2.5 flex flex-col justify-between shadow-[0_1px_3px_rgba(245,158,11,0.15)] hover:border-amber-400 hover:shadow-md transition-all cursor-pointer relative group"
    >
      {/* Badges superiores: descuento correspondiente del nivel y PATROCINADO */}
      <div className="flex items-center justify-between gap-1 mb-1.5">
        {offer.discount && offer.discount > 0 ? (
          <span className="inline-flex items-center gap-0.5 text-[10px] font-black text-rose-700 bg-rose-50 border border-rose-200/80 px-1.5 py-0.5 rounded-md">
            <Flame size={10} className="fill-rose-500 text-rose-500" />
            -{offer.discount}%
          </span>
        ) : (
          <span className="text-[10px] font-black text-amber-900 bg-amber-100 px-1.5 py-0.5 rounded-md">
            SUPER PROMO
          </span>
        )}

        <span className="px-1.5 py-0.5 rounded text-[9px] font-black uppercase tracking-wider bg-amber-400 text-amber-950 shadow-2xs">
          PATROCINADO
        </span>
      </div>

      {/* Imagen del producto patrocinado */}
      <div className="w-full h-24 flex items-center justify-center py-1 bg-white rounded-xl border border-amber-100/80 p-1">
        <img
          src={product.imagen}
          alt={product.nombre}
          loading="lazy"
          className="max-h-full max-w-full object-contain"
          onError={e => ((e.target as HTMLImageElement).style.visibility = 'hidden')}
        />
      </div>

      {/* Tienda Mercado Libre y badge FULL */}
      <div className="mt-2 flex items-center justify-between gap-1 text-[10px] font-extrabold text-amber-950">
        <div className="flex items-center gap-1 min-w-0">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
          <span className="truncate">Destacado en Mercado Libre</span>
        </div>
        {offer.is_full && (
          <span className="shrink-0 inline-flex items-center gap-0.5 text-[8.5px] font-black text-emerald-800 bg-emerald-100/90 px-1 py-0.2 rounded">
            <Zap size={8} className="fill-emerald-700 text-emerald-700" /> FULL
          </span>
        )}
      </div>

      {/* Marca y Nombre del Producto */}
      <div className="mt-1 flex-1 min-w-0">
        <p className="text-[10px] font-bold uppercase tracking-wider text-amber-700/80 truncate">
          {product.marca}
        </p>
        <h4 className="text-[12px] font-bold text-slate-900 line-clamp-2 leading-snug mt-0.5 h-[32px]">
          {product.nombre}
        </h4>
      </div>

      {/* Precio y Botón Ver en Mercado Libre */}
      <div className="mt-2 pt-2 border-t border-amber-100 flex items-center justify-between gap-1">
        <div className="min-w-0">
          <span className="text-[15px] font-black tracking-tight text-slate-900 block leading-tight">
            {formatPrice(offer.precio)}
          </span>
          {offer.precio_lista && offer.precio_lista > offer.precio ? (
            <span className="text-[10px] text-slate-400 line-through block">
              {formatPrice(offer.precio_lista)}
            </span>
          ) : null}
        </div>

        <a
          href={decoratedUrl}
          target="_blank"
          rel="noopener noreferrer"
          onClick={handleLinkClick}
          aria-label={`Ver oferta de ${product.nombre} en Mercado Libre`}
          className="w-8 h-8 rounded-xl bg-amber-400 hover:bg-amber-500 text-amber-950 flex items-center justify-center font-bold shadow-xs active:scale-95 transition-all shrink-0"
        >
          <ExternalLink size={14} />
        </a>
      </div>
    </article>
  )
}

export default SponsoredGondolaCard
