import { useState, useEffect } from 'react'
import { Search, ShoppingBasket, User } from 'lucide-react'
import SearchScreen from './components/SearchScreen'
import ListScreen from './components/ListScreen'
import ProfileScreen from './components/ProfileScreen'
import { LocationModal } from './components/LocationModal'
import { useCart } from './cart/CartContext'

type Tab = 'buscar' | 'lista' | 'perfil'

function App() {
  const [tab, setTab] = useState<Tab>('buscar')
  const { totalUnits } = useCart()

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const code = params.get('code')
    if (code) {
      fetch(`/api/meli/callback?code=${encodeURIComponent(code)}`)
        .then(r => r.json())
        .then(data => {
          if (data.status === 'success') {
            alert('🎉 ¡Mercado Libre vinculado exitosamente a SuperVmarket!')
          }
          window.history.replaceState({}, document.title, window.location.pathname)
        })
        .catch(() => {})
    }
  }, [])

  const go = (t: Tab) => {
    setTab(t)
    window.scrollTo({ top: 0 })
  }

  const NAV: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: 'buscar', label: 'Buscar', icon: <Search size={22} /> },
    { id: 'lista', label: 'Mi lista', icon: <ShoppingBasket size={22} /> },
    { id: 'perfil', label: 'Perfil', icon: <User size={22} /> },
  ]

  return (
    <div className="min-h-[100dvh] bg-slate-50 text-slate-900">
      <div className="max-w-xl mx-auto">
        {/* El buscador queda montado para conservar resultados y scroll al cambiar de pestaña */}
        <div className={tab === 'buscar' ? '' : 'hidden'}>
          <SearchScreen />
        </div>
        {tab === 'lista' && <ListScreen onGoSearch={() => go('buscar')} onGoProfile={() => go('perfil')} />}
        {tab === 'perfil' && <ProfileScreen />}
      </div>

      <LocationModal />

      <nav className="fixed bottom-0 inset-x-0 z-40 bg-white/95 backdrop-blur-md border-t border-slate-200 pb-safe">
        <div className="max-w-xl mx-auto grid grid-cols-3">
          {NAV.map(n => {
            const on = tab === n.id
            return (
              <button
                key={n.id}
                type="button"
                onClick={() => go(n.id)}
                className={`relative h-16 flex flex-col items-center justify-center gap-0.5 text-[11px] font-bold ${
                  on ? 'text-blue-600' : 'text-slate-400'
                }`}
              >
                <span className="relative">
                  {n.icon}
                  {n.id === 'lista' && totalUnits > 0 && (
                    <span
                      key={totalUnits}
                      className="absolute -top-1.5 -right-2.5 min-w-[18px] h-[18px] px-1 rounded-full bg-orange-500 text-white text-[10px] font-extrabold flex items-center justify-center animate-[pop_0.25s_ease-out]"
                    >
                      {totalUnits}
                    </span>
                  )}
                </span>
                {n.label}
              </button>
            )
          })}
        </div>
      </nav>
    </div>
  )
}

export default App
