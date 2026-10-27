import React from 'react'
import { ShoppingBasket, Plus, RefreshCw, X } from 'lucide-react'
import type { SharedItem } from '../types'

interface Props {
  isOpen: boolean
  sharedItems: SharedItem[]
  currentCartCount: number
  onMerge: () => void
  onReplace: () => void
  onDismiss: () => void
}

export const ImportSharedListModal: React.FC<Props> = ({
  isOpen,
  sharedItems,
  currentCartCount,
  onMerge,
  onReplace,
  onDismiss,
}) => {
  if (!isOpen || !sharedItems.length) return null

  const sharedUnits = sharedItems.reduce((acc, i) => acc + (i.qty || 1), 0)

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="shared-list-title"
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-[fade-in_0.2s_ease-out]"
    >
      <div className="w-full max-w-md bg-white rounded-3xl p-6 shadow-2xl border border-slate-100 flex flex-col gap-4">
        {/* Encabezado */}
        <div className="flex items-start justify-between">
          <div className="w-12 h-12 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
            <ShoppingBasket size={24} />
          </div>
          <button
            type="button"
            onClick={onDismiss}
            className="w-11 h-11 rounded-xl text-slate-400 hover:text-slate-600 flex items-center justify-center active:scale-95 transition-all"
            aria-label="Cerrar modal"
          >
            <X size={20} />
          </button>
        </div>

        <div>
          <h2 id="shared-list-title" className="text-[19px] font-extrabold text-slate-900">
            ¡Lista compartida recibida!
          </h2>
          <p className="mt-1 text-[14px] text-slate-600 leading-relaxed">
            Te compartieron una lista con{' '}
            <strong className="text-slate-900">
              {sharedItems.length} producto{sharedItems.length === 1 ? '' : 's'}
            </strong>{' '}
            ({sharedUnits} unidad{sharedUnits === 1 ? '' : 'es'}).
          </p>
          {currentCartCount > 0 && (
            <div className="mt-2.5 px-3.5 py-2.5 rounded-xl bg-amber-50 border border-amber-200/60 text-[12px] text-amber-800 font-medium">
              Actualmente tenés <strong>{currentCartCount} producto{currentCartCount === 1 ? '' : 's'}</strong> en tu changuito.
            </div>
          )}
        </div>

        {/* Acciones Ergonómicas Mobile (Touch Targets >= 48px) */}
        <div className="flex flex-col gap-2.5 pt-2">
          {/* Opción 1: Fusionar (Default recomendado) */}
          <button
            type="button"
            onClick={onMerge}
            className="min-h-[48px] h-12 w-full px-4 rounded-2xl bg-blue-600 text-white font-bold flex items-center justify-center gap-2 shadow-md shadow-blue-500/20 active:scale-[0.98] transition-all"
          >
            <Plus size={18} />
            <span>Sumar a mi changuito actual</span>
          </button>

          {/* Opción 2: Reemplazar */}
          {currentCartCount > 0 && (
            <button
              type="button"
              onClick={onReplace}
              className="min-h-[48px] h-12 w-full px-4 rounded-2xl bg-slate-100 hover:bg-slate-200/70 text-slate-700 font-bold flex items-center justify-center gap-2 active:scale-[0.98] transition-all text-[13px]"
            >
              <RefreshCw size={16} />
              <span>Reemplazar mi changuito</span>
            </button>
          )}

          {/* Opción 3: Descartar */}
          <button
            type="button"
            onClick={onDismiss}
            className="min-h-[44px] h-11 w-full text-[13px] text-slate-400 hover:text-slate-600 font-semibold active:scale-[0.98] transition-all flex items-center justify-center"
          >
            Ignorar y mantener mi lista actual
          </button>
        </div>
      </div>
    </div>
  )
}

export default ImportSharedListModal
