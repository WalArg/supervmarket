import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Search, X, ScanBarcode, ArrowUpDown, Flame, Layers, SearchX, MapPin, ChevronDown, Store, Check, Sparkles } from 'lucide-react'
import ProductCard from './ProductCard'
import BarcodeScanner from './BarcodeScanner'
import SponsoredProductBox from './SponsoredProductBox'
import { searchProducts } from '../api'
import { useLocation } from '../location/LocationContext'
import { SPONSORED_CONFIG } from '../lib/sponsoredConfig'
import { storeColor, storeLabel, storeVertical, type StoreVertical } from '../lib/stores'
import type { ProductGroup } from '../types'

type Sort = 'unit_price_asc' | 'price_asc'

export type VerticalFilter = 'all' | 'supermarket' | 'marketplace_electro'

interface VerticalChipDef {
  id: VerticalFilter
  label: string
  queryParam?: string
  groceryOnly?: boolean
}

const VERTICAL_CHIPS: VerticalChipDef[] = [
  { id: 'all', label: 'Todos' },
  { id: 'supermarket', label: 'Supermercados', queryParam: 'supermarket', groceryOnly: true },
  { id: 'marketplace_electro', label: 'Marketplaces / Electro', queryParam: 'marketplace,electro', groceryOnly: false },
]

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
  const { cp, locationLabel, openModal } = useLocation()
  const [query, setQuery] = useState('')
  const [debounced, setDebounced] = useState('')
  const [results, setResults] = useState<ProductGroup[]>([])
  const [loading, setLoading] = useState(false)
  const [sort, setSort] = useState<Sort>('unit_price_asc')
  const [onlyOffers, setOnlyOffers] = useState(false)
  const [onlyBulk, setOnlyBulk] = useState(false)
  const [onlyMulti, setOnlyMulti] = useState(false)
  const [selectedVertical, setSelectedVertical] = useState<VerticalFilter>('all')
  const [selectedStore, setSelectedStore] = useState<string | null>(null)
  const [storeDropdownOpen, setStoreDropdownOpen] = useState(false)
  const [scanning, setScanning] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleVerticalChange = (v: VerticalFilter) => {
    setSelectedVertical(v)
    setSelectedStore(null)
  }

  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), 350)
    return () => clearTimeout(t)
  }, [query])

  useEffect(() => {
    if (debounced.length < 2) {
      setResults([])
      setLoading(false)
      setSelectedStore(null)
      return
    }
    let alive = true
    setLoading(true)
    const vertChip = VERTICAL_CHIPS.find(c => c.id === selectedVertical)
    searchProducts(debounced, sort, onlyOffers, cp, {
      vertical: vertChip?.queryParam || null,
      grocery_only: vertChip?.groceryOnly ?? false,
    })
      .then(data => {
        if (!alive) return
        setResults(data)
      })
      .catch(() => alive && setResults([]))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
  }, [debounced, sort, onlyOffers, cp, selectedVertical])

  // Lista de comercios presentes en los resultados de búsqueda para filtrado
  const availableStores = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const g of results) {
      const storesInProd = new Set(g.offers.map(o => o.supermercado))
      for (const s of storesInProd) {
        counts[s] = (counts[s] || 0) + 1
      }
    }
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .map(([store, count]) => ({ store, count }))
  }, [results])

  // Deseleccionar comercio si deja de existir en los nuevos resultados
  useEffect(() => {
    if (selectedStore && !availableStores.some(s => s.store === selectedStore)) {
      setSelectedStore(null)
    }
  }, [availableStores, selectedStore])

  const visible = useMemo(
    () =>
      results.filter(g => {
        if (selectedStore && !g.offers.some(o => o.supermercado === selectedStore)) return false
        if (selectedVertical !== 'all') {
          const chip = VERTICAL_CHIPS.find(c => c.id === selectedVertical)
          if (chip?.queryParam) {
            const allowedVerts = chip.queryParam.split(',')
            const matchesVertical =
              (g.vertical && allowedVerts.includes(g.vertical)) ||
              g.offers.some(o => allowedVerts.includes(o.vertical || storeVertical(o.supermercado)))
            if (!matchesVertical) return false
          }
        }
        if (onlyOffers && !g.offers.some(o => (o.discount >= 5) || (o.promo_label && !o.requires_club))) return false
        if (onlyMulti && g.offers.length < 2) return false
        if (onlyBulk && !g.offers.some(o => (o.promo_min_qty || 1) > 1 && !o.requires_club)) return false
        return true
      }),
    [results, selectedStore, selectedVertical, onlyOffers, onlyMulti, onlyBulk],
  )

  const groupedStores = useMemo(() => {
    const order: { key: StoreVertical; title: string }[] = [
      { key: 'supermarket', title: 'Supermercados' },
      { key: 'marketplace', title: 'Marketplaces Generales' },
      { key: 'electro', title: 'Electro y Tecnología' },
      { key: 'pharmacy', title: 'Farmacias y Perfumería' },
      { key: 'specialty', title: 'Hogar y Especialidades' },
    ]
    const res: { title: string; stores: { store: string; count: number }[] }[] = []
    for (const cat of order) {
      const matched = availableStores.filter(s => storeVertical(s.store) === cat.key)
      if (matched.length > 0) {
        res.push({ title: cat.title, stores: matched })
      }
    }
    const assigned = new Set(res.flatMap(g => g.stores.map(s => s.store)))
    const unassigned = availableStores.filter(s => !assigned.has(s.store))
    if (unassigned.length > 0) {
      res.push({ title: 'Otros Comercios', stores: unassigned })
    }
    return res
  }, [availableStores])

  // Detecta el producto para el recuadro patrocinado (Mercado Libre)
  const sponsoredCandidate = useMemo(() => {
    const qTokens = debounced
      .toLowerCase()
      .split(/\s+/)
      .map(t => t.trim())
      .filter(t => t.length >= 3)

    const matchesQuery = (group: ProductGroup) => {
      if (qTokens.length === 0) return true
      const prodText = `${group.nombre} ${group.marca}`.toLowerCase()
      return qTokens.some(tok => prodText.includes(tok))
    }

    // 1. Prioridad: Oferta patrocinada de FULL SÚPER que coincida temáticamente
    for (const group of visible) {
      if (!matchesQuery(group)) continue
      const fullOffer = group.offers.find(
        o => SPONSORED_CONFIG.isStoreSponsored(o.supermercado) && o.is_full === true,
      )
      if (fullOffer) {
        return { product: group, offer: fullOffer }
      }
    }

    // 2. Fallback: Si no hay oferta FULL en la búsqueda, tomar la mejor oferta de Mercado Libre que coincida
    for (const group of visible) {
      if (!matchesQuery(group)) continue
      const storeOffer = group.offers.find(
        o => SPONSORED_CONFIG.isStoreSponsored(o.supermercado),
      )
      if (storeOffer) {
        return { product: group, offer: storeOffer }
      }
    }

    return null
  }, [visible, debounced])

  const runSearch = (q: string) => {
    setSelectedStore(null)
    setStoreDropdownOpen(false)
    setQuery(q)
    setDebounced(q)
    inputRef.current?.blur()
    window.scrollTo({ top: 0 })
  }

  const onScan = useCallback((ean: string) => {
    setScanning(false)
    setSelectedStore(null)
    setStoreDropdownOpen(false)
    setQuery(ean)
    setDebounced(ean)
  }, [])

  const hasQuery = debounced.length >= 2

  return (
    <div className="pb-28">
      {/* HEADER DINÁMICO: Centrado inicialmente y sticky arriba cuando hay búsqueda */}
      <header
        className={`transition-all duration-300 ${
          hasQuery
            ? 'sticky top-0 z-30 bg-slate-50/95 backdrop-blur-md pt-safe border-b border-slate-100/90 shadow-2xs'
            : 'pt-safe'
        }`}
      >
        <div className="px-4 pt-3 pb-2.5">
          {/* Fila superior: Logo y selector de ubicación */}
          <div className="flex items-center justify-between mb-2">
            <h1
              onClick={() => {
                setQuery('')
                setDebounced('')
                setSelectedStore(null)
              }}
              className="text-[20px] font-extrabold tracking-tight cursor-pointer"
            >
              Super<span className="text-blue-600">V</span>market
            </h1>
            <button
              type="button"
              onClick={openModal}
              className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-blue-50/90 hover:bg-blue-100/80 border border-blue-200/80 text-blue-700 text-[11px] font-bold active:scale-95 transition-all max-w-[200px] shadow-2xs"
            >
              <MapPin size={12} className="text-blue-600 shrink-0" />
              <span className="truncate">{locationLabel || (cp ? `CP ${cp}` : 'Elegir zona')}</span>
              <ChevronDown size={11} className="text-blue-500 shrink-0" />
            </button>
          </div>

          {/* Hero Branding centrado: Visible únicamente en el estado inicial sin búsqueda */}
          {!hasQuery && (
            <div className="pt-8 pb-4 text-center animate-in fade-in zoom-in-95 duration-300">
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-50 border border-blue-200 text-blue-700 text-[11.5px] font-bold mb-3 shadow-2xs">
                <Sparkles size={13} className="text-blue-600" /> Compará precios de supermercados
              </div>
              <h2 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight leading-tight">
                Encontrá el mejor precio
              </h2>
              <p className="text-[13.5px] text-slate-500 font-medium max-w-sm mx-auto mt-1">
                Buscá por producto, marca o escaneá con la cámara de tu celular.
              </p>
            </div>
          )}

          {/* Formulario de búsqueda centrado (sin botón de escáner al inicio) / sticky arriba con escáner */}
          <form
            onSubmit={e => {
              e.preventDefault()
              runSearch(query.trim())
            }}
            className={`flex items-center gap-2 transition-all duration-300 ${
              !hasQuery ? 'max-w-lg mx-auto mt-2' : ''
            }`}
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
                placeholder="Buscá o escaneá el producto que querés buscar..."
                className={`w-full pl-11 pr-10 rounded-2xl bg-white border text-base font-medium placeholder:text-slate-400 focus:outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 transition-all ${
                  hasQuery
                    ? 'h-12 border-slate-200'
                    : 'h-14 border-slate-300/80 shadow-xs focus:border-blue-500'
                }`}
              />
              {query && (
                <button
                  type="button"
                  aria-label="Borrar"
                  onClick={() => {
                    setQuery('')
                    setDebounced('')
                    setSelectedStore(null)
                    inputRef.current?.focus()
                  }}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-full text-slate-400 active:bg-slate-100"
                >
                  <X size={18} />
                </button>
              )}
            </div>

            {/* Botón de escáner a la derecha del buscador: Solo cuando el usuario busca */}
            {hasQuery && (
              <button
                type="button"
                onClick={() => setScanning(true)}
                aria-label="Escanear código de barras"
                className="h-12 w-12 shrink-0 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white flex items-center justify-center active:scale-95 transition-all shadow-md animate-in fade-in duration-200"
              >
                <ScanBarcode size={22} />
              </button>
            )}
          </form>
        </div>

        {/* Selector de Verticales (WCAG 2.5.5 touch target >= 44px) */}
        {hasQuery && (
          <div className="px-4 pb-2 pt-0.5 flex items-center gap-2 overflow-x-auto no-scrollbar animate-in fade-in duration-200">
            {VERTICAL_CHIPS.map(chip => {
              const isActive = selectedVertical === chip.id
              return (
                <button
                  key={chip.id}
                  type="button"
                  onClick={() => handleVerticalChange(chip.id)}
                  className={`shrink-0 min-h-[44px] h-11 px-4 rounded-full text-[13px] font-bold flex items-center gap-1.5 border transition-all active:scale-95 shadow-2xs ${
                    isActive
                      ? 'bg-blue-600 text-white border-blue-600 shadow-xs'
                      : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
                  }`}
                >
                  <span>{chip.label}</span>
                </button>
              )
            })}
          </div>
        )}

        {/* Filtros generales y Desplegable de Comercios (solo cuando hay búsqueda) */}
        {hasQuery && (
          <div className="px-4 pb-2.5 flex items-center gap-2 overflow-x-auto no-scrollbar animate-in fade-in duration-200">
            {/* Botón activador del Desplegable de Comercios */}
            {availableStores.length > 0 && (
              <button
                type="button"
                id="store-filter-dropdown"
                aria-haspopup="listbox"
                aria-expanded={storeDropdownOpen}
                onClick={() => setStoreDropdownOpen(v => !v)}
                className={`shrink-0 h-8 px-3 rounded-full text-[13px] font-semibold flex items-center gap-1.5 border transition-all ${
                  selectedStore
                    ? 'bg-blue-600 text-white border-blue-600 shadow-xs font-bold'
                    : 'bg-white text-slate-700 border-slate-200 active:bg-slate-100'
                }`}
              >
                {selectedStore ? (
                  <>
                    <span
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{ background: '#ffffff' }}
                    />
                    <span>{storeLabel(selectedStore)}</span>
                    <ChevronDown
                      size={13}
                      className={`transition-transform duration-200 ${
                        storeDropdownOpen ? 'rotate-180' : ''
                      }`}
                    />
                  </>
                ) : (
                  <>
                    <Store size={14} className="text-slate-500" />
                    <span>Comercio: Todos</span>
                    <ChevronDown
                      size={13}
                      className={`transition-transform duration-200 ${
                        storeDropdownOpen ? 'rotate-180' : ''
                      }`}
                    />
                  </>
                )}
              </button>
            )}

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

        {/* Menú Desplegable de Comercios */}
        {storeDropdownOpen && (
          <>
            <div
              className="fixed inset-0 z-40 bg-slate-900/20 backdrop-blur-[1px]"
              onClick={() => setStoreDropdownOpen(false)}
              aria-hidden="true"
            />
            <div
              role="listbox"
              aria-labelledby="store-filter-dropdown"
              className="absolute left-4 top-full mt-1.5 z-50 w-72 max-w-[calc(100vw-2rem)] bg-white rounded-2xl shadow-xl border border-slate-200/90 py-2 px-1 flex flex-col max-h-[60vh] animate-in fade-in slide-in-from-top-2 duration-150"
            >
              <div className="flex items-center justify-between px-3 py-1.5 pb-2 border-b border-slate-100">
                <span className="text-[12px] font-bold text-slate-500 uppercase tracking-wider">
                  Filtrar por comercio
                </span>
                <button
                  type="button"
                  onClick={() => setStoreDropdownOpen(false)}
                  className="p-1 -mr-1 rounded-full text-slate-400 hover:text-slate-600 active:bg-slate-100"
                  aria-label="Cerrar"
                >
                  <X size={16} />
                </button>
              </div>

              <div className="overflow-y-auto divide-y divide-slate-50 py-1 overscroll-contain">
                <button
                  type="button"
                  role="option"
                  aria-selected={selectedStore === null}
                  onClick={() => {
                    setSelectedStore(null)
                    setStoreDropdownOpen(false)
                  }}
                  className={`w-full py-2.5 px-2.5 rounded-xl text-left flex items-center justify-between transition-colors min-h-[44px] ${
                    selectedStore === null
                      ? 'bg-blue-50 text-blue-700 font-bold'
                      : 'text-slate-700 hover:bg-slate-50 active:bg-slate-100'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-slate-400 shrink-0" />
                    <span className="text-[13px]">Todos los comercios</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-normal text-slate-400">({results.length})</span>
                    {selectedStore === null && <Check size={16} strokeWidth={2.5} className="text-blue-600" />}
                  </div>
                </button>

                {groupedStores.map(cat => (
                  <div key={cat.title} className="py-1">
                    <div className="px-2.5 py-1 text-[10.5px] font-extrabold uppercase tracking-wider text-slate-400 bg-slate-50/80 rounded-md mb-0.5">
                      {cat.title}
                    </div>
                    {cat.stores.map(({ store, count }) => {
                      const isSel = selectedStore === store
                      return (
                        <button
                          key={store}
                          type="button"
                          role="option"
                          aria-selected={isSel}
                          onClick={() => {
                            setSelectedStore(store)
                            setStoreDropdownOpen(false)
                          }}
                          className={`w-full py-2.5 px-2.5 rounded-xl text-left flex items-center justify-between transition-colors min-h-[44px] ${
                            isSel
                              ? 'bg-blue-50 text-blue-700 font-bold'
                              : 'text-slate-700 hover:bg-slate-50 active:bg-slate-100'
                          }`}
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            <span
                              className="w-2.5 h-2.5 rounded-full shrink-0"
                              style={{ background: storeColor(store) }}
                            />
                            <span className="text-[13px] truncate">{storeLabel(store)}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-[11px] font-normal text-slate-400">({count})</span>
                            {isSel && <Check size={16} strokeWidth={2.5} className="text-blue-600" />}
                          </div>
                        </button>
                      )
                    })}
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </header>

      {/* CONTENIDO PRINCIPAL */}
      <main className="px-4 pt-2 space-y-4">
        {/* VISTA INICIAL CENTRADA EN BUSCAR Y ESCANEAR (sin búsquedas habituales) */}
        {!hasQuery && (
          <div className="space-y-6 pt-2 max-w-lg mx-auto">
            {/* Banner escáner centrado */}
            <button
              type="button"
              onClick={() => setScanning(true)}
              className="w-full rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-600 text-white p-4 flex items-center gap-3.5 text-left active:scale-[0.99] transition-all shadow-md hover:shadow-lg"
            >
              <div className="w-12 h-12 rounded-xl bg-white/15 backdrop-blur-xs flex items-center justify-center shrink-0">
                <ScanBarcode size={26} />
              </div>
              <div className="flex-1">
                <div className="font-extrabold text-[15.5px]">¿Estás en el súper?</div>
                <div className="text-[13px] text-blue-100 leading-snug mt-0.5">
                  Escaneá el código de barras y fijate si en otro lado está más barato.
                </div>
              </div>
            </button>

            {/* Explorar por categoría con acceso rápido */}
            <div className="space-y-2.5 pt-1">
              <h3 className="text-[12.5px] font-black tracking-tight text-slate-800 uppercase px-1">
                Explorar por categoría
              </h3>
              <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
                {[
                  { label: 'Almacén', icon: '🧺', q: 'almacen', bg: 'bg-amber-50 hover:bg-amber-100/80 border-amber-200/80 text-amber-900' },
                  { label: 'Lácteos', icon: '🥛', q: 'leche', bg: 'bg-sky-50 hover:bg-sky-100/80 border-sky-200/80 text-sky-900' },
                  { label: 'Bebidas', icon: '🍷', q: 'bebidas', bg: 'bg-purple-50 hover:bg-purple-100/80 border-purple-200/80 text-purple-900' },
                  { label: 'Limpieza', icon: '🧼', q: 'jabon', bg: 'bg-emerald-50 hover:bg-emerald-100/80 border-emerald-200/80 text-emerald-900' },
                  { label: 'Carnes', icon: '🥩', q: 'carne', bg: 'bg-rose-50 hover:bg-rose-100/80 border-rose-200/80 text-rose-900' },
                  { label: 'Tech & Electro', icon: '📱', q: 'smart tv', bg: 'bg-indigo-50 hover:bg-indigo-100/80 border-indigo-200/80 text-indigo-900' },
                ].map(cat => (
                  <button
                    key={cat.label}
                    type="button"
                    onClick={() => {
                      setQuery(cat.q)
                      setDebounced(cat.q)
                    }}
                    className={`p-3 rounded-2xl border text-center flex flex-col items-center justify-center gap-1.5 transition-all active:scale-95 shadow-2xs cursor-pointer ${cat.bg}`}
                  >
                    <span className="text-2xl">{cat.icon}</span>
                    <span className="text-[11px] font-bold leading-tight">{cat.label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Atajos directos a productos cotidianos */}
            <div className="space-y-2 pt-1">
              <span className="text-[11px] font-extrabold uppercase text-slate-400 px-1 tracking-wider">
                Atajos frecuentes
              </span>
              <div className="flex flex-wrap gap-1.5">
                {[
                  'Aceite de girasol',
                  'Leche entera',
                  'Café molido',
                  'Cerveza',
                  'Jabón líquido',
                  'Smart TV 50"',
                  'Celular Motorola',
                ].map(prod => (
                  <button
                    key={prod}
                    type="button"
                    onClick={() => {
                      setQuery(prod)
                      setDebounced(prod)
                    }}
                    className="h-8 px-3 rounded-full text-[12px] font-bold bg-white hover:bg-slate-50 active:bg-slate-100 border border-slate-200 text-slate-700 transition-all shadow-2xs flex items-center gap-1"
                  >
                    <Search size={11} className="text-slate-400" />
                    <span>{prod}</span>
                  </button>
                ))}
              </div>
            </div>

            <p className="text-[12px] text-slate-400 text-center px-4 leading-relaxed pt-2">
              Comparamos en vivo Carrefour, Coto, Día, Jumbo, Disco, Vea, Más Online, Farmacity, Mercado Libre y más.
            </p>
          </div>
        )}

        {/* SKELETONS AL CARGAR RESULTADOS */}
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

        {/* SIN RESULTADOS */}
        {hasQuery && !loading && visible.length === 0 && (
          <div className="text-center py-14 px-6">
            <SearchX size={40} className="mx-auto text-slate-300" />
            <p className="mt-3 font-bold text-slate-700">
              {selectedStore
                ? `No encontramos productos en ${storeLabel(selectedStore)} para "${debounced}"`
                : `No encontramos "${debounced}" con stock`}
            </p>
            <p className="text-[13px] text-slate-500 mt-1">
              {selectedStore
                ? 'Probá seleccionando "Todos" para ver los precios de otras cadenas.'
                : 'Probá con otra palabra o sacá los filtros.'}
            </p>
            {selectedStore && (
              <button
                type="button"
                onClick={() => setSelectedStore(null)}
                className="mt-4 px-4 py-2 rounded-xl bg-blue-50 hover:bg-blue-100 text-blue-700 font-bold text-[13px] transition-colors"
              >
                Ver todos los comercios ({results.length})
              </button>
            )}
          </div>
        )}

        {/* RESULTADOS DE BÚSQUEDA */}
        {hasQuery && visible.length > 0 && (
          <div className={`space-y-3 transition-opacity ${loading ? 'opacity-50' : ''}`}>
            {/* RECUADRO DE PATROCINADO EXCLUSIVO: MERCADO LIBRE */}
            {sponsoredCandidate && (!selectedStore || selectedStore === 'MercadoLibre') && (
              <SponsoredProductBox
                product={sponsoredCandidate.product}
                offer={sponsoredCandidate.offer}
              />
            )}

            <p className="text-[12px] font-semibold text-slate-400 px-1">
              {visible.length} producto{visible.length === 1 ? '' : 's'}
              {selectedStore ? ` en ${storeLabel(selectedStore)}` : ''} · ordenados por{' '}
              {sort === 'unit_price_asc' ? 'precio por kg/l/unidad' : 'precio final'}
            </p>
            {visible.map(g => (
              <ProductCard
                key={g.ean}
                group={g}
                selectedStore={selectedStore}
              />
            ))}
          </div>
        )}
      </main>

      {scanning && <BarcodeScanner onDetected={onScan} onClose={() => setScanning(false)} />}
    </div>
  )
}

export default SearchScreen
