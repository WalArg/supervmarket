import React, { useEffect, useState } from 'react'
import { MapPin, Navigation, Search, X, Loader2, Check, AlertCircle } from 'lucide-react'
import { useLocation } from '../location/LocationContext'
import { searchLocations, type GeocodeLocation } from '../api'

const POPULAR_ZONES = [
  { name: 'Palermo', cp: '1414', zone: 'CABA' },
  { name: 'Caballito', cp: '1424', zone: 'CABA' },
  { name: 'Belgrano', cp: '1428', zone: 'CABA' },
  { name: 'Recoleta', cp: '1425', zone: 'CABA' },
  { name: 'Almagro', cp: '1179', zone: 'CABA' },
  { name: 'Villa Urquiza', cp: '1431', zone: 'CABA' },
  { name: 'Olivos', cp: '1636', zone: 'GBA Norte' },
  { name: 'San Isidro', cp: '1642', zone: 'GBA Norte' },
  { name: 'Tigre', cp: '1648', zone: 'GBA Norte' },
  { name: 'Ramos Mejía', cp: '1704', zone: 'GBA Oeste' },
  { name: 'Morón', cp: '1708', zone: 'GBA Oeste' },
  { name: 'Quilmes', cp: '1878', zone: 'GBA Sur' },
  { name: 'Lomas de Zamora', cp: '1832', zone: 'GBA Sur' },
  { name: 'La Plata', cp: '1900', zone: 'Bs. As.' },
  { name: 'Córdoba Capital', cp: '5000', zone: 'Córdoba' },
  { name: 'Rosario', cp: '2000', zone: 'Santa Fe' },
]

export const LocationModal: React.FC = () => {
  const {
    cp,
    locationLabel,
    setLocation,
    detectLocation,
    isDetecting,
    detectError,
    isModalOpen,
    closeModal,
  } = useLocation()

  const [query, setQuery] = useState('')
  const [results, setResults] = useState<GeocodeLocation[]>([])
  const [searching, setSearching] = useState(false)
  const [manualCp, setManualCp] = useState(cp || '')

  useEffect(() => {
    if (!isModalOpen) {
      setQuery('')
      setResults([])
    } else {
      setManualCp(cp || '')
    }
  }, [isModalOpen, cp])

  // Búsqueda con debounce
  useEffect(() => {
    const trimmed = query.trim()
    if (!trimmed) {
      setResults([])
      setSearching(false)
      return
    }

    let active = true
    setSearching(true)
    const timer = setTimeout(() => {
      searchLocations(trimmed)
        .then(res => {
          if (active) setResults(res)
        })
        .catch(() => {
          if (active) setResults([])
        })
        .finally(() => {
          if (active) setSearching(false)
        })
    }, 280)

    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [query])

  if (!isModalOpen) return null

  const handleSelect = (selectedCp: string, label: string) => {
    setLocation(selectedCp, label)
    closeModal()
  }

  const handleGPS = async () => {
    const res = await detectLocation()
    if (res?.cp) {
      closeModal()
    }
  }

  const handleManualSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const clean = manualCp.replace(/\D/g, '').slice(0, 4)
    if (clean.length === 4) {
      setLocation(clean, `CP ${clean}`)
      closeModal()
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-200">
      <div
        className="w-full max-w-lg bg-white rounded-t-3xl sm:rounded-3xl shadow-2xl border border-slate-100 overflow-hidden flex flex-col max-h-[90vh] animate-in slide-in-from-bottom-6 sm:zoom-in-95 duration-200"
        onClick={e => e.stopPropagation()}
      >
        {/* Cabecera */}
        <div className="px-5 pt-4 pb-3 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center">
              <MapPin size={18} />
            </div>
            <div>
              <h2 className="text-[17px] font-extrabold text-slate-900 leading-tight">
                Ubicación de entrega
              </h2>
              <p className="text-[12px] text-slate-500">
                Para mostrar stock real y fletes a tu zona
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={closeModal}
            className="w-8 h-8 rounded-full bg-slate-100 text-slate-500 hover:text-slate-800 flex items-center justify-center transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Contenido scrolleable */}
        <div className="p-5 overflow-y-auto space-y-4">
          {/* Botón 1-tap GPS */}
          <button
            type="button"
            onClick={handleGPS}
            disabled={isDetecting}
            className="w-full p-3.5 rounded-2xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-bold flex items-center justify-between shadow-md shadow-blue-500/20 active:scale-[0.99] transition-all disabled:opacity-75"
          >
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-white/20 flex items-center justify-center">
                {isDetecting ? (
                  <Loader2 size={19} className="animate-spin text-white" />
                ) : (
                  <Navigation size={18} className="text-white fill-white/30" />
                )}
              </div>
              <div className="text-left">
                <div className="text-[14px] leading-snug">
                  {isDetecting ? 'Detectando con GPS…' : 'Usar mi ubicación actual'}
                </div>
                <div className="text-[11px] text-blue-100 font-normal">
                  Identifica tu barrio y CP en 1 toque
                </div>
              </div>
            </div>
            <span className="text-[12px] bg-white/20 px-2 py-0.5 rounded-full font-semibold">
              GPS
            </span>
          </button>

          {detectError && (
            <div className="flex items-center gap-2 p-3 rounded-xl bg-red-50 text-red-700 text-[12px] font-medium border border-red-100">
              <AlertCircle size={15} className="shrink-0" />
              <span>{detectError}</span>
            </div>
          )}

          {/* Buscador de barrio o calle */}
          <div>
            <label className="block text-[12px] font-bold text-slate-700 mb-1.5">
              O buscá por barrio, calle o localidad
            </label>
            <div className="relative">
              <Search
                size={16}
                className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400"
              />
              <input
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="Ej: Caballito, Olivos, Av Santa Fe 3200…"
                className="w-full h-11 pl-10 pr-9 rounded-xl border border-slate-200 text-[14px] font-medium placeholder:text-slate-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10"
              />
              {searching && (
                <Loader2
                  size={15}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 animate-spin text-slate-400"
                />
              )}
              {query && !searching && (
                <button
                  type="button"
                  onClick={() => setQuery('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  <X size={15} />
                </button>
              )}
            </div>
          </div>

          {/* Resultados de búsqueda */}
          {results.length > 0 && (
            <div className="space-y-1 bg-slate-50 p-1.5 rounded-2xl border border-slate-200/80">
              <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider px-2.5 py-1">
                Resultados
              </div>
              {results.map((r, idx) => (
                <button
                  key={`${r.cp}-${idx}`}
                  type="button"
                  onClick={() => handleSelect(r.cp, r.label)}
                  className="w-full p-2.5 rounded-xl text-left bg-white hover:bg-blue-50 border border-slate-100 flex items-center justify-between transition-colors group"
                >
                  <div className="min-w-0 pr-2">
                    <div className="text-[13px] font-bold text-slate-800 group-hover:text-blue-700 flex items-center gap-1.5">
                      <MapPin size={13} className="text-blue-600 shrink-0" />
                      <span className="truncate">{r.neighborhood || r.label}</span>
                    </div>
                    <div className="text-[11px] text-slate-500 truncate ml-5">
                      {r.display_name}
                    </div>
                  </div>
                  <span className="shrink-0 px-2 py-0.5 rounded-md bg-blue-100/70 text-blue-800 font-extrabold text-[11px]">
                    CP {r.cp}
                  </span>
                </button>
              ))}
            </div>
          )}

          {/* Zonas populares de acceso rápido */}
          {!query && (
            <div>
              <div className="text-[12px] font-bold text-slate-700 mb-2 flex items-center justify-between">
                <span>Zonas frecuentes</span>
                {locationLabel && (
                  <span className="text-[11px] text-blue-600 font-semibold truncate max-w-[180px]">
                    Activa: {locationLabel}
                  </span>
                )}
              </div>
              <div className="flex flex-wrap gap-1.5 max-h-40 overflow-y-auto pr-1">
                {POPULAR_ZONES.map(z => {
                  const isSelected = cp === z.cp
                  return (
                    <button
                      key={z.name}
                      type="button"
                      onClick={() => handleSelect(z.cp, `${z.name} (${z.cp})`)}
                      className={`h-8 px-2.5 rounded-full text-[12px] font-semibold border flex items-center gap-1 transition-all ${
                        isSelected
                          ? 'bg-blue-600 text-white border-blue-600 shadow-xs'
                          : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100 hover:border-slate-300'
                      }`}
                    >
                      {isSelected && <Check size={12} strokeWidth={3} />}
                      <span>{z.name}</span>
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {/* Ingreso manual tradicional de CP */}
          <div className="pt-2 border-t border-slate-100">
            <form onSubmit={handleManualSubmit} className="flex gap-2 items-center">
              <div className="relative flex-1">
                <input
                  type="text"
                  inputMode="numeric"
                  value={manualCp}
                  onChange={e => setManualCp(e.target.value.replace(/\D/g, '').slice(0, 4))}
                  placeholder="O ingresá el CP (ej: 1414)"
                  className="w-full h-10 px-3 rounded-xl border border-slate-200 text-[13px] font-semibold focus:outline-none focus:border-blue-500"
                />
              </div>
              <button
                type="submit"
                disabled={manualCp.length !== 4}
                className="h-10 px-4 rounded-xl bg-slate-900 text-white text-[13px] font-bold disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-800"
              >
                Aplicar
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
