import { useState } from 'react'
import { motion } from 'framer-motion'
import { AlertOctagon, ArrowDown, Check } from 'lucide-react'
import DeptTag from '@/components/common/DeptTag'
import { DataTag } from '@/components/common/StatusChip'
import { conflicts } from '@/lib/optimizer'
import { DEPARTMENTS } from '@/lib/constants'
import { taskById } from '@/data/tasks'
import { DAYS, clock, duration } from '@/lib/format'

/**
 * Why RailOpt exists, in one picture.
 *
 * Three departments, one section, one night, three requests that overlap.
 * The lanes are the requests as raised; the band down the middle is the part
 * of the night more than one of them wants. Underneath is what the plan
 * actually did with them.
 *
 * The axis is fixed at 00:00–08:00 so every conflict is read against the
 * same night, and the eye can compare one section with another.
 */
const AXIS_START = 0
const AXIS_END = 480

function pct(minutes) {
  return ((minutes - AXIS_START) / (AXIS_END - AXIS_START)) * 100
}

export default function ConflictRadar({ compact = false }) {
  const [index, setIndex] = useState(0)
  const conflict = conflicts[index]
  if (!conflict) return null

  const resolution = conflict.resolution
  const hours = [0, 1, 2, 3, 4, 5, 6, 7, 8]

  return (
    <section className="panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hair px-5 py-4 sm:px-6">
        <div>
          <h2 className="text-[15px] font-semibold">Block conflict radar</h2>
          <p className="mt-0.5 text-[12.5px] text-muted">
            Maintenance requests as each department raised them, before coordination.
          </p>
        </div>
        <DataTag kind="demo" />
      </div>

      {/* Which contested section to look at */}
      <div className="scrollbar-thin flex gap-1.5 overflow-x-auto border-b border-hair px-5 py-3 sm:px-6">
        {conflicts.map((c, i) => (
          <button
            key={c.section}
            onClick={() => setIndex(i)}
            aria-pressed={i === index}
            className={`flex shrink-0 items-center gap-2 rounded-panel border px-3 py-1.5 font-mono text-[12px] transition-colors ${
              i === index
                ? 'border-merge/50 bg-raised text-ink'
                : 'border-line text-muted hover:text-ink'
            }`}
          >
            {c.section}
            <span className="rounded-[2px] bg-danger/15 px-1.5 text-[10.5px] text-danger">
              {c.requests.length}
            </span>
          </button>
        ))}
      </div>

      <div className="px-5 py-5 sm:px-6">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <p className="font-mono text-[15px]">{conflict.section}</p>
          <p className="text-[12.5px] text-muted">
            {DAYS[conflict.day]} night · {conflict.departments.length} departments ·{' '}
            {conflict.requests.length} overlapping requests
          </p>
        </div>

        {/* Time axis */}
        <div className="relative mt-4 h-4">
          {hours.map((h) => (
            <span
              key={h}
              className="absolute top-0 -translate-x-1/2 tnum font-mono text-[10px] text-faint"
              style={{ left: `${pct(h * 60)}%` }}
            >
              {String(h).padStart(2, '0')}
            </span>
          ))}
        </div>

        <div className="relative mt-1">
          {/* The contested band */}
          {conflict.overlapMinutes > 0 && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5, duration: 0.5 }}
              className="pointer-events-none absolute inset-y-0 z-10 border-x border-danger/45 bg-danger/[0.09]"
              style={{
                left: `${pct(conflict.overlapStart)}%`,
                width: `${pct(conflict.overlapEnd) - pct(conflict.overlapStart)}%`,
              }}
            />
          )}

          <ul className="relative space-y-2">
            {conflict.requests.map((r, i) => {
              const task = taskById[r.taskId]
              const dept = DEPARTMENTS[r.dept]
              return (
                <li key={r.id} className="flex items-center gap-3">
                  <span className="w-[112px] shrink-0 sm:w-[150px]">
                    <span className="flex items-center gap-2">
                      <DeptTag dept={r.dept} showName={false} size="sm" />
                      <span className="truncate font-mono text-[11.5px] text-muted">
                        {r.taskId}
                      </span>
                    </span>
                    <span className="mt-0.5 block truncate text-[11px] text-faint">
                      {dept?.name}
                    </span>
                  </span>
                  <span className="relative h-8 min-w-0 flex-1 rounded-[3px] bg-deep/40">
                    <motion.span
                      className="absolute inset-y-[5px] flex items-center overflow-hidden rounded-[2px] px-2"
                      style={{
                        left: `${pct(r.start)}%`,
                        background: `${dept?.color}2E`,
                        borderLeft: `2px solid ${dept?.color}`,
                      }}
                      initial={{ width: 0 }}
                      animate={{ width: `${pct(r.end) - pct(r.start)}%` }}
                      transition={{ delay: 0.12 * i, duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
                      title={`${task?.defectType ?? r.taskId} · ${clock(r.start)}–${clock(r.end)}`}
                    >
                      <span className="tnum truncate font-mono text-[10.5px] text-ink/85">
                        {clock(r.start)}–{clock(r.end)}
                      </span>
                    </motion.span>
                  </span>
                </li>
              )
            })}
          </ul>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-3 rounded-panel border border-danger/30 bg-danger/[0.07] px-4 py-3">
          <AlertOctagon size={16} className="shrink-0 text-danger" strokeWidth={1.8} />
          <p className="text-[13.5px] leading-relaxed text-ink/90">
            <span className="font-medium text-danger">Conflict detected.</span>{' '}
            {conflict.departments.length} departments, one section,{' '}
            {conflict.requests.length} overlapping requests —{' '}
            {duration(conflict.overlapMinutes)} of the night is wanted by more than one of them.
          </p>
        </div>

        {!compact && (
          <>
            <div className="my-4 flex justify-center">
              <ArrowDown size={18} className="text-faint" aria-hidden="true" />
            </div>

            <div className="rounded-panel border border-merge/25 bg-merge/[0.06] px-4 py-4">
              <p className="font-mono text-[11px] tracking-[0.14em] text-faint">
                RAILOPT RECOMMENDATION
              </p>
              <ul className="mt-3 space-y-2">
                {resolution.blocks.map((b, i) => (
                  <motion.li
                    key={b.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.7 + i * 0.09, duration: 0.4 }}
                    className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-[3px] border border-hair bg-deep/30 px-3 py-2.5"
                  >
                    <Check size={13} className="shrink-0 text-ok" strokeWidth={2.2} />
                    <span className="font-mono text-[12px] text-faint">{b.id}</span>
                    <span className="tnum font-mono text-[12.5px]">
                      {DAYS[b.day]} {clock(b.start)}–{clock(b.end)}
                    </span>
                    <span className="text-[12.5px] text-muted">
                      {b.merged
                        ? `one coordinated block, ${b.taskIds.length} jobs`
                        : '1 job'}
                    </span>
                    {b.merged && (
                      <span className="ml-auto rounded-[2px] border border-merge/40 bg-merge/10 px-2 py-0.5 font-mono text-[10.5px] text-merge">
                        MERGED
                      </span>
                    )}
                  </motion.li>
                ))}
              </ul>
              <p className="mt-3 text-[13px] leading-relaxed text-muted">
                {conflict.requests.length} competing requests became {resolution.closures}{' '}
                {resolution.closures === 1 ? 'closure' : 'closures'}
                {resolution.merged.length > 0 &&
                  `, ${resolution.merged.length} of them shared across departments`}
                . Nothing was dropped — the work that could not share a window was moved to a
                quieter night on the same section.
              </p>
            </div>
          </>
        )}
      </div>
    </section>
  )
}
