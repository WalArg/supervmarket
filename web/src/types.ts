export interface Offer {
  supermercado: string
  precio: number
  precio_lista: number
  stock: boolean
  link: string
  sku_id: string
  unit_price: number | null
  unit_measure: string | null
  discount: number
  promo_label?: string | null
  promo_type?: 'DIRECT' | 'NXM' | 'BULK_PCT' | 'CLUB_PCT' | string | null
  promo_min_qty?: number
  promo_unit_price?: number
  requires_club?: boolean
  supports_cart: boolean
}

export interface ProductGroup {
  ean: string
  nombre: string
  marca: string
  imagen: string
  offers: Offer[]
}

export type OptimizeMode = 'ahorro' | 'comodidad' | 'balanceada'

export interface CartLineItem {
  ean: string
  nombre: string | null
  sku_id: string | null
  precio: number
  precio_base?: number
  line_total?: number
  applied_promo?: string | null
  qty: number
  link: string | null
}

export interface BankBenefit {
  payment_id: string
  label: string
  pct: number
  cap: number | null
  kind: 'en_caja' | 'reintegro'
  saving: number
  day: string
  day_label: string
  official_url: string
}

export interface StorePlan {
  supermercado: string
  supports_cart: boolean
  checkout_url: string | null
  subtotal: number
  ahorro?: number
  reintegro_bancario?: number
  bank_benefit?: BankBenefit | null
  envio_estimado?: number
  free_shipping_threshold: number
  falta_envio_gratis: number
  items: CartLineItem[]
}

export interface BestDaySuggestion {
  day: string
  day_label: string
  saving: number
  details: string[]
}

export interface ModePreview {
  total: number
  stops: number
  ahorro_total: number
  diff: number
}

export interface OptimizePlan {
  mode: OptimizeMode
  cp?: string | null
  day?: string
  day_label?: string
  stops: number
  subtotal_mercaderia?: number
  envio_estimado?: number
  reintegro_bancario_total?: number
  total: number
  ahorro_total?: number
  best_day_suggestion?: BestDaySuggestion | null
  excluded_stores?: string[]
  missing: { ean: string; nombre: string }[]
  carts: StorePlan[]
  all_plans?: Record<OptimizeMode, OptimizePlan>
  mode_previews?: Record<OptimizeMode, ModePreview>
}

export interface PaymentOption {
  id: string
  name: string
  category: 'club' | 'wallet' | 'bank'
  store?: string
}

export interface DailyPromo {
  supermercado: string
  days: string[]
  payment_id: string
  label: string
  pct: number
  cap: number | null
  kind: 'en_caja' | 'reintegro'
  applies_online: boolean
  official_url: string
}

export interface BenefitsCatalog {
  today: string
  today_label: string
  weekdays: { id: string; label: string }[]
  payment_options: PaymentOption[]
  official_links: Record<string, string>
  daily_promos: DailyPromo[]
}

export interface ListItem {
  ean: string
  nombre: string
  imagen: string
  qty: number
}

export interface StatsSummary {
  productos: number
  ofertas_totales: number
  promociones_activas: number
  tiendas: { supermercado: string; productos: number }[]
}
