import React, { useState, useRef } from 'react'
import {
  Sparkles,
  Receipt,
  ChefHat,
  Camera,
  Upload,
  ShoppingBasket,
  CheckCircle2,
  TrendingDown,
  Loader2,
  AlertCircle,
  Plus,
  Play,
  ArrowRight,
} from 'lucide-react'
import {
  analyzeReceipt,
  generateRecipeCart,
  type ReceiptAnalysis,
  type RecipeCartResult,
} from '../api'
import { useCart } from '../cart/CartContext'
import { useLocation } from '../location/LocationContext'
import { formatPrice } from '../lib/pricing'
import { storeLabel, storeColor } from '../lib/stores'
import { RewardedAdModal } from './RewardedAdModal'

type AIFeature = 'ticket' | 'receta'

const SAMPLE_PROMPTS = [
  '🥩 Asado para 6 amigos con fernet y carbón',
  '🥗 Canasta saludable semanal para 2 personas',
  '🍲 Guiso de lentejas rendidor para 4 personas',
  '🎈 Cumpleaños infantil: panchos, snacks y gaseosa',
]

export const AIScreen: React.FC<{ onGoCart: () => void; onGoSearch: () => void }> = ({
  onGoCart,
}) => {
  const { add } = useCart()
  const { cp } = useLocation()

  const [activeTab, setActiveTab] = useState<AIFeature>('ticket')

  // Estado para Vision AI (Tickets)
  const [ticketImage, setTicketImage] = useState<string | null>(null)
  const [analyzingTicket, setAnalyzingTicket] = useState(false)
  const [ticketResult, setTicketResult] = useState<ReceiptAnalysis | null>(null)
  const [ticketError, setTicketError] = useState<string | null>(null)
  const [addedTicketToCart, setAddedTicketToCart] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  // Estado para Prompt-to-Cart (Recetas)
  const [recipePrompt, setRecipePrompt] = useState('')
  const [generatingRecipe, setGeneratingRecipe] = useState(false)
  const [recipeResult, setRecipeResult] = useState<RecipeCartResult | null>(null)
  const [recipeError, setRecipeError] = useState<string | null>(null)
  const [addedRecipeToCart, setAddedRecipeToCart] = useState(false)

  // Estado del anuncio recompensado obligatorio
  const [adModalOpen, setAdModalOpen] = useState(false)
  const [pendingAction, setPendingAction] = useState<'ticket' | 'recipe' | null>(null)

  // 1. Manejo de subida / captura de ticket
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = () => {
      const b64 = reader.result as string
      setTicketImage(b64)
      setTicketResult(null)
      setTicketError(null)
      // Disparar anuncio antes de procesar
      setPendingAction('ticket')
      setAdModalOpen(true)
    }
    reader.readAsDataURL(file)
  }

  const triggerTestTicket = () => {
    setTicketImage('sample_ticket')
    setTicketResult(null)
    setTicketError(null)
    setPendingAction('ticket')
    setAdModalOpen(true)
  }

  // 2. Ejecución de análisis de ticket tras ver el anuncio
  const runTicketAnalysis = async (imageB64: string) => {
    setAnalyzingTicket(true)
    setTicketError(null)
    try {
      const res = await analyzeReceipt(imageB64, 'image/jpeg', cp)
      setTicketResult(res)
    } catch {
      setTicketError('Error al procesar el ticket. Intentá nuevamente.')
    } finally {
      setAnalyzingTicket(false)
    }
  }

  // 3. Ejecución de generación de receta tras ver el anuncio
  const triggerRecipePrompt = (promptText?: string) => {
    const text = (promptText || recipePrompt).trim()
    if (!text) return
    setRecipePrompt(text)
    setRecipeResult(null)
    setRecipeError(null)
    setPendingAction('recipe')
    setAdModalOpen(true)
  }

  const runRecipeGeneration = async (promptText: string) => {
    setGeneratingRecipe(true)
    setRecipeError(null)
    try {
      const res = await generateRecipeCart(promptText, cp)
      setRecipeResult(res)
    } catch {
      setRecipeError('No se pudo generar la receta. Probá con otro texto.')
    } finally {
      setGeneratingRecipe(false)
    }
  }

  // 4. Callback cuando el usuario termina de ver el video obligatorio
  const handleRewardUnlocked = () => {
    if (pendingAction === 'ticket') {
      runTicketAnalysis(ticketImage || 'sample_ticket')
    } else if (pendingAction === 'recipe') {
      runRecipeGeneration(recipePrompt)
    }
    setPendingAction(null)
  }

  // 5. Cargar items del ticket al carrito
  const handleAddTicketItemsToCart = () => {
    if (!ticketResult) return
    let count = 0
    for (const item of ticketResult.items) {
      if (item.matched && item.product) {
        add(
          {
            ean: item.product.ean,
            nombre: item.product.nombre,
            imagen: item.product.imagen || '',
            marca: '',
            offers: [],
            all_names: [],
          },
          item.qty,
        )
        count++
      }
    }
    setAddedTicketToCart(true)
  }

  // 6. Cargar ingredientes de receta al carrito
  const handleAddRecipeItemsToCart = () => {
    if (!recipeResult) return
    for (const ing of recipeResult.ingredientes) {
      if (ing.matched && ing.product) {
        add(
          {
            ean: ing.product.ean,
            nombre: ing.product.nombre,
            imagen: ing.product.imagen || '',
            marca: '',
            offers: [],
            all_names: [],
          },
          ing.qty,
        )
      }
    }
    setAddedRecipeToCart(true)
  }

  return (
    <div>
      <header className="sticky top-0 z-30 bg-slate-50/95 backdrop-blur-md pt-safe border-b border-slate-100">
        <div className="px-4 pt-3 pb-3">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-[20px] font-extrabold tracking-tight flex items-center gap-2">
                <Sparkles size={20} className="text-amber-500 fill-amber-500/20" />
                Asistente <span className="text-blue-600">IA</span>
              </h1>
              <p className="text-[12px] text-slate-500">
                Ahorrá tiempo y dinero con Inteligencia Artificial
              </p>
            </div>
            <span className="text-[11px] font-extrabold px-2.5 py-1 rounded-full bg-amber-100 text-amber-800 border border-amber-200">
              ⚡ Gratis c/ad
            </span>
          </div>

          {/* Selector de funcionalidad IA */}
          <div className="grid grid-cols-2 p-1 bg-slate-200/70 rounded-xl mt-3">
            <button
              type="button"
              onClick={() => setActiveTab('ticket')}
              className={`h-9 rounded-lg text-[13px] font-bold flex items-center justify-center gap-1.5 transition-all ${
                activeTab === 'ticket'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              <Receipt size={16} /> Escanear Ticket
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('receta')}
              className={`h-9 rounded-lg text-[13px] font-bold flex items-center justify-center gap-1.5 transition-all ${
                activeTab === 'receta'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              <ChefHat size={16} /> Menú & Recetas
            </button>
          </div>
        </div>
      </header>

      <main className="px-4 pt-4 pb-28 space-y-4">
        {/* ============================================================== */}
        {/* TAB 1: ESCANEAR TICKET CON VISION IA */}
        {/* ============================================================== */}
        {activeTab === 'ticket' && (
          <div className="space-y-4">
            {/* Tarjeta de bienvenida y carga */}
            <div className="p-5 rounded-2xl bg-white border border-slate-200/80 shadow-2xs text-center space-y-3">
              <div className="w-14 h-14 mx-auto rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center shadow-xs">
                <Receipt size={28} />
              </div>
              <div>
                <h2 className="text-[17px] font-extrabold text-slate-900">
                  ¿Cuánto pagaste de más en tu ticket?
                </h2>
                <p className="text-[13px] text-slate-500 max-w-sm mx-auto mt-1">
                  Sacale una foto al ticket de cualquier supermercado. La IA extrae los productos y te dice cuánto habrías ahorrado en SuperVmarket.
                </p>
              </div>

              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                capture="environment"
                className="hidden"
                onChange={handleFileChange}
              />

              <div className="pt-2 flex flex-col sm:flex-row gap-2">
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="flex-1 h-12 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-extrabold text-[13px] flex items-center justify-center gap-2 shadow-md shadow-blue-500/20 active:scale-[0.98] transition-all"
                >
                  <Camera size={18} /> Sacar foto al ticket
                </button>
                <button
                  type="button"
                  onClick={triggerTestTicket}
                  className="h-12 px-4 rounded-xl border border-slate-200 bg-slate-50 text-slate-700 font-bold text-[12px] hover:bg-slate-100 active:scale-[0.98] transition-all"
                >
                  Probar con ticket demo
                </button>
              </div>

              <p className="text-[11px] text-slate-400">
                🔒 Procesamiento confidencial y financiado por 1 anuncio de 15 segundos.
              </p>
            </div>

            {analyzingTicket && (
              <div className="p-8 rounded-2xl bg-white border border-slate-200 text-center space-y-3">
                <Loader2 size={32} className="animate-spin text-blue-600 mx-auto" />
                <h3 className="text-[15px] font-extrabold text-slate-900">
                  La IA está analizando tu ticket…
                </h3>
                <p className="text-[12px] text-slate-500">
                  Detectando productos y buscando los precios más bajos en 12 cadenas argentinas.
                </p>
              </div>
            )}

            {ticketError && (
              <div className="p-4 rounded-xl bg-red-50 text-red-700 border border-red-100 flex items-center gap-2 text-[13px]">
                <AlertCircle size={16} className="shrink-0" />
                <span>{ticketError}</span>
              </div>
            )}

            {/* Resultado de la comparación del ticket */}
            {ticketResult && (
              <div className="space-y-3">
                {/* Banner de ahorro total */}
                <div className="p-4 rounded-2xl bg-gradient-to-br from-emerald-600 to-teal-700 text-white shadow-md shadow-emerald-500/15">
                  <div className="flex items-center justify-between text-[12px] font-semibold text-emerald-100 mb-1">
                    <span>{ticketResult.supermercado}</span>
                    <span className="bg-white/20 px-2 py-0.5 rounded-full font-bold">
                      Ahorrás {ticketResult.ahorro_porcentaje}%
                    </span>
                  </div>
                  <div className="flex items-baseline justify-between">
                    <div>
                      <div className="text-[12px] text-emerald-100 font-medium">Pagaste en ticket:</div>
                      <div className="text-[18px] font-bold line-through text-emerald-200">
                        {formatPrice(ticketResult.total_ticket)}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-[12px] text-emerald-100 font-medium">En SuperVmarket:</div>
                      <div className="text-[26px] font-black tracking-tight">
                        {formatPrice(ticketResult.total_supervmarket)}
                      </div>
                    </div>
                  </div>
                  <div className="mt-2 pt-2 border-t border-white/20 flex items-center justify-between text-[13px] font-extrabold">
                    <span className="flex items-center gap-1">
                      <TrendingDown size={16} /> Ahorro de bolsillo:
                    </span>
                    <span className="text-[16px] text-amber-300">
                      +{formatPrice(ticketResult.ahorro)}
                    </span>
                  </div>
                </div>

                {/* Desglose de ítems */}
                <div className="bg-white rounded-2xl border border-slate-200/80 overflow-hidden divide-y divide-slate-100 shadow-2xs">
                  <div className="p-3 bg-slate-50 font-bold text-[12px] text-slate-700 uppercase tracking-wider">
                    Productos detectados ({ticketResult.items.length})
                  </div>
                  {ticketResult.items.map((it, idx) => (
                    <div key={idx} className="p-3 flex items-start justify-between gap-2.5">
                      <div className="min-w-0 flex-1">
                        <div className="text-[13px] font-bold text-slate-900 leading-snug">
                          {it.product?.nombre || it.nombre_ticket}
                        </div>
                        <div className="text-[11px] text-slate-500 mt-0.5">
                          En ticket: {formatPrice(it.precio_ticket)} {it.qty > 1 ? `(${it.qty} un)` : ''}
                        </div>
                        {it.product && (
                          <div className="flex items-center gap-1.5 mt-1">
                            <span
                              className="w-2 h-2 rounded-full shrink-0"
                              style={{ background: storeColor(it.product.supermercado) }}
                            />
                            <span className="text-[11px] font-bold text-slate-700">
                              {storeLabel(it.product.supermercado)}: {formatPrice(it.product.precio)}
                            </span>
                          </div>
                        )}
                      </div>
                      <div className="text-right shrink-0">
                        {it.ahorro > 0 ? (
                          <span className="text-[11px] font-extrabold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200/50">
                            -{formatPrice(it.ahorro)}
                          </span>
                        ) : (
                          <span className="text-[11px] text-slate-400 font-medium">Mismo precio</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Botón para cargar al changuito */}
                {!addedTicketToCart ? (
                  <button
                    type="button"
                    onClick={handleAddTicketItemsToCart}
                    className="w-full h-12 rounded-2xl bg-blue-600 text-white font-extrabold text-[14px] flex items-center justify-center gap-2 shadow-md shadow-blue-500/20 active:scale-[0.98] transition-all"
                  >
                    <ShoppingBasket size={18} /> Cargar estos productos a Mi Lista
                  </button>
                ) : (
                  <div className="space-y-2">
                    <div className="p-3 rounded-xl bg-emerald-50 text-emerald-800 text-[13px] font-bold flex items-center justify-center gap-2 border border-emerald-200">
                      <CheckCircle2 size={16} /> ¡Productos cargados en Mi Lista!
                    </div>
                    <button
                      type="button"
                      onClick={onGoCart}
                      className="w-full h-11 rounded-xl bg-slate-900 text-white font-bold text-[13px] flex items-center justify-center gap-2"
                    >
                      Ir a optimizar mi changuito <ArrowRight size={15} />
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 2: PROMPT-TO-CART (RECETAS Y MENÚS) */}
        {/* ============================================================== */}
        {activeTab === 'receta' && (
          <div className="space-y-4">
            <div className="p-5 rounded-2xl bg-white border border-slate-200/80 shadow-2xs space-y-3">
              <div className="w-14 h-14 mx-auto rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center shadow-xs">
                <ChefHat size={28} />
              </div>
              <div className="text-center">
                <h2 className="text-[17px] font-extrabold text-slate-900">
                  Pedí lo que querés cocinar
                </h2>
                <p className="text-[13px] text-slate-500 max-w-sm mx-auto mt-1">
                  Decile a la IA qué querés preparar o tu presupuesto, y te arma el changuito óptimo con los mejores precios.
                </p>
              </div>

              <div className="space-y-2">
                <textarea
                  value={recipePrompt}
                  onChange={e => setRecipePrompt(e.target.value)}
                  placeholder="Ej: Asado completo para 6 amigos con fernet, gaseosa y carbón…"
                  rows={3}
                  className="w-full p-3 rounded-xl border border-slate-200 text-[14px] placeholder:text-slate-400 focus:outline-none focus:border-blue-500 font-medium"
                />

                {/* Ideas de prompt rápidas */}
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {SAMPLE_PROMPTS.map((sample, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => triggerRecipePrompt(sample)}
                      className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-slate-100 hover:bg-blue-50 hover:text-blue-700 text-slate-700 border border-slate-200/80 transition-colors"
                    >
                      {sample}
                    </button>
                  ))}
                </div>

                <button
                  type="button"
                  onClick={() => triggerRecipePrompt()}
                  disabled={!recipePrompt.trim() || generatingRecipe}
                  className="w-full h-12 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 text-white font-extrabold text-[14px] flex items-center justify-center gap-2 shadow-md shadow-orange-500/20 active:scale-[0.98] transition-all disabled:opacity-50"
                >
                  <Sparkles size={18} /> Generar Changuito con IA
                </button>
              </div>

              <p className="text-[11px] text-slate-400 text-center">
                💡 Cada generación está financiada por 1 anuncio patrocinado de 15 segundos.
              </p>
            </div>

            {generatingRecipe && (
              <div className="p-8 rounded-2xl bg-white border border-slate-200 text-center space-y-3">
                <Loader2 size={32} className="animate-spin text-amber-500 mx-auto" />
                <h3 className="text-[15px] font-extrabold text-slate-900">
                  Planificando ingredientes y buscando ofertas…
                </h3>
                <p className="text-[12px] text-slate-500">
                  Desglosando cantidades exactas y cotizando en los supermercados más convenientes.
                </p>
              </div>
            )}

            {recipeError && (
              <div className="p-4 rounded-xl bg-red-50 text-red-700 border border-red-100 flex items-center gap-2 text-[13px]">
                <AlertCircle size={16} className="shrink-0" />
                <span>{recipeError}</span>
              </div>
            )}

            {/* Resultado de la receta generada */}
            {recipeResult && (
              <div className="space-y-3">
                <div className="p-4 rounded-2xl bg-gradient-to-br from-slate-900 to-slate-800 text-white shadow-md">
                  <div className="flex items-center justify-between text-[12px] text-slate-300">
                    <span className="font-bold uppercase tracking-wider">Menú sugerido</span>
                    <span>{recipeResult.porciones} porciones</span>
                  </div>
                  <h3 className="text-[20px] font-extrabold tracking-tight mt-1">
                    {recipeResult.titulo}
                  </h3>
                  <div className="mt-3 pt-3 border-t border-slate-700/80 flex items-center justify-between">
                    <span className="text-[13px] text-slate-300">Costo total estimado:</span>
                    <span className="text-[24px] font-black text-amber-400">
                      {formatPrice(recipeResult.total_estimado)}
                    </span>
                  </div>
                </div>

                {/* Lista de ingredientes encontrados */}
                <div className="bg-white rounded-2xl border border-slate-200/80 overflow-hidden divide-y divide-slate-100 shadow-2xs">
                  <div className="p-3 bg-slate-50 font-bold text-[12px] text-slate-700 uppercase tracking-wider">
                    Ingredientes recomendados ({recipeResult.ingredientes.length})
                  </div>
                  {recipeResult.ingredientes.map((ing, idx) => (
                    <div key={idx} className="p-3 flex items-start justify-between gap-2.5">
                      <div className="min-w-0 flex-1">
                        <div className="text-[13px] font-bold text-slate-900 leading-snug">
                          {ing.product?.nombre || ing.item_pedido}
                        </div>
                        <div className="text-[11px] text-slate-500 mt-0.5">
                          Cantidad sugerida: {ing.item_pedido || `${ing.qty} ${ing.unit}`}
                        </div>
                        {ing.product && (
                          <div className="flex items-center gap-1.5 mt-1">
                            <span
                              className="w-2 h-2 rounded-full shrink-0"
                              style={{ background: storeColor(ing.product.supermercado) }}
                            />
                            <span className="text-[11px] font-semibold text-slate-700">
                              {storeLabel(ing.product.supermercado)}
                            </span>
                          </div>
                        )}
                      </div>
                      <div className="text-right shrink-0 font-extrabold text-[13px] text-slate-900">
                        {ing.product ? formatPrice(ing.product.subtotal) : '—'}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Botón de carga al changuito */}
                {!addedRecipeToCart ? (
                  <button
                    type="button"
                    onClick={handleAddRecipeItemsToCart}
                    className="w-full h-12 rounded-2xl bg-amber-600 hover:bg-amber-700 text-white font-extrabold text-[14px] flex items-center justify-center gap-2 shadow-md shadow-amber-500/20 active:scale-[0.98] transition-all"
                  >
                    <ShoppingBasket size={18} /> Cargar ingredientes a Mi Lista
                  </button>
                ) : (
                  <div className="space-y-2">
                    <div className="p-3 rounded-xl bg-emerald-50 text-emerald-800 text-[13px] font-bold flex items-center justify-center gap-2 border border-emerald-200">
                      <CheckCircle2 size={16} /> ¡Ingredientes agregados a tu lista!
                    </div>
                    <button
                      type="button"
                      onClick={onGoCart}
                      className="w-full h-11 rounded-xl bg-slate-900 text-white font-bold text-[13px] flex items-center justify-center gap-2"
                    >
                      Ir a optimizar mi changuito <ArrowRight size={15} />
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </main>

      {/* Modal del Anuncio Recompensado Obligatorio de 15 segundos */}
      <RewardedAdModal
        isOpen={adModalOpen}
        onClose={() => setAdModalOpen(false)}
        onRewardUnlocked={handleRewardUnlocked}
        featureName={
          pendingAction === 'ticket' ? 'el escaneo de ticket con IA' : 'la receta inteligente'
        }
      />
    </div>
  )
}

export default AIScreen
