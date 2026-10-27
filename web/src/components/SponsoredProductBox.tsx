import React from 'react'
import { ExternalLink, Zap, Truck, ShieldCheck } from 'lucide-react'
import type { ProductGroup, Offer } from '../types'
import { formatPrice } from '../lib/pricing'
import { decorateOutboundUrl, trackOutboundAffiliateClick } from '../lib/affiliate'
import { storeLabel, storeColor } from '../lib/stores'

interface SponsoredProductBoxProps {
  product: ProductGroup
  offer: Offer
}

export const SponsoredProductBox: React.FC<SponsoredProductBoxProps> = ({ product, offer }) => {
  const store = offer.supermercado || 'MercadoLibre'
  const decoratedUrl = decorateOutboundUrl(offer.link, store, 'item')

  const handleOutboundClick = () => {
    trackOutboundAffiliateClick(
      product.nombre,
      store,
      decoratedUrl,
      offer.precio,
      'sponsored_top_box',
    )
  }

  return (
    <div className="bg-gradient-to-br from-amber-50/90 via-white to-yellow-50/50 rounded-2xl border-2 border-amber-300 p-3.5 shadow-sm space-y-2.5">
      {/* Encabezado del Recuadro de Patrocinado */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <span className="px-2 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-amber-400 text-amber-950 shadow-2xs">
            PATROCINADO
          </span>
          <span className="text-[12px] font-extrabold text-slate-800">
            Destacado en {storeLabel(store)}
          </span>
        </div>
        <div className="flex items-center gap-1 bg-amber-100/90 border border-amber-200/80 px-2 py-0.5 rounded-full">
          <span
            className="w-2 h-2 rounded-full shrink-0"
            style={{ background: storeColor(store) }}
          />
          <span className="text-[11px] font-extrabold text-amber-950">
            {storeLabel(store)}
          </span>
        </div>
      </div>

      {/* Contenido del Producto */}
      <div className="flex items-center gap-3">
        <div className="w-14 h-14 shrink-0 rounded-xl bg-white border border-amber-100 p-1 flex items-center justify-center">
          <img
            src={product.imagen}
            alt=""
            loading="lazy"
            className="max-w-full max-h-full object-contain"
            onError={e => ((e.target as HTMLImageElement).style.visibility = 'hidden')}
          />
        </div>

        <div className="flex-1 min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400 truncate">
            {product.marca}
          </p>
          <h3 className="text-[13.5px] leading-snug font-bold text-slate-900 line-clamp-2">
            {product.nombre}
          </h3>

          <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px]">
            {offer.seller_name && (
              <span className="text-slate-600 font-medium">
                Vendido por <strong className="text-slate-800">{offer.seller_name}</strong>
              </span>
            )}
            {offer.is_full && (
              <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded font-black text-[10.5px] bg-emerald-600 text-white shadow-2xs tracking-wide">
                <Zap size={10} className="fill-white" /> FULL SÚPER
              </span>
            )}
            {offer.free_shipping && (
              <span className="inline-flex items-center gap-0.5 px-1.5 py-0.2 rounded font-bold text-[10px] bg-blue-100 text-blue-800">
                <Truck size={10} /> Envío gratis
              </span>
            )}
          </div>
        </div>

        {/* Precio y CTA Saliente */}
        <div className="text-right shrink-0">
          <span className="text-[19px] font-black text-slate-900 block leading-tight">
            {formatPrice(offer.precio)}
          </span>
          {offer.unit_price && (
            <span className="text-[10.5px] font-semibold text-slate-400 block -mt-0.5 mb-1">
              {formatPrice(offer.unit_price)}/{offer.unit_measure || 'un'}
            </span>
          )}
          <a
            href={decoratedUrl}
            target="_blank"
            rel="noopener noreferrer"
            onClick={handleOutboundClick}
            className="inline-flex items-center gap-1 h-8 px-3 rounded-xl bg-amber-500 hover:bg-amber-600 active:bg-amber-700 text-white text-[11px] font-extrabold shadow-2xs active:scale-95 transition-all"
          >
            <span>Comprar</span>
            <ExternalLink size={12} />
          </a>
        </div>
      </div>

      {/* Nota de Transparencia y Firewall Ético */}
      <div className="pt-1 border-t border-amber-200/50 flex items-center justify-between text-[10px] text-slate-500">
        <span>Patrocinado · {storeLabel(store)} también participa abajo en la comparación orgánica.</span>
        <span className="inline-flex items-center gap-0.5 text-amber-800 font-bold shrink-0">
          <ShieldCheck size={11} /> Tienda Oficial
        </span>
      </div>
    </div>
  )
}

export default SponsoredProductBox
