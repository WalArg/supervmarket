import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { getRegions, reverseGeocode, type GeocodeLocation } from '../api'

export interface Coverage {
  supermercado: string
  delivers: boolean | null
  sellers: string[]
  region_id: string | null
  note?: string
}

interface LocationCtx {
  cp: string | null
  locationLabel: string | null
  exactAddress: string | null
  setCp: (cp: string, label?: string) => void
  setLocation: (cp: string, label?: string) => void
  setExactAddress: (address: string) => void
  detectLocation: () => Promise<GeocodeLocation | null>
  isDetecting: boolean
  detectError: string | null
  isModalOpen: boolean
  openModal: () => void
  closeModal: () => void
  coverage: Coverage[]
  loading: boolean
  delivers: (store: string) => boolean | null
}

const Ctx = createContext<LocationCtx | null>(null)
const KEY_CP = 'sv_cp'
const KEY_LABEL = 'sv_location_label'
const KEY_ADDR = 'sv_exact_address'

export function LocationProvider({ children }: { children: ReactNode }) {
  const [cp, setCpState] = useState<string | null>(() => localStorage.getItem(KEY_CP))
  const [locationLabel, setLocationLabelState] = useState<string | null>(() => localStorage.getItem(KEY_LABEL))
  const [exactAddress, setExactAddressState] = useState<string | null>(() => localStorage.getItem(KEY_ADDR))
  const [coverage, setCoverage] = useState<Coverage[]>([])
  const [loading, setLoading] = useState(false)
  const [isDetecting, setIsDetecting] = useState(false)
  const [detectError, setDetectError] = useState<string | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)

  const setLocation = (newCp: string, newLabel?: string) => {
    const cleanCp = newCp.trim()
    setCpState(cleanCp)
    localStorage.setItem(KEY_CP, cleanCp)
    const finalLabel = (newLabel && newLabel.trim()) ? newLabel.trim() : `CP ${cleanCp}`
    setLocationLabelState(finalLabel)
    localStorage.setItem(KEY_LABEL, finalLabel)
  }

  const setCp = (value: string, label?: string) => {
    setLocation(value, label)
  }

  const setExactAddress = (addr: string) => {
    const clean = addr.trim()
    setExactAddressState(clean)
    localStorage.setItem(KEY_ADDR, clean)
  }

  const openModal = () => setIsModalOpen(true)
  const closeModal = () => setIsModalOpen(false)

  const detectLocation = async (): Promise<GeocodeLocation | null> => {
    if (!navigator.geolocation) {
      setDetectError('Tu navegador no permite acceder a la geolocalización.')
      return null
    }

    setIsDetecting(true)
    setDetectError(null)

    return new Promise((resolve) => {
      navigator.geolocation.getCurrentPosition(
        async (pos) => {
          try {
            const res = await reverseGeocode(pos.coords.latitude, pos.coords.longitude)
            if (res.cp) {
              const displayLabel = res.neighborhood ? `${res.neighborhood} (${res.cp})` : res.label
              setLocation(res.cp, displayLabel)
              setIsDetecting(false)
              resolve(res)
            } else {
              setDetectError('No pudimos detectar el CP exacto para tu coordenada.')
              setIsDetecting(false)
              resolve(null)
            }
          } catch {
            setDetectError('No pudimos conectar con el servicio de ubicación.')
            setIsDetecting(false)
            resolve(null)
          }
        },
        (err) => {
          setIsDetecting(false)
          if (err.code === 1) {
            setDetectError('Permiso de ubicación denegado en el navegador.')
          } else {
            setDetectError('No pudimos obtener tu ubicación actual.')
          }
          resolve(null)
        },
        { timeout: 9000, enableHighAccuracy: true }
      )
    })
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
    () => ({
      cp,
      locationLabel,
      exactAddress,
      setCp,
      setLocation,
      setExactAddress,
      detectLocation,
      isDetecting,
      detectError,
      isModalOpen,
      openModal,
      closeModal,
      coverage,
      loading,
      delivers,
    }),
    [cp, locationLabel, exactAddress, isDetecting, detectError, isModalOpen, coverage, loading],
  )

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useLocation() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useLocation debe usarse dentro de <LocationProvider>')
  return ctx
}
