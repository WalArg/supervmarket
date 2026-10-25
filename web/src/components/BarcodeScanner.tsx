import React, { useEffect, useRef, useState, useCallback } from 'react'
import { X, Zap, ZapOff, Keyboard, ArrowRight } from 'lucide-react'

interface BarcodeScannerProps {
  onDetected: (ean: string) => void
  onClose: () => void
}

/** Reproduce un "beep" sutil al leer exitosamente el código (estilo caja de súper). */
const playBeep = () => {
  try {
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
    if (!AudioCtx) return
    const ctx = new AudioCtx()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = 'sine'
    osc.frequency.setValueAtTime(1760, ctx.currentTime) // Nota A6 nítida y limpia
    gain.gain.setValueAtTime(0.12, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.09)
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.start()
    osc.stop(ctx.currentTime + 0.09)
  } catch {
    // Si el navegador bloquea audio sin gesto previo, ignoramos
  }
}

/**
 * Escáner de código de barras de alta velocidad optimizado para góndolas:
 * 1. Usa la API nativa de hardware `BarcodeDetector` (60 FPS, <10ms por frame) si está disponible (Android Chrome / Edge).
 * 2. Si no, usa `@zxing/browser` restringido exclusivamente a 1D (EAN-13, EAN-8, UPC) con escaneo continuo cada 60ms (no 500ms).
 * 3. Configura autofoco continuo y resolución óptima 720p para evitar retrasos por resolución 4K.
 * 4. Botón de linterna (torch) y opción de ingresar código numérico a mano.
 */
const BarcodeScanner: React.FC<BarcodeScannerProps> = ({ onDetected, onClose }) => {
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [torchAvailable, setTorchAvailable] = useState(false)
  const [torchOn, setTorchOn] = useState(false)
  const [manualMode, setManualMode] = useState(false)
  const [manualCode, setManualCode] = useState('')
  const [activeEngine, setActiveEngine] = useState<'native' | 'zxing' | 'starting'>('starting')

  // Manejador centralizado de detección exitosa
  const handleSuccess = useCallback((code: string) => {
    const clean = code.trim()
    if (!/^\d{8,14}$/.test(clean)) return
    playBeep()
    if (typeof navigator !== 'undefined' && 'vibrate' in navigator) {
      try {
        navigator.vibrate([50, 40, 50])
      } catch {
        // no-op
      }
    }
    onDetected(clean)
  }, [onDetected])

  // Iniciar cámara y motor de detección
  useEffect(() => {
    let stopped = false
    let frameId: number | undefined
    let zxingControls: { stop: () => void } | undefined

    const initScanner = async () => {
      try {
        // 1. Solicitar cámara con autofoco continuo y resolución óptima (1280x720)
        // 720p es ideal: suficiente nitidez para barras finas pero 4x más liviano que 1080p/4K
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: { ideal: 'environment' },
            width: { ideal: 1280, min: 640 },
            height: { ideal: 720, min: 480 },
            // eslint-disable-next-line @typescript-eslint/ban-ts-comment
            // @ts-ignore
            focusMode: { ideal: 'continuous' },
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            advanced: [{ focusMode: 'continuous' }] as any,
          },
          audio: false,
        })

        if (stopped) {
          stream.getTracks().forEach(t => t.stop())
          return
        }

        streamRef.current = stream

        // Verificar si soporta linterna (flash)
        const track = stream.getVideoTracks()[0]
        if (track && 'getCapabilities' in track) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const caps = (track.getCapabilities as any)()
          if (caps && 'torch' in caps) {
            setTorchAvailable(true)
          }
        }

        if (videoRef.current) {
          videoRef.current.srcObject = stream
          await videoRef.current.play()
        }

        // 2. Probar API nativa BarcodeDetector (ultra rápida por aceleración GPU)
        const hasNative = typeof window !== 'undefined' && 'BarcodeDetector' in window
        if (hasNative) {
          try {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const BD = (window as any).BarcodeDetector
            const formats: string[] = (await BD.getSupportedFormats?.()) || []
            const targetFormats = ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128']
            const chosen = formats.length ? targetFormats.filter(f => formats.includes(f)) : targetFormats

            const detector = new BD({ formats: chosen })
            setActiveEngine('native')

            // Bucle nativo súper eficiente usando requestVideoFrameCallback o requestAnimationFrame
            const scanNativeFrame = async () => {
              if (stopped) return
              const video = videoRef.current
              if (video && video.readyState >= 2) {
                try {
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  const barcodes = await detector.detect(video)
                  if (barcodes && barcodes.length > 0) {
                    for (const b of barcodes) {
                      const val = (b.rawValue || '').trim()
                      if (/^\d{8,14}$/.test(val)) {
                        stopped = true
                        handleSuccess(val)
                        return
                      }
                    }
                  }
                } catch {
                  // Ignorar errores transitorios de cuadro
                }
              }

              if (!stopped) {
                if (video && 'requestVideoFrameCallback' in video) {
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  (video as any).requestVideoFrameCallback(scanNativeFrame)
                } else {
                  frameId = requestAnimationFrame(scanNativeFrame)
                }
              }
            }

            scanNativeFrame()
            return // Motor nativo activado con éxito
          } catch {
            // Si el motor nativo falla al inicializarse, continuar al fallback ZXing
          }
        }

        // 3. Fallback: ZXing optimizado específicamente para 1D de supermercado
        setActiveEngine('zxing')
        const [{ BrowserMultiFormatReader }, { BarcodeFormat, DecodeHintType }] = await Promise.all([
          import('@zxing/browser'),
          import('@zxing/library'),
        ])

        if (stopped) return

        const hints = new Map()
        // Restringir SOLAMENTE a formatos de góndola evita procesar 15 tipos de códigos 2D
        hints.set(DecodeHintType.POSSIBLE_FORMATS, [
          BarcodeFormat.EAN_13,
          BarcodeFormat.EAN_8,
          BarcodeFormat.UPC_A,
          BarcodeFormat.UPC_E,
          BarcodeFormat.CODE_128,
        ])
        hints.set(DecodeHintType.TRY_HARDER, true)

        const reader = new BrowserMultiFormatReader(hints, {
          delayBetweenScanAttempts: 60, // 60ms en vez de 500ms: respuesta 8x más rápida
          delayBetweenScanSuccess: 500,
        })

        if (videoRef.current) {
          zxingControls = await reader.decodeFromStream(stream, videoRef.current, res => {
            if (!res || stopped) return
            const text = res.getText()
            if (/^\d{8,14}$/.test(text)) {
              stopped = true
              zxingControls?.stop()
              handleSuccess(text)
            }
          })
        }
      } catch (err) {
        if (!stopped) {
          setError('No pudimos acceder a la cámara. Verificá los permisos del navegador o ingresá el código a mano.')
        }
      }
    }

    initScanner()

    return () => {
      stopped = true
      if (frameId) cancelAnimationFrame(frameId)
      zxingControls?.stop()
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop())
        streamRef.current = null
      }
    }
  }, [handleSuccess])

  // Alternar linterna
  const toggleTorch = async () => {
    if (!streamRef.current) return
    const track = streamRef.current.getVideoTracks()[0]
    if (!track) return
    const nextState = !torchOn
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      await (track.applyConstraints as any)({
        advanced: [{ torch: nextState }],
      })
      setTorchOn(nextState)
    } catch {
      // no-op
    }
  }

  const handleManualSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const clean = manualCode.trim().replace(/\D/g, '')
    if (clean.length >= 8 && clean.length <= 14) {
      handleSuccess(clean)
    }
  }

  return (
    <div className="fixed inset-0 z-[60] bg-black flex flex-col select-none">
      {/* Barra superior con controles */}
      <div className="pt-safe flex items-center justify-between px-4 py-3 text-white z-20 bg-gradient-to-b from-black/80 to-transparent">
        <div className="flex items-center gap-2">
          <span className="font-bold text-[16px]">Escanear producto</span>
          {activeEngine === 'native' && (
            <span className="text-[10px] bg-emerald-500/20 text-emerald-300 font-extrabold px-2 py-0.5 rounded-full border border-emerald-500/30">
              ⚡ Modo Rápido
            </span>
          )}
        </div>

        <div className="flex items-center gap-1">
          {torchAvailable && !manualMode && (
            <button
              type="button"
              onClick={toggleTorch}
              aria-label="Linterna"
              className={`p-2.5 rounded-full transition-colors ${
                torchOn ? 'bg-amber-400 text-black' : 'bg-white/15 text-white active:bg-white/30'
              }`}
            >
              {torchOn ? <Zap size={20} className="fill-current" /> : <ZapOff size={20} />}
            </button>
          )}

          <button
            type="button"
            onClick={onClose}
            aria-label="Cerrar escáner"
            className="p-2.5 rounded-full bg-white/15 text-white active:bg-white/30"
          >
            <X size={20} />
          </button>
        </div>
      </div>

      {/* Visor de la cámara */}
      <div className="relative flex-1 overflow-hidden bg-black flex items-center justify-center">
        <video
          ref={videoRef}
          className="absolute inset-0 w-full h-full object-cover"
          muted
          playsInline
          autoPlay
        />

        {!manualMode && (
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            {/* Recuadro de mira con esquinas marcadas */}
            <div className="relative w-[82%] max-w-sm h-36 rounded-2xl border-2 border-white/50 shadow-[0_0_0_9999px_rgba(0,0,0,0.55)] overflow-hidden">
              {/* Esquinas destacadas */}
              <div className="absolute top-0 left-0 w-5 h-5 border-t-4 border-l-4 border-blue-500 rounded-tl-lg" />
              <div className="absolute top-0 right-0 w-5 h-5 border-t-4 border-r-4 border-blue-500 rounded-tr-lg" />
              <div className="absolute bottom-0 left-0 w-5 h-5 border-b-4 border-l-4 border-blue-500 rounded-bl-lg" />
              <div className="absolute bottom-0 right-0 w-5 h-5 border-b-4 border-r-4 border-blue-500 rounded-br-lg" />

              {/* Láser rojo de lectura que se desplaza continuamente */}
              <div className="absolute inset-x-2 h-0.5 bg-gradient-to-r from-transparent via-red-500 to-transparent shadow-[0_0_10px_#ef4444] animate-laser" />
            </div>

            <p className="mt-6 text-[13px] font-medium text-white/90 drop-shadow px-6 text-center">
              Centrá las barras dentro del recuadro
            </p>
          </div>
        )}

        {/* Modal de ingreso manual cuando la cámara no enfoca o el código está roto */}
        {manualMode && (
          <div className="absolute inset-x-4 top-1/2 -translate-y-1/2 bg-slate-900 border border-slate-700 rounded-2xl p-5 text-white shadow-2xl z-30">
            <h3 className="font-extrabold text-[17px] mb-1">Ingresar código numérico</h3>
            <p className="text-[13px] text-slate-400 mb-4">
              Escribí los números que figuran debajo del código de barras (ej. 779...)
            </p>
            <form onSubmit={handleManualSubmit} className="space-y-4">
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                autoFocus
                placeholder="Ej. 7791234567890"
                value={manualCode}
                onChange={e => setManualCode(e.target.value)}
                className="w-full h-12 px-4 rounded-xl bg-slate-800 border border-slate-600 text-white font-mono text-[18px] text-center tracking-wider focus:outline-none focus:border-blue-500"
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setManualMode(false)}
                  className="flex-1 h-11 rounded-xl bg-slate-800 text-slate-300 font-semibold text-[14px]"
                >
                  Volver a cámara
                </button>
                <button
                  type="submit"
                  disabled={manualCode.trim().length < 8}
                  className="flex-1 h-11 rounded-xl bg-blue-600 disabled:bg-blue-600/40 text-white font-extrabold text-[14px] flex items-center justify-center gap-1.5"
                >
                  Buscar <ArrowRight size={16} />
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Mensaje de error de permisos */}
        {error && (
          <div className="absolute inset-x-6 top-1/2 -translate-y-1/2 bg-red-950/95 border border-red-500/50 rounded-2xl p-5 text-white text-center z-30">
            <p className="text-[14px] font-semibold mb-3">{error}</p>
            <button
              type="button"
              onClick={() => setManualMode(true)}
              className="h-10 px-4 rounded-xl bg-white text-slate-900 font-extrabold text-[13px]"
            >
              Ingresar código a mano
            </button>
          </div>
        )}
      </div>

      {/* Barra inferior: tips e ingreso manual */}
      <div className="pb-safe bg-gradient-to-t from-black/90 to-black/40 px-4 py-3 text-center z-20">
        {!manualMode && (
          <button
            type="button"
            onClick={() => setManualMode(true)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/10 hover:bg-white/20 active:bg-white/30 text-white text-[13px] font-medium transition-colors"
          >
            <Keyboard size={16} /> ¿Problemas para enfocar? Ingresar código a mano
          </button>
        )}
      </div>
    </div>
  )
}

export default BarcodeScanner