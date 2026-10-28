import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { ListItem, ProductGroup } from '../types'

interface CartExtra {
  link?: string
  precio?: number
  sku_id?: string
}

export function getItemKey(ean: string, store?: string, sku_id?: string): string {
  if (!store && !sku_id) return ean
  return `${ean}::${store || ''}::${sku_id || ''}`
}

interface CartCtx {
  items: ListItem[]
  add: (group: ProductGroup, qty?: number, store?: string, extra?: CartExtra) => void
  remove: (keyOrEan: string) => void
  setQty: (keyOrEan: string, qty: number) => void
  setStoreForEan: (ean: string, store?: string, extra?: CartExtra) => void
  clear: () => void
  has: (keyOrEan: string) => boolean
  qtyOf: (keyOrEan: string) => number
  itemOf: (keyOrEan: string) => ListItem | undefined
  count: number
  totalUnits: number
  replaceItems: (newItems: ListItem[]) => void
  mergeItems: (newItems: ListItem[]) => void
  importItems: (
    incoming: { ean: string; qty: number; nombre?: string; imagen?: string; store?: string }[],
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

  const add = (
    g: ProductGroup,
    addQty: number = 1,
    store?: string,
    extra?: CartExtra,
  ) => {
    const ean = g.ean || g.offers?.[0]?.ean || (g as any).id || g.nombre
    const itemKey = getItemKey(ean, store, extra?.sku_id)

    setItems(prev => {
      const idx = prev.findIndex(i => (i.id || i.ean) === itemKey || (!i.store && !store && i.ean === ean))
      if (idx >= 0) {
        return prev.map((it, i) =>
          i === idx
            ? {
                ...it,
                qty: it.qty + Math.max(1, addQty),
                store: store !== undefined ? store : it.store,
                link: extra?.link !== undefined ? extra.link : it.link,
                precio: extra?.precio !== undefined ? extra.precio : it.precio,
                sku_id: extra?.sku_id !== undefined ? extra.sku_id : it.sku_id,
              }
            : it,
        )
      }
      return [
        ...prev,
        {
          id: itemKey,
          ean,
          nombre: g.nombre,
          imagen: g.imagen,
          qty: Math.max(1, addQty),
          store,
          link: extra?.link,
          precio: extra?.precio,
          sku_id: extra?.sku_id,
        },
      ]
    })
  }

  const setStoreForEan = (ean: string, store?: string, extra?: CartExtra) => {
    setItems(prev =>
      prev.map(it =>
        it.ean === ean || (it as any).id === ean
          ? {
              ...it,
              store,
              link: extra?.link !== undefined ? extra.link : it.link,
              precio: extra?.precio !== undefined ? extra.precio : it.precio,
              sku_id: extra?.sku_id !== undefined ? extra.sku_id : it.sku_id,
            }
          : it,
      ),
    )
  }

  const remove = (keyOrEan: string) =>
    setItems(prev => {
      if (keyOrEan.includes('::')) {
        return prev.filter(i => (i.id || i.ean) !== keyOrEan)
      }
      return prev.filter(i => (i.id || i.ean) !== keyOrEan && i.ean !== keyOrEan)
    })

  const setQty = (keyOrEan: string, qty: number) => {
    if (qty <= 0) {
      remove(keyOrEan)
      return
    }
    setItems(prev => {
      const hasExact = prev.some(i => (i.id || i.ean) === keyOrEan)
      if (hasExact) {
        return prev.map(i =>
          (i.id || i.ean) === keyOrEan ? { ...i, qty: Math.max(1, qty) } : i,
        )
      }
      return prev.map(i =>
        i.ean === keyOrEan ? { ...i, qty: Math.max(1, qty) } : i,
      )
    })
  }

  const clear = () => {
    setItems([])
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {}
  }
  const has = (keyOrEan: string) =>
    items.some(
      i =>
        (i.id || i.ean) === keyOrEan ||
        i.ean === keyOrEan ||
        (i.id && i.id.startsWith(`${keyOrEan}::`)),
    )

  const qtyOf = (keyOrEan: string) => {
    const exact = items.find(i => (i.id || i.ean) === keyOrEan)
    if (exact && keyOrEan.includes('::')) return exact.qty
    const matching = items.filter(i => i.ean === keyOrEan || (i.id && i.id.startsWith(`${keyOrEan}::`)))
    if (matching.length > 0) {
      return matching.reduce((sum, i) => sum + i.qty, 0)
    }
    return exact?.qty || 0
  }

  const itemOf = (keyOrEan: string) =>
    items.find(i => (i.id || i.ean) === keyOrEan) ||
    items.find(i => i.ean === keyOrEan || (i.id && i.id.startsWith(`${keyOrEan}::`)))

  const replaceItems = (newItems: ListItem[]) => {
    setItems(
      newItems.map(i => ({
        id: i.id || getItemKey(i.ean, i.store, i.sku_id),
        ean: i.ean,
        nombre: i.nombre || `Producto ${i.ean}`,
        imagen: i.imagen || '',
        qty: Math.max(1, i.qty),
        store: i.store,
        link: i.link,
        precio: i.precio,
        sku_id: i.sku_id,
      })),
    )
  }

  const mergeItems = (newItems: ListItem[]) => {
    setItems(prev => {
      const map = new Map<string, ListItem>()
      for (const item of prev) {
        const k = item.id || getItemKey(item.ean, item.store, item.sku_id)
        map.set(k, { ...item, id: k })
      }
      for (const item of newItems) {
        const k = item.id || getItemKey(item.ean, item.store, item.sku_id)
        if (map.has(k)) {
          const existing = map.get(k)!
          map.set(k, {
            ...existing,
            qty: existing.qty + Math.max(1, item.qty),
            store: item.store || existing.store,
            link: item.link || existing.link,
            precio: item.precio || existing.precio,
            sku_id: item.sku_id || existing.sku_id,
          })
        } else {
          map.set(k, {
            id: k,
            ean: item.ean,
            nombre: item.nombre || `Producto ${item.ean}`,
            imagen: item.imagen || '',
            qty: Math.max(1, item.qty),
            store: item.store,
            link: item.link,
            precio: item.precio,
            sku_id: item.sku_id,
          })
        }
      }
      return Array.from(map.values())
    })
  }

  const importItems = (
    incoming: { ean: string; qty: number; nombre?: string; imagen?: string; store?: string }[],
    mode: 'replace' | 'merge',
  ) => {
    const formatted: ListItem[] = incoming.map(i => ({
      ean: i.ean,
      nombre: i.nombre || `Producto ${i.ean}`,
      imagen: i.imagen || '',
      qty: Math.max(1, i.qty),
      store: i.store,
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
      setStoreForEan,
      clear,
      has,
      qtyOf,
      itemOf,
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
  setStoreForEan: () => {},
  clear: () => {},
  has: () => false,
  qtyOf: () => 0,
  itemOf: () => undefined,
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
