import React, { useEffect, useState } from 'react'
import { MapPin, Calendar, CreditCard, Wallet, Building2, Check, ExternalLink, Loader2 } from 'lucide-react'
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
  const { cp, setCp, loading: cpLoading, coverage } = useLocation()
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
        <Section icon={<MapPin size={17} className="text-blue-600" />} title="Código postal" hint="Para mostrarte solo stock y súper que envían a tu zona.">
          <form
            onSubmit={e => {
              e.preventDefault()
              if (cpInput.trim().length === 4) setCp(cpInput.trim())
              ;(document.activeElement as HTMLElement)?.blur()
            }}
            className="flex gap-2"
          >
            <input
              value={cpInput}
              onChange={e => setCpInput(e.target.value.replace(/\D/g, '').slice(0, 4))}
              inputMode="numeric"
              placeholder="Ej: 1414"
              className="flex-1 h-11 px-3 rounded-xl border border-slate-200 text-base font-bold focus:outline-none focus:border-blue-500"
            />
            <button type="submit" className="h-11 px-4 rounded-xl bg-blue-600 text-white font-bold active:bg-blue-700">
              {cpLoading ? <Loader2 size={18} className="animate-spin" /> : 'Guardar'}
            </button>
          </form>
          {cp && coverage.length > 0 && (
            <p className="text-[12px] text-emerald-700 font-semibold mt-2">{deliverCount} supermercados envían a CP {cp}</p>
          )}
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
