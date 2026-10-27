import { AlertTriangle, CheckCircle2, CircleDot, Clock, Square, Triangle } from 'lucide-react'
import { NODE_STATES } from '@/lib/optimizer'

/**
 * Section status, shown the same way everywhere.
 *
 * Colour is never the only carrier: every chip has a shape and a word beside
 * it, so the board reads correctly in monochrome, on a projector with the
 * contrast washed out, and to anyone who cannot separate red from green.
 */
const ICONS = {
  available: CheckCircle2,
  planned: Clock,
  active: Square,
  critical: Triangle,
  conflict: CircleDot,
}

const TONE = {
  available: 'border-ok/35 bg-ok/10 text-ok',
  planned: 'border-warn/35 bg-warn/10 text-warn',
  active: 'border-danger/40 bg-danger/10 text-danger',
  critical: 'border-[#F2731B]/45 bg-[#F2731B]/10 text-[#F2731B]',
  conflict: 'border-[#A78BFA]/45 bg-[#A78BFA]/12 text-[#A78BFA]',
}

export default function StatusChip({ state, size = 'md', showLabel = true, label }) {
  const meta = NODE_STATES[state] ?? NODE_STATES.available
  const Icon = ICONS[state] ?? CheckCircle2
  const small = size === 'sm'
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-[3px] border ${
        TONE[state] ?? TONE.available
      } ${small ? 'px-1.5 py-0.5 text-[11px]' : 'px-2 py-1 text-[12px]'}`}
    >
      <Icon size={small ? 10 : 12} strokeWidth={2.2} aria-hidden="true" />
      {showLabel && (label ?? meta.label)}
    </span>
  )
}

/** The five states, for legends. */
export function StatusLegend({ className = '' }) {
  return (
    <ul className={`flex flex-wrap items-center gap-x-4 gap-y-2 ${className}`}>
      {Object.values(NODE_STATES).map((s) => (
        <li key={s.id}>
          <StatusChip state={s.id} size="sm" />
        </li>
      ))}
    </ul>
  )
}

/**
 * Where a number came from. Used anywhere a figure could be mistaken for a
 * live reading off a railway system — which, in this prototype, is all of them.
 */
export function DataTag({ kind = 'demo', className = '' }) {
  const copy = {
    demo: { label: 'DEMO DATA', hint: 'Synthetic records, not a live railway feed' },
    simulation: { label: 'SIMULATION', hint: 'Computed by the prototype, not observed' },
    model: { label: 'MODEL OUTPUT', hint: 'Produced by the scoring and scheduling logic' },
    estimate: { label: 'ESTIMATE', hint: 'Derived from demonstration data' },
    prototype: { label: 'PROTOTYPE', hint: 'Not connected to any production system' },
  }[kind]

  return (
    <span
      title={copy.hint}
      className={`inline-flex items-center gap-1.5 rounded-[3px] border border-line bg-raised/50 px-1.5 py-0.5 font-mono text-[10px] tracking-[0.12em] text-faint ${className}`}
    >
      <AlertTriangle size={9} strokeWidth={2.2} aria-hidden="true" />
      {copy.label}
    </span>
  )
}
