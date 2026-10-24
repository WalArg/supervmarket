import React from 'react'
import { X, CreditCard, Calendar, ExternalLink, Check, Sparkles, Building2, Wallet } from 'lucide-react'
import { useBenefits } from '../benefits/BenefitsContext'
import { STORE_BRANDS, formatPrice } from './OfferCard'

interface BenefitsModalProps {
  open: boolean
  onClose: () => void
}

const SHORT_DAYS: Record<string, string> = {
  lunes: 'Lun',
  martes: 'Mar',
  miercoles: 'Mié',
  jueves: 'Jue',
  viernes: 'Vie',
  sabado: 'Sáb',
  domingo: 'Dom',
}

const BenefitsModal: React.FC<BenefitsModalProps> = ({ open, onClose }) => {
  const {
    catalog,
    selectedCards,
    selectedDay,
    toggleCard,
    clearCards,
    setSelectedDay,
    promosForDay,
  } = useBenefits()

  if (!open) return null

  const clubs = catalog?.payment_options.filter(p => p.category === 'club') || []
  const wallets = catalog?.payment_options.filter(p => p.category === 'wallet') || []
  const banks = catalog?.payment_options.filter(p => p.category === 'bank') || []
  const dayPromos = promosForDay(selectedDay)
  const myDayPromos = dayPromos.filter(p => selectedCards.includes(p.payment_id))

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4">
      <div className="absolute inset-0 bg-slate-900/50 backdrop-blur-xs" onClick={onClose} />

      <div className="relative bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-purple-100 text-purple-700">
              <CreditCard size={18} />
            </div>
            <div>
              <h2 className="text-sm sm:text-base font-extrabold text-slate-900">
                Mis Tarjetas, Billeteras y Día de Compra
              </h2>
              <p className="text-[11px] text-slate-500">
                Solo aplicamos descuentos de tarjetas o membresías que vos selecciones acá.
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/60"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-5 text-xs">
          {/* 1. Selector de Día de Compra */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="font-extrabold text-slate-800 flex items-center gap-1.5">
                <Calendar size={14} className="text-blue-600" />
                1. ¿Qué día pensás hacer la compra?
              </span>
              {catalog?.today && (
                <button
                  type="button"
                  onClick={() => setSelectedDay(catalog.today)}
                  className="text-[11px] font-bold text-blue-600 hover:underline"
                >
                  Ir a Hoy ({catalog.today_label})
                </button>
              )}
            </div>

            <div className="grid grid-cols-7 gap-1.5">
              {(
                catalog?.weekdays || [
                  { id: 'lunes', label: 'Lunes' },
                  { id: 'martes', label: 'Martes' },
                  { id: 'miercoles', label: 'Miércoles' },
                  { id: 'jueves', label: 'Jueves' },
                  { id: 'viernes', label: 'Viernes' },
                  { id: 'sabado', label: 'Sábado' },
                  { id: 'domingo', label: 'Domingo' },
                ]
              ).map(d => {
                const isSelected = selectedDay === d.id
                const isToday = catalog?.today === d.id
                return (
                  <button
                    key={d.id}
                    type="button"
                    onClick={() => setSelectedDay(d.id)}
                    className={`py-2 px-1 rounded-xl border text-center transition-all relative ${
                      isSelected
                        ? 'bg-blue-600 text-white border-blue-600 font-extrabold shadow-xs'
                        : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100 font-semibold'
                    }`}
                  >
                    <div>{SHORT_DAYS[d.id] || d.label}</div>
                    {isToday && (
                      <span
                        className={`block text-[9px] font-extrabold uppercase mt-0.5 ${
                          isSelected ? 'text-amber-300' : 'text-blue-600'
                        }`}
                      >
                        Hoy
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          </div>

          {/* 2. Selector de Membresías, Billeteras y Bancos */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-extrabold text-slate-800 flex items-center gap-1.5">
                <Sparkles size={14} className="text-purple-600" />
                2. Marcá tus Membresías, Billeteras y Bancos ({selectedCards.length} activos)
              </span>
              {selectedCards.length > 0 && (
                <button
                  type="button"
                  onClick={clearCards}
                  className="text-[11px] text-rose-600 font-bold hover:underline"
                >
                  Desmarcar todos
                </button>
              )}
            </div>

            {/* Clubes y tarjetas de supermercado */}
            <div className="bg-purple-50/50 border border-purple-100 rounded-xl p-3">
              <div className="text-[11px] font-extrabold text-purple-900 mb-2 flex items-center gap-1.5">
                <CreditCard size={13} className="text-purple-600" />
                Clubes y Tarjetas del Supermercado (habilitan ofertas exclusivas en productos)
              </div>
              <div className="flex flex-wrap gap-1.5">
                {clubs.map(opt => {
                  const active = selectedCards.includes(opt.id)
                  return (
                    <button
                      key={opt.id}
                      type="button"
                      onClick={() => toggleCard(opt.id)}
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border font-bold transition-all ${
                        active
                          ? 'bg-purple-600 text-white border-purple-600 shadow-2xs'
                          : 'bg-white text-slate-700 border-slate-200 hover:border-purple-300'
                      }`}
                    >
                      {active && <Check size={12} />}
                      <span>{opt.name}</span>
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Billeteras virtuales */}
            <div className="bg-slate-50 border border-slate-200/80 rounded-xl p-3">
              <div className="text-[11px] font-extrabold text-slate-800 mb-2 flex items-center gap-1.5">
                <Wallet size={13} className="text-emerald-600" />
                Billeteras Virtuales (reintegros y descuentos por día)
              </div>
              <div className="flex flex-wrap gap-1.5">
                {wallets.map(opt => {
                  const active = selectedCards.includes(opt.id)
                  return (
                    <button
                      key={opt.id}
                      type="button"
                      onClick={() => toggleCard(opt.id)}
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border font-bold transition-all ${
                        active
                          ? 'bg-emerald-600 text-white border-emerald-600 shadow-2xs'
                          : 'bg-white text-slate-700 border-slate-200 hover:border-emerald-300'
                      }`}
                    >
                      {active && <Check size={12} />}
                      <span>{opt.name}</span>
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Bancos */}
            <div className="bg-slate-50 border border-slate-200/80 rounded-xl p-3">
              <div className="text-[11px] font-extrabold text-slate-800 mb-2 flex items-center gap-1.5">
                <Building2 size={13} className="text-blue-600" />
                Bancos y Beneficios (reintegros por día en carrito)
              </div>
              <div className="flex flex-wrap gap-1.5">
                {banks.map(opt => {
                  const active = selectedCards.includes(opt.id)
                  return (
                    <button
                      key={opt.id}
                      type="button"
                      onClick={() => toggleCard(opt.id)}
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border font-bold transition-all ${
                        active
                          ? 'bg-blue-600 text-white border-blue-600 shadow-2xs'
                          : 'bg-white text-slate-700 border-slate-200 hover:border-blue-300'
                      }`}
                    >
                      {active && <Check size={12} />}
                      <span>{opt.name}</span>
                    </button>
                  )
                })}
              </div>
            </div>
          </div>

          {/* 3. Grilla de Promociones del Día Seleccionado */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="font-extrabold text-slate-800">
                Promociones bancarias y de billeteras del{' '}
                <span className="text-blue-600 capitalize">{selectedDay}</span> (
                {myDayPromos.length > 0
                  ? `${myDayPromos.length} coinciden con tus tarjetas`
                  : `${dayPromos.length} disponibles`}
                )
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {dayPromos.map((p, idx) => {
                const isMine = selectedCards.includes(p.payment_id)
                const b = STORE_BRANDS[p.supermercado]
                return (
                  <a
                    key={`${p.supermercado}-${p.payment_id}-${idx}`}
                    href={p.official_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`p-2.5 rounded-xl border flex items-start justify-between gap-2 transition-all ${
                      isMine
                        ? 'bg-emerald-50/80 border-emerald-400 ring-1 ring-emerald-400'
                        : 'bg-white border-slate-200 hover:border-slate-300'
                    }`}
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className={`w-2 h-2 rounded-full ${b?.dot || 'bg-slate-400'}`} />
                        <span className={`font-extrabold ${b?.text || 'text-slate-800'}`}>
                          {p.supermercado}
                        </span>
                        {isMine && (
                          <span className="px-1.5 py-0.2 rounded bg-emerald-600 text-white text-[9px] font-extrabold">
                            TENÉS ESTA TARJETA
                          </span>
                        )}
                      </div>
                      <div className="font-bold text-slate-900 mt-1">{p.label}</div>
                      <div className="text-[10px] text-slate-500 mt-0.5">
                        {p.cap ? `Tope: ${formatPrice(p.cap)}` : 'Sin tope de reintegro'} ·{' '}
                        {p.kind === 'en_caja' ? 'Descuento en caja' : 'Reintegro en cuenta'}
                      </div>
                    </div>

                    <div className="flex flex-col items-end shrink-0">
                      <span className="px-2 py-0.5 rounded-lg bg-slate-900 text-white font-extrabold text-xs">
                        {p.pct}%
                      </span>
                      <span className="text-[10px] text-blue-600 flex items-center gap-0.5 mt-2">
                        Bases <ExternalLink size={9} />
                      </span>
                    </div>
                  </a>
                )
              })}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-4 py-2.5 bg-slate-50 border-t border-slate-200 flex items-center justify-between">
          <span className="text-[11px] text-slate-500">
            Tus tarjetas quedan guardadas en este dispositivo.
          </span>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-extrabold text-xs"
          >
            Aplicar y cerrar
          </button>
        </div>
      </div>
    </div>
  )
}

export default BenefitsModal
