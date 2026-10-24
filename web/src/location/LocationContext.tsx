import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { getRegions } from '../api'

export interface Coverage {
  supermercado: string
  delivers: boolean | null
  sellers: string[]
  region_id: string | null
  note?: string
}

interface LocationCtx {
  cp: string | null
  setCp: (cp: string) => void
  coverage: Coverage[]
  loading: boolean
  delivers: (store: string) => boolean | null
}

const Ctx = createContext<LocationCtx | null>(null)
const KEY = 'sv_cp'

export function LocationProvider({ children }: { children: ReactNode }) {
  const [cp, setCpState] = useState<string | null>(() => localStorage.getItem(KEY))
  const [coverage, setCoverage] = useState<Coverage[]>([])
  const [loading, setLoading] = useState(false)

  const setCp = (value: string) => {
    const clean = value.trim()
    setCpState(clean)
    localStorage.setItem(KEY, clean)
  }

  useEffect(() => {
    if (!cp) return
    let alive = true
    setLoading(true)
    getRegions(cp)
      .then(data => { if (alive) setCoverage(data) })
      .catch(() => { if (alive) setCoverage([]) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [cp])

  const delivers = (store: string): boolean | null => {
    const c = coverage.find(x => x.supermercado === store)
    return c ? c.delivers : null
  }

  const value = useMemo(
    () => ({ cp, setCp, coverage, loading, delivers }),
    [cp, coverage, loading],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useLocation() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useLocation debe usarse dentro de <LocationProvider>')
  return ctx
}
