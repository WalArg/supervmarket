import React, { useEffect, useState, useRef } from 'react'
import {
  Sparkles,
  Volume2,
  VolumeX,
  ExternalLink,
  CheckCircle2,
  Lock,
  Loader2,
  X,
  ShieldCheck,
} from 'lucide-react'

interface SponsorAd {
  brand: string
  tagline: string
  badge: string
  bgGradient: string
  textColor: string
  ctaText: string
  ctaUrl: string
  bulletPoints: string[]
  accentColor: string
}

const SPONSORS: SponsorAd[] = [
  {
    brand: 'Mercado Pago',
    tagline: 'Tu dinero rinde todos los días automáticamente',
    badge: 'Cuenta Remunerada',
    bgGradient: 'from-sky-500 via-blue-600 to-indigo-700',
    textColor: 'text-sky-100',
    ctaText: 'Abrir cuenta gratis',
    ctaUrl: 'https://www.mercadopago.com.ar',
    bulletPoints: [
      'Generá rendimientos diarios con tu saldo',
      'Sin costos de mantenimiento ni comisiones',
      'Descuentos exclusivos en supermercados adheridos',
    ],
    accentColor: '#009ee3',
  },
  {
    brand: 'Ualá',
    tagline: 'Tarjeta Mastercard Internacional y rendimientos reales',
    badge: 'Fintech Argentina',
    bgGradient: 'from-red-500 via-rose-600 to-indigo-800',
    textColor: 'text-rose-100',
    ctaText: 'Pedí tu tarjeta ahora',
    ctaUrl: 'https://www.uala.com.ar',
    bulletPoints: [
      'Hasta 25% de reintegro en supermercados y combustible',
      'Invertí en plazos fijos y fondos comunes de inversión',
      '100% gratuita y sin burocracia bancaria',
    ],
    accentColor: '#e02844',
  },
  {
    brand: 'Banco Galicia',
    tagline: 'Ahorrá hasta 30% en Coto, Carrefour y Jumbo cada semana',
    badge: 'Beneficios Exclusivos',
    bgGradient: 'from-orange-500 via-amber-600 to-red-700',
    textColor: 'text-amber-100',
    ctaText: 'Ver promociones',
    ctaUrl: 'https://www.galicia.ar',
    bulletPoints: [
      'Promociones fijas todos los miércoles y jueves',
      'Cuotas sin interés en compras online',
      'Puntos Quiero! acumulables en cada compra de changuito',
    ],
    accentColor: '#f36e21',
  },
]

interface RewardedAdModalProps {
  isOpen: boolean
  onClose: () => void
  onRewardUnlocked: () => void
  featureName?: string
}

export const RewardedAdModal: React.FC<RewardedAdModalProps> = ({
  isOpen,
  onClose,
  onRewardUnlocked,
  featureName = 'la funcionalidad de IA',
}) => {
  const [countdown, setCountdown] = useState(15)
  const [isCompleted, setIsCompleted] = useState(false)
  const [isMuted, setIsMuted] = useState(true)
  const [sponsorIndex, setSponsorIndex] = useState(0)
  const timerRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    if (isOpen) {
      setCountdown(15)
      setIsCompleted(false)
      // Rotar sponsor al azar
      setSponsorIndex(Math.floor(Math.random() * SPONSORS.length))

      timerRef.current = setInterval(() => {
        setCountdown(prev => {
          if (prev <= 1) {
            clearInterval(timerRef.current!)
            setIsCompleted(true)
            return 0
          }
          return prev - 1
        })
      }, 1000)
    } else {
      if (timerRef.current) clearInterval(timerRef.current)
    }

    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [isOpen])

  if (!isOpen) return null

  const sponsor = SPONSORS[sponsorIndex]
  const progressPercent = Math.min(100, Math.round(((15 - countdown) / 15) * 100))

  const handleClaim = () => {
    onRewardUnlocked()
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/85 backdrop-blur-md animate-in fade-in duration-200">
      <div
        className="w-full max-w-md bg-white rounded-3xl shadow-2xl overflow-hidden border border-slate-800 flex flex-col relative animate-in zoom-in-95 duration-200"
        onClick={e => e.stopPropagation()}
      >
        {/* Barra superior de status publicitario */}
        <div className="bg-slate-900 text-slate-300 px-4 py-2.5 flex items-center justify-between text-[11px] font-bold">
          <span className="flex items-center gap-1.5 text-amber-400">
            <Sparkles size={13} /> Anuncio Recompensado
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setIsMuted(v => !v)}
              className="text-slate-400 hover:text-white p-1"
              aria-label={isMuted ? 'Activar sonido' : 'Silenciar'}
            >
              {isMuted ? <VolumeX size={15} /> : <Volume2 size={15} />}
            </button>
            {isCompleted ? (
              <button
                type="button"
                onClick={onClose}
                className="w-6 h-6 rounded-full bg-slate-800 hover:bg-slate-700 flex items-center justify-center text-slate-300"
              >
                <X size={14} />
              </button>
            ) : (
              <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">
                <Lock size={10} /> {countdown}s
              </span>
            )}
          </div>
        </div>

        {/* Video / Banner Interactivo del Patrocinador */}
        <div
          className={`p-6 bg-gradient-to-br ${sponsor.bgGradient} text-white flex flex-col justify-between min-h-[260px] relative overflow-hidden`}
        >
          {/* Círculos decorativos de fondo */}
          <div className="absolute -right-8 -top-8 w-36 h-36 bg-white/10 rounded-full blur-xl pointer-events-none" />
          <div className="absolute -left-10 -bottom-10 w-44 h-44 bg-black/20 rounded-full blur-2xl pointer-events-none" />

          <div>
            <div className="inline-block px-2.5 py-0.5 rounded-full bg-white/20 backdrop-blur-md text-[11px] font-extrabold uppercase tracking-wider mb-2">
              {sponsor.badge}
            </div>
            <h3 className="text-[22px] font-black tracking-tight leading-tight">
              {sponsor.brand}
            </h3>
            <p className={`text-[13px] font-medium mt-1 leading-snug ${sponsor.textColor}`}>
              {sponsor.tagline}
            </p>
          </div>

          <div className="my-4 space-y-1.5">
            {sponsor.bulletPoints.map((b, idx) => (
              <div key={idx} className="flex items-center gap-2 text-[12px] font-medium">
                <ShieldCheck size={14} className="shrink-0 text-white/80" />
                <span className="leading-snug">{b}</span>
              </div>
            ))}
          </div>

          <div className="pt-2 flex items-center justify-between">
            <a
              href={sponsor.ctaUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white text-slate-900 font-bold text-[12px] shadow-lg active:scale-95 transition-all hover:bg-slate-100"
            >
              <span>{sponsor.ctaText}</span>
              <ExternalLink size={13} />
            </a>
            <span className="text-[10px] text-white/60 uppercase tracking-widest font-bold">
              Publicidad
            </span>
          </div>

          {/* Barra de progreso de visualización obligatoria */}
          <div className="absolute bottom-0 inset-x-0 h-1.5 bg-black/30">
            <div
              className="h-full bg-amber-400 transition-all duration-1000 ease-linear"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        {/* Zona inferior de desbloqueo */}
        <div className="p-4 bg-white text-center space-y-3">
          {!isCompleted ? (
            <div className="space-y-1.5">
              <div className="flex items-center justify-center gap-2 text-slate-700 text-[13px] font-bold">
                <Loader2 size={16} className="animate-spin text-blue-600" />
                <span>Mirá el anuncio para desbloquear {featureName}</span>
              </div>
              <p className="text-[11px] text-slate-400">
                Tu recompensa se activará al finalizar los {countdown} segundos
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center justify-center gap-2 text-emerald-700 font-extrabold text-[14px]">
                <CheckCircle2 size={18} className="text-emerald-600" />
                <span>¡Recompensa desbloqueada exitosamente!</span>
              </div>
              <button
                type="button"
                onClick={handleClaim}
                className="w-full h-12 rounded-2xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-extrabold text-[14px] flex items-center justify-center gap-2 shadow-lg shadow-blue-500/25 active:scale-[0.98] transition-all animate-pulse"
              >
                <Sparkles size={17} /> Continuar con la IA
              </button>
            </div>
          )}

          <p className="text-[10px] text-slate-400 pt-1 border-t border-slate-100 leading-tight">
            💡 Este anuncio financia el costo computacional de la Inteligencia Artificial para que SuperVmarket siga siendo 100% gratuito para vos.
          </p>
        </div>
      </div>
    </div>
  )
}
