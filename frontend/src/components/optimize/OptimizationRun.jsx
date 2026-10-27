import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { ArrowRight, GitMerge, RotateCcw, Zap } from 'lucide-react'
import Button from '@/components/common/Button'
import DeptTag from '@/components/common/DeptTag'
import { DataTag } from '@/components/common/StatusChip'
import { useAppState } from '@/state/AppState'
import { useCountUp } from '@/hooks/useCountUp'
import PipelineFlow from '@/components/optimize/PipelineFlow'
import {
  baseline,
  improvement,
  optimised,
  pipelineStages,
  prevented,
} from '@/lib/optimizer'
import { weeklyBlocks } from '@/data/plan'
import { taskById } from '@/data/tasks'
import { DEPARTMENTS } from '@/lib/constants'
import { clock, duration } from '@/lib/format'

/**
 * The moment the product is built around.
 *
 * On the left, the week as the three departments asked for it. Press the
 * button and the solver walks its stages — each one reporting a real count
 * from the data, not a progress bar with nothing behind it — and the
 * coordinated plan is revealed beside it, with the merges drawn closing.
 *
 * The improvement percentages are divisions between the two columns. There
 * is no separate table of claimed savings anywhere in this product.
 */
const STAGE_MS = 380

export default function OptimizationRun({ onComplete }) {
  const reduce = useReducedMotion()
  const { optimised: revealed, setOptimised } = useAppState()
  const [running, setRunning] = useState(false)
  const [stage, setStage] = useState(-1)
  const timers = useRef([])

  const stages = useMemo(() => pipelineStages(), [])

  useEffect(() => () => timers.current.forEach(clearTimeout), [])

  const run = () => {
    if (running) return
    setRunning(true)
    setStage(-1)
    timers.current.forEach(clearTimeout)
    timers.current = []
    const step = reduce ? 40 : STAGE_MS

    stages.forEach((_, i) => {
      timers.current.push(setTimeout(() => setStage(i), step * (i + 1)))
    })
    timers.current.push(
      setTimeout(
        () => {
          setRunning(false)
          setOptimised(true)
          onComplete?.()
        },
        step * (stages.length + 1)
      )
    )
  }

  const reset = () => {
    timers.current.forEach(clearTimeout)
    setRunning(false)
    setStage(-1)
    setOptimised(false)
  }

  const rows = [
    {
      key: 'blocks',
      label: 'Possessions (closures)',
      before: baseline.blocks,
      after: optimised.blocks,
      format: (v) => v,
    },
    {
      key: 'downtime',
      label: 'Planned maintenance closure',
      before: baseline.downtimeMinutes,
      after: optimised.downtimeMinutes,
      format: (v) => `${v} min`,
    },
    {
      key: 'trains',
      label: 'Estimated train movements impacted',
      before: baseline.trainsAffected,
      after: optimised.trainsAffected,
      format: (v) => v,
    },
    {
      key: 'sla',
      label: 'SLA / deferral breaches',
      before: baseline.slaBreaches,
      after: optimised.slaBreaches,
      format: (v) => v,
    },
  ]

  return (
    <section className="panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hair px-5 py-4 sm:px-6">
        <div>
          <h2 className="text-[15px] font-semibold">Optimisation impact</h2>
          <p className="mt-0.5 text-[12.5px] text-muted">
            The same {optimised.tasksCovered} jobs, planned two ways.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <DataTag kind="model" />
          {revealed && (
            <button
              onClick={reset}
              className="flex items-center gap-1.5 rounded-panel border border-line px-2.5 py-1.5 text-[12px] text-muted transition-colors hover:border-merge/50 hover:text-ink"
            >
              <RotateCcw size={12} />
              Replay
            </button>
          )}
        </div>
      </div>

      <div className="grid gap-px bg-line lg:grid-cols-2">
        {/* Baseline */}
        <div className="bg-surface px-5 py-5 sm:px-6">
          <p className="font-mono text-[11px] tracking-[0.16em] text-faint">BASELINE PLAN</p>
          <p className="mt-1 text-[13px] text-muted">
            Every department&rsquo;s request as raised — one possession per job.
          </p>
          <dl className="mt-5 space-y-3.5">
            {rows.map((r) => (
              <div key={r.key} className="flex items-baseline justify-between gap-4">
                <dt className="text-[13.5px] text-muted">{r.label}</dt>
                <dd className="tnum font-mono text-[20px]">{r.format(r.before)}</dd>
              </div>
            ))}
          </dl>
        </div>

        {/* Optimised */}
        <div className="relative min-h-[260px] bg-surface px-5 py-5 sm:px-6">
          <AnimatePresence mode="wait">
            {revealed ? (
              <motion.div
                key="result"
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
              >
                <p className="font-mono text-[11px] tracking-[0.16em] text-merge">
                  RAILOPT OPTIMISED PLAN
                </p>
                <p className="mt-1 text-[13px] text-muted">
                  {optimised.mergedBlocks} blocks shared across departments.
                </p>
                <dl className="mt-5 space-y-3.5">
                  {rows.map((r, i) => (
                    <ResultRow key={r.key} row={r} delay={i * 0.1} />
                  ))}
                </dl>
              </motion.div>
            ) : running ? (
              <motion.div key="run" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <p className="font-mono text-[11px] tracking-[0.16em] text-faint">
                  RUNNING THE PIPELINE
                </p>
                <div className="-mx-2 mt-3">
                  <PipelineFlow
                    activeStage={Math.max(0, stage)}
                    orientation="vertical"
                    showHuman={false}
                    className="border-0 bg-transparent shadow-none"
                  />
                </div>
              </motion.div>
            ) : (
              <motion.div
                key="idle"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex h-full flex-col items-center justify-center py-6 text-center"
              >
                <p className="max-w-[300px] text-[13.5px] leading-relaxed text-muted">
                  The {baseline.blocks} requests have not been coordinated yet. Run the optimiser
                  to see what the same work costs when the departments share windows.
                </p>
                <Button onClick={run} size="lg" className="group mt-6">
                  <Zap size={16} className="transition-transform group-hover:scale-110" />
                  Run RailOpt optimisation
                </Button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      <AnimatePresence>
        {revealed && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden border-t border-hair"
          >
            <div className="px-5 py-5 sm:px-6">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h3 className="text-[13.5px] font-medium">What merged</h3>
                <p className="text-[12.5px] text-muted">
                  {prevented.closuresAvoided} closures removed ·{' '}
                  {duration(prevented.downtimeAvoided)} of track time returned
                </p>
              </div>
              <ul className="mt-4 space-y-3">
                {weeklyBlocks
                  .filter((b) => b.merged)
                  .map((b, i) => (
                    <MergeRow key={b.id} block={b} delay={0.5 + i * 0.22} reduce={reduce} />
                  ))}
              </ul>
              <p className="mt-5 border-t border-hair pt-4 text-[12px] leading-relaxed text-faint">
                Estimated operational improvement, computed as the difference between the two
                columns above: closure time down{' '}
                {improvement(baseline.downtimeMinutes, optimised.downtimeMinutes).toFixed(1)}%,
                estimated movements impacted down{' '}
                {improvement(baseline.trainsAffected, optimised.trainsAffected).toFixed(1)}%,
                possessions down{' '}
                {improvement(baseline.blocks, optimised.blocks).toFixed(1)}%. Demonstration data
                throughout — these are not measured railway outcomes.
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  )
}

function ResultRow({ row, delay }) {
  const shown = useCountUp(row.after, 1100)
  const change = improvement(row.before, row.after)
  return (
    <motion.div
      initial={{ opacity: 0, x: 12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay, duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
      className="flex items-baseline justify-between gap-4"
    >
      <dt className="text-[13.5px] text-muted">{row.label}</dt>
      <dd className="flex items-baseline gap-3">
        <span className="tnum font-mono text-[20px] text-merge">
          {row.format(Number(String(shown).replace(/,/g, '')))}
        </span>
        <span
          className={`tnum w-[54px] text-right font-mono text-[12px] ${
            change > 0 ? 'text-ok' : 'text-faint'
          }`}
        >
          {row.before === row.after
            ? '—'
            : row.before === 0
              ? ''
              : `−${change.toFixed(0)}%`}
        </span>
      </dd>
    </motion.div>
  )
}

/**
 * Two requests closing into one block. The bars start where each department
 * asked for the track and slide together to the window they now share.
 */
function MergeRow({ block, delay, reduce }) {
  const tasks = block.taskIds.map((id) => taskById[id]).filter(Boolean)
  const span = { start: 0, end: 480 }
  const pct = (m) => ((m - span.start) / (span.end - span.start)) * 100

  return (
    <li className="rounded-panel border border-hair bg-deep/30 px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex items-center gap-2">
          <span className="font-mono text-[12px] text-faint">{block.id}</span>
          <span className="font-mono text-[13px]">{block.section}</span>
        </span>
        <span className="tnum font-mono text-[12.5px] text-merge">
          {clock(block.start)}–{clock(block.end)}
        </span>
      </div>

      {/* What each department asked for, before coordination. */}
      <ul className="mt-2.5 space-y-1">
        {tasks.map((t) => (
          <li key={t.id} className="flex flex-wrap items-center gap-x-2.5 text-[12px]">
            <DeptTag dept={t.department} showName={false} size="sm" />
            <span className="text-muted">{DEPARTMENTS[t.department]?.name}</span>
            <span className="font-mono text-faint">{t.id}</span>
            <span className="tnum ml-auto font-mono text-faint">
              {clock(t.requested.start)}–{clock(t.requested.start + t.estDuration + 45)}
            </span>
          </li>
        ))}
      </ul>

      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: delay + 0.2, duration: 0.4 }}
        className="mt-3 flex items-center gap-1.5 font-mono text-[10.5px] tracking-[0.14em] text-ok"
      >
        <GitMerge size={11} aria-hidden="true" />
        COMPATIBILITY DETECTED — SAME SECTION, DIFFERENT DEPARTMENTS
      </motion.p>

      {/* The two requested windows sliding into the one they now share. */}
      <div className="relative mt-2.5 h-[30px]">
        {tasks.map((t, i) => (
          <motion.span
            key={t.id}
            className="absolute h-[11px] overflow-hidden rounded-[2px]"
            style={{
              top: i * 15,
              background: `${DEPARTMENTS[t.department]?.color}33`,
              borderLeft: `2px solid ${DEPARTMENTS[t.department]?.color}`,
            }}
            initial={
              reduce
                ? false
                : {
                    left: `${pct(t.requested.start)}%`,
                    width: `${pct(t.requested.start + t.estDuration + 45) - pct(t.requested.start)}%`,
                  }
            }
            animate={{
              left: `${pct(block.start)}%`,
              width: `${pct(block.end) - pct(block.start)}%`,
              top: i * 15,
            }}
            transition={{ delay: delay + 0.35, duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
            title={`${t.id} · ${t.defectType}`}
          />
        ))}
      </div>

      <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1">
        <span className="font-mono text-[11.5px] text-merge">
          ONE COORDINATED POSSESSION · {block.id}
        </span>
        <span className="ml-auto flex items-center gap-1.5 text-[12px] text-ok">
          <ArrowRight size={11} />
          one closure instead of {tasks.length}
        </span>
      </div>
    </li>
  )
}
