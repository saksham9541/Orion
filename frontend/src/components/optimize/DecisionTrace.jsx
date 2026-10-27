import { useState } from 'react'
import { motion } from 'framer-motion'
import { ChevronRight } from 'lucide-react'
import DeptTag from '@/components/common/DeptTag'
import { DataTag } from '@/components/common/StatusChip'
import { decisionTrace, featuredTraces } from '@/lib/optimizer'
import { taskById } from '@/data/tasks'

/**
 * One job, followed all the way through.
 *
 * Request, conflict, constraint, decision, impact — five beats, each read out
 * of the data rather than narrated. This is the panel to point at when
 * someone asks whether the optimiser is doing anything, because it shows the
 * one thing a scoring bar cannot: that a specific request met a specific
 * obstacle and a specific rule resolved it.
 */
const TONE = {
  alert: 'border-danger/35 bg-danger/[0.07]',
  good: 'border-ok/35 bg-ok/[0.07]',
  neutral: 'border-hair bg-deep/30',
}

export default function DecisionTrace({ taskId, onSelect, showPicker = true }) {
  const [localId, setLocalId] = useState(featuredTraces[0])
  const active = taskId ?? localId
  const trace = decisionTrace(active)
  if (!trace) return null

  const pick = (id) => {
    setLocalId(id)
    onSelect?.(id)
  }

  return (
    <section className="panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hair px-5 py-4 sm:px-6">
        <div>
          <h2 className="text-[15px] font-semibold">Decision trace</h2>
          <p className="mt-0.5 text-[12.5px] text-muted">
            How one maintenance request became a scheduling decision.
          </p>
        </div>
        <DataTag kind="model" />
      </div>

      {showPicker && (
        <div className="scrollbar-thin flex gap-1.5 overflow-x-auto border-b border-hair px-5 py-3 sm:px-6">
          {featuredTraces.map((id) => {
            const t = taskById[id]
            return (
              <button
                key={id}
                onClick={() => pick(id)}
                aria-pressed={id === active}
                className={`flex shrink-0 items-center gap-2 rounded-panel border px-3 py-1.5 font-mono text-[12px] transition-colors ${
                  id === active
                    ? 'border-merge/50 bg-raised text-ink'
                    : 'border-line text-muted hover:text-ink'
                }`}
              >
                <DeptTag dept={t.department} showName={false} size="sm" />
                {id}
              </button>
            )
          })}
        </div>
      )}

      <div className="px-5 py-5 sm:px-6">
        <p className="text-[13.5px] leading-relaxed text-muted">
          <span className="text-ink">{trace.task.defectType}</span> — {trace.task.section},
          urgency {trace.task.score}/100.
        </p>

        <ol className="mt-4 grid gap-2 lg:grid-cols-5 lg:items-stretch">
          {trace.steps.map((step, i) => (
            <motion.li
              key={step.label}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.09, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
              className="relative"
            >
              <div
                className={`h-full rounded-panel border px-4 py-3.5 ${TONE[step.tone ?? 'neutral']}`}
              >
                <p className="font-mono text-[10.5px] tracking-[0.14em] text-faint">
                  {step.label.toUpperCase()}
                </p>
                <p className="mt-1.5 font-mono text-[14px] leading-snug">{step.value}</p>
                <p className="mt-1.5 text-[12px] leading-relaxed text-muted">{step.detail}</p>
              </div>
              {i < trace.steps.length - 1 && (
                <ChevronRight
                  size={14}
                  aria-hidden="true"
                  className="absolute -right-[11px] top-1/2 hidden -translate-y-1/2 text-faint lg:block"
                />
              )}
            </motion.li>
          ))}
        </ol>
      </div>
    </section>
  )
}
