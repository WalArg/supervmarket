import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Search, X, ScanBarcode, ArrowUpDown, Flame, Layers, Clock, TrendingUp, SearchX } from 'lucide-react'
import ProductCard from './ProductCard'
import BarcodeScanner from './BarcodeScanner'
import { searchProducts } from '../api'
import { useLocation } from '../location/LocationContext'
import type { ProductGroup } from '../types'

const POPULAR = ['Leche', 'Coca Cola', 'Yerba', 'Aceite', 'Fideos', 'Café', 'Pañales', 'Arroz', 'Cerveza', 'Detergente', 'Papel higiénico', 'Azúcar']
const RECENT_KEY = 'sv_recent_v1'

type Sort = 'unit_price_asc' | 'price_asc'

const loadRecent = (): string[] => {
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]')
  } catch {
    return []
  }
}

const Chip: React.FC<{ active: boolean; onClick: () => void; children: React.ReactNode }> = ({ active, onClick, children }) => (
  <button
    type="button"
    onClick={onClick}
    className={`shrink-0 h-8 px-3 rounded-full text-[13px] font-semibold flex items-center gap-1.5 border transition-colors ${
      active ? 'bg-slate-900 text-white border-slate-900' : 'bg-white text-slate-700 border-slate-200 active:bg-slate-100'
    }`}
  >
    {children}
  </button>
)

const SearchScreen: React.FC = () => {
  const { cp } = useLocation()
  const [query, setQuery] = useState('')
  const [debounced, setDebounced] = useState('')
  const [results, setResults] = useState<ProductGroup[]>([])
  const [loading, setLoading] = useState(false)
  const [sort, setSort] = useState<Sort>('unit_price_asc')
  const [onlyOffers, setOnlyOffers] = useState(false)
  const [onlyBulk, setOnlyBulk] = useState(false)
  const [onlyMulti, setOnlyMulti] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [recent, setRecent] = useState<string[]>(loadRecent)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), 350)
    return () => clearTimeout(t)
  }, [query])

  const pushRecent = useCallback((q: string) => {
    if (q.length < 2 || /^\d{8,14}$/.test(q)) return
    setRecent(prev => {
      const next = [q, ...prev.filter(x => x.toLowerCase() !== q.toLowerCase())].slice(0, 8)
      localStorage.setItem(RECENT_KEY, JSON.stringify(next))
      return next
    })
  }, [])

  useEffect(() => {
    if (debounced.length < 2) {
      setResults([])
      setLoading(false)
      return
    }
    let alive = true
    setLoading(true)
    searchProducts(debounced, sort, onlyOffers, cp)
      .then(data => {
        if (!alive) return
        setResults(data)
        if (data.length) pushRecent(debounced)
      })
      .catch(() => alive && setResults([]))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
  }, [debounced, sort, onlyOffers, cp, pushRecent])

  const visible = useMemo(
    () =>
      results.filter(g => {
        if (onlyOffers && !g.offers.some(o => (o.discount >= 5) || (o.promo_label && !o.requires_club))) return false
        if (onlyMulti && g.offers.length < 2) return false
        if (onlyBulk && !g.offers.some(o => (o.promo_min_qty || 1) > 1 && !o.requires_club)) return false
        return true
      }),
    [results, onlyOffers, onlyMulti, onlyBulk],
  )

  const runSearch = (q: string) => {
    setQuery(q)
    setDebounced(q)
    inputRef.current?.blur()
    window.scrollTo({ top: 0 })
  }

  const onScan = useCallback((ean: string) => {
    setScanning(false)
    setQuery(ean)
    setDebounced(ean)
  }, [])

  const hasQuery = debounced.length >= 2

  return (
    <div>
      {/* Header fijo con buscador */}
      <header className="sticky top-0 z-30 bg-slate-50/95 backdrop-blur-md pt-safe">
        <div className="px-4 pt-3 pb-2">
          <div className="flex items-center justify-between mb-2.5">
            <h1 className="text-[20px] font-extrabold tracking-tight">
              Super<span className="text-blue-600">V</span>market
            </h1>
            {cp && <span className="text-[12px] font-semibold text-slate-500">CP {cp}</span>}
          </div>
          <form
            onSubmit={e => {
              e.preventDefault()
              runSearch(query.trim())
            }}
            className="flex items-center gap-2"
          >
            <div className="relative flex-1">
              <Search size={18} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                ref={inputRef}
                type="search"
                inputMode="search"
                enterKeyHint="search"
                autoComplete="off"
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="¿Qué querés comprar?"
                className="w-full h-12 pl-11 pr-10 rounded-2xl bg-white border border-slate-200 text-base font-medium placeholder:text-slate-400 focus:outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10"
              />
              {query && (
                <button
                  type="button"
                  aria-label="Borrar"
                  onClick={() => {
                    setQuery('')
                    setDebounced('')
                    inputRef.current?.focus()
                  }}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-full text-slate-400 active:bg-slate-100"
                >
                  <X size={18} />
                </button>
              )}
            </div>
            <button
              type="button"
              onClick={() => setScanning(true)}
              aria-label="Escanear código de barras"
              className="h-12 w-12 shrink-0 rounded-2xl bg-blue-600 text-white flex items-center justify-center active:bg-blue-700"
            >
              <ScanBarcode size={22} />
            </button>
          </form>
        </div>

        {hasQuery && (
          <div className="px-4 pb-2.5 flex gap-2 overflow-x-auto no-scrollbar">
            <Chip active={false} onClick={() => setSort(s => (s === 'unit_price_asc' ? 'price_asc' : 'unit_price_asc'))}>
              <ArrowUpDown size={14} />
              {sort === 'unit_price_asc' ? 'Precio por kg/l' : 'Precio final'}
            </Chip>
            <Chip active={onlyOffers} onClick={() => setOnlyOffers(v => !v)}>
              <Flame size={14} /> Ofertas
            </Chip>
            <Chip active={onlyBulk} onClick={() => setOnlyBulk(v => !v)}>
              2x1 · 3x2 · 2do %
            </Chip>
            <Chip active={onlyMulti} onClick={() => setOnlyMulti(v => !v)}>
              <Layers size={14} /> En 2+ súper
            </Chip>
          </div>
        )}
      </header>

      <main className="px-4 pt-1 pb-28 space-y-3">
        {/* Inicio sin búsqueda */}
        {!hasQuery && (
          <div className="space-y-6 pt-2">
            {recent.length > 0 && (
              <section>
                <div className="flex items-center justify-between mb-2">
                  <h2 className="text-[13px] font-bold text-slate-500 flex items-center gap-1.5">
                    <Clock size={14} /> Búsquedas recientes
                  </h2>
                  <button
                    type="button"
                    onClick={() => {
                      setRecent([])
                      localStorage.removeItem(RECENT_KEY)
                    }}
                    className="text-[12px] font-semibold text-slate-400"
                  >
                    Borrar
                  </button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {recent.map(r => (
                    <button
                      key={r}
                      type="button"
                      onClick={() => runSearch(r)}
                      className="h-9 px-3.5 rounded-full bg-white border border-slate-200 text-[14px] font-medium text-slate-800 active:bg-slate-100"
                    >
                      {r}
                    </button>
                  ))}
                </div>
              </section>
            )}

            <section>
              <h2 className="text-[13px] font-bold text-slate-500 flex items-center gap-1.5 mb-2">
                <TrendingUp size={14} /> Lo más buscado
              </h2>
              <div className="flex flex-wrap gap-2">
                {POPULAR.map(p => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => runSearch(p)}
                    className="h-9 px-3.5 rounded-full bg-white border border-slate-200 text-[14px] font-medium text-slate-800 active:bg-slate-100"
                  >
                    {p}
                  </button>
                ))}
              </div>
            </section>

            <button
              type="button"
              onClick={() => setScanning(true)}
              className="w-full rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-600 text-white p-4 flex items-center gap-3 text-left active:opacity-90"
            >
              <div className="w-11 h-11 rounded-xl bg-white/15 flex items-center justify-center shrink-0">
                <ScanBarcode size={24} />
              </div>
              <div>
                <div className="font-extrabold text-[15px]">¿Estás en el súper?</div>
                <div className="text-[13px] text-blue-100">Escaneá un producto y fijate si en otro lado está más barato.</div>
              </div>
            </button>

            <p className="text-[12px] text-slate-400 text-center px-6">
              Comparamos en vivo Carrefour, Coto, Día, Jumbo, Disco, Vea, Más Online, Farmacity y más.
            </p>
          </div>
        )}

        {/* Cargando */}
        {hasQuery && loading && results.length === 0 &&
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-white rounded-2xl border border-slate-200/80 p-3 flex gap-3 animate-pulse">
              <div className="w-[72px] h-[72px] rounded-xl bg-slate-100" />
              <div className="flex-1 space-y-2 py-1">
                <div className="h-3 w-1/3 bg-slate-100 rounded" />
                <div className="h-4 w-4/5 bg-slate-100 rounded" />
                <div className="h-6 w-1/2 bg-slate-100 rounded mt-3" />
              </div>
            </div>
          ))}

        {hasQuery && !loading && visible.length === 0 && (
          <div className="text-center py-14 px-6">
            <SearchX size={40} className="mx-auto text-slate-300" />
            <p className="mt-3 font-bold text-slate-700">No encontramos "{debounced}" con stock</p>
            <p className="text-[13px] text-slate-500 mt-1">Probá con otra palabra o sacá los filtros.</p>
          </div>
        )}

        {hasQuery && visible.length > 0 && (
          <div className={`space-y-3 transition-opacity ${loading ? 'opacity-50' : ''}`}>
            <p className="text-[12px] font-semibold text-slate-400 px-1">
              {visible.length} productos · ordenados por {sort === 'unit_price_asc' ? 'precio por kg/l/unidad' : 'precio final'}
            </p>
            {visible.map(g => (
              <ProductCard key={g.ean} group={g} />
            ))}
          </div>
        )}
      </main>

      {scanning && <BarcodeScanner onDetected={onScan} onClose={() => setScanning(false)} />}
    </div>
  )
}

export default SearchScreen
