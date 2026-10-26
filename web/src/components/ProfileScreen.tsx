import React, { useEffect, useState } from 'react'
import { MapPin, Calendar, CreditCard, Wallet, Building2, Check, ExternalLink, Loader2, Navigation, AlertCircle } from 'lucide-react'
import { useBenefits } from '../benefits/BenefitsContext'
import { useLocation } from '../location/LocationContext'
import { storeColor, storeLabel } from '../lib/stores'
import { formatPrice } from '../lib/pricing'
import type { PaymentOption } from '../types'

const DAYS = [
  { id: 'lunes', short: 'Lun' },
  { id: 'martes', short: 'Mar' },
  { id: 'miercoles', short: 'Mié' },
  { id: 'jueves', short: 'Jue' },
  { id: 'viernes', short: 'Vie' },
  { id: 'sabado', short: 'Sáb' },
  { id: 'domingo', short: 'Dom' },
]

const Section: React.FC<{ icon: React.ReactNode; title: string; hint?: string; children: React.ReactNode }> = ({
  icon,
  title,
  hint,
  children,
}) => (
  <section className="bg-white rounded-2xl border border-slate-200/80 p-4">
    <h2 className="text-[14px] font-extrabold text-slate-900 flex items-center gap-2">
      {icon} {title}
    </h2>
    {hint && <p className="text-[12px] text-slate-500 mt-0.5">{hint}</p>}
    <div className="mt-3">{children}</div>
  </section>
)

const Toggles: React.FC<{ options: PaymentOption[]; selected: string[]; onToggle: (id: string) => void }> = ({
  options,
  selected,
  onToggle,
}) => (
  <div className="flex flex-wrap gap-2">
    {options.map(o => {
      const on = selected.includes(o.id)
      return (
        <button
          key={o.id}
          type="button"
          onClick={() => onToggle(o.id)}
          className={`h-9 px-3 rounded-full text-[13px] font-semibold border flex items-center gap-1.5 transition-colors ${
            on ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-slate-700 border-slate-200 active:bg-slate-100'
          }`}
        >
          {on && <Check size={14} strokeWidth={3} />}
          {o.name}
        </button>
      )
    })}
  </div>
)

const ProfileScreen: React.FC = () => {
  const {
    cp,
    locationLabel,
    setCp,
    openModal,
    detectLocation,
    isDetecting,
    detectError,
    loading: cpLoading,
    coverage,
  } = useLocation()
  const { catalog, selectedCards, selectedDay, toggleCard, setSelectedDay, promosForDay } = useBenefits()
  const [cpInput, setCpInput] = useState(cp || '')

  useEffect(() => {
    if (cp) setCpInput(cp)
  }, [cp])

  const opts = catalog?.payment_options || []
  const dayPromos = promosForDay(selectedDay)
  const mine = dayPromos.filter(p => selectedCards.includes(p.payment_id))
  const others = dayPromos.filter(p => !selectedCards.includes(p.payment_id))
  const deliverCount = coverage.filter(c => c.delivers).length

  return (
    <div>
      <header className="sticky top-0 z-30 bg-slate-50/95 backdrop-blur-md pt-safe">
        <div className="px-4 pt-3 pb-3">
          <h1 className="text-[20px] font-extrabold tracking-tight">Mi perfil</h1>
          <p className="text-[12px] text-slate-500">Personalizá precios, envíos y reintegros</p>
        </div>
      </header>

      <main className="px-4 pb-28 space-y-3">
        <Section icon={<MapPin size={17} className="text-blue-600" />} title="Ubicación de entrega" hint="Para mostrarte solo stock y súper que envían a tu zona.">
          <div className="space-y-2.5">
            {/* Tarjeta de ubicación activa */}
            <div className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-200">
              <div className="flex items-center gap-2.5 min-w-0 pr-2">
                <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center shrink-0">
                  <MapPin size={16} />
                </div>
                <div className="min-w-0">
                  <div className="text-[14px] font-extrabold text-slate-900 truncate">
                    {locationLabel || (cp ? `CP ${cp}` : 'Sin ubicación')}
                  </div>
                  <div className="text-[11px] text-slate-500 truncate">
                    {cp ? (cpLoading ? 'Verificando súper…' : `${deliverCount} supermercados con entrega`) : 'Configurá tu zona para ver disponibilidad'}
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={openModal}
                className="shrink-0 h-9 px-3 rounded-lg bg-blue-600 text-white text-[12px] font-bold hover:bg-blue-700 active:scale-95 transition-all"
              >
                Cambiar
              </button>
            </div>

            {/* Botón rápido GPS */}
            <button
              type="button"
              onClick={() => detectLocation()}
              disabled={isDetecting}
              className="w-full h-10 px-3 rounded-xl border border-blue-200 bg-blue-50/70 text-blue-700 hover:bg-blue-100/70 text-[12px] font-bold flex items-center justify-center gap-2 transition-all active:scale-[0.99] disabled:opacity-60"
            >
              {isDetecting ? (
                <Loader2 size={15} className="animate-spin text-blue-600" />
              ) : (
                <Navigation size={14} className="text-blue-600 fill-blue-600/30" />
              )}
              <span>{isDetecting ? 'Detectando coordenadas con GPS…' : 'Autodetectar con GPS actual'}</span>
            </button>

            {detectError && (
              <div className="flex items-center gap-1.5 p-2 rounded-lg bg-red-50 text-red-700 text-[11px] font-medium border border-red-100">
                <AlertCircle size={13} className="shrink-0" />
                <span>{detectError}</span>
              </div>
            )}
          </div>
        </Section>

        <Section icon={<Calendar size={17} className="text-blue-600" />} title="¿Qué día comprás?" hint="Las promos bancarias cambian según el día.">
          <div className="grid grid-cols-7 gap-1">
            {DAYS.map(d => {
              const on = selectedDay === d.id
              const today = catalog?.today === d.id
              return (
                <button
                  key={d.id}
                  type="button"
                  onClick={() => setSelectedDay(d.id)}
                  className={`h-12 rounded-xl text-[13px] font-bold flex flex-col items-center justify-center ${
                    on ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-700 active:bg-slate-200'
                  }`}
                >
                  {d.short}
                  {today && <span className={`text-[9px] font-extrabold ${on ? 'text-blue-100' : 'text-blue-600'}`}>HOY</span>}
                </button>
              )
            })}
          </div>
        </Section>

        <Section
          icon={<CreditCard size={17} className="text-purple-600" />}
          title="Clubes y tarjetas del súper"
          hint="Solo si las tenés aplicamos sus precios exclusivos."
        >
          <Toggles options={opts.filter(o => o.category === 'club')} selected={selectedCards} onToggle={toggleCard} />
        </Section>

        <Section icon={<Wallet size={17} className="text-emerald-600" />} title="Billeteras virtuales">
          <Toggles options={opts.filter(o => o.category === 'wallet')} selected={selectedCards} onToggle={toggleCard} />
        </Section>

        <Section icon={<Building2 size={17} className="text-slate-600" />} title="Bancos">
          <Toggles options={opts.filter(o => o.category === 'bank')} selected={selectedCards} onToggle={toggleCard} />
        </Section>

        <Section
          icon={<Calendar size={17} className="text-purple-600" />}
          title={`Promos del ${DAYS.find(d => d.id === selectedDay)?.short || ''}`}
          hint={mine.length ? `${mine.length} aplican con tus tarjetas` : 'Marcá tus medios de pago para ver cuáles te sirven'}
        >
          <ul className="space-y-2">
            {[...mine, ...others].map((p, idx) => {
              const isMine = selectedCards.includes(p.payment_id)
              return (
                <li key={`${p.supermercado}-${p.payment_id}-${idx}`}>
                  <a
                    href={p.official_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`flex items-center gap-3 p-2.5 rounded-xl border ${
                      isMine ? 'border-emerald-300 bg-emerald-50/70' : 'border-slate-100 bg-slate-50/60'
                    }`}
                  >
                    <span className="w-10 h-10 rounded-xl bg-slate-900 text-white text-[13px] font-extrabold flex items-center justify-center shrink-0">
                      {p.pct}%
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-[13px] font-bold text-slate-900 flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full" style={{ background: storeColor(p.supermercado) }} />
                        {storeLabel(p.supermercado)}
                      </p>
                      <p className="text-[12px] text-slate-600 truncate">{p.label}</p>
                      <p className="text-[11px] text-slate-400">
                        {p.cap ? `Tope ${formatPrice(p.cap)}` : 'Sin tope'} · {p.kind === 'en_caja' ? 'en caja' : 'reintegro'}
                      </p>
                    </div>
                    <ExternalLink size={14} className="text-slate-300 shrink-0" />
                  </a>
                </li>
              )
            })}
          </ul>
        </Section>

        <p className="text-[11px] text-slate-400 text-center px-4">
          Tus preferencias se guardan solo en este celular. Verificá siempre las bases y condiciones de cada promo.
        </p>
      </main>
    </div>
  )
}

export default ProfileScreen
