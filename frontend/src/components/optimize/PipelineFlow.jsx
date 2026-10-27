import { motion } from 'framer-motion'
import { Check, ChevronDown, ChevronRight, Loader2, UserCheck } from 'lucide-react'
import { pipelineStages } from '@/lib/optimizer'

/**
 * The optimisation pipeline, in one component used two ways.
 *
 * Static, on the block plan, it is the diagram of how a request becomes a
 * recommendation. Driven by `activeStage`, on the overview, it is the run
 * itself: stages light up in order, each reporting a real count from the
 * data as it passes.
 *
 * The last two stages are the point of the diagram. The engine produces a
 * recommendation and hands it to a person — RailOpt does not grant a block,
 * and nothing in this product implies it does.
 */
const HUMAN_STAGES = [
  { id: 'review', label: 'Human review', status: 'section controller', human: true },
  { id: 'decision', label: 'Approve or revise', status: 'decision rests here', human: true },
]

export default function PipelineFlow({
  activeStage = null,
  orientation = 'horizontal',
  showHuman = true,
  className = '',
}) {
  const stages = pipelineStages()
  const all = showHuman ? [...stages, ...HUMAN_STAGES] : stages
  const live = activeStage !== null
  const vertical = orientation === 'vertical'
  const Arrow = vertical ? ChevronDown : ChevronRight

  return (
    <section className={`panel overflow-hidden ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hair px-5 py-4 sm:px-6">
        <div>
          <h2 className="text-[15px] font-semibold">Optimisation pipeline</h2>
          <p className="mt-0.5 text-[12.5px] text-muted">
            RailOpt recommends. Authorised railway personnel approve.
          </p>
        </div>
      </div>

      <ol
        className={
          vertical
            ? 'space-y-1.5 px-5 py-5 sm:px-6'
            : 'scrollbar-thin flex gap-2 overflow-x-auto px-5 py-5 sm:px-6'
        }
      >
        {all.map((s, i) => {
          const done = live && i < activeStage
          const running = live && i === activeStage
          const pending = live && i > activeStage
          return (
            <motion.li
              key={s.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: live ? 0 : i * 0.05, duration: 0.35 }}
              className={vertical ? '' : 'flex shrink-0 items-center gap-2'}
            >
              <div
                className={`rounded-panel border px-3.5 py-3 transition-colors duration-300 ${
                  vertical ? 'w-full' : 'min-w-[172px]'
                } ${
                  running
                    ? 'border-merge/60 bg-merge/[0.10]'
                    : s.human
                      ? 'border-merge/35 bg-merge/[0.06]'
                      : 'border-line bg-deep/30'
                } ${pending ? 'opacity-30' : 'opacity-100'}`}
              >
                <p className="flex items-center gap-1.5 text-[13px] font-medium leading-snug">
                  {s.human && !live && (
                    <UserCheck size={12} className="shrink-0 text-merge" aria-hidden="true" />
                  )}
                  {done && <Check size={12} className="shrink-0 text-ok" strokeWidth={2.6} />}
                  {running && (
                    <Loader2 size={12} className="shrink-0 animate-spin text-merge" aria-hidden="true" />
                  )}
                  {s.label}
                </p>
                <p className="mt-1 font-mono text-[10.5px] leading-relaxed text-faint">
                  {done || running || !live ? s.status : '—'}
                </p>
                {(done || running) && s.checks && (
                  <ul className="mt-2 space-y-0.5">
                    {s.checks.map((c) => (
                      <li key={c} className="flex items-center gap-1.5 text-[11px] text-muted">
                        <Check size={9} className="shrink-0 text-ok" strokeWidth={3} />
                        {c}
                      </li>
                    ))}
                  </ul>
                )}
                {!live && s.detail && (
                  <p className="mt-1 text-[11px] leading-relaxed text-faint">{s.detail}</p>
                )}
              </div>
              {i < all.length - 1 && !vertical && (
                <Arrow size={14} className="shrink-0 text-faint" aria-hidden="true" />
              )}
            </motion.li>
          )
        })}
      </ol>
    </section>
  )
}
