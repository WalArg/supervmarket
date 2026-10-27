export interface MeliOption {
  item_id?: string
  price: number
  seller_name: string
  reputation: string
  power_status?: string | null
  is_full?: boolean
  free_shipping?: boolean
  shipping_cost?: number
  link: string
}

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
  // Marketplace / Mercado Libre transparency
  seller_name?: string | null
  seller_reputation?: string | null
  power_seller_status?: string | null
  free_shipping?: boolean
  free_shipping_threshold?: number | null
  shipping_cost?: number | null
  is_full?: boolean
  meli_options?: MeliOption[]
}

export interface ProductGroup {
  ean: string
  nombre: string
  marca: string
  imagen: string
  offers: Offer[]
  all_names?: string[]
}

export type OptimizeMode = 'ahorro' | 'comodidad' | 'balanceada'

/** Detalle enriquecido de cada ítem dentro del changuito de un supermercado */
export interface CartItemDetail {
  ean: string
  nombre: string | null
  sku_id?: string | null
  imagen?: string
  qty: number
  precio: number
  precio_base?: number
  precio_regular?: number
  precio_unitario_efectivo?: number
  line_total?: number
  subtotal_linea?: number
  unit_multiplier?: number
  applied_promo?: string | null
  promo_badge?: string | null
  ahorro_linea?: number
  link?: string | null
}

/** Compatibilidad retroactiva con CartLineItem */
export type CartLineItem = CartItemDetail

export interface BankBenefit {
  payment_id?: string
  label: string
  pct?: number
  cap: number | null
  kind?: 'en_caja' | 'reintegro'
  saving: number
  day?: string
  day_label?: string
  official_url?: string
}

/** Desglose completo de changuito por supermercado individual */
export interface StoreCartBreakdown {
  supermercado: string
  supports_cart: boolean
  is_vtex?: boolean
  checkout_url: string | null
  affiliate_checkout_url?: string | null
  subtotal_merch?: number
  subtotal: number
  volume_discounts_total?: number
  ahorro?: number
  bank_discount_amount?: number
  reintegro_bancario?: number
  bank_card_applied?: string | null
  bank_benefit?: BankBenefit | null
  shipping_fee?: number
  envio_estimado?: number
  free_shipping_threshold: number
  is_free_shipping?: boolean
  amount_for_free_shipping?: number
  falta_envio_gratis: number
  final_store_total?: number
  items: CartItemDetail[]
}

/** Compatibilidad retroactiva con StorePlan */
export type StorePlan = StoreCartBreakdown

export interface BestDaySuggestion {
  day: string
  day_label: string
  saving: number
  details: string[]
}

/** Alternativa de producto en otra tienda para faltantes */
export interface MissingItemAlternative {
  supermercado: string
  precio: number
  promo_badge?: string
}

/** Detalle estructurado de producto faltante con alternativas disponibles */
export interface MissingItemDetail {
  ean: string
  nombre: string
  missing_in_assigned_stores?: string[]
  available_in_other_stores?: MissingItemAlternative[]
}

/** Previsualización de escenario comparativo para el Smart Cart Hero */
export interface ScenarioPreview {
  mode: OptimizeMode
  title: string
  tagline: string
  total: number
  ahorro_vs_comoda: number
  ahorro_vs_regular: number
  ahorro_pct: number
  supermercados_count: number
  covered_items: number
  total_items: number
  badge?: string
  logistics_warning?: string | null
  // Metadatos de compatibilidad
  diff?: number
  stops?: number
  ahorro_total?: number
}

/** Compatibilidad retroactiva con ModePreview */
export type ModePreview = ScenarioPreview

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
  missing: MissingItemDetail[]
  carts: StoreCartBreakdown[]
  all_plans?: Record<OptimizeMode, OptimizePlan>
  mode_previews?: Record<OptimizeMode, ScenarioPreview>
  scenario_preview?: ScenarioPreview
  logistics_warning?: string | null
  context_key?: string
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

/** Ítem individual guardado en la lista habitual */
export interface HabitualItem {
  ean: string
  nombre: string
  imagen: string
  qty: number
  unit_multiplier?: number
  categoria?: string
  added_at: string // ISO timestamp
  last_known_unit_price?: number
}

/** Estructura de la lista habitual en localStorage (sv_habitual_v1) */
export interface HabitualList {
  version: '1.0'
  updated_at: string // ISO timestamp
  name: string // ej: "Mi lista habitual"
  items: HabitualItem[]
}

/** Registro histórico de optimización en sv_basket_history_v1 (52 semanas FIFO) */
export interface BasketSnapshot {
  id: string // `snap_${timestamp}`
  timestamp: string // ISO timestamp
  cp?: string | null
  items_count: number
  total_units: number
  total_comodidad: number // Modo Cómoda (1 solo súper)
  total_ahorro: number // Modo Más Barata (split óptimo)
  total_balanceada?: number // Modo Equilibrada
  ahorro_ars: number // total_comodidad - total_ahorro
  savings_pct: number
  store_split?: Record<string, number>
  source?: 'checkout' | 'optimization_view' | 'manual'
}

/** Comparativa delta vs snapshot previo */
export interface BasketDeltaComparison {
  has_history: boolean
  previous_date?: string
  days_elapsed?: number
  current_total: number
  previous_total?: number
  delta_ars: number
  percentage_delta: number
  current_savings: number
  previous_savings?: number
  savings_delta_ars: number
  items_count_diff: number
  is_basket_size_different: boolean
  normalized_unit_delta_pct?: number
}

/** Resumen estadístico acumulado sobre todo el búfer de 52 semanas */
export interface BasketHistoryStats {
  total_snapshots: number
  cumulative_savings_ars: number
  average_savings_ars: number
  first_snapshot_date?: string
  latest_snapshot_date?: string
  min_basket_total?: number
  max_basket_total?: number
  overall_period_inflation_pct?: number
}

/** Ítem transportable para compartir listas vía URL Base64url */
export interface SharedItem {
  ean: string
  qty: number
}

