import { motion } from 'framer-motion'
import { Check, GitMerge, Minus } from 'lucide-react'
import Drawer from '@/components/common/Drawer'
import DeptTag from '@/components/common/DeptTag'
import { DataTag } from '@/components/common/StatusChip'
import { useRetainedValue } from '@/hooks/useRetainedValue'
import { explainTask } from '@/lib/optimizer'
import { DAYS, clock, duration } from '@/lib/format'

/**
 * "Why did RailOpt decide this?"
 *
 * Every line is read out of the plan and the task record — the urgency band,
 * the days over the limit, the traffic on that section, whether the
 * possession fits the window, and which other job it can share with. None of
 * it is a template sentence with a number dropped in, and none of it invents
 * mathematics the engine does not actually do.
 */
export default function ExplainDrawer({ taskId, onClose }) {
  const shown = useRetainedValue(taskId)
  if (!shown) return null

  const e = explainTask(shown)
  if (!e) return null
  const { task, block, reasons, constraints, coordination } = e
  const merged = coordination.filter((c) => c.shared)
  const possible = coordination.filter((c) => !c.shared)

  return (
    <Drawer
      open={!!taskId}
      onClose={onClose}
      title="Why this decision?"
      subtitle={`${task.id} · ${task.defectType}`}
    >
      <div className="flex items-center justify-between gap-3">
        <DeptTag dept={task.department} />
        <DataTag kind="model" />
      </div>

      <section className="mt-6">
        <h3 className="text-[13px] text-muted">RailOpt selected this window because</h3>
        <ol className="mt-3 space-y-2.5">
          {reasons.map((r, i) => (
            <motion.li
              key={r}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.05 * i, duration: 0.35 }}
              className="flex gap-3 rounded-panel border border-hair bg-deep/30 px-4 py-3"
            >
              <span className="tnum shrink-0 font-mono text-[12px] text-faint">{i + 1}.</span>
              <span className="text-[13.5px] leading-relaxed text-ink/90">{r}</span>
            </motion.li>
          ))}
        </ol>
      </section>

      {block && (
        <section className="mt-7 rounded-panel border border-merge/25 bg-merge/[0.06] px-5 py-4">
          <p className="font-mono text-[11px] tracking-[0.14em] text-faint">RECOMMENDED WINDOW</p>
          <p className="mt-2 text-[17px]">
            {DAYS[block.day]} {clock(block.start)} – {clock(block.end)}
          </p>
          <p className="mt-1 font-mono text-[12px] text-faint">
            {block.id} · {block.section} · {duration(block.end - block.start)} possession
          </p>
        </section>
      )}

      <section className="mt-7">
        <h3 className="text-[13px] text-muted">Constraints considered</h3>
        <ul className="mt-3 grid grid-cols-1 gap-1.5 sm:grid-cols-2">
          {constraints.map((c) => (
            <li
              key={c.label}
              className="flex items-center gap-2 rounded-[3px] border border-hair bg-deep/20 px-3 py-2 text-[12.5px]"
            >
              {c.met ? (
                <Check size={12} className="shrink-0 text-ok" strokeWidth={2.4} />
              ) : (
                <Minus size={12} className="shrink-0 text-warn" strokeWidth={2.4} />
              )}
              <span className={c.met ? '' : 'text-warn'}>{c.label}</span>
            </li>
          ))}
        </ul>
      </section>

      {coordination.length > 0 && (
        <section className="mt-7">
          <h3 className="text-[13px] text-muted">Coordination opportunities</h3>
          <ul className="mt-3 space-y-2">
            {[...merged, ...possible].map((c) => (
              <li
                key={c.task.id}
                className={`rounded-panel border px-4 py-3 ${
                  c.shared ? 'border-ok/30 bg-ok/[0.07]' : 'border-hair bg-deep/30'
                }`}
              >
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  {c.shared && <GitMerge size={13} className="text-ok" aria-hidden="true" />}
                  <span className="font-mono text-[12.5px]">{c.task.id}</span>
                  <DeptTag dept={c.task.department} size="sm" />
                  <span className="ml-auto font-mono text-[11.5px] text-faint">
                    {c.shared ? `${c.saving} min saved` : `${c.combinedMinutes} min combined`}
                  </span>
                </div>
                <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{c.reason}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      <p className="mt-7 border-t border-hair pt-5 text-[12px] leading-relaxed text-faint">
        Explanation generated from the plan record and the task&rsquo;s own fields. The scoring
        model&rsquo;s feature contributions are shown separately on the task panel. Demonstration
        data — this is not a decision taken on any live railway.
      </p>
    </Drawer>
  )
}
