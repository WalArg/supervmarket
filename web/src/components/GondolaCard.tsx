import React, { useState, useMemo } from 'react'
import { Plus, Bookmark, Flame, Check } from 'lucide-react'
import type { ProductGroup } from '../types'
import { useCart } from '../cart/CartContext'
import { useSaved, getCanonicalProductId } from '../saved/SavedContext'
import { storeColor, storeLabel } from '../lib/stores'
import { formatPrice } from '../lib/pricing'
import OffersSheet from './OffersSheet'
import type { OfferRow } from './ProductCard'

interface GondolaCardProps {
  group: ProductGroup
}

export const GondolaCard: React.FC<GondolaCardProps> = ({ group }) => {
  const { add, qtyOf } = useCart()
  const { isSaved, toggleSave } = useSaved()
  const [sheetOpen, setSheetOpen] = useState(false)
  const [justAdded, setJustAdded] = useState(false)

  const prodId = getCanonicalProductId(group)
  const saved = isSaved(prodId)
  const ean = group.ean || group.offers?.[0]?.ean || prodId
  const inCartQty = qtyOf(ean)

  // Calcular filas de ofertas ordenadas por mejor precio
  const rows: OfferRow[] = useMemo(() => {
    return group.offers
      .map(o => ({
        o,
        eff: o.precio,
        unit: o.unit_price ?? null,
        club: null,
        promo: o.promo_label ?? null,
        minQty: o.promo_min_qty || 1,
        noDelivery: false,
      }))
      .sort((a, b) => a.eff - b.eff)
  }, [group.offers])

  const best = rows[0]
  if (!best) return null

  const handleAdd = (e: React.MouseEvent) => {
    e.stopPropagation()
    add(group, 1)
    setJustAdded(true)
    navigator.vibrate?.(10)
    setTimeout(() => setJustAdded(false), 1500)
  }

  const handleToggleSave = (e: React.MouseEvent) => {
    e.stopPropagation()
    toggleSave(group)
    navigator.vibrate?.(10)
  }

  return (
    <>
      <article
        onClick={() => setSheetOpen(true)}
        className="w-[168px] shrink-0 bg-white rounded-2xl border border-slate-200/80 p-2.5 flex flex-col justify-between shadow-[0_1px_2px_rgba(15,23,42,0.04)] hover:border-slate-300 hover:shadow-md transition-all cursor-pointer relative group"
      >
        {/* Badges superiores: descuento y guardado */}
        <div className="flex items-center justify-between gap-1 mb-1.5">
          {best.o.discount && best.o.discount > 0 ? (
            <span className="inline-flex items-center gap-0.5 text-[10px] font-black text-rose-700 bg-rose-50 border border-rose-100 px-1.5 py-0.5 rounded-md">
              <Flame size={10} className="fill-rose-500 text-rose-500" />
              -{best.o.discount}%
            </span>
          ) : best.o.promo_label ? (
            <span className="text-[10px] font-extrabold text-orange-700 bg-orange-50 px-1.5 py-0.5 rounded-md truncate max-w-[100px]">
              {best.o.promo_label}
            </span>
          ) : (
            <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded-md">
              OFERTA
            </span>
          )}

          <button
            type="button"
            onClick={handleToggleSave}
            aria-label={saved ? 'Quitar de guardados' : 'Guardar producto'}
            className={`w-7 h-7 rounded-lg flex items-center justify-center transition-all ${
              saved
                ? 'text-amber-500 bg-amber-50'
                : 'text-slate-300 hover:text-amber-500 hover:bg-slate-50'
            }`}
          >
            <Bookmark size={14} className={saved ? 'fill-amber-500' : ''} />
          </button>
        </div>

        {/* Imagen del producto */}
        <div className="w-full h-24 flex items-center justify-center py-1">
          <img
            src={group.imagen}
            alt={group.nombre}
            loading="lazy"
            className="max-h-full max-w-full object-contain"
            onError={e => ((e.target as HTMLImageElement).style.visibility = 'hidden')}
          />
        </div>

        {/* Información textual */}
        <div className="mt-2 flex-1 min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 truncate">
            {group.marca}
          </p>
          <h4 className="text-[12px] font-semibold text-slate-800 line-clamp-2 leading-snug mt-0.5 h-[32px]">
            {group.nombre}
          </h4>
        </div>

        {/* Tienda con mejor precio */}
        <div className="mt-2 flex items-center gap-1 text-[11px] font-semibold text-slate-500">
          <span
            className="w-1.5 h-1.5 rounded-full shrink-0"
            style={{ background: storeColor(best.o.supermercado) }}
          />
          <span className="truncate">en {storeLabel(best.o.supermercado)}</span>
        </div>

        {/* Precio y Botón Agregar al Carrito */}
        <div className="mt-2 pt-2 border-t border-slate-100 flex items-center justify-between gap-1">
          <div className="min-w-0">
            <span className="text-[15px] font-black tracking-tight text-slate-900 block leading-tight">
              {formatPrice(best.eff)}
            </span>
            {best.o.precio_lista && best.o.precio_lista > best.eff ? (
              <span className="text-[10px] text-slate-400 line-through block">
                {formatPrice(best.o.precio_lista)}
              </span>
            ) : null}
          </div>

          <button
            type="button"
            onClick={handleAdd}
            aria-label={`Agregar ${group.nombre} al carrito`}
            className={`min-h-[32px] h-8 px-2.5 rounded-xl font-bold text-[11px] flex items-center gap-1 transition-all active:scale-90 shadow-2xs ${
              justAdded
                ? 'bg-emerald-600 text-white'
                : inCartQty > 0
                ? 'bg-blue-50 text-blue-700 border border-blue-200'
                : 'bg-blue-600 hover:bg-blue-700 text-white'
            }`}
          >
            {justAdded ? (
              <>
                <Check size={13} strokeWidth={3} />
                <span>Listo</span>
              </>
            ) : inCartQty > 0 ? (
              <>
                <Check size={12} strokeWidth={3} />
                <span>({inCartQty})</span>
              </>
            ) : (
              <>
                <Plus size={14} strokeWidth={3} />
                <span>Sumar</span>
              </>
            )}
          </button>
        </div>
      </article>

      <OffersSheet
        open={sheetOpen}
        onClose={() => setSheetOpen(false)}
        group={group}
        rows={rows}
      />
    </>
  )
}

export default GondolaCard
