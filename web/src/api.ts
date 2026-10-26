import axios from 'axios'
import type {
  ProductGroup,
  OptimizeMode,
  OptimizePlan,
  ListItem,
  StatsSummary,
  BenefitsCatalog,
} from './types'

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
  opts?: {
    cp?: string | null
    includeClubs?: boolean
    includeShipping?: boolean
    selectedCards?: string[]
    day?: string | null
  },
): Promise<OptimizePlan> {
  const payload = {
    items: items.map(i => ({ ean: i.ean, qty: i.qty, nombre: i.nombre })),
    mode,
    cp: opts?.cp || null,
    include_clubs: opts?.includeClubs ?? false,
    include_shipping: opts?.includeShipping ?? false,
    selected_cards: opts?.selectedCards ?? [],
    day: opts?.day || null,
  }
  const { data } = await http.post('/api/optimize', payload)
  return data
}

export async function getBenefits(): Promise<BenefitsCatalog> {
  const { data } = await http.get('/api/benefits')
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

export interface GeocodeLocation {
  cp: string
  neighborhood: string
  zone?: string
  label: string
  display_name: string
  lat?: number | string
  lon?: number | string
}

export async function reverseGeocode(lat: number, lon: number): Promise<GeocodeLocation> {
  const { data } = await http.get('/api/geocode/reverse', { params: { lat, lon } })
  return data
}

export async function searchLocations(q: string): Promise<GeocodeLocation[]> {
  const { data } = await http.get('/api/geocode/search', { params: { q } })
  return data
}

export interface ReceiptItemResult {
  nombre_ticket: string
  qty: number
  precio_ticket: number
  subtotal_ticket: number
  matched: boolean
  product?: {
    ean: string
    nombre: string
    imagen?: string
    supermercado: string
    precio: number
    subtotal: number
    promo_label?: string
  } | null
  ahorro: number
}

export interface ReceiptAnalysis {
  ok: boolean
  supermercado: string
  total_ticket: number
  total_supervmarket: number
  ahorro: number
  ahorro_porcentaje: number
  items: ReceiptItemResult[]
}

export interface RecipeIngredient {
  item_pedido: string
  qty: number
  unit: string
  matched: boolean
  subtotal?: number
  product?: {
    ean: string
    nombre: string
    imagen?: string
    supermercado: string
    precio: number
    subtotal: number
    promo_label?: string
  } | null
}

export interface RecipeCartResult {
  ok: boolean
  titulo: string
  porciones: number
  prompt_original: string
  total_estimado: number
  ingredientes: RecipeIngredient[]
}

export async function analyzeReceipt(
  image: string,
  mimeType?: string,
  cp?: string | null,
): Promise<ReceiptAnalysis> {
  const { data } = await http.post('/api/ai/receipt', {
    image,
    mime_type: mimeType || 'image/jpeg',
    cp,
  })
  return data
}

export async function generateRecipeCart(
  prompt: string,
  cp?: string | null,
): Promise<RecipeCartResult> {
  const { data } = await http.post('/api/ai/recipe', { prompt, cp })
  return data
}


