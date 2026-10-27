import { motion } from 'framer-motion'
import { HelpCircle } from 'lucide-react'
import Button from '@/components/common/Button'
import { DataTag } from '@/components/common/StatusChip'
import { useRetainedValue } from '@/hooks/useRetainedValue'
import Drawer from '@/components/common/Drawer'
import DeptTag from '@/components/common/DeptTag'
import ScoreMeter from '@/components/common/ScoreMeter'
import { corridors } from '@/data/corridors'
import { weeklyBlocks } from '@/data/plan'
import { DAYS, clock, duration } from '@/lib/format'
import { urgencyClass } from '@/lib/constants'

/**
 * Why a task scored what it scored. Each bar is one feature's signed
 * contribution to the urgency score — this is the panel a department head opens
 * when they think their work was unfairly ranked.
 */
export default function TaskDetail({ task, onClose, onExplain }) {
  // Kept so the panel can finish sliding out after the selection clears.
  const shown = useRetainedValue(task)
  if (!shown) return null

  const corridor = corridors.find((c) => c.id === shown.corridorId)
  const u = urgencyClass(shown.score)
  const block = weeklyBlocks.find((b) => b.taskIds.includes(shown.id))
  const max = Math.max(...shown.contributions.map((c) => Math.abs(c.value)))

  return (
    <Drawer
      open={!!task}
      onClose={onClose}
      title={shown.defectType}
      subtitle={`${corridor?.name} · ${shown.section}`}
    >
      <div className="flex items-center justify-between gap-4">
        <DeptTag dept={shown.department} />
        <span className="flex items-center gap-2">
          <DataTag kind="demo" />
          <span className="font-mono text-[12px] text-faint">{shown.id}</span>
        </span>
      </div>

      {onExplain && (
        <Button className="mt-5 w-full" onClick={() => onExplain(shown.id)}>
          <HelpCircle size={15} />
          Why this decision?
        </Button>
      )}

      <div className="mt-5 rounded-panel border border-hair bg-deep/30 px-5 py-4">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="text-[12.5px] text-muted">Urgency on the shared scale</p>
            <p className="mt-1 font-mono tnum text-[34px] leading-none" style={{ color: u.color }}>
              {shown.score}
            </p>
          </div>
          <span
            className="rounded-[3px] border px-2.5 py-1 text-[12.5px]"
            style={{ borderColor: `${u.color}55`, background: `${u.color}15`, color: u.color }}
          >
            {u.label}
          </span>
        </div>
        <div className="mt-4">
          <ScoreMeter score={shown.score} width={'100%'} showValue={false} />
        </div>
      </div>

      <p className="mt-5 text-[14px] leading-relaxed text-muted">{shown.note}</p>

      <section className="mt-7">
        <h3 className="text-[13px] text-muted">What drove the score</h3>
        <ul className="mt-4 space-y-2.5">
          {shown.contributions.map((c, i) => {
            const positive = c.value > 0
            const width = (Math.abs(c.value) / max) * 50
            return (
              <li key={c.feature}>
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-[13px] leading-snug text-ink/85">{c.feature}</span>
                  <span
                    className={`shrink-0 font-mono tnum text-[12.5px] ${
                      positive ? 'text-warn' : 'text-ok'
                    }`}
                  >
                    {positive ? '+' : ''}
                    {c.value}
                  </span>
                </div>
                {/* Bars grow from a shared centre line so raising and lowering
                    factors are readable at a glance. */}
                <div className="relative mt-1.5 h-1.5">
                  <span className="absolute left-1/2 top-0 h-full w-px bg-line" />
                  <motion.span
                    className="absolute top-0 h-full rounded-full"
                    style={{
                      background: positive ? '#E8A33D' : '#4FC3A1',
                      left: positive ? '50%' : `${50 - width}%`,
                    }}
                    initial={{ width: 0 }}
                    animate={{ width: `${width}%` }}
                    transition={{ delay: 0.06 * i, duration: 0.45, ease: 'easeOut' }}
                  />
                </div>
              </li>
            )
          })}
        </ul>
        <p className="mt-4 text-[12.5px] leading-relaxed text-faint">
          Contributions are calibrated against this department&rsquo;s own score distribution, so they
          can be compared directly with a task from any other department.
        </p>
      </section>

      <section className="mt-7 grid grid-cols-2 gap-3">
        <Fact label="Days past due" value={shown.daysOverdue} />
        <Fact
          label="Deferral limit"
          value={shown.slaDays <= 0 ? `${Math.abs(shown.slaDays)}d over` : `${shown.slaDays}d left`}
          tone={shown.slaDays <= 0 ? 'danger' : undefined}
        />
        <Fact label="Estimated duration" value={duration(shown.estDuration)} />
        <Fact label="Asset" value={shown.assetId} mono />
      </section>

      <section className="mt-7 rounded-panel border border-hair bg-deep/30 px-5 py-4">
        <h3 className="text-[13px] text-muted">Placement</h3>
        {block ? (
          <>
            <p className="mt-2 text-[14px]">
              {DAYS[block.day]} {clock(block.start)} – {clock(block.end)} on {block.section}
            </p>
            <p className="mt-1 font-mono text-[12px] text-faint">
              {block.id}
              {block.merged ? ` · shared with ${block.taskIds.length - 1} other job` : ''}
            </p>
          </>
        ) : (
          <p className="mt-2 text-[14px] text-muted">
            Not in this week&rsquo;s plan. Deferred to the monthly horizon.
          </p>
        )}
      </section>
    </Drawer>
  )
}

function Fact({ label, value, tone, mono }) {
  return (
    <div className="rounded-panel border border-hair bg-deep/30 px-4 py-3">
      <p className="text-[12px] text-muted">{label}</p>
      <p
        className={`mt-1 text-[15px] ${mono ? 'font-mono text-[13px]' : ''} ${
          tone === 'danger' ? 'text-danger' : ''
        }`}
      >
        {value}
      </p>
    </div>
  )
}
