import axios from 'axios'
import type {
  ProductGroup,
  OptimizeMode,
  OptimizePlan,
  ListItem,
  StatsSummary,
  BenefitsCatalog,
} from './types'
import type { DiscountTier } from './data/gondolasData'

// Mismo origen por defecto (/api en Vercel). VITE_API_URL para apuntar a otro host.
const base = import.meta.env.VITE_API_URL || ''
const http = axios.create({ baseURL: base })

export interface LiveOffersResponse {
  tiers: DiscountTier[]
  marketplace_tiers?: DiscountTier[]
  updated_at: string
  is_live: boolean
  total_deals: number
}

export async function getLiveOffers(
  cp?: string | null,
  force: boolean = false,
): Promise<LiveOffersResponse> {
  const { data } = await http.get('/api/offers', {
    params: { ...(cp ? { cp } : {}), ...(force ? { force: 'true' } : {}) },
  })
  return data
}

export interface SearchFilterOpts {
  vertical?: string | null
  store_type?: string | null
  grocery_only?: boolean
}

export async function searchProducts(
  q: string,
  sort: string,
  onlyOffers: boolean = false,
  cp?: string | null,
  filterOptsOrVertical?: SearchFilterOpts | string | null,
  storeType?: string | null,
  groceryOnly: boolean = false,
): Promise<ProductGroup[]> {
  const params: Record<string, any> = {
    q,
    sort,
    only_offers: onlyOffers,
  }
  if (cp) params.cp = cp

  let vert: string | null = null
  let sType: string | null = null
  let gOnly: boolean = false

  if (typeof filterOptsOrVertical === 'object' && filterOptsOrVertical !== null) {
    vert = filterOptsOrVertical.vertical ?? null
    sType = filterOptsOrVertical.store_type ?? null
    gOnly = Boolean(filterOptsOrVertical.grocery_only)
  } else if (typeof filterOptsOrVertical === 'string') {
    vert = filterOptsOrVertical
    sType = storeType ?? null
    gOnly = Boolean(groceryOnly)
  }

  if (vert && vert !== 'all' && vert !== 'todos') {
    params.vertical = vert
  }
  if (sType && sType !== 'all' && sType !== 'todos') {
    params.store_type = sType
  }
  if (gOnly) {
    params.grocery_only = true
  }

  const { data } = await http.get('/api/search', { params })
  return data
}

export interface McpLiveSearchResult {
  query: string
  vertical?: string | null
  store_type?: string | null
  grocery_only: boolean
  synced_offers: number
  stores_hit: Record<string, number>
  grouped_count: number
  results: ProductGroup[]
}

export async function searchLiveMCP(
  q: string,
  opts?: {
    limit_per_store?: number
    vertical?: string | null
    store_type?: string | null
    grocery_only?: boolean
  },
): Promise<McpLiveSearchResult> {
  const { data } = await http.get('/api/mcp/search', {
    params: {
      q,
      limit_per_store: opts?.limit_per_store ?? 18,
      ...(opts?.vertical ? { vertical: opts.vertical } : {}),
      ...(opts?.store_type ? { store_type: opts.store_type } : {}),
      ...(opts?.grocery_only !== undefined ? { grocery_only: opts.grocery_only } : {}),
    },
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
    items: items.map(i => ({
      ean: i.ean,
      qty: i.qty,
      nombre: i.nombre,
      store: i.store,
      link: i.link,
      precio: i.precio,
      sku_id: i.sku_id,
    })),
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


