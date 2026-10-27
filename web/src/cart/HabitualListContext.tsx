import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useMemo,
  useCallback,
  type ReactNode,
} from 'react'
import type {
  HabitualList,
  HabitualItem,
  BasketSnapshot,
  BasketDeltaComparison,
  BasketHistoryStats,
  ListItem,
  OptimizePlan,
} from '../types'
import { useCart } from './CartContext'
import {
  loadBasketHistory,
  saveBasketHistory,
  createSnapshotFromPlan,
  pushSnapshotToHistory,
  calculateBasketDelta,
  calculateHistoryStats,
  clearBasketHistory,
} from './basketHistory'
import { generateShareUrl } from './portableList'

export const HABITUAL_STORAGE_KEY = 'sv_habitual_v1'

export interface HabitualListCtx {
  habitualList: HabitualList | null
  hasHabitualList: boolean
  itemsCount: number
  totalUnits: number
  lastUpdated: string | null
  isCartSavedAsHabitual: boolean
  history: BasketSnapshot[]
  lastSnapshot: BasketSnapshot | null
  comparison: BasketDeltaComparison | null
  stats: BasketHistoryStats
  saveCartAsHabitual: (name?: string) => { success: boolean; count: number; error?: string }
  loadHabitualIntoCart: (strategy?: 'replace' | 'merge') => { success: boolean; count: number }
  clearHabitualList: () => void
  recordSnapshot: (
    plan: OptimizePlan | null,
    source?: 'checkout' | 'optimization_view' | 'manual',
    force?: boolean,
  ) => BasketSnapshot | null
  encodeShareUrl: (paramKey?: 'list' | 'habitual') => string
}

function sanitizeList(raw: unknown): HabitualList | null {
  if (!raw || typeof raw !== 'object') return null
  const candidate = raw as Partial<HabitualList>
  if (!Array.isArray(candidate.items)) return null
  const validItems: HabitualItem[] = candidate.items
    .filter(i => i && typeof i.ean === 'string' && i.ean.length >= 8 && typeof i.nombre === 'string')
    .map(i => ({
      ean: i.ean,
      nombre: i.nombre,
      imagen: i.imagen || '',
      qty: Math.max(1, Number(i.qty) || 1),
      added_at: i.added_at || new Date().toISOString(),
      unit_multiplier: i.unit_multiplier,
      categoria: i.categoria,
      last_known_unit_price: i.last_known_unit_price,
    }))
  if (validItems.length === 0) return null
  return {
    version: '1.0',
    updated_at: typeof candidate.updated_at === 'string' ? candidate.updated_at : new Date().toISOString(),
    name: typeof candidate.name === 'string' ? candidate.name : 'Mi lista habitual',
    items: validItems,
  }
}

const defaultHabitualCtx: HabitualListCtx = {
  habitualList: null,
  hasHabitualList: false,
  itemsCount: 0,
  totalUnits: 0,
  lastUpdated: null,
  isCartSavedAsHabitual: false,
  history: [],
  lastSnapshot: null,
  comparison: null,
  stats: {
    total_snapshots: 0,
    cumulative_savings_ars: 0,
    average_savings_ars: 0,
  },
  saveCartAsHabitual: () => ({ success: false, count: 0, error: 'Context not provided' }),
  loadHabitualIntoCart: () => ({ success: false, count: 0 }),
  clearHabitualList: () => {},
  recordSnapshot: () => null,
  encodeShareUrl: () => '',
}

const Ctx = createContext<HabitualListCtx | null>(null)

export function HabitualListProvider({ children }: { children: ReactNode }) {
  const { items: cartItems, replaceItems, mergeItems, totalUnits: totalCartUnits } = useCart()

  const [habitualList, setHabitualList] = useState<HabitualList | null>(() => {
    try {
      const saved = localStorage.getItem(HABITUAL_STORAGE_KEY)
      return saved ? sanitizeList(JSON.parse(saved)) : null
    } catch {
      return null
    }
  })

  const [history, setHistory] = useState<BasketSnapshot[]>(() => loadBasketHistory())

  // Sincronización multi-pestaña (StorageEvent)
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === HABITUAL_STORAGE_KEY) {
        try {
          setHabitualList(e.newValue ? sanitizeList(JSON.parse(e.newValue)) : null)
        } catch {
          // ignore
        }
      } else if (e.key === 'sv_basket_history_v1') {
        setHistory(loadBasketHistory())
      }
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  // Comprobación reactiva O(N): ¿el changuito actual coincide exactamente con la lista habitual?
  const isCartSavedAsHabitual = useMemo(() => {
    if (!habitualList || !habitualList.items.length || !cartItems.length) return false
    if (habitualList.items.length !== cartItems.length) return false
    const map = new Map(habitualList.items.map(i => [i.ean, i.qty]))
    return cartItems.every(i => map.get(i.ean) === i.qty)
  }, [habitualList, cartItems])

  const saveCartAsHabitual = useCallback(
    (customName = 'Mi lista habitual') => {
      if (!cartItems.length) {
        return { success: false, count: 0, error: 'El changuito está vacío' }
      }
      const now = new Date().toISOString()
      const existingMap = new Map(habitualList?.items.map(i => [i.ean, i.added_at]) || [])
      const items: HabitualItem[] = cartItems.map(i => ({
        ean: i.ean,
        nombre: i.nombre,
        imagen: i.imagen,
        qty: i.qty,
        added_at: existingMap.get(i.ean) || now,
      }))

      const list: HabitualList = {
        version: '1.0',
        updated_at: now,
        name: customName,
        items,
      }

      try {
        localStorage.setItem(HABITUAL_STORAGE_KEY, JSON.stringify(list))
      } catch (e) {
        console.warn('Error saving habitual list to localStorage:', e)
      }
      setHabitualList(list)
      return { success: true, count: items.length }
    },
    [cartItems, habitualList],
  )

  const loadHabitualIntoCart = useCallback(
    (strategy: 'replace' | 'merge' = 'replace') => {
      if (!habitualList || !habitualList.items.length) {
        return { success: false, count: 0 }
      }
      const toLoad: ListItem[] = habitualList.items.map(i => ({
        ean: i.ean,
        nombre: i.nombre,
        imagen: i.imagen,
        qty: i.qty,
      }))
      if (strategy === 'replace') {
        replaceItems(toLoad)
      } else {
        mergeItems(toLoad)
      }
      return { success: true, count: toLoad.length }
    },
    [habitualList, replaceItems, mergeItems],
  )

  const clearHabitual = useCallback(() => {
    try {
      localStorage.removeItem(HABITUAL_STORAGE_KEY)
    } catch {
      // ignore
    }
    setHabitualList(null)
  }, [])

  const recordSnapshot = useCallback(
    (
      plan: OptimizePlan | null,
      source: 'checkout' | 'optimization_view' | 'manual' = 'optimization_view',
      force: boolean = false,
    ) => {
      if (!plan || !cartItems.length) return null
      const snap = createSnapshotFromPlan(plan, cartItems.length, totalCartUnits, source)
      if (!snap) return null

      setHistory(prev => {
        const { updatedHistory } = pushSnapshotToHistory(prev, snap, force)
        return updatedHistory
      })
      return snap
    },
    [cartItems.length, totalCartUnits],
  )

  const encodeShareUrl = useCallback(
    (paramKey: 'list' | 'habitual' = 'habitual') => {
      if (!habitualList || !habitualList.items.length) return ''
      return generateShareUrl(habitualList.items, paramKey)
    },
    [habitualList],
  )

  const lastSnapshot = history.length > 0 ? history[history.length - 1] : null

  const comparison = useMemo<BasketDeltaComparison | null>(() => {
    if (!lastSnapshot) return null
    return calculateBasketDelta(lastSnapshot, history)
  }, [history, lastSnapshot])

  const stats = useMemo<BasketHistoryStats>(() => {
    return calculateHistoryStats(history)
  }, [history])

  const value = useMemo(
    () => ({
      habitualList,
      hasHabitualList: Boolean(habitualList && habitualList.items.length > 0),
      itemsCount: habitualList?.items.length || 0,
      totalUnits: habitualList?.items.reduce((acc, i) => acc + i.qty, 0) || 0,
      lastUpdated: habitualList?.updated_at || null,
      isCartSavedAsHabitual,
      history,
      lastSnapshot,
      comparison,
      stats,
      saveCartAsHabitual,
      loadHabitualIntoCart,
      clearHabitualList: clearHabitual,
      recordSnapshot,
      encodeShareUrl,
    }),
    [
      habitualList,
      isCartSavedAsHabitual,
      history,
      lastSnapshot,
      comparison,
      stats,
      saveCartAsHabitual,
      loadHabitualIntoCart,
      clearHabitual,
      recordSnapshot,
      encodeShareUrl,
    ],
  )

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useHabitualList() {
  const ctx = useContext(Ctx)
  return ctx || defaultHabitualCtx
}
