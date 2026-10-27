import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react'
import type { ProductGroup } from '../types'

export interface SavedItem {
  id: string
  ean?: string
  sku?: string
  nombre: string
  marca?: string
  imagen?: string
  minPrice?: number
  bestStore?: string
  group: ProductGroup
  savedAt: number
}

interface SavedContextValue {
  savedItems: SavedItem[]
  savedCount: number
  isSaved: (productIdOrEan: string) => boolean
  toggleSave: (group: ProductGroup) => boolean
  saveProduct: (group: ProductGroup) => void
  removeSaved: (productIdOrEan: string) => void
  clearSaved: () => void
}

const STORAGE_KEY = 'sv_saved_products_v1'

const SavedContext = createContext<SavedContextValue | null>(null)

export const getCanonicalProductId = (group: ProductGroup): string => {
  return group.offers[0]?.ean || group.id || group.nombre
}

export const SavedProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [savedItems, setSavedItems] = useState<SavedItem[]>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return []
      const parsed = JSON.parse(raw)
      return Array.isArray(parsed) ? parsed : []
    } catch {
      return []
    }
  })

  // Sincronizar persistencia en localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(savedItems))
    } catch {
      // Ignorar si storage quota exceeded
    }
  }, [savedItems])

  const isSaved = useCallback(
    (productIdOrEan: string): boolean => {
      if (!productIdOrEan) return false
      const clean = productIdOrEan.trim()
      return savedItems.some(
        it => it.id === clean || it.ean === clean || it.group.id === clean,
      )
    },
    [savedItems],
  )

  const saveProduct = useCallback((group: ProductGroup) => {
    const id = getCanonicalProductId(group)
    const ean = group.offers.find(o => o.ean)?.ean || group.offers[0]?.ean
    const sku = group.offers[0]?.sku
    const bestOffer = [...group.offers].sort((a, b) => a.precio - b.precio)[0]

    setSavedItems(prev => {
      if (prev.some(it => it.id === id || (ean && it.ean === ean))) {
        return prev
      }
      const newItem: SavedItem = {
        id,
        ean,
        sku,
        nombre: group.nombre,
        marca: group.marca,
        imagen: group.imagen,
        minPrice: bestOffer ? bestOffer.precio : undefined,
        bestStore: bestOffer ? bestOffer.supermercado : undefined,
        group,
        savedAt: Date.now(),
      }
      return [newItem, ...prev]
    })
  }, [])

  const removeSaved = useCallback((productIdOrEan: string) => {
    if (!productIdOrEan) return
    const clean = productIdOrEan.trim()
    setSavedItems(prev =>
      prev.filter(
        it => it.id !== clean && it.ean !== clean && it.group.id !== clean,
      ),
    )
  }, [])

  const toggleSave = useCallback(
    (group: ProductGroup): boolean => {
      const id = getCanonicalProductId(group)
      const ean = group.offers.find(o => o.ean)?.ean || group.offers[0]?.ean
      const alreadySaved = isSaved(id) || (Boolean(ean) && isSaved(ean!))

      if (alreadySaved) {
        removeSaved(id)
        if (ean) removeSaved(ean)
        return false
      } else {
        saveProduct(group)
        return true
      }
    },
    [isSaved, removeSaved, saveProduct],
  )

  const clearSaved = useCallback(() => {
    setSavedItems([])
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {}
  }, [])

  const value = useMemo<SavedContextValue>(
    () => ({
      savedItems,
      savedCount: savedItems.length,
      isSaved,
      toggleSave,
      saveProduct,
      removeSaved,
      clearSaved,
    }),
    [savedItems, isSaved, toggleSave, saveProduct, removeSaved, clearSaved],
  )

  return <SavedContext.Provider value={value}>{children}</SavedContext.Provider>
}

const DEFAULT_SAVED_VALUE: SavedContextValue = {
  savedItems: [],
  savedCount: 0,
  isSaved: () => false,
  toggleSave: () => false,
  saveProduct: () => {},
  removeSaved: () => {},
  clearSaved: () => {},
}

export const useSaved = (): SavedContextValue => {
  const ctx = useContext(SavedContext)
  if (!ctx) {
    return DEFAULT_SAVED_VALUE
  }
  return ctx
}
