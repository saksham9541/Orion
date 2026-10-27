import { useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, ArrowRight, Siren } from 'lucide-react'
import Button from '@/components/common/Button'
import DeptTag from '@/components/common/DeptTag'
import { DataTag } from '@/components/common/StatusChip'
import { emergencyReplan } from '@/lib/optimizer'
import { DAYS, clock, duration } from '@/lib/format'

/**
 * A critical defect arrives mid-week.
 *
 * Pressing re-plan runs the whole week again with the new job in the pool —
 * it does not patch one block. That matters: inserting a critical possession
 * on a section that already had one pushes the existing work out, and the
 * panel shows that consequence rather than hiding it.
 */
export default function EmergencyPanel() {
  const [replanned, setReplanned] = useState(false)
  const [running, setRunning] = useState(false)
  // Two full re-plans; held across renders so scrubbing the panel is free.
  const r = useMemo(() => emergencyReplan(), [])
  const { before, after, task, inserted } = r

  const rows = [
    { label: 'Blocks', before: before.blocksCount, after: after.blocksCount },
    {
      label: 'Downtime',
      before: before.downtime,
      after: after.downtime,
      format: (v) => `${v} min`,
    },
    { label: 'Est. movements impacted', before: before.trainsAffected, after: after.trainsAffected },
    { label: 'Past deferral limit', before: before.slaBreaches, after: after.slaBreaches },
  ]

  const late = after.blocks.filter((b) => b.late)

  const run = () => {
    setRunning(true)
    setTimeout(() => {
      setRunning(false)
      setReplanned(true)
    }, 900)
  }

  return (
    <section className="panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hair px-5 py-4 sm:px-6">
        <div>
          <h2 className="flex items-center gap-2 text-[15px] font-semibold">
            <Siren size={15} className="text-danger" aria-hidden="true" />
            Emergency re-optimisation
          </h2>
          <p className="mt-0.5 text-[12.5px] text-muted">
            A critical defect raised after the plan was published.
          </p>
        </div>
        <DataTag kind="simulation" />
      </div>

      <div className="px-5 py-5 sm:px-6">
        <div className="rounded-panel border border-danger/35 bg-danger/[0.07] px-4 py-4">
          <p className="flex items-center gap-2 font-mono text-[11px] tracking-[0.14em] text-danger">
            <AlertTriangle size={11} aria-hidden="true" />
            NEW CRITICAL MAINTENANCE REQUEST
          </p>
          <div className="mt-2.5 flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="font-mono text-[14px]">{task.id}</span>
            <span className="text-[14px]">{task.defectType}</span>
            <span className="ml-auto rounded-[2px] border border-danger/45 bg-danger/10 px-2 py-0.5 font-mono text-[11px] text-danger">
              RISK: {task.risk}
            </span>
          </div>
          <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[12.5px] text-muted">
            <DeptTag dept={task.department} size="sm" />
            <span className="font-mono">{task.section}</span>
            <span>urgency {task.score}/100</span>
            <span>{duration(task.estDuration)} of work</span>
          </div>
          <p className="mt-2.5 text-[13px] leading-relaxed text-muted">{task.note}</p>
        </div>

        {!replanned ? (
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <Button onClick={run} disabled={running} variant="danger">
              <Siren size={15} />
              {running ? 'Re-planning the week…' : 'Re-optimise plan'}
            </Button>
            <p className="text-[12.5px] text-muted">
              The current plan has {before.blocksCount} blocks. Nothing changes until you run it.
            </p>
          </div>
        ) : (
          <AnimatePresence>
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
              className="mt-5"
            >
              <div className="grid gap-px overflow-hidden rounded-panel border border-line bg-line sm:grid-cols-2">
                <div className="bg-surface px-5 py-4">
                  <p className="font-mono text-[11px] tracking-[0.14em] text-faint">
                    CURRENT PLAN
                  </p>
                  <dl className="mt-3 space-y-2.5">
                    {rows.map((row) => (
                      <div key={row.label} className="flex items-baseline justify-between gap-3">
                        <dt className="text-[13px] text-muted">{row.label}</dt>
                        <dd className="tnum font-mono text-[15px]">
                          {(row.format ?? ((v) => v))(row.before)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </div>
                <div className="bg-surface px-5 py-4">
                  <p className="font-mono text-[11px] tracking-[0.14em] text-danger">
                    EMERGENCY PLAN
                  </p>
                  <dl className="mt-3 space-y-2.5">
                    {rows.map((row, i) => {
                      const fmt = row.format ?? ((v) => v)
                      const moved = row.after !== row.before
                      return (
                        <motion.div
                          key={row.label}
                          initial={{ opacity: 0, x: 10 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: 0.15 + i * 0.09, duration: 0.4 }}
                          className="flex items-baseline justify-between gap-3"
                        >
                          <dt className="text-[13px] text-muted">{row.label}</dt>
                          <dd
                            className={`tnum font-mono text-[15px] ${moved ? 'text-warn' : ''}`}
                          >
                            {fmt(row.after)}
                          </dd>
                        </motion.div>
                      )
                    })}
                  </dl>
                </div>
              </div>

              <ul className="mt-4 space-y-2">
                {inserted && (
                  <li className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-panel border border-danger/30 bg-danger/[0.06] px-4 py-3 text-[13px]">
                    <ArrowRight size={13} className="shrink-0 text-danger" />
                    <span>
                      <span className="font-medium">Critical task inserted</span> on{' '}
                      {inserted.section}, {DAYS[inserted.day]} {clock(inserted.start)}–
                      {clock(inserted.end)}.
                    </span>
                  </li>
                )}
                {late.length > 0 && (
                  <li className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-panel border border-warn/30 bg-warn/[0.06] px-4 py-3 text-[13px]">
                    <ArrowRight size={13} className="shrink-0 text-warn" />
                    <span>
                      <span className="font-medium">
                        {late.length} block{late.length === 1 ? '' : 's'} rearranged
                      </span>{' '}
                      to make room —{' '}
                      {late.map((b) => b.taskIds.join(', ')).join('; ')} now runs past its
                      deferral limit and is flagged for the controller.
                    </span>
                  </li>
                )}
                <li className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-panel border border-hair bg-deep/30 px-4 py-3 text-[13px]">
                  <ArrowRight size={13} className="shrink-0 text-faint" />
                  <span>
                    <span className="font-medium">Train impact recalculated</span> across the
                    whole week: {before.trainsAffected} → {after.trainsAffected} estimated movements impacted.
                  </span>
                </li>
              </ul>

              <div className="mt-4 flex flex-wrap items-center gap-3">
                <Button variant="ghost" size="sm" onClick={() => setReplanned(false)}>
                  Back to the current plan
                </Button>
                <p className="text-[12px] text-faint">
                  A simulation. Neither plan has been sanctioned, and no possession has been
                  granted.
                </p>
              </div>
            </motion.div>
          </AnimatePresence>
        )}
      </div>
    </section>
  )
}
