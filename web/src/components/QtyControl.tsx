import React from 'react'
import { Plus, Minus } from 'lucide-react'
import type { ProductGroup } from '../types'
import { useCart } from '../cart/CartContext'

/** Botón "Agregar" que se transforma en stepper (− 2 +) al sumar el producto a la lista. */
const QtyControl: React.FC<{ group: ProductGroup; bulkQty?: number; compact?: boolean }> = ({
  group,
  bulkQty = 1,
  compact,
}) => {
  const { add, setQty, qtyOf } = useCart()
  const qty = qtyOf(group.ean)
  const h = compact ? 'h-9' : 'h-10'

  const haptic = () => navigator.vibrate?.(8)
  const plus = (n: number) => {
    haptic()
    if (qty === 0) add(group, n)
    else setQty(group.ean, qty + n)
  }

  if (qty === 0) {
    return (
      <div className="flex items-center gap-1.5 shrink-0">
        {bulkQty > 1 && (
          <button
            type="button"
            onClick={() => plus(bulkQty)}
            className={`${h} px-2.5 rounded-xl bg-orange-50 border border-orange-200 text-orange-800 text-[13px] font-extrabold active:bg-orange-100`}
            title={`Agregar ${bulkQty} para activar la promo`}
          >
            +{bulkQty}
          </button>
        )}
        <button
          type="button"
          onClick={() => plus(1)}
          className={`${h} px-3.5 rounded-xl bg-blue-600 text-white text-[13px] font-extrabold flex items-center gap-1 active:bg-blue-700`}
        >
          <Plus size={16} strokeWidth={3} /> Agregar
        </button>
      </div>
    )
  }

  return (
    <div className={`${h} shrink-0 flex items-center rounded-xl bg-blue-600 text-white`}>
      <button
        type="button"
        aria-label="Restar"
        onClick={() => {
          haptic()
          setQty(group.ean, qty - 1)
        }}
        className={`${compact ? 'w-9' : 'w-10'} h-full flex items-center justify-center active:bg-blue-700 rounded-l-xl`}
      >
        <Minus size={16} strokeWidth={3} />
      </button>
      <span className="min-w-[24px] text-center text-[14px] font-extrabold">{qty}</span>
      <button
        type="button"
        aria-label="Sumar"
        onClick={() => plus(1)}
        className={`${compact ? 'w-9' : 'w-10'} h-full flex items-center justify-center active:bg-blue-700 rounded-r-xl`}
      >
        <Plus size={16} strokeWidth={3} />
      </button>
    </div>
  )
}

export default QtyControl
