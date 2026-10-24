import { useState, useEffect, useMemo } from 'react'
import {
  Search,
  Loader2,
  ArrowUpDown,
  ShoppingBasket,
  Flame,
  Store,
  Tag,
  X,
  HelpCircle,
  CreditCard,
  Layers,
  MapPin,
  CheckCircle2,
} from 'lucide-react'
import ProductRow from './components/ProductRow'
import SmartCart from './components/SmartCart'
import { STORE_BRANDS } from './components/OfferCard'
import { useCart } from './cart/CartContext'
import { useLocation } from './location/LocationContext'
import { searchProducts, getStats } from './api'
import type { ProductGroup, StatsSummary } from './types'

const QUICK_TERMS = [
  'Pepsi',
  'Coca Cola',
  'Leche',
  'Aceite',
  'Azúcar',
  'Yerba',
  'Arroz',
  'Fideos',
  'Galletitas',
  'Cerveza',
  'Queso',
  'Café',
  'Shampoo',
]

type FilterMode = 'all' | 'multi_store' | 'all_offers' | 'bulk_offers' | 'direct_offers' | 'club_offers'

function App() {
  const [query, setQuery] = useState('')
  const [filterMode, setFilterMode] = useState<FilterMode>('multi_store')
  const [selectedStore, setSelectedStore] = useState<string>('')
  const [showGuide, setShowGuide] = useState(false)
  const [results, setResults] = useState<ProductGroup[]>([])
  const [stats, setStats] = useState<StatsSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [sortBy, setSortBy] = useState<'price_asc' | 'unit_price_asc'>('price_asc')
  const [debounced, setDebounced] = useState(query)
  const [cartOpen, setCartOpen] = useState(false)

  const { count, totalUnits } = useCart()
  const { cp, setCp, loading: cpLoading } = useLocation()
  const [cpInput, setCpInput] = useState(cp || '')

  useEffect(() => {
    if (cp) setCpInput(cp)
  }, [cp])

  const serverOnlyOffers =
    filterMode === 'all_offers' ||
    filterMode === 'bulk_offers' ||
    filterMode === 'direct_offers' ||
    filterMode === 'club_offers'

  useEffect(() => {
    getStats()
      .then(setStats)
      .catch(() => {})
  }, [])

  useEffect(() => {
    const t = setTimeout(() => setDebounced(query), 320)
    return () => clearTimeout(t)
  }, [query])

  useEffect(() => {
    let alive = true
    setLoading(true)
    const effectiveQuery = selectedStore ? `${debounced} ${selectedStore}`.trim() : debounced
    searchProducts(effectiveQuery, sortBy, serverOnlyOffers, cp)
      .then(data => {
        if (alive) {
          setResults(data)
          getStats().then(setStats).catch(() => {})
        }
      })
      .catch(() => {
        if (alive) setResults([])
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [debounced, selectedStore, sortBy, serverOnlyOffers, cp])

  const filteredResults = useMemo(() => {
    return results.filter(g => {
      if (selectedStore && !g.offers.some(o => o.supermercado === selectedStore)) {
        return false
      }
      if (filterMode === 'multi_store') {
        return debounced.trim().length > 0 ? true : g.offers.length >= 2
      }
      if (filterMode === 'bulk_offers') {
        return g.offers.some(
          o => (o.promo_min_qty || 1) > 1 || o.promo_type === 'NXM' || o.promo_type === 'BULK_PCT',
        )
      }
      if (filterMode === 'direct_offers') {
        return g.offers.some(
          o =>
            (o.discount >= 5 || o.promo_type === 'DIRECT') &&
            !o.requires_club &&
            (o.promo_min_qty || 1) === 1,
        )
      }
      if (filterMode === 'club_offers') {
        return g.offers.some(o => o.requires_club || o.promo_type === 'CLUB_PCT')
      }
      return true
    })
  }, [results, filterMode, selectedStore, debounced])

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans pb-20">
      {/* Header compacto en una sola pieza (estilo Ratoneando) */}
      <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-md border-b border-slate-200 shadow-2xs">
        <div className="container mx-auto px-3 sm:px-4 py-2 flex flex-wrap items-center justify-between gap-2.5">
          {/* Logo */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setQuery('')
                setSelectedStore('')
                setFilterMode('multi_store')
              }}
              className="text-xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-indigo-600"
            >
              SuperVmarket
            </button>
            <span
              title="Conectado en vivo a 12 cadenas"
              className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Live
            </span>
          </div>

          {/* Buscador central compacto */}
          <div className="relative flex-1 min-w-[220px] max-w-xl order-3 md:order-2 w-full md:w-auto">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <Search className="text-slate-400" size={16} />
            </div>
            <input
              type="text"
              className="block w-full pl-9 pr-16 py-1.5 border border-slate-200 rounded-xl bg-slate-50 text-slate-900 placeholder-slate-400 focus:outline-none focus:bg-white focus:border-blue-600 focus:ring-2 focus:ring-blue-500/15 transition-all font-medium text-xs sm:text-sm"
              placeholder="Buscar producto, marca o EAN (ej: Pepsi, Leche, Coca Cola)..."
              value={query}
              onChange={e => setQuery(e.target.value)}
            />
            <div className="absolute inset-y-0 right-0 pr-2 flex items-center gap-1">
              {query && (
                <button
                  type="button"
                  onClick={() => setQuery('')}
                  className="p-0.5 rounded text-slate-400 hover:text-slate-700"
                >
                  <X size={14} />
                </button>
              )}
              {loading && <Loader2 className="animate-spin text-blue-600" size={15} />}
            </div>
          </div>

          {/* Controles derechos: CP + Orden + Ayuda + Carrito */}
          <div className="flex items-center gap-1.5 order-2 md:order-3">
            {/* Selector compacto de CP integrado en la barra */}
            <form
              onSubmit={e => {
                e.preventDefault()
                if (cpInput.trim()) setCp(cpInput.trim())
              }}
              className="hidden sm:flex items-center bg-slate-100 rounded-lg px-2 py-1 border border-slate-200"
              title="Código Postal para validar stock y envío"
            >
              <MapPin size={13} className="text-blue-600 mr-1 shrink-0" />
              <input
                value={cpInput}
                onChange={e => setCpInput(e.target.value.replace(/\D/g, '').slice(0, 4))}
                placeholder="CP 1414"
                className="bg-transparent w-14 text-xs font-bold text-slate-800 placeholder-slate-400 focus:outline-none"
              />
              {cpLoading && <Loader2 className="animate-spin text-blue-600 ml-1" size={12} />}
            </form>

            <button
              type="button"
              onClick={() => setSortBy(p => (p === 'price_asc' ? 'unit_price_asc' : 'price_asc'))}
              className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-bold text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors"
              title="Cambiar criterio de ordenamiento"
            >
              <ArrowUpDown size={13} className="text-blue-600" />
              <span className="hidden sm:inline">
                {sortBy === 'price_asc' ? 'Menor precio' : 'Precio x Kg/L'}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setShowGuide(v => !v)}
              className={`p-1.5 rounded-lg border text-xs font-bold transition-colors ${
                showGuide
                  ? 'bg-blue-50 text-blue-600 border-blue-200'
                  : 'bg-slate-100 text-slate-500 border-transparent hover:text-slate-800'
              }`}
              title="¿Qué significan los colores de las ofertas?"
            >
              <HelpCircle size={15} />
            </button>

            <button
              type="button"
              onClick={() => setCartOpen(true)}
              className="relative flex items-center gap-1.5 px-3 py-1.5 text-xs font-extrabold text-white bg-blue-600 rounded-lg hover:bg-blue-700 shadow-2xs transition-colors"
            >
              <ShoppingBasket size={15} />
              <span>Mi lista</span>
              {count > 0 && (
                <span className="bg-amber-400 text-slate-950 text-[11px] font-extrabold px-1.5 rounded-full">
                  {totalUnits}
                </span>
              )}
            </button>
          </div>
        </div>

        {/* Única tira compacta de filtros + accesos rápidos */}
        <div className="border-t border-slate-100 bg-slate-50/80">
          <div className="container mx-auto px-3 sm:px-4 py-1.5 flex items-center justify-between gap-2 overflow-x-auto no-scrollbar text-[11px]">
            <div className="flex items-center gap-1 shrink-0">
              <button
                type="button"
                onClick={() => setFilterMode('multi_store')}
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg font-bold transition-colors ${
                  filterMode === 'multi_store'
                    ? 'bg-blue-600 text-white'
                    : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-100'
                }`}
              >
                <Layers size={12} /> 2+ Súper
              </button>

              <button
                type="button"
                onClick={() => setFilterMode('all')}
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg font-bold transition-colors ${
                  filterMode === 'all'
                    ? 'bg-slate-900 text-white'
                    : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-100'
                }`}
              >
                <Store size={12} /> Todos
              </button>

              <button
                type="button"
                onClick={() => setFilterMode('all_offers')}
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg font-bold transition-colors ${
                  filterMode === 'all_offers'
                    ? 'bg-orange-500 text-white'
                    : 'bg-orange-50 text-orange-800 border border-orange-200 hover:bg-orange-100'
                }`}
              >
                <Flame size={12} /> Ofertas
              </button>

              <button
                type="button"
                onClick={() => setFilterMode('bulk_offers')}
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg font-bold transition-colors ${
                  filterMode === 'bulk_offers'
                    ? 'bg-amber-500 text-slate-950'
                    : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-100'
                }`}
              >
                2x1 / 2do %
              </button>

              <button
                type="button"
                onClick={() => setFilterMode('direct_offers')}
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg font-bold transition-colors ${
                  filterMode === 'direct_offers'
                    ? 'bg-emerald-600 text-white'
                    : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-100'
                }`}
              >
                <Tag size={11} /> Dto. 1 un.
              </button>

              <button
                type="button"
                onClick={() => setFilterMode('club_offers')}
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg font-bold transition-colors ${
                  filterMode === 'club_offers'
                    ? 'bg-purple-600 text-white'
                    : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-100'
                }`}
              >
                <CreditCard size={11} /> Club/Tarjeta
              </button>

              <span className="mx-1 text-slate-300">|</span>

              {QUICK_TERMS.map(term => {
                const active = query.toLowerCase() === term.toLowerCase()
                return (
                  <button
                    key={term}
                    type="button"
                    onClick={() => setQuery(active ? '' : term)}
                    className={`px-2 py-0.5 rounded-md font-semibold transition-colors ${
                      active
                        ? 'bg-blue-100 text-blue-800 font-bold'
                        : 'text-slate-500 hover:text-slate-900 hover:bg-slate-200/60'
                    }`}
                  >
                    {term}
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-3 sm:px-4 py-3 max-w-7xl">
        {/* Leyenda compacta si el usuario toca el botón (?) */}
        {showGuide && (
          <div className="mb-3 bg-white rounded-xl border border-slate-200 p-3 flex flex-wrap items-center justify-between gap-2 text-xs shadow-2xs">
            <div className="flex flex-wrap items-center gap-3">
              <span className="inline-flex items-center gap-1.5 font-semibold text-slate-700">
                <span className="px-1.5 py-0.5 rounded bg-emerald-600 text-white text-[10px] font-extrabold">
                  MÁS BARATO
                </span>
                Menor precio comprando 1 unidad
              </span>
              <span className="inline-flex items-center gap-1.5 font-semibold text-slate-700">
                <span className="px-1.5 py-0.5 rounded bg-orange-500 text-white text-[10px] font-extrabold">
                  2x1 / 2do al %
                </span>
                Precio c/u llevando cantidad mínima
              </span>
              <span className="inline-flex items-center gap-1.5 font-semibold text-slate-700">
                <span className="px-1.5 py-0.5 rounded bg-purple-600 text-white text-[10px] font-extrabold">
                  Club / Tarjeta
                </span>
                Exclusivo Comunidad Coto / Mi Carrefour / Club DIA
              </span>
            </div>
            <button
              type="button"
              onClick={() => setShowGuide(false)}
              className="text-slate-400 hover:text-slate-600 font-bold"
            >
              ✕
            </button>
          </div>
        )}

        {/* Tira opcional muy finita de cadenas */}
        {stats && stats.tiendas.length > 0 && (
          <div className="mb-2.5 flex items-center justify-between gap-2 overflow-x-auto no-scrollbar text-[11px]">
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setSelectedStore('')}
                className={`px-2 py-0.5 rounded-md font-bold whitespace-nowrap ${
                  selectedStore === ''
                    ? 'bg-slate-800 text-white'
                    : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-100'
                }`}
              >
                Todas ({stats.tiendas.length})
              </button>
              {stats.tiendas.map(t => {
                const active = selectedStore === t.supermercado
                const b = STORE_BRANDS[t.supermercado]
                return (
                  <button
                    key={t.supermercado}
                    type="button"
                    onClick={() => setSelectedStore(active ? '' : t.supermercado)}
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md font-semibold whitespace-nowrap border transition-colors ${
                      active
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'bg-white text-slate-600 border-slate-200/80 hover:border-slate-300'
                    }`}
                  >
                    <span
                      className={`w-1.5 h-1.5 rounded-full ${
                        active ? 'bg-white' : b?.dot || 'bg-slate-400'
                      }`}
                    />
                    {t.supermercado}
                  </button>
                )
              })}
            </div>

            <span className="text-[11px] text-slate-400 font-medium whitespace-nowrap hidden md:inline">
              {filteredResults.length} productos en pantalla
            </span>
          </div>
        )}

        {/* Lista compacta de productos (4 a 5 filas visibles por pantalla) */}
        {filteredResults.map(group => (
          <ProductRow key={group.ean} group={group} />
        ))}

        {!loading && filteredResults.length === 0 && (
          <div className="bg-white rounded-xl border border-slate-200 p-8 text-center my-4">
            <p className="text-sm font-bold text-slate-700">
              No se encontraron productos con ese filtro
            </p>
            <button
              type="button"
              onClick={() => {
                setFilterMode('all')
                setSelectedStore('')
              }}
              className="mt-2 px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-bold hover:bg-blue-700"
            >
              Ver todos los productos
            </button>
          </div>
        )}
      </main>

      {/* Barra inferior compacta para optimizar lista */}
      {count > 0 && !cartOpen && (
        <div className="fixed bottom-3 inset-x-0 z-30 px-4 pointer-events-none">
          <div className="max-w-md mx-auto bg-slate-900 text-white rounded-xl px-3.5 py-2.5 shadow-xl border border-slate-700 flex items-center justify-between gap-3 pointer-events-auto">
            <div className="flex items-center gap-2 text-xs">
              <CheckCircle2 size={15} className="text-emerald-400 shrink-0" />
              <span>
                <strong>{count}</strong> prod. ({totalUnits} un.) en tu lista
              </span>
            </div>
            <button
              type="button"
              onClick={() => setCartOpen(true)}
              className="px-3 py-1.5 rounded-lg bg-amber-400 hover:bg-amber-300 text-slate-950 font-extrabold text-xs whitespace-nowrap transition-colors"
            >
              Optimizar Carrito →
            </button>
          </div>
        </div>
      )}

      <SmartCart open={cartOpen} onClose={() => setCartOpen(false)} />
    </div>
  )
}

export default App
