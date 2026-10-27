import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { CalendarRange, HelpCircle, Lightbulb, ListOrdered, Train, X } from 'lucide-react'
import StatusChip, { DataTag } from '@/components/common/StatusChip'
import DeptTag from '@/components/common/DeptTag'
import ScoreMeter from '@/components/common/ScoreMeter'
import { sectionDetail } from '@/lib/optimizer'
import { DAYS, clock, duration } from '@/lib/format'

/**
 * Everything about one section at the simulated moment: who is working on it,
 * what it costs in train movements, and what RailOpt did about the competing
 * requests. The recommendation at the bottom is looked up from the plan, not
 * composed from a template.
 */
export default function SectionPanel({ section, day, minutes, onClose, onExplain }) {
  if (!section) {
    return (
      <div className="panel flex h-full min-h-[280px] flex-col items-center justify-center px-6 py-10 text-center">
        <Train size={22} className="text-faint" strokeWidth={1.6} />
        <p className="mt-3 text-[14px] font-medium">Select a section</p>
        <p className="mt-1 max-w-[260px] text-[13px] leading-relaxed text-muted">
          Pick any length of track on the diagram to see the work on it, the movements it
          carries, and how the competing requests were resolved.
        </p>
      </div>
    )
  }

  const d = sectionDetail(section, day, minutes)

  return (
    <motion.div
      key={section}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      className="panel flex h-full flex-col"
    >
      <header className="flex items-start justify-between gap-3 border-b border-hair px-5 py-4">
        <div className="min-w-0">
          <p className="font-mono text-[11px] tracking-[0.16em] text-faint">SECTION</p>
          <h2 className="mt-0.5 font-mono text-[19px] font-medium">{d.section}</h2>
          <p className="mt-1 text-[12.5px] text-muted">{d.corridor.long}</p>
        </div>
        <button
          onClick={onClose}
          className="rounded-panel p-1.5 text-muted transition-colors hover:bg-raised hover:text-ink"
          aria-label="Close section detail"
        >
          <X size={16} />
        </button>
      </header>

      <div className="scrollbar-thin flex-1 space-y-5 overflow-y-auto px-5 py-4">
        <div className="flex flex-wrap items-center gap-2">
          <StatusChip state={d.state.state} />
          <DataTag kind="simulation" />
        </div>

        <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-panel border border-line bg-line">
          <Cell label="Traffic" value={d.traffic} sub={`${d.corridor.trainsPerDay} movements/day`} />
          <Cell label="Tasks on section" value={d.tasks.length} />
          <Cell
            label="Departments"
            value={d.departments.length}
            sub={d.departments.join(' + ') || '—'}
          />
          <Cell
            label="Scheduling risk"
            value={d.risk}
            tone={d.risk === 'High' ? 'warn' : undefined}
          />
        </dl>

        {d.state.block ? (
          <section>
            <h3 className="text-[13px] text-muted">
              {d.state.state === 'planned' ? 'Next block' : 'Block in force'}
            </h3>
            <div className="mt-2 rounded-panel border border-hair bg-deep/30 px-4 py-3.5">
              <div className="flex items-baseline justify-between gap-3">
                <span className="font-mono text-[12px] text-faint">{d.state.block.id}</span>
                <span className="tnum font-mono text-[13px]">
                  {DAYS[d.state.block.day]} {clock(d.state.block.start)}–{clock(d.state.block.end)}
                </span>
              </div>
              <p className="mt-1.5 text-[13px] text-muted">
                {duration(d.state.block.end - d.state.block.start)} possession ·{' '}
                {d.trainsAffected} estimated movements impacted
              </p>
              <ul className="mt-3 space-y-2">
                {d.state.tasks.map((t) => (
                  <li key={t.id} className="flex items-center justify-between gap-3">
                    <span className="min-w-0">
                      <span className="block truncate text-[13px]">{t.defectType}</span>
                      <span className="mt-0.5 flex items-center gap-2">
                        <DeptTag dept={t.department} size="sm" />
                        <span className="font-mono text-[11px] text-faint">{t.id}</span>
                      </span>
                    </span>
                    <ScoreMeter score={t.score} width={46} />
                  </li>
                ))}
              </ul>
            </div>
          </section>
        ) : (
          <p className="rounded-panel border border-hair bg-deep/30 px-4 py-3.5 text-[13px] leading-relaxed text-muted">
            No possession on this section at the simulated moment. It carries traffic normally.
          </p>
        )}

        {d.conflict && (
          <section>
            <h3 className="text-[13px] text-muted">As-raised requests</h3>
            <div className="mt-2 rounded-panel border border-[#A78BFA]/30 bg-[#A78BFA]/[0.07] px-4 py-3.5">
              <p className="text-[13px] leading-relaxed text-ink/85">
                {d.conflict.departments.length} departments asked for this section on{' '}
                {DAYS[d.conflict.day]} night. {d.conflict.overlapMinutes} minutes of those
                requests sit on top of each other — the part no control office can grant.
              </p>
              <ul className="mt-3 space-y-1.5">
                {d.conflict.requests.map((r) => (
                  <li key={r.id} className="flex items-center justify-between gap-3 text-[12.5px]">
                    <span className="flex items-center gap-2">
                      <DeptTag dept={r.dept} showName={false} size="sm" />
                      <span className="font-mono text-faint">{r.taskId}</span>
                    </span>
                    <span className="tnum font-mono text-muted">
                      {clock(r.start)}–{clock(r.end)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </section>
        )}

        <section className="rounded-panel border border-merge/25 bg-merge/[0.06] px-4 py-3.5">
          <p className="flex items-center gap-2 font-mono text-[11px] tracking-[0.14em] text-faint">
            <Lightbulb size={11} aria-hidden="true" />
            RAILOPT RECOMMENDATION
          </p>
          <p className="mt-2 text-[13.5px] leading-relaxed text-ink/90">{d.recommendation}</p>
          <p className="mt-2.5 text-[12px] text-faint">
            A recommendation only. A section controller decides whether it is taken.
          </p>
        </section>

        {/* Straight into the record behind whatever is on this section. */}
        <div className="flex flex-wrap gap-2">
          <Link
            to="/app/plan"
            className="flex items-center gap-1.5 rounded-panel border border-line px-3 py-2 text-[12.5px] text-muted transition-colors hover:border-merge/50 hover:text-ink"
          >
            <CalendarRange size={13} aria-hidden="true" />
            View block
          </Link>
          <Link
            to="/app/tasks"
            className="flex items-center gap-1.5 rounded-panel border border-line px-3 py-2 text-[12.5px] text-muted transition-colors hover:border-merge/50 hover:text-ink"
          >
            <ListOrdered size={13} aria-hidden="true" />
            View tasks
          </Link>
          {onExplain && d.state.tasks.length > 0 && (
            <button
              onClick={() => onExplain(d.state.tasks[0].id)}
              className="flex items-center gap-1.5 rounded-panel border border-merge/40 bg-merge/10 px-3 py-2 text-[12.5px] text-ink transition-colors hover:bg-merge/20"
            >
              <HelpCircle size={13} aria-hidden="true" />
              Why this decision?
            </button>
          )}
        </div>
      </div>
    </motion.div>
  )
}

function Cell({ label, value, sub, tone }) {
  return (
    <div className="bg-surface px-4 py-3">
      <p className="text-[11.5px] text-muted">{label}</p>
      <p className={`mt-1 tnum font-mono text-[16px] ${tone === 'warn' ? 'text-warn' : ''}`}>
        {value}
      </p>
      {sub && <p className="mt-0.5 text-[11px] text-faint">{sub}</p>}
    </div>
  )
}
