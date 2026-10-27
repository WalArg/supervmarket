import React, { useState } from 'react'
import {
  Bookmark,
  Trash2,
  ShoppingCart,
  Search,
  ExternalLink,
  ChevronRight,
  Sparkles,
  Check,
} from 'lucide-react'
import { useSaved, type SavedItem } from '../saved/SavedContext'
import { useCart } from '../cart/CartContext'
import { formatPrice } from '../lib/pricing'
import { storeLabel, storeColor } from '../lib/stores'
import OffersSheet from './OffersSheet'
import { effPrice, unitPriceFor, clubPriceHint, promoText } from '../lib/pricing'
import type { OfferRow } from './ProductCard'

interface SavedScreenProps {
  onGoSearch: () => void
  onGoCart: () => void
}

export const SavedScreen: React.FC<SavedScreenProps> = ({ onGoSearch, onGoCart }) => {
  const { savedItems, savedCount, removeSaved, clearSaved } = useSaved()
  const { add: addToCart } = useCart()
  const [selectedItemForOffers, setSelectedItemForOffers] = useState<SavedItem | null>(null)
  const [addedMap, setAddedMap] = useState<Record<string, boolean>>({})
  const [toastMessage, setToastMessage] = useState<string | null>(null)

  const showToast = (msg: string) => {
    setToastMessage(msg)
    setTimeout(() => setToastMessage(null), 2500)
  }

  const handleAddToCart = (item: SavedItem) => {
    addToCart(item.group, 1)
    setAddedMap(prev => ({ ...prev, [item.id]: true }))
    setTimeout(() => {
      setAddedMap(prev => ({ ...prev, [item.id]: false }))
    }, 2000)
    showToast(`✓ "${item.nombre.slice(0, 24)}..." agregado al carrito`)
  }

  const handleAddAllToCart = () => {
    let addedCount = 0
    for (const item of savedItems) {
      if (item.group) {
        addToCart(item.group, 1)
        addedCount++
      }
    }
    showToast(`🛒 Se agregaron ${addedCount} productos al carrito`)
  }

  // Preparar filas de ofertas si el usuario abre "Ver ofertas" de un producto guardado
  const sheetRows: OfferRow[] = selectedItemForOffers
    ? selectedItemForOffers.group.offers
        .map(o => {
          const eff = effPrice(o, false)
          return {
            o,
            eff,
            unit: unitPriceFor(o, eff),
            club: clubPriceHint(o, false),
            promo: promoText(o, false),
            minQty: o.promo_min_qty || 1,
            noDelivery: false,
          }
        })
        .sort((a, b) => a.eff - b.eff)
    : []

  return (
    <div className="pb-32">
      {/* Header Sticky */}
      <header className="sticky top-0 z-30 bg-slate-50/95 backdrop-blur-md pt-safe border-b border-slate-100">
        <div className="px-4 pt-3 pb-2.5 flex items-center justify-between">
          <div>
            <h1 className="text-[20px] font-extrabold tracking-tight text-slate-900 flex items-center gap-2">
              <Bookmark size={20} className="fill-amber-500 text-amber-500" />
              Guardados
            </h1>
            <p className="text-[12px] text-slate-500 font-medium">
              {savedCount === 0
                ? 'Sin productos guardados'
                : `${savedCount} producto${savedCount === 1 ? '' : 's'} para tener a mano`}
            </p>
          </div>

          {savedCount > 0 && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleAddAllToCart}
                className="min-h-[40px] px-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-[12px] font-bold active:scale-95 transition-all flex items-center gap-1.5 shadow-xs"
                title="Agregar todos los productos guardados al carrito"
              >
                <ShoppingCart size={14} />
                <span>Pasar todo al carrito</span>
              </button>
              <button
                type="button"
                onClick={clearSaved}
                className="min-h-[40px] px-2.5 text-slate-400 hover:text-red-600 text-[12px] font-bold rounded-xl hover:bg-red-50 active:scale-95 transition-all"
                title="Vaciar lista de guardados"
              >
                Vaciar
              </button>
            </div>
          )}
        </div>

        {/* Toast Notificación */}
        {toastMessage && (
          <div className="mx-4 mb-2 p-2 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-[11px] font-bold flex items-center gap-2 animate-[fade-in_0.2s_ease-out]">
            <Check size={14} className="text-emerald-600 shrink-0" />
            <span>{toastMessage}</span>
          </div>
        )}
      </header>

      {/* Contenido */}
      <main className="px-4 pt-4">
        {savedCount === 0 ? (
          <div className="min-h-[65dvh] flex flex-col items-center justify-center text-center max-w-md mx-auto">
            <div className="w-16 h-16 rounded-3xl bg-amber-50 text-amber-500 flex items-center justify-center shadow-xs">
              <Bookmark size={32} className="fill-amber-400 text-amber-500" />
            </div>
            <h2 className="mt-4 text-[19px] font-extrabold text-slate-900">
              No tenés productos guardados
            </h2>
            <p className="mt-1.5 text-[14px] text-slate-500 max-w-xs leading-relaxed">
              Tocá el ícono de marcador (<span className="text-amber-500 font-bold">🔖</span>) en cualquier producto para guardarlo acá y agregarlo al carrito cuando lo necesites.
            </p>

            <button
              type="button"
              onClick={onGoSearch}
              className="mt-6 min-h-[48px] px-6 rounded-2xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-[14px] active:scale-95 transition-all shadow-md shadow-blue-500/20 flex items-center gap-2"
            >
              <Search size={17} /> Explorar productos en el buscador
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {savedItems.map(item => {
              const bestOffer = item.group.offers[0]
              const wasAdded = addedMap[item.id]

              return (
                <div
                  key={item.id}
                  className="bg-white rounded-2xl border border-slate-200/80 p-3.5 shadow-2xs hover:shadow-xs transition-shadow flex items-center gap-3.5"
                >
                  {/* Imagen */}
                  <div className="w-16 h-16 shrink-0 rounded-xl bg-slate-50 border border-slate-100 p-1 flex items-center justify-center overflow-hidden">
                    {item.imagen ? (
                      <img
                        src={item.imagen}
                        alt=""
                        loading="lazy"
                        className="max-w-full max-h-full object-contain"
                        onError={e => ((e.target as HTMLImageElement).style.visibility = 'hidden')}
                      />
                    ) : (
                      <Bookmark size={24} className="text-slate-300" />
                    )}
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    {item.marca && (
                      <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400 truncate">
                        {item.marca}
                      </p>
                    )}
                    <h3 className="text-[13.5px] leading-snug font-bold text-slate-900 line-clamp-2">
                      {item.nombre}
                    </h3>

                    {/* Precio y Supermercado */}
                    <div className="mt-1 flex items-center gap-2 flex-wrap">
                      {item.minPrice !== undefined && (
                        <span className="text-[15px] font-black text-slate-900">
                          {formatPrice(item.minPrice)}
                        </span>
                      )}
                      {item.bestStore && (
                        <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-slate-600 bg-slate-100 px-2 py-0.5 rounded-full">
                          <span
                            className="w-1.5 h-1.5 rounded-full"
                            style={{ background: storeColor(item.bestStore) }}
                          />
                          {storeLabel(item.bestStore)}
                        </span>
                      )}
                      {item.group.offers.length > 1 && (
                        <button
                          type="button"
                          onClick={() => setSelectedItemForOffers(item)}
                          className="text-[11px] font-bold text-blue-600 hover:text-blue-800 underline"
                        >
                          Ver {item.group.offers.length} ofertas
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Acciones */}
                  <div className="flex flex-col items-end gap-1.5 shrink-0">
                    <button
                      type="button"
                      onClick={() => handleAddToCart(item)}
                      className={`min-h-[40px] px-3 rounded-xl text-[12px] font-bold flex items-center gap-1.5 active:scale-95 transition-all shadow-xs ${
                        wasAdded
                          ? 'bg-emerald-600 text-white'
                          : 'bg-blue-600 hover:bg-blue-700 text-white'
                      }`}
                      title="Agregar al carrito"
                    >
                      {wasAdded ? (
                        <>
                          <Check size={14} /> Agregado
                        </>
                      ) : (
                        <>
                          <ShoppingCart size={14} /> Al carrito
                        </>
                      )}
                    </button>

                    <button
                      type="button"
                      onClick={() => removeSaved(item.id)}
                      className="min-h-[36px] px-2 text-[11px] font-medium text-slate-400 hover:text-red-600 flex items-center gap-1 active:scale-95 transition-all"
                      title="Sacar de guardados"
                      aria-label="Sacar de guardados"
                    >
                      <Trash2 size={13} />
                      <span>Quitar</span>
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </main>

      {/* Modal de ofertas si el usuario quiere ver comparativa */}
      {selectedItemForOffers && (
        <OffersSheet
          open={Boolean(selectedItemForOffers)}
          onClose={() => setSelectedItemForOffers(null)}
          group={selectedItemForOffers.group}
          rows={sheetRows}
        />
      )}
    </div>
  )
}

export default SavedScreen
