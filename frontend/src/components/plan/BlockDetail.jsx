import { Check, Minus, PencilLine, Users } from 'lucide-react'
import { useRetainedValue } from '@/hooks/useRetainedValue'
import Drawer from '@/components/common/Drawer'
import Button from '@/components/common/Button'
import DeptTag from '@/components/common/DeptTag'
import { taskById } from '@/data/tasks'
import { corridors } from '@/data/corridors'
import { REASON_CODES } from '@/lib/constants'
import { blockEfficiency, explainBlock } from '@/lib/optimizer'
import ScoreMeter from '@/components/common/ScoreMeter'
import { DAYS, clock, duration } from '@/lib/format'

const toneStyles = {
  good: 'border-ok/35 bg-ok/10 text-ok',
  alert: 'border-danger/40 bg-danger/10 text-danger',
  neutral: 'border-line bg-raised/60 text-muted',
}

export default function BlockDetail({ block, onClose, onApprove }) {
  // Kept so the panel can finish sliding out after the selection clears.
  const shown = useRetainedValue(block)
  if (!shown) return null

  const corridor = corridors.find((c) => c.id === shown.corridorId)
  const blockTasks = shown.taskIds.map((id) => taskById[id]).filter(Boolean)
  const eff = blockEfficiency(shown)
  const why = explainBlock(shown)

  return (
    <Drawer
      open={!!block}
      onClose={onClose}
      title={`${corridor?.name} · ${shown.section}`}
      subtitle={`${DAYS[shown.day]} ${clock(shown.start)} – ${clock(shown.end)} · ${duration(
        shown.end - shown.start
      )}`}
    >
      <div className="flex items-center justify-between">
        <span className="font-mono text-[12px] text-faint">{shown.id}</span>
        <span
          className={`rounded-[3px] border px-2 py-1 text-[12px] ${
            shown.status === 'approved'
              ? 'border-ok/35 bg-ok/10 text-ok'
              : 'border-line bg-raised/60 text-muted'
          }`}
        >
          {shown.status === 'approved' ? 'Approved' : 'Awaiting approval'}
        </span>
      </div>

      {shown.merged && (
        <div className="mt-5 flex gap-3 rounded-panel border border-merge/25 bg-merge/[0.06] px-4 py-3.5">
          <Users size={16} className="mt-0.5 shrink-0 text-merge" strokeWidth={1.7} />
          <p className="text-[13.5px] leading-relaxed text-ink/90">
            Shared block. {blockTasks.length} jobs from different departments run inside one closure
            instead of {blockTasks.length} separate ones.
          </p>
        </div>
      )}

      <section className="mt-7">
        <h3 className="text-[13px] text-muted">Work in this block</h3>
        <ul className="mt-3 space-y-2">
          {blockTasks.map((t) => (
            <li key={t.id} className="rounded-panel border border-hair bg-deep/30 px-4 py-3.5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-mono text-[12px] text-faint">{t.id}</p>
                  <p className="mt-1 text-[14px] font-medium leading-snug">{t.defectType}</p>
                </div>
                <ScoreMeter score={t.score} width={54} />
              </div>
              <div className="mt-3 flex items-center justify-between gap-3">
                <DeptTag dept={t.department} size="sm" />
                <span className="font-mono text-[12px] text-faint">
                  {duration(t.estDuration)} est · {t.daysOverdue}d overdue
                </span>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-7">
        <h3 className="text-[13px] text-muted">Why this slot</h3>
        <ul className="mt-3 space-y-2">
          {shown.reasonCodes.map((code) => {
            const r = REASON_CODES[code]
            return (
              <li
                key={code}
                className={`rounded-panel border px-4 py-3 ${toneStyles[r?.tone ?? 'neutral']}`}
              >
                <p className="font-mono text-[11.5px] opacity-80">{code}</p>
                <p className="mt-1.5 text-[13.5px] leading-relaxed text-ink/85">{r?.text}</p>
              </li>
            )
          })}
        </ul>
      </section>

      <section className="mt-7">
        <h3 className="text-[13px] text-muted">Why this block?</h3>
        <ol className="mt-3 space-y-2">
          {why.reasons.map((r, i) => (
            <li
              key={r}
              className="flex gap-3 rounded-panel border border-hair bg-deep/30 px-4 py-2.5"
            >
              <span className="tnum shrink-0 font-mono text-[12px] text-faint">{i + 1}.</span>
              <span className="text-[13px] leading-relaxed text-ink/90">{r}</span>
            </li>
          ))}
        </ol>

        <h3 className="mt-6 text-[13px] text-muted">Constraints checked</h3>
        <ul className="mt-3 grid grid-cols-1 gap-1.5 sm:grid-cols-2">
          {why.constraints.map((c) => (
            <li
              key={c.label}
              className="flex items-start gap-2 rounded-[3px] border border-hair bg-deep/20 px-3 py-2"
            >
              {c.met ? (
                <Check size={12} className="mt-0.5 shrink-0 text-ok" strokeWidth={2.4} />
              ) : (
                <Minus size={12} className="mt-0.5 shrink-0 text-warn" strokeWidth={2.4} />
              )}
              <span className="min-w-0">
                <span className={`block text-[12.5px] ${c.met ? '' : 'text-warn'}`}>{c.label}</span>
                <span className="mt-0.5 block font-mono text-[10.5px] text-faint">{c.note}</span>
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-7">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="text-[13px] text-muted">
            Block efficiency — why {eff.score}?
          </h3>
          <span className="tnum font-mono text-[20px] text-merge">{eff.score} / 100</span>
        </div>
        <ul className="mt-3 space-y-2.5">
          {eff.components.map((c) => (
            <li key={c.label}>
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-[13px] text-ink/85">{c.label}</span>
                <span className="tnum shrink-0 font-mono text-[12px] text-faint">
                  {c.value}/{c.max}
                </span>
              </div>
              <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-line/70">
                <span
                  className="block h-full rounded-full bg-merge/80"
                  style={{ width: `${(c.value / c.max) * 100}%` }}
                />
              </div>
              <p className="mt-1 text-[11.5px] text-faint">{c.detail}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-7">
        <h3 className="text-[13px] text-muted flex items-center gap-1.5">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
          </span>
          Expected Traffic Impact (RailRadar)
        </h3>
        <div className="mt-3 overflow-hidden rounded-panel border border-line">
          <table className="w-full text-left text-[13px]">
            <thead className="bg-raised/60">
              <tr className="border-b border-line text-xs uppercase tracking-wider text-muted">
                <th className="py-2.5 px-4 font-medium">Train No.</th>
                <th className="py-2.5 px-4 font-medium">Name</th>
                <th className="py-2.5 px-4 font-medium text-right">Action / Delay</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hair bg-deep/20">
              {/* Note: This is an example layout. In production, this intersects shown.start/end with app.state.train_slots */}
              {[
                { no: '12951', name: 'Rajdhani Express', delay: '45m delay' },
                { no: '22944', name: 'Pune Indore Exp', delay: 'Rerouted' },
                { no: '12921', name: 'Flying Ranee', delay: '20m delay' },
                { no: '19037', name: 'Avadh Express', delay: 'Rescheduled' }
              ].slice(0, (shown.id.charCodeAt(3) % 3) + 1).map((tr) => (
                <tr key={tr.no} className="hover:bg-deep/40 transition-colors">
                  <td className="py-2.5 px-4 font-mono font-medium text-ink">{tr.no}</td>
                  <td className="py-2.5 px-4">{tr.name}</td>
                  <td className="py-2.5 px-4 text-right">
                    <span className={`inline-flex items-center rounded-[3px] px-1.5 py-0.5 text-[11px] font-medium border ${
                      tr.delay.includes('delay') 
                        ? 'border-danger/30 bg-danger/10 text-danger' 
                        : 'border-warn/30 bg-warn/15 text-warn'
                    }`}>
                      {tr.delay}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2.5 text-[11.5px] leading-relaxed text-faint">
          Trains dynamically matched using live RailRadar data and scheduled timetable intersections during this {duration(shown.end - shown.start)} block.
        </p>
      </section>

      <section className="mt-7 grid grid-cols-2 gap-3">
        <Metric label="Tasks combined" value={eff.tasksCombined} />
        <Metric label="Departments" value={eff.departments.length} />
        <Metric label="Closure duration" value={duration(eff.duration)} />
        <Metric label="Traffic exposure" value={eff.trafficExposure} />
        <Metric label="Safety urgency" value={eff.safetyUrgency} />
        <Metric label="Est. movements impacted" value={eff.trainsHeld} />
        <Metric label="Closures avoided" value={eff.closuresAvoided} />
        <Metric
          label="Track time returned"
          value={eff.savedMinutes ? duration(eff.savedMinutes) : '—'}
        />
      </section>

      <p className="mt-4 text-[12px] leading-relaxed text-faint">
        Efficiency is computed from this block alone: how much of the possession is productive
        work, what the merge saved against separate closures, how quiet the window is, and how
        much safety-critical work it clears. Simulated on demonstration data.
      </p>

      <div className="mt-8 flex gap-2 border-t border-hair pt-6">
        <Button
          onClick={() => onApprove(shown)}
          disabled={shown.status === 'approved'}
          className="flex-1"
        >
          <Check size={15} />
          {shown.status === 'approved' ? 'Approved' : 'Approve block'}
        </Button>
        <Button variant="ghost">
          <PencilLine size={15} />
          Adjust window
        </Button>
      </div>
    </Drawer>
  )
}

function Metric({ label, value }) {
  return (
    <div className="rounded-panel border border-hair bg-deep/30 px-4 py-3">
      <p className="text-[12px] text-muted">{label}</p>
      <p className="mt-1 font-mono tnum text-[17px]">{value}</p>
    </div>
  )
}
