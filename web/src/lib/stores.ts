/**
 * web/src/lib/stores.ts
 *
 * Registro canónico unificado de tiendas, verticales, colores y soporte de carrito.
 * Mapea las 40 tiendas y marketplaces compatibles con backend api/_lib/stores.py.
 */

export type StoreVertical = 'supermarket' | 'marketplace' | 'electro' | 'specialty' | 'pharmacy'

export interface StoreMeta {
  id: string
  label: string
  color: string
  vertical: StoreVertical
  isMarketplace?: boolean
  supportsCart?: boolean
  dominio?: string
}

export type StoreMap = Record<string, StoreMeta>

export const VERTICAL_LABELS: Record<StoreVertical, string> = {
  supermarket: 'Supermercados',
  marketplace: 'Marketplaces Generales',
  electro: 'Electro y Tecnología',
  pharmacy: 'Farmacias y Perfumería',
  specialty: 'Hogar y Especialidades',
}

export const STORES: StoreMap = {
  // --- Supermercados tradicionales ---
  Jumbo: { id: 'jumbo', label: 'Jumbo', color: '#16a34a', vertical: 'supermarket', isMarketplace: false, supportsCart: true, dominio: 'https://www.jumbo.com.ar' },
  Disco: { id: 'disco', label: 'Disco', color: '#db2777', vertical: 'supermarket', isMarketplace: false, supportsCart: true, dominio: 'https://www.disco.com.ar' },
  Vea: { id: 'vea', label: 'Vea', color: '#15803d', vertical: 'supermarket', isMarketplace: false, supportsCart: true, dominio: 'https://www.vea.com.ar' },
  Carrefour: { id: 'carrefour', label: 'Carrefour', color: '#1d4ed8', vertical: 'supermarket', isMarketplace: true, supportsCart: true, dominio: 'https://www.carrefour.com.ar' },
  Dia: { id: 'dia', label: 'Día', color: '#e11d48', vertical: 'supermarket', isMarketplace: false, supportsCart: true, dominio: 'https://diaonline.supermercadosdia.com.ar' },
  Masonline: { id: 'masonline', label: 'Más Online', color: '#0d9488', vertical: 'supermarket', isMarketplace: true, supportsCart: true, dominio: 'https://www.masonline.com.ar' },
  Coto: { id: 'coto', label: 'Coto', color: '#dc2626', vertical: 'supermarket', isMarketplace: false, supportsCart: false, dominio: 'https://www.cotodigital3.com.ar' },
  Josimar: { id: 'josimar', label: 'Josimar', color: '#007a3d', vertical: 'supermarket', isMarketplace: false, supportsCart: true, dominio: 'https://www.josimar.com.ar' },
  Toledo: { id: 'toledo', label: 'Toledo Digital', color: '#005ba4', vertical: 'supermarket', isMarketplace: false, supportsCart: true, dominio: 'https://www.toledodigital.com.ar' },
  Cordiez: { id: 'cordiez', label: 'Cordiez', color: '#ed1c24', vertical: 'supermarket', isMarketplace: false, supportsCart: true, dominio: 'https://www.cordiez.com.ar' },
  TheFoodMarket: { id: 'thefoodmarket', label: 'Food Market', color: '#d97706', vertical: 'supermarket', isMarketplace: false, supportsCart: true, dominio: 'https://www.thefoodmarket.com.ar' },
  LaBarata: { id: 'labarata', label: 'La Barata', color: '#16a34a', vertical: 'supermarket', isMarketplace: false, supportsCart: false, dominio: 'https://labarata.ar' },
  ArcorEnCasa: { id: 'arcorencasa', label: 'Arcor en Casa', color: '#0284c7', vertical: 'supermarket', isMarketplace: false, supportsCart: false, dominio: 'https://arcorencasa.com' },

  // --- Marketplaces Generales ---
  'Provincia Compras': { id: 'provinciacompras', label: 'Provincia Compras', color: '#008859', vertical: 'marketplace', isMarketplace: true, supportsCart: true, dominio: 'https://www.provinciacompras.com.ar' },
  'On City': { id: 'oncity', label: 'On City', color: '#001489', vertical: 'marketplace', isMarketplace: true, supportsCart: true, dominio: 'https://www.oncity.com' },
  MercadoLibre: { id: 'mercadolibre', label: 'Mercado Libre', color: '#eab308', vertical: 'marketplace', isMarketplace: true, supportsCart: false, dominio: 'https://www.mercadolibre.com.ar' },

  // --- Cadenas de Electro y Tecnología ---
  Fravega: { id: 'fravega', label: 'Frávega', color: '#4a154b', vertical: 'electro', isMarketplace: true, supportsCart: true, dominio: 'https://www.fravega.com' },
  Cetrogar: { id: 'cetrogar', label: 'Cetrogar', color: '#004b93', vertical: 'electro', isMarketplace: false, supportsCart: true, dominio: 'https://www.cetrogar.com.ar' },
  Naldo: { id: 'naldo', label: 'Naldo', color: '#e30613', vertical: 'electro', isMarketplace: false, supportsCart: true, dominio: 'https://www.naldo.com.ar' },
  Pardo: { id: 'pardo', label: 'Pardo', color: '#e20613', vertical: 'electro', isMarketplace: false, supportsCart: true, dominio: 'https://www.pardo.com.ar' },
  Coppel: { id: 'coppel', label: 'Coppel', color: '#ffd000', vertical: 'electro', isMarketplace: false, supportsCart: true, dominio: 'https://www.coppel.com.ar' },
  Musimundo: { id: 'musimundo', label: 'Musimundo', color: '#e30613', vertical: 'electro', isMarketplace: false, supportsCart: true, dominio: 'https://www.musimundo.com' },

  // --- Tiendas Oficiales de Marca ---
  Samsung: { id: 'samsung', label: 'Samsung', color: '#1249ff', vertical: 'electro', isMarketplace: false, supportsCart: true, dominio: 'https://shop.samsung.com.ar' },
  Philips: { id: 'philips', label: 'Philips', color: '#0b5ed7', vertical: 'electro', isMarketplace: false, supportsCart: true, dominio: 'https://tienda.philips.com.ar' },
  Whirlpool: { id: 'whirlpool', label: 'Whirlpool', color: '#f0b400', vertical: 'electro', isMarketplace: false, supportsCart: true, dominio: 'https://www.whirlpool.com.ar' },
  Moulinex: { id: 'moulinex', label: 'Moulinex / Tefal', color: '#da291c', vertical: 'electro', isMarketplace: false, supportsCart: true, dominio: 'https://tienda.moulinex.com.ar' },
  Sony: { id: 'sony', label: 'Sony Store', color: '#000000', vertical: 'electro', isMarketplace: false, supportsCart: true, dominio: 'https://store.sony.com.ar' },
  Oster: { id: 'oster', label: 'Oster', color: '#b22222', vertical: 'electro', isMarketplace: false, supportsCart: true, dominio: 'https://www.osterargentina.com' },

  // --- Hogar, Farmacia, Perfumería, Mascotas y Especialidad ---
  Easy: { id: 'easy', label: 'Easy', color: '#d6001c', vertical: 'specialty', isMarketplace: false, supportsCart: true, dominio: 'https://www.easy.com.ar' },
  Pigmento: { id: 'pigmento', label: 'Perfumerías Pigmento', color: '#e5007e', vertical: 'pharmacy', isMarketplace: false, supportsCart: true, dominio: 'https://www.perfumeriaspigmento.com.ar' },
  Farmacity: { id: 'farmacity', label: 'Farmacity', color: '#f97316', vertical: 'pharmacy', isMarketplace: false, supportsCart: true, dominio: 'https://www.farmacity.com' },
  Simplicity: { id: 'simplicity', label: 'Simplicity', color: '#c026d3', vertical: 'pharmacy', isMarketplace: false, supportsCart: true, dominio: 'https://www.simplicity.com.ar' },
  Farmaonline: { id: 'farmaonline', label: 'Farmaonline', color: '#0891b2', vertical: 'pharmacy', isMarketplace: false, supportsCart: true, dominio: 'https://www.farmaonline.com' },
  Farmaplus: { id: 'farmaplus', label: 'Farmaplus', color: '#0284c7', vertical: 'pharmacy', isMarketplace: false, supportsCart: true, dominio: 'https://www.farmaplus.com.ar' },
  Puppis: { id: 'puppis', label: 'Puppis', color: '#ff6b00', vertical: 'specialty', isMarketplace: false, supportsCart: true, dominio: 'https://www.puppis.com.ar' },
  Catycan: { id: 'catycan', label: 'Catycan', color: '#ff5500', vertical: 'specialty', isMarketplace: false, supportsCart: true, dominio: 'https://www.catycan.com.ar' },
  'Natural Life': { id: 'naturallife', label: 'Natural Life', color: '#16a34a', vertical: 'specialty', isMarketplace: false, supportsCart: true, dominio: 'https://www.natural-life.com.ar' },
  StyleStore: { id: 'stylestore', label: 'StyleStore', color: '#1a1a1a', vertical: 'specialty', isMarketplace: false, supportsCart: true, dominio: 'https://www.stylestore.com.ar' },
  'Bodegas Bianchi': { id: 'bodegasbianchi', label: 'Bodegas Bianchi', color: '#581845', vertical: 'specialty', isMarketplace: false, supportsCart: false, dominio: 'https://www.bodegasbianchi.com.ar' },
  LaBarraCCU: { id: 'labarraccu', label: 'La Barra', color: '#475569', vertical: 'specialty', isMarketplace: false, supportsCart: false, dominio: 'https://labarraccu.com.ar' },
  TonelPrivado: { id: 'tonelprivado', label: 'Tonel Privado', color: '#7c2d12', vertical: 'specialty', isMarketplace: false, supportsCart: false, dominio: 'https://www.tonelprivado.com' },
  DePastura: { id: 'depastura', label: 'De Pastura', color: '#b91c1c', vertical: 'specialty', isMarketplace: false, supportsCart: false, dominio: 'https://tienda.depastura.com.ar' },

  // --- Aliases comunes directamente mapeados en STORES para compatibilidad retroactiva directa ---
  ProvinciaCompras: { id: 'provinciacompras', label: 'Provincia Compras', color: '#008859', vertical: 'marketplace', isMarketplace: true, supportsCart: true, dominio: 'https://www.provinciacompras.com.ar' },
  provinciacompras: { id: 'provinciacompras', label: 'Provincia Compras', color: '#008859', vertical: 'marketplace', isMarketplace: true, supportsCart: true, dominio: 'https://www.provinciacompras.com.ar' },
  OnCity: { id: 'oncity', label: 'On City', color: '#001489', vertical: 'marketplace', isMarketplace: true, supportsCart: true, dominio: 'https://www.oncity.com' },
  oncity: { id: 'oncity', label: 'On City', color: '#001489', vertical: 'marketplace', isMarketplace: true, supportsCart: true, dominio: 'https://www.oncity.com' },
  'Frávega': { id: 'fravega', label: 'Frávega', color: '#4a154b', vertical: 'electro', isMarketplace: true, supportsCart: true, dominio: 'https://www.fravega.com' },
  fravega: { id: 'fravega', label: 'Frávega', color: '#4a154b', vertical: 'electro', isMarketplace: true, supportsCart: true, dominio: 'https://www.fravega.com' },
  'Moulinex / Tefal': { id: 'moulinex', label: 'Moulinex / Tefal', color: '#da291c', vertical: 'electro', isMarketplace: false, supportsCart: true, dominio: 'https://tienda.moulinex.com.ar' },
  'Moulinex/Tefal': { id: 'moulinex', label: 'Moulinex / Tefal', color: '#da291c', vertical: 'electro', isMarketplace: false, supportsCart: true, dominio: 'https://tienda.moulinex.com.ar' },
  'Sony Store': { id: 'sony', label: 'Sony Store', color: '#000000', vertical: 'electro', isMarketplace: false, supportsCart: true, dominio: 'https://store.sony.com.ar' },
  SonyStore: { id: 'sony', label: 'Sony Store', color: '#000000', vertical: 'electro', isMarketplace: false, supportsCart: true, dominio: 'https://store.sony.com.ar' },
  'Perfumerías Pigmento': { id: 'pigmento', label: 'Perfumerías Pigmento', color: '#e5007e', vertical: 'pharmacy', isMarketplace: false, supportsCart: true, dominio: 'https://www.perfumeriaspigmento.com.ar' },
  'Perfumerias Pigmento': { id: 'pigmento', label: 'Perfumerías Pigmento', color: '#e5007e', vertical: 'pharmacy', isMarketplace: false, supportsCart: true, dominio: 'https://www.perfumeriaspigmento.com.ar' },
  'Toledo Digital': { id: 'toledo', label: 'Toledo Digital', color: '#005ba4', vertical: 'supermarket', isMarketplace: false, supportsCart: true, dominio: 'https://www.toledodigital.com.ar' },
  ToledoDigital: { id: 'toledo', label: 'Toledo Digital', color: '#005ba4', vertical: 'supermarket', isMarketplace: false, supportsCart: true, dominio: 'https://www.toledodigital.com.ar' },
  'Food Market': { id: 'thefoodmarket', label: 'Food Market', color: '#d97706', vertical: 'supermarket', isMarketplace: false, supportsCart: true, dominio: 'https://www.thefoodmarket.com.ar' },
  BodegasBianchi: { id: 'bodegasbianchi', label: 'Bodegas Bianchi', color: '#581845', vertical: 'specialty', isMarketplace: false, supportsCart: false, dominio: 'https://www.bodegasbianchi.com.ar' },
  bodegasbianchi: { id: 'bodegasbianchi', label: 'Bodegas Bianchi', color: '#581845', vertical: 'specialty', isMarketplace: false, supportsCart: false, dominio: 'https://www.bodegasbianchi.com.ar' },
  'La Barra': { id: 'labarraccu', label: 'La Barra', color: '#475569', vertical: 'specialty', isMarketplace: false, supportsCart: false, dominio: 'https://labarraccu.com.ar' },
  'Arcor en Casa': { id: 'arcorencasa', label: 'Arcor en Casa', color: '#0284c7', vertical: 'supermarket', isMarketplace: false, supportsCart: false, dominio: 'https://arcorencasa.com' },
  catycan: { id: 'catycan', label: 'Catycan', color: '#ff5500', vertical: 'specialty', isMarketplace: false, supportsCart: true, dominio: 'https://www.catycan.com.ar' },
  'NaturalLife': { id: 'naturallife', label: 'Natural Life', color: '#16a34a', vertical: 'specialty', isMarketplace: false, supportsCart: true, dominio: 'https://www.natural-life.com.ar' },
  naturallife: { id: 'naturallife', label: 'Natural Life', color: '#16a34a', vertical: 'specialty', isMarketplace: false, supportsCart: true, dominio: 'https://www.natural-life.com.ar' },
}

export function normalizeStoreKey(s: string): string {
  if (!s) return ''
  return s
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim()
    .toLowerCase()
    .replace(/[\s_\-\/]+/g, '')
}

export function getStoreMeta(s: string): StoreMeta | undefined {
  if (!s) return undefined
  if (STORES[s]) return STORES[s]
  const clean = normalizeStoreKey(s)
  for (const [k, v] of Object.entries(STORES)) {
    if (
      normalizeStoreKey(k) === clean ||
      normalizeStoreKey(v.id) === clean ||
      normalizeStoreKey(v.label) === clean
    ) {
      return v
    }
  }
  return undefined
}

export const storeLabel = (s: string): string => getStoreMeta(s)?.label ?? s
export const storeColor = (s: string): string => getStoreMeta(s)?.color ?? '#64748b'
export const storeVertical = (s: string): StoreVertical => getStoreMeta(s)?.vertical ?? 'supermarket'
export const isMarketplaceStore = (s: string): boolean => Boolean(getStoreMeta(s)?.isMarketplace)
export const storeSupportsCart = (s: string): boolean => Boolean(getStoreMeta(s)?.supportsCart)

export const STORE_DOMAINS: Record<string, string> = Object.fromEntries(
  Object.entries(STORES)
    .filter(([_, meta]) => Boolean(meta.dominio))
    .map(([key, meta]) => [key, meta.dominio!])
)

export function getStoreDomain(s?: string | null): string {
  if (!s) return 'https://www.mercadolibre.com.ar'
  const meta = getStoreMeta(s)
  if (meta?.dominio) return meta.dominio
  return 'https://www.mercadolibre.com.ar'
}

export function resolveOutboundUrl(
  rawLink: string | null | undefined,
  store: string,
  productTitle?: string,
  sellerId?: string | null,
): string {
  let url = (rawLink || '').trim()
  const domain = getStoreDomain(store).replace(/\/+$/, '')

  if (url.startsWith('http://') || url.startsWith('https://')) {
    // Keep absolute
  } else if (url.startsWith('/')) {
    url = `${domain}${url}`
  } else if (url.length > 0) {
    url = `${domain}/${url}`
  } else {
    const q = productTitle ? encodeURIComponent(productTitle.trim()) : ''
    url = `${domain}/search?q=${q}`
  }

  if (sellerId && sellerId !== '1' && sellerId !== 'default' && !url.includes('seller=')) {
    const sep = url.includes('?') ? '&' : '?'
    url = `${url}${sep}seller=${encodeURIComponent(sellerId)}`
  }

  return url
}
