/** Nombre visible y color de marca de cada cadena (nombres cortos para que no se corten en mobile). */
export const STORES: Record<string, { label: string; color: string }> = {
  Carrefour: { label: 'Carrefour', color: '#1d4ed8' },
  Coto: { label: 'Coto', color: '#dc2626' },
  Dia: { label: 'Día', color: '#e11d48' },
  Jumbo: { label: 'Jumbo', color: '#16a34a' },
  Disco: { label: 'Disco', color: '#db2777' },
  Vea: { label: 'Vea', color: '#15803d' },
  Masonline: { label: 'Más Online', color: '#0d9488' },
  Farmacity: { label: 'Farmacity', color: '#f97316' },
  Simplicity: { label: 'Simplicity', color: '#c026d3' },
  Farmaonline: { label: 'Farmaonline', color: '#0891b2' },
  Farmaplus: { label: 'Farmaplus', color: '#0284c7' },
  TheFoodMarket: { label: 'Food Market', color: '#d97706' },
  LaBarraCCU: { label: 'La Barra', color: '#475569' },
  MercadoLibre: { label: 'Mercado Libre', color: '#eab308' },
  LaBarata: { label: 'La Barata', color: '#16a34a' },
}

export const storeLabel = (s: string) => STORES[s]?.label ?? s
export const storeColor = (s: string) => STORES[s]?.color ?? '#64748b'
