import React, { useState, useMemo, useEffect } from 'react'
import { Plus, Bookmark, Flame, Check, Package } from 'lucide-react'
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
  const [imgIdx, setImgIdx] = useState(0)
  const [imgFailed, setImgFailed] = useState(false)

  const candidateImages = useMemo(() => {
    const raw = [
      group.imagen,
      ...(group.gallery_images || []),
      ...(group.offers || []).map(o => o.imagen),
    ].filter((u): u is string => Boolean(u && u.startsWith('http')))
    return Array.from(new Set(raw))
  }, [group.imagen, group.gallery_images, group.offers])

  useEffect(() => {
    setImgIdx(0)
    setImgFailed(false)
  }, [group.ean, group.imagen])

  const handleImgError = () => {
    if (imgIdx + 1 < candidateImages.length) {
      setImgIdx(prev => prev + 1)
    } else {
      setImgFailed(true)
    }
  }

  const brandInitials = (group.marca || group.nombre || 'SV')
    .trim()
    .slice(0, 2)
    .toUpperCase()

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

  const promoUnitText =
    best.o.promo_label && best.o.promo_label.includes('(')
      ? best.o.promo_label.split('(')[1].replace(')', '').trim()
      : best.o.precio_promo_unit && best.o.precio_promo_unit < best.eff
      ? `${formatPrice(best.o.precio_promo_unit)} c/u${best.minQty > 1 ? ` x${best.minQty}` : ''}`
      : null

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
        {/* Badges superiores: descuento / promo y guardado */}
        <div className="flex items-center justify-between gap-1 mb-1.5">
          {best.o.promo_label && (best.o.promo_label.includes('2do') || best.o.promo_label.includes('2x1') || best.o.promo_label.includes('3x2')) ? (
            <span className="inline-flex items-center gap-0.5 text-[10px] font-black text-rose-700 bg-rose-50 border border-rose-200/80 px-1.5 py-0.5 rounded-md truncate max-w-[110px]" title={best.o.promo_label}>
              <Flame size={10} className="fill-rose-500 text-rose-500 shrink-0" />
              {best.o.promo_label.split('(')[0].trim()}
            </span>
          ) : best.o.discount && best.o.discount > 0 ? (
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

        {/* Imagen del producto con fallback inteligente */}
        <div className="w-full h-24 flex items-center justify-center py-1">
          {!imgFailed && candidateImages.length > 0 ? (
            <img
              src={candidateImages[imgIdx]}
              alt={group.nombre}
              loading="lazy"
              className="max-h-full max-w-full object-contain"
              onError={handleImgError}
              referrerPolicy="no-referrer"
            />
          ) : (
            <div
              className="w-20 h-20 rounded-xl bg-slate-50 border border-slate-100 flex flex-col items-center justify-center text-slate-400 select-none"
              aria-label={group.nombre}
            >
              <Package size={22} className="text-slate-300 mb-0.5" />
              <span className="text-[10px] font-extrabold tracking-wider text-slate-400">
                {brandInitials}
              </span>
            </div>
          )}
        </div>

        {/* Información textual */}
        <div className="mt-2 flex-1 min-w-0">
          <div className="flex items-center gap-1 min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 truncate">
              {group.marca}
            </p>
            {group.modelo && (
              <span className="text-[9px] font-mono font-bold bg-slate-100 text-slate-600 px-1 py-0.2 rounded truncate">
                {group.modelo}
              </span>
            )}
          </div>
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
          {best.o.seller_name && best.o.seller_name.toLowerCase() !== storeLabel(best.o.supermercado).toLowerCase() && (
            <span className="text-[9.5px] font-normal text-slate-400 truncate" title={`Vendido por ${best.o.seller_name}`}>
              · {best.o.seller_name}
            </span>
          )}
        </div>

        {/* Cuotas y financiación */}
        {best.o.cuotas && best.o.cuotas > 1 && (
          <div className="mt-1">
            <span
              className={`inline-flex items-center gap-0.5 text-[9.5px] font-extrabold px-1.5 py-0.5 rounded-md truncate max-w-full ${
                best.o.sin_interes
                  ? 'text-emerald-800 bg-emerald-50 border border-emerald-200/80'
                  : 'text-indigo-800 bg-indigo-50 border border-indigo-200/80'
              }`}
              title={best.o.cuotas_info || `${best.o.cuotas} cuotas`}
            >
              💳 {best.o.cuotas} cuotas {best.o.sin_interes ? 'sin interés' : 'fijas'}
            </span>
          </div>
        )}

        {/* Precio y Botón Agregar al Carrito */}
        <div className="mt-2 pt-2 border-t border-slate-100 flex items-center justify-between gap-1">
          <div className="min-w-0">
            <div className="flex items-baseline gap-1 flex-wrap">
              <span className="text-[15px] font-black tracking-tight text-slate-900 leading-tight">
                {formatPrice(best.eff)}
              </span>
              {best.o.precio_lista && best.o.precio_lista > best.eff ? (
                <span className="text-[10px] text-slate-400 line-through">
                  {formatPrice(best.o.precio_lista)}
                </span>
              ) : null}
            </div>
            {best.o.cuotas && best.o.cuotas > 1 && best.o.cuota_monto && best.o.cuota_monto > 0 ? (
              <span className="text-[10px] text-emerald-700 font-bold block leading-none mt-0.5">
                {best.o.cuotas}x {formatPrice(best.o.cuota_monto)}
              </span>
            ) : null}
            {promoUnitText ? (
              <span
                className="mt-0.5 inline-block text-[10px] font-bold text-rose-700 bg-rose-50 border border-rose-200/70 px-1.5 py-0.2 rounded truncate max-w-[95px]"
                title={best.o.promo_label || promoUnitText}
              >
                {promoUnitText}
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
