import { useState, useEffect } from 'react'
import { MapPin, CheckCircle2, XCircle, Loader2 } from 'lucide-react'
import { useLocation } from '../location/LocationContext'

const PRESET_CPS = [
  { label: 'CABA (1414)', cp: '1414' },
  { label: 'Belgrano (1428)', cp: '1428' },
  { label: 'Vicente López (1638)', cp: '1638' },
  { label: 'La Plata (1900)', cp: '1900' },
  { label: 'Córdoba (5000)', cp: '5000' },
]

const LocationBar: React.FC = () => {
  const { cp, setCp, coverage, loading } = useLocation()
  const [value, setValue] = useState(cp || '')

  useEffect(() => {
    if (cp) setValue(cp)
  }, [cp])

  const entregan = coverage.filter(c => c.delivers === true)
  const noEntregan = coverage.filter(c => c.delivers === false)

  return (
    <div className="bg-slate-900 text-slate-100 border-b border-slate-800">
      <div className="container mx-auto px-4 py-2 flex flex-col lg:flex-row lg:items-center justify-between gap-2.5 text-xs">
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="flex items-center gap-1.5 font-bold text-amber-400">
            <MapPin size={15} className="shrink-0" />
            <span>
              {cp ? `Cobertura validada en CP ${cp}:` : 'Ingresá tu Código Postal para validar stock y envío:'}
            </span>
          </div>

          <form
            onSubmit={e => {
              e.preventDefault()
              if (value.trim()) setCp(value.trim())
            }}
            className="flex items-center gap-1.5"
          >
            <input
              value={value}
              onChange={e => setValue(e.target.value.replace(/\D/g, '').slice(0, 4))}
              placeholder="Ej: 1414"
              className="bg-slate-800 border border-slate-700 text-white placeholder-slate-400 rounded-lg px-2.5 py-1 w-24 text-xs font-bold focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              type="submit"
              className="bg-blue-600 hover:bg-blue-500 text-white px-3 py-1 rounded-lg font-bold transition-colors flex items-center gap-1"
            >
              {loading ? <Loader2 className="animate-spin" size={13} /> : 'Validar CP'}
            </button>
          </form>

          <div className="hidden sm:flex items-center gap-1">
            {PRESET_CPS.map(p => (
              <button
                key={p.cp}
                type="button"
                onClick={() => {
                  setValue(p.cp)
                  setCp(p.cp)
                }}
                className={`px-2 py-0.5 rounded-md text-[11px] font-medium transition-colors ${
                  cp === p.cp
                    ? 'bg-amber-400 text-slate-950 font-bold'
                    : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        {cp && coverage.length > 0 && (
          <div className="flex flex-wrap items-center gap-3 text-[11px]">
            {entregan.length > 0 && (
              <span className="inline-flex items-center gap-1 text-emerald-400 font-semibold">
                <CheckCircle2 size={13} className="shrink-0" />
                Llegan ({entregan.length}):{' '}
                <span className="text-slate-200 font-normal">
                  {entregan.map(c => c.supermercado).join(', ')}
                </span>
              </span>
            )}
            {noEntregan.length > 0 && (
              <span className="inline-flex items-center gap-1 text-rose-400 font-medium">
                <XCircle size={13} className="shrink-0" />
                Sin envío:{' '}
                <span className="text-slate-400">
                  {noEntregan.map(c => c.supermercado).join(', ')}
                </span>
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default LocationBar
