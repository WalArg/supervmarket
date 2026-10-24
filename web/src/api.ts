import axios from 'axios'
import type { ProductGroup, OptimizeMode, OptimizePlan, ListItem, StatsSummary } from './types'

// Mismo origen por defecto (/api en Vercel). VITE_API_URL para apuntar a otro host.
const base = import.meta.env.VITE_API_URL || ''
const http = axios.create({ baseURL: base })

export async function searchProducts(
  q: string,
  sort: string,
  onlyOffers: boolean = false,
  cp?: string | null,
): Promise<ProductGroup[]> {
  const { data } = await http.get('/api/search', {
    params: { q, sort, only_offers: onlyOffers, ...(cp ? { cp } : {}) },
  })
  return data
}

export async function getStats(): Promise<StatsSummary> {
  const { data } = await http.get('/api/stats')
  return data
}

export async function suggest(q: string): Promise<string[]> {
  const { data } = await http.get('/api/suggest', { params: { q } })
  return data
}

export async function optimize(
  items: ListItem[],
  mode: OptimizeMode,
  opts?: { cp?: string | null; includeClubs?: boolean; includeShipping?: boolean },
): Promise<OptimizePlan> {
  const payload = {
    items: items.map(i => ({ ean: i.ean, qty: i.qty })),
    mode,
    cp: opts?.cp || null,
    include_clubs: opts?.includeClubs ?? false,
    include_shipping: opts?.includeShipping ?? false,
  }
  const { data } = await http.post('/api/optimize', payload)
  return data
}

export async function getRegions(cp: string) {
  const { data } = await http.get('/api/regions', { params: { cp } })
  return data
}

export async function validateCart(
  supermercado: string,
  items: { sku_id: string; qty: number; nombre?: string | null }[],
  cp?: string | null,
) {
  const { data } = await http.post('/api/cart/validate', { supermercado, items, cp })
  return data
}
