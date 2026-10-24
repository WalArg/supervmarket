import React from 'react'
import { Swiper, SwiperSlide } from 'swiper/react'
import { FreeMode, Mousewheel } from 'swiper/modules'
import { Plus, Minus, Flame } from 'lucide-react'
import type { ProductGroup } from '../types'
import OfferCard from './OfferCard'
import { useCart } from '../cart/CartContext'
import 'swiper/css'
import 'swiper/css/free-mode'

const ProductRow: React.FC<{ group: ProductGroup }> = ({ group }) => {
  const { add, setQty, qtyOf } = useCart()
  const currentQty = qtyOf(group.ean)

  // Ordenar por el mejor precio efectivo abierto a todo público (sin exigir tarjeta/club)
  const publicEff = (o: ProductGroup['offers'][number]) =>
    o.requires_club ? o.precio : (o.promo_unit_price ?? o.precio)

  const sortedOffers = [...group.offers].sort((a, b) => publicEff(a) - publicEff(b))

  const effectivePrices = sortedOffers.map(publicEff)
  const minEffectivePrice = Math.min(...effectivePrices)
  const maxEffectivePrice = Math.max(...effectivePrices)
  const savingsPct =
    sortedOffers.length > 1 && maxEffectivePrice > minEffectivePrice
      ? Math.round(((maxEffectivePrice - minEffectivePrice) / maxEffectivePrice) * 100)
      : 0

  const bestOffer = sortedOffers[0]
  const multiPromoOffer = sortedOffers.find(o => (o.promo_min_qty || 1) > 1)

  return (
    <div className="bg-white rounded-xl border border-slate-200/90 px-3.5 py-2.5 mb-2.5 shadow-2xs hover:border-slate-300 transition-colors flex flex-col md:flex-row md:items-center gap-3">
      {/* Ficha compacta izquierda estilo Ratoneando (~116px de alto) */}
      <div className="md:w-72 lg:w-80 shrink-0 flex items-center gap-3 pr-2 md:border-r md:border-slate-100">
        <div className="w-16 h-16 shrink-0 bg-white rounded-lg border border-slate-100 p-1 flex items-center justify-center">
          <img
            src={group.imagen}
            alt={group.nombre}
            className="w-full h-full object-contain"
            onError={e => {
              ;(e.target as HTMLImageElement).src =
                'https://placehold.co/100x100/f8fafc/64748b?text=Img'
            }}
          />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-0.5 flex-wrap">
            <span className="text-[10px] uppercase tracking-wider font-extrabold text-blue-600 truncate max-w-[120px]">
              {group.marca || 'Genérico'}
            </span>
            <span className="text-[10px] text-slate-400 font-semibold">
              · {sortedOffers.length} {sortedOffers.length === 1 ? 'súper' : 'súper'}
            </span>
            {savingsPct >= 5 && (
              <span className="text-[10px] font-extrabold bg-emerald-100 text-emerald-800 px-1.5 py-0.2 rounded">
                -{savingsPct}% vs máx
              </span>
            )}
          </div>

          <h3
            title={group.nombre}
            className="text-xs sm:text-[13px] font-bold text-slate-800 leading-snug line-clamp-2 mb-2"
          >
            {group.nombre}
          </h3>

          {/* Acciones compactas en 1 sola línea */}
          <div className="flex items-center gap-1.5">
            {currentQty === 0 ? (
              <>
                <button
                  type="button"
                  onClick={() => add(group, (bestOffer?.promo_min_qty || 1) > 1 ? 1 : 1)}
                  className="inline-flex items-center gap-1 py-1 px-2.5 rounded-lg text-[11px] font-bold bg-blue-600 text-white hover:bg-blue-700 transition-colors"
                >
                  <Plus size={13} />
                  Sumar
                </button>
                {multiPromoOffer && multiPromoOffer.promo_min_qty && (
                  <button
                    type="button"
                    onClick={() => add(group, multiPromoOffer.promo_min_qty)}
                    title={`Sumar ${multiPromoOffer.promo_min_qty} unidades para activar ${multiPromoOffer.promo_label}`}
                    className="inline-flex items-center gap-1 py-1 px-2 rounded-lg text-[11px] font-bold bg-orange-50 text-orange-800 border border-orange-200 hover:bg-orange-100 transition-colors truncate"
                  >
                    <Flame size={11} className="text-orange-500 shrink-0" />
                    +{multiPromoOffer.promo_min_qty} ({multiPromoOffer.promo_label})
                  </button>
                )}
              </>
            ) : (
              <div className="inline-flex items-center gap-2 bg-blue-50 border border-blue-200 rounded-lg px-1.5 py-0.5">
                <button
                  type="button"
                  onClick={() => setQty(group.ean, currentQty - 1)}
                  className="p-0.5 rounded bg-white text-blue-700 hover:bg-blue-100 shadow-2xs"
                >
                  <Minus size={12} />
                </button>
                <span className="text-[11px] font-extrabold text-blue-900 px-1">
                  {currentQty} en lista
                </span>
                <button
                  type="button"
                  onClick={() => setQty(group.ean, currentQty + 1)}
                  className="p-0.5 rounded bg-blue-600 text-white hover:bg-blue-700"
                >
                  <Plus size={12} />
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Carrusel horizontal compacto de supermercados (~116px de alto, ordenado por menor precio efectivo) */}
      <div className="flex-1 min-w-0 w-full">
        <Swiper
          modules={[FreeMode, Mousewheel]}
          spaceBetween={8}
          slidesPerView="auto"
          freeMode
          mousewheel={{ forceToAxis: true }}
          className="w-full"
        >
          {sortedOffers.map((offer, idx) => {
            const eff = publicEff(offer)
            return (
              <SwiperSlide
                key={`${offer.supermercado}-${offer.sku_id}-${idx}`}
                className="!w-auto"
              >
                <OfferCard
                  offer={offer}
                  minEffectivePrice={minEffectivePrice}
                  isBestPrice={eff === minEffectivePrice}
                />
              </SwiperSlide>
            )
          })}
        </Swiper>
      </div>
    </div>
  )
}

export default ProductRow
