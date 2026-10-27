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
  replaceItems: (newItems: ListItem[]) => void
  mergeItems: (newItems: ListItem[]) => void
  importItems: (
    incoming: { ean: string; qty: number; nombre?: string; imagen?: string }[],
    mode: 'replace' | 'merge',
  ) => void
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

  const add = (g: ProductGroup, addQty: number = 1) => {
    const ean = g.ean || g.offers?.[0]?.ean || (g as any).id || g.nombre
    setItems(prev =>
      prev.some(i => i.ean === ean)
        ? prev.map(i => (i.ean === ean ? { ...i, qty: i.qty + addQty } : i))
        : [...prev, { ean, nombre: g.nombre, imagen: g.imagen, qty: Math.max(1, addQty) }],
    )
  }

  const remove = (ean: string) =>
    setItems(prev => prev.filter(i => i.ean !== ean && (i as any).id !== ean))

  const setQty = (ean: string, qty: number) => {
    if (qty <= 0) {
      remove(ean)
      return
    }
    setItems(prev =>
      prev.map(i => (i.ean === ean || (i as any).id === ean ? { ...i, qty: Math.max(1, qty) } : i)),
    )
  }

  const clear = () => {
    setItems([])
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {}
  }
  const has = (ean: string) => items.some(i => i.ean === ean)
  const qtyOf = (ean: string) => items.find(i => i.ean === ean)?.qty || 0

  const replaceItems = (newItems: ListItem[]) => {
    setItems(
      newItems.map(i => ({
        ean: i.ean,
        nombre: i.nombre || `Producto ${i.ean}`,
        imagen: i.imagen || '',
        qty: Math.max(1, i.qty),
      })),
    )
  }

  const mergeItems = (newItems: ListItem[]) => {
    setItems(prev => {
      const map = new Map<string, ListItem>()
      for (const item of prev) {
        map.set(item.ean, { ...item })
      }
      for (const item of newItems) {
        if (map.has(item.ean)) {
          const existing = map.get(item.ean)!
          map.set(item.ean, {
            ...existing,
            qty: existing.qty + Math.max(1, item.qty),
          })
        } else {
          map.set(item.ean, {
            ean: item.ean,
            nombre: item.nombre || `Producto ${item.ean}`,
            imagen: item.imagen || '',
            qty: Math.max(1, item.qty),
          })
        }
      }
      return Array.from(map.values())
    })
  }

  const importItems = (
    incoming: { ean: string; qty: number; nombre?: string; imagen?: string }[],
    mode: 'replace' | 'merge',
  ) => {
    const formatted: ListItem[] = incoming.map(i => ({
      ean: i.ean,
      nombre: i.nombre || `Producto ${i.ean}`,
      imagen: i.imagen || '',
      qty: Math.max(1, i.qty),
    }))
    if (mode === 'replace') {
      replaceItems(formatted)
    } else {
      mergeItems(formatted)
    }
  }

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
      replaceItems,
      mergeItems,
      importItems,
    }),
    [items],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

const DEFAULT_CART_VALUE: CartCtx = {
  items: [],
  add: () => {},
  remove: () => {},
  setQty: () => {},
  clear: () => {},
  has: () => false,
  qtyOf: () => 0,
  count: 0,
  totalUnits: 0,
  replaceItems: () => {},
  mergeItems: () => {},
  importItems: () => {},
}

export function useCart() {
  const ctx = useContext(Ctx)
  return ctx || DEFAULT_CART_VALUE
}
