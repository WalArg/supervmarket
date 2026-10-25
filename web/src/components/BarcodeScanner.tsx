import React, { useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'

/** Escáner de código de barras (EAN) con la cámara trasera del celular. */
const BarcodeScanner: React.FC<{ onDetected: (ean: string) => void; onClose: () => void }> = ({
  onDetected,
  onClose,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let stopped = false
    let controls: { stop: () => void } | undefined
    ;(async () => {
      try {
        const { BrowserMultiFormatReader } = await import('@zxing/browser')
        const reader = new BrowserMultiFormatReader()
        controls = await reader.decodeFromConstraints(
          { video: { facingMode: { ideal: 'environment' } } },
          videoRef.current!,
          res => {
            if (!res || stopped) return
            const text = res.getText()
            if (/^\d{8,14}$/.test(text)) {
              stopped = true
              navigator.vibrate?.(60)
              controls?.stop()
              onDetected(text)
            }
          },
        )
        if (stopped) controls.stop()
      } catch {
        setError('No pudimos acceder a la cámara. Revisá los permisos del navegador.')
      }
    })()
    return () => {
      stopped = true
      controls?.stop()
    }
  }, [onDetected])

  return (
    <div className="fixed inset-0 z-[60] bg-black flex flex-col">
      <div className="pt-safe flex items-center justify-between px-4 py-3 text-white">
        <span className="font-bold">Escaneá el código de barras</span>
        <button type="button" onClick={onClose} aria-label="Cerrar" className="p-2 -mr-2 rounded-full active:bg-white/10">
          <X size={24} />
        </button>
      </div>
      <div className="relative flex-1">
        <video ref={videoRef} className="absolute inset-0 w-full h-full object-cover" muted playsInline />
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="w-[78%] max-w-sm h-36 rounded-2xl border-[3px] border-white/90 shadow-[0_0_0_9999px_rgba(0,0,0,0.45)]" />
        </div>
        {error && (
          <div className="absolute inset-x-6 bottom-10 bg-white rounded-xl p-4 text-sm text-slate-800 text-center">
            {error}
          </div>
        )}
      </div>
      <p className="pb-safe text-center text-white/80 text-sm py-4">
        Apuntá al código del producto en la góndola para comparar precios al instante
      </p>
    </div>
  )
}

export default BarcodeScanner
