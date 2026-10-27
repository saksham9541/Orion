import { Check, Target } from 'lucide-react'
import { DataTag } from '@/components/common/StatusChip'

/**
 * What the engine is actually trying to do, written so a divisional officer
 * can read it. Deliberately framed as a framework rather than a formulation:
 * the terms below are the things this prototype trades off, not a claim
 * about a solver's exact objective function.
 */
const TERMS = [
  { label: 'Maintenance downtime', note: 'section-minutes closed' },
  { label: 'Train disruption', note: 'movements exposed to closure, weighted by traffic' },
  { label: 'Deferral-limit penalties', note: 'jobs left past their limit' },
  { label: 'Cross-department conflict', note: 'competing requests on one section' },
  { label: 'Rescheduling cost', note: 'work pushed to a later horizon' },
]

const CONSTRAINTS = [
  'Safety constraints',
  'Available block windows',
  'Maintenance duration',
  'Department requirements',
  'Section capacity',
  'Operational restrictions',
]

export default function ObjectivePanel({ className = '' }) {
  return (
    <section className={`panel overflow-hidden ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hair px-5 py-4 sm:px-6">
        <div>
          <h2 className="text-[15px] font-semibold">What does RailOpt optimise?</h2>
          <p className="mt-0.5 text-[12.5px] text-muted">Optimisation framework</p>
        </div>
        <DataTag kind="prototype" />
      </div>

      <div className="grid gap-px bg-line md:grid-cols-2">
        <div className="bg-surface px-5 py-5 sm:px-6">
          <p className="flex items-center gap-2 font-mono text-[11px] tracking-[0.14em] text-faint">
            <Target size={12} aria-hidden="true" />
            PRIMARY OBJECTIVE
          </p>
          <p className="mt-2.5 text-[17px] leading-snug">Minimise total operational disruption</p>
          <p className="mt-2 text-[13px] leading-relaxed text-muted">
            Not minimise closures, and not minimise downtime alone. A plan with fewer blocks that
            holds more trains is a worse plan, so the terms below are traded against each other
            rather than optimised one at a time.
          </p>
          <ul className="mt-4 space-y-2">
            {TERMS.map((t) => (
              <li
                key={t.label}
                className="flex items-baseline justify-between gap-3 border-b border-hair/60 pb-2 text-[13px] last:border-0"
              >
                <span>{t.label}</span>
                <span className="shrink-0 font-mono text-[11px] text-faint">{t.note}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="bg-surface px-5 py-5 sm:px-6">
          <p className="font-mono text-[11px] tracking-[0.14em] text-faint">SUBJECT TO</p>
          <ul className="mt-3 space-y-2">
            {CONSTRAINTS.map((c) => (
              <li key={c} className="flex items-center gap-2.5 text-[13.5px]">
                <Check size={13} className="shrink-0 text-ok" strokeWidth={2.3} />
                {c}
              </li>
            ))}
          </ul>
          <p className="mt-5 border-t border-hair pt-4 text-[12px] leading-relaxed text-faint">
            These are the constraints the prototype enforces in its scheduling logic. They are
            not presented as the formal mathematical programme a production solver would carry —
            that lives in the backend, which is not connected here.
          </p>
        </div>
      </div>
    </section>
  )
}
