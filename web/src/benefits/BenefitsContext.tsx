import React, { createContext, useContext, useState, useEffect } from 'react'
import type { BenefitsCatalog, DailyPromo } from '../types'
import { getBenefits } from '../api'

const STORAGE_CARDS_KEY = 'supervmarket.cards.v1'
const STORAGE_DAY_KEY = 'supervmarket.day.v1'

const STORE_CLUB_MAP: Record<string, string[]> = {
  Carrefour: ['tarjeta_carrefour', 'mi_carrefour'],
  Coto: ['comunidad_coto'],
  Dia: ['club_dia'],
  Jumbo: ['cencopay'],
  Disco: ['cencopay'],
  Vea: ['cencopay'],
  Masonline: ['mas_club'],
  Farmacity: ['tu_farmacity'],
}

interface BenefitsContextValue {
  catalog: BenefitsCatalog | null
  selectedCards: string[]
  selectedDay: string
  toggleCard: (id: string) => void
  clearCards: () => void
  setSelectedDay: (day: string) => void
  hasStoreClub: (store: string) => boolean
  promosForDay: (day?: string) => DailyPromo[]
}

const BenefitsContext = createContext<BenefitsContextValue>({
  catalog: null,
  selectedCards: [],
  selectedDay: 'sabado',
  toggleCard: () => {},
  clearCards: () => {},
  setSelectedDay: () => {},
  hasStoreClub: () => false,
  promosForDay: () => [],
})

const WEEKDAYS_JS = ['domingo', 'lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado']

export const BenefitsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [catalog, setCatalog] = useState<BenefitsCatalog | null>(null)
  const [selectedCards, setSelectedCards] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_CARDS_KEY)
      return raw ? JSON.parse(raw) : []
    } catch {
      return []
    }
  })

  const [selectedDay, setSelectedDayState] = useState<string>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_DAY_KEY)
      if (saved) return saved
    } catch {}
    return WEEKDAYS_JS[new Date().getDay()] || 'sabado'
  })

  useEffect(() => {
    getBenefits()
      .then(data => {
        setCatalog(data)
        if (!localStorage.getItem(STORAGE_DAY_KEY) && data.today) {
          setSelectedDayState(data.today)
        }
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_CARDS_KEY, JSON.stringify(selectedCards))
    } catch {}
  }, [selectedCards])

  const setSelectedDay = (day: string) => {
    setSelectedDayState(day)
    try {
      localStorage.setItem(STORAGE_DAY_KEY, day)
    } catch {}
  }

  const toggleCard = (id: string) => {
    setSelectedCards(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id],
    )
  }

  const clearCards = () => setSelectedCards([])

  const hasStoreClub = (store: string): boolean => {
    const needed = STORE_CLUB_MAP[store]
    if (!needed || selectedCards.length === 0) return false
    return needed.some(id => selectedCards.includes(id))
  }

  const promosForDay = (day?: string): DailyPromo[] => {
    if (!catalog) return []
    const d = (day || selectedDay).toLowerCase()
    return catalog.daily_promos.filter(p => p.days.includes(d))
  }

  return (
    <BenefitsContext.Provider
      value={{
        catalog,
        selectedCards,
        selectedDay,
        toggleCard,
        clearCards,
        setSelectedDay,
        hasStoreClub,
        promosForDay,
      }}
    >
      {children}
    </BenefitsContext.Provider>
  )
}

export const useBenefits = () => useContext(BenefitsContext)
