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

export interface StorePlan {
  supermercado: string
  supports_cart: boolean
  checkout_url: string | null
  subtotal: number
  ahorro?: number
  envio_estimado?: number
  free_shipping_threshold: number
  falta_envio_gratis: number
  items: CartLineItem[]
}

export interface OptimizePlan {
  mode: OptimizeMode
  cp?: string | null
  stops: number
  subtotal_mercaderia?: number
  envio_estimado?: number
  total: number
  ahorro_total?: number
  excluded_stores?: string[]
  missing: { ean: string; nombre: string }[]
  carts: StorePlan[]
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
