import { useState, useEffect } from 'react'
import { Search, Flame, ShoppingCart, Bookmark, User, Sparkles } from 'lucide-react'
import SearchScreen from './components/SearchScreen'
import OffersScreen from './components/OffersScreen'
import ListScreen from './components/ListScreen'
import SavedScreen from './components/SavedScreen'
import ProfileScreen from './components/ProfileScreen'
import AIScreen from './components/AIScreen'
import { LocationModal } from './components/LocationModal'
import { ImportSharedListModal } from './components/ImportSharedListModal'
import { useCart } from './cart/CartContext'
import { useSaved } from './saved/SavedContext'
import { decodeShareableList, cleanUrlParams } from './cart/portableList'
import type { SharedItem } from './types'
import ErrorBoundary from './components/ErrorBoundary'

type MainTab = 'buscar' | 'ofertas' | 'ia' | 'perfil'
type Tab = MainTab | 'carrito' | 'guardados'

function App() {
  const [tab, setTab] = useState<Tab>('buscar')
  const [lastMainTab, setLastMainTab] = useState<MainTab>('buscar')
  const { items, totalUnits, importItems } = useCart()
  const { savedCount } = useSaved()
  const [incomingSharedItems, setIncomingSharedItems] = useState<SharedItem[]>([])
  const [isImportModalOpen, setIsImportModalOpen] = useState(false)

  const go = (t: Tab) => {
    if (t === 'buscar' || t === 'ofertas' || t === 'ia' || t === 'perfil') {
      setLastMainTab(t)
    }
    setTab(t)
    window.scrollTo({ top: 0 })
  }

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

    const shareParam = params.get('list') || params.get('habitual') || params.get('cart')
    if (shareParam) {
      const decoded = decodeShareableList(shareParam)
      if (decoded.length > 0) {
        if (items.length === 0) {
          // Si el changuito está vacío, importar automáticamente
          importItems(decoded, 'replace')
          cleanUrlParams(['list', 'habitual', 'cart'])
          go('carrito')
        } else {
          // Si ya hay productos, abrir modal interactivo de fusionar o reemplazar
          setIncomingSharedItems(decoded)
          setIsImportModalOpen(true)
        }
      }
    }
  }, [])

  const handleMergeImport = () => {
    if (incomingSharedItems.length > 0) {
      importItems(incomingSharedItems, 'merge')
    }
    cleanUrlParams(['list', 'habitual', 'cart'])
    setIsImportModalOpen(false)
    setIncomingSharedItems([])
    go('carrito')
  }

  const handleReplaceImport = () => {
    if (incomingSharedItems.length > 0) {
      importItems(incomingSharedItems, 'replace')
    }
    cleanUrlParams(['list', 'habitual', 'cart'])
    setIsImportModalOpen(false)
    setIncomingSharedItems([])
    go('carrito')
  }

  const handleDismissImport = () => {
    cleanUrlParams(['list', 'habitual', 'cart'])
    setIsImportModalOpen(false)
    setIncomingSharedItems([])
  }

  // 4 pestañas de navegación inferior: Buscador a la izquierda de todas, luego Ofertas, Asistente IA y Perfil
  const NAV: { id: MainTab; label: string; icon: React.ReactNode }[] = [
    { id: 'buscar', label: 'Buscador', icon: <Search size={21} /> },
    { id: 'ofertas', label: 'Ofertas', icon: <Flame size={21} /> },
    { id: 'ia', label: 'Asistente IA', icon: <Sparkles size={21} /> },
    { id: 'perfil', label: 'Perfil', icon: <User size={21} /> },
  ]

  return (
    <div className="min-h-[100dvh] bg-slate-50 text-slate-900">
      <div className="max-w-xl mx-auto">
        {/* El buscador queda montado para conservar resultados y scroll al cambiar de pestaña */}
        <div className={tab === 'buscar' ? '' : 'hidden'}>
          <ErrorBoundary fallbackTitle="Error al cargar el buscador">
            <SearchScreen />
          </ErrorBoundary>
        </div>

        {tab === 'ofertas' && (
          <ErrorBoundary fallbackTitle="Error al cargar Ofertas">
            <OffersScreen onGoSearch={() => go('buscar')} />
          </ErrorBoundary>
        )}

        {tab === 'ia' && (
          <ErrorBoundary fallbackTitle="Error en Asistente IA">
            <AIScreen onGoCart={() => go('carrito')} onGoSearch={() => go('buscar')} />
          </ErrorBoundary>
        )}

        {tab === 'perfil' && (
          <ErrorBoundary fallbackTitle="Error al cargar Perfil">
            <ProfileScreen />
          </ErrorBoundary>
        )}

        {tab === 'carrito' && (
          <ErrorBoundary fallbackTitle="Error al cargar Carrito">
            <ListScreen
              onGoSearch={() => go('buscar')}
              onGoProfile={() => go('perfil')}
              onBack={() => go(lastMainTab)}
            />
          </ErrorBoundary>
        )}

        {tab === 'guardados' && (
          <ErrorBoundary fallbackTitle="Error al cargar Guardados">
            <SavedScreen
              onGoSearch={() => go('buscar')}
              onGoCart={() => go('carrito')}
              onBack={() => go(lastMainTab)}
            />
          </ErrorBoundary>
        )}
      </div>

      {/* BOTONES FLOTANTES: Guardados y Carrito */}
      <aside
        aria-label="Acciones rápidas de compra"
        className="fixed bottom-20 inset-x-0 pointer-events-none z-40 max-w-xl mx-auto px-4 flex justify-end"
      >
        <div className="flex flex-col items-end gap-2.5 pointer-events-auto">
          {/* Botón flotante Guardados */}
          {tab !== 'guardados' && (
            <button
              type="button"
              onClick={() => go('guardados')}
              aria-label={`Ver ${savedCount} productos guardados`}
              className="h-11 px-3.5 rounded-full flex items-center gap-2 bg-white/95 backdrop-blur-md text-slate-700 border border-slate-200/90 shadow-md hover:bg-slate-50 hover:border-slate-300 active:scale-95 transition-all group"
            >
              <span className="relative">
                <Bookmark
                  size={18}
                  className={savedCount > 0 ? 'text-amber-500 fill-amber-500' : 'text-slate-500 group-hover:text-amber-500'}
                />
                {savedCount > 0 && (
                  <span
                    key={savedCount}
                    className="absolute -top-1.5 -right-2.5 min-w-[17px] h-[17px] px-1 rounded-full bg-amber-500 text-white text-[10px] font-extrabold flex items-center justify-center animate-[pop_0.25s_ease-out]"
                  >
                    {savedCount}
                  </span>
                )}
              </span>
              <span className="text-[12px] font-bold text-slate-700">Guardados</span>
            </button>
          )}

          {/* Botón flotante Carrito */}
          {tab !== 'carrito' && (
            <button
              type="button"
              onClick={() => go('carrito')}
              aria-label={`Ver carrito con ${totalUnits} productos`}
              className="h-12 px-4 rounded-full flex items-center gap-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white shadow-lg shadow-blue-500/25 active:scale-95 transition-all group"
            >
              <span className="relative">
                <ShoppingCart size={20} className="text-white" />
                {totalUnits > 0 && (
                  <span
                    key={totalUnits}
                    className="absolute -top-2 -right-3 min-w-[19px] h-[19px] px-1 rounded-full bg-orange-500 text-white text-[10px] font-black flex items-center justify-center border-2 border-white animate-[pop_0.25s_ease-out]"
                  >
                    {totalUnits}
                  </span>
                )}
              </span>
              <span className="text-[13px] font-extrabold text-white">Carrito</span>
            </button>
          )}
        </div>
      </aside>

      <ImportSharedListModal
        isOpen={isImportModalOpen}
        sharedItems={incomingSharedItems}
        currentCartCount={items.length}
        onMerge={handleMergeImport}
        onReplace={handleReplaceImport}
        onDismiss={handleDismissImport}
      />

      <LocationModal />

      {/* Navegador inferior de pestañas principales: 4 columnas */}
      <nav className="fixed bottom-0 inset-x-0 z-40 bg-white/95 backdrop-blur-md border-t border-slate-200 pb-safe">
        <div className="max-w-xl mx-auto grid grid-cols-4">
          {NAV.map(n => {
            const on = tab === n.id
            return (
              <button
                key={n.id}
                type="button"
                onClick={() => go(n.id)}
                className={`relative h-16 flex flex-col items-center justify-center gap-0.5 text-[11px] font-bold transition-colors ${
                  on ? 'text-blue-600' : 'text-slate-400 hover:text-slate-600'
                }`}
              >
                <span className="relative">
                  {n.icon}
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
