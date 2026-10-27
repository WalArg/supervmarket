import { useState, useEffect } from 'react'
import { Home, ShoppingCart, Bookmark, User, Sparkles } from 'lucide-react'
import SearchScreen from './components/SearchScreen'
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

type Tab = 'buscar' | 'carrito' | 'guardados' | 'ia' | 'perfil'

function App() {
  const [tab, setTab] = useState<Tab>('buscar')
  const { items, totalUnits, importItems } = useCart()
  const { savedCount } = useSaved()
  const [incomingSharedItems, setIncomingSharedItems] = useState<SharedItem[]>([])
  const [isImportModalOpen, setIsImportModalOpen] = useState(false)

  const go = (t: Tab) => {
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

  const NAV: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: 'buscar', label: 'Inicio', icon: <Home size={21} /> },
    { id: 'carrito', label: 'Carrito', icon: <ShoppingCart size={21} /> },
    { id: 'guardados', label: 'Guardados', icon: <Bookmark size={21} /> },
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
        {tab === 'carrito' && (
          <ErrorBoundary fallbackTitle="Error al cargar Carrito">
            <ListScreen onGoSearch={() => go('buscar')} onGoProfile={() => go('perfil')} />
          </ErrorBoundary>
        )}
        {tab === 'guardados' && (
          <ErrorBoundary fallbackTitle="Error al cargar Guardados">
            <SavedScreen onGoSearch={() => go('buscar')} onGoCart={() => go('carrito')} />
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
      </div>

      <ImportSharedListModal
        isOpen={isImportModalOpen}
        sharedItems={incomingSharedItems}
        currentCartCount={items.length}
        onMerge={handleMergeImport}
        onReplace={handleReplaceImport}
        onDismiss={handleDismissImport}
      />

      <LocationModal />

      <nav className="fixed bottom-0 inset-x-0 z-40 bg-white/95 backdrop-blur-md border-t border-slate-200 pb-safe">
        <div className="max-w-xl mx-auto grid grid-cols-5">
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
                  {n.id === 'carrito' && totalUnits > 0 && (
                    <span
                      key={totalUnits}
                      className="absolute -top-1.5 -right-2.5 min-w-[18px] h-[18px] px-1 rounded-full bg-orange-500 text-white text-[10px] font-extrabold flex items-center justify-center animate-[pop_0.25s_ease-out]"
                    >
                      {totalUnits}
                    </span>
                  )}
                  {n.id === 'guardados' && savedCount > 0 && (
                    <span
                      key={savedCount}
                      className="absolute -top-1.5 -right-2.5 min-w-[18px] h-[18px] px-1 rounded-full bg-amber-500 text-white text-[10px] font-extrabold flex items-center justify-center animate-[pop_0.25s_ease-out]"
                    >
                      {savedCount}
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
