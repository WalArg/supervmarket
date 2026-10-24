import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { ListItem, ProductGroup } from '../types'

interface CartCtx {
  items: ListItem[]
  add: (group: ProductGroup, qty?: number) => void
  remove: (ean: string) => void
  setQty: (ean: string, qty: number) => void
  clear: () => void
  has: (ean: string) => boolean
  qtyOf: (ean: string) => number
  count: number
  totalUnits: number
}

const Ctx = createContext<CartCtx | null>(null)
const STORAGE_KEY = 'sv_cart_v2'

export function CartProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ListItem[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      return saved ? JSON.parse(saved) : []
    } catch {
      return []
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(items))
    } catch {
      // Ignore quota errors
    }
  }, [items])

  const add = (g: ProductGroup, addQty: number = 1) =>
    setItems(prev =>
      prev.some(i => i.ean === g.ean)
        ? prev.map(i => (i.ean === g.ean ? { ...i, qty: i.qty + addQty } : i))
        : [...prev, { ean: g.ean, nombre: g.nombre, imagen: g.imagen, qty: Math.max(1, addQty) }],
    )

  const remove = (ean: string) => setItems(prev => prev.filter(i => i.ean !== ean))

  const setQty = (ean: string, qty: number) => {
    if (qty <= 0) {
      remove(ean)
      return
    }
    setItems(prev =>
      prev.map(i => (i.ean === ean ? { ...i, qty: Math.max(1, qty) } : i)),
    )
  }

  const clear = () => setItems([])
  const has = (ean: string) => items.some(i => i.ean === ean)
  const qtyOf = (ean: string) => items.find(i => i.ean === ean)?.qty || 0

  const value = useMemo(
    () => ({
      items,
      add,
      remove,
      setQty,
      clear,
      has,
      qtyOf,
      count: items.length,
      totalUnits: items.reduce((acc, i) => acc + i.qty, 0),
    }),
    [items],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useCart() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useCart debe usarse dentro de <CartProvider>')
  return ctx
}
