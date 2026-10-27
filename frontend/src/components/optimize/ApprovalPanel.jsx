import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Check, ClipboardCheck, PencilLine, RotateCcw } from 'lucide-react'
import Button from '@/components/common/Button'
import { useAppState } from '@/state/AppState'
import { weeklyBlocks } from '@/data/plan'
import { optimised } from '@/lib/optimizer'

/**
 * Where the plan stops being a recommendation.
 *
 * Approving here records a controller's decision in this session and nothing
 * else: no block is granted, no message goes back to a maintenance system,
 * no train is held. The panel says so, because a demonstration that implies
 * otherwise is the one thing a railway audience will not forgive.
 */
export default function ApprovalPanel({ onNotify }) {
  const { approvals, approvedCount, approveAll, resetApprovals, planDecision, setPlanDecision } =
    useAppState()
  const [note, setNote] = useState('')
  const total = weeklyBlocks.length
  const complete = approvedCount === total

  const approve = () => {
    approveAll()
    setPlanDecision('approved')
    onNotify?.(`All ${total} blocks marked approved for ${optimised.tasksCovered} jobs`)
  }

  const revise = () => {
    setPlanDecision('revision')
    onNotify?.('Revision requested — returned to the planner')
  }

  return (
    <section className="panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hair px-5 py-4 sm:px-6">
        <div>
          <h2 className="text-[15px] font-semibold">Plan ready for controller review</h2>
          <p className="mt-0.5 text-[12.5px] text-muted">
            {approvedCount} of {total} blocks signed.
          </p>
        </div>
        <span className="tnum font-mono text-[12px] text-faint">
          {Math.round((approvedCount / total) * 100)}%
        </span>
      </div>

      <div className="px-5 py-5 sm:px-6">
        <div className="h-[3px] w-full overflow-hidden rounded-full bg-hair">
          <motion.div
            className="h-full bg-merge"
            animate={{ width: `${(approvedCount / total) * 100}%` }}
            transition={{ type: 'spring', stiffness: 220, damping: 30 }}
          />
        </div>

        <ul className="mt-4 flex flex-wrap gap-1.5">
          {weeklyBlocks.map((b) => (
            <li
              key={b.id}
              title={`${b.id} · ${b.section}${approvals[b.id] ? ' · approved' : ' · awaiting approval'}`}
              className={`flex items-center gap-1 rounded-[3px] border px-2 py-1 font-mono text-[11px] transition-colors ${
                approvals[b.id]
                  ? 'border-ok/35 bg-ok/10 text-ok'
                  : 'border-line bg-raised/50 text-muted'
              }`}
            >
              {approvals[b.id] && <Check size={10} strokeWidth={2.6} aria-hidden="true" />}
              {b.id}
            </li>
          ))}
        </ul>

        <AnimatePresence mode="wait">
          {planDecision ? (
            <motion.div
              key={planDecision}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className={`mt-5 rounded-panel border px-4 py-3.5 ${
                planDecision === 'approved'
                  ? 'border-ok/35 bg-ok/[0.08]'
                  : 'border-warn/35 bg-warn/[0.08]'
              }`}
            >
              <p className="flex items-center gap-2 text-[13.5px] font-medium">
                <ClipboardCheck size={14} aria-hidden="true" />
                {planDecision === 'approved'
                  ? 'Recommendation accepted by the controller'
                  : 'Revision requested'}
              </p>
              <p className="mt-1.5 text-[13px] leading-relaxed text-muted">
                {planDecision === 'approved'
                  ? 'Recorded in this session only. In service this would return to the block demand system for formal sanction — no block is granted from here.'
                  : 'The plan goes back to the maintenance planner with the controller’s note. Nothing in the schedule has changed yet.'}
                {note && planDecision === 'revision' && (
                  <span className="mt-2 block rounded-[3px] border border-hair bg-deep/30 px-3 py-2 text-[12.5px] text-ink/85">
                    {note}
                  </span>
                )}
              </p>
              <button
                onClick={() => {
                  resetApprovals()
                  setNote('')
                }}
                className="mt-3 inline-flex items-center gap-1.5 rounded-panel text-[12.5px] text-muted transition-colors hover:text-ink"
              >
                <RotateCcw size={12} />
                Start the review again
              </button>
            </motion.div>
          ) : (
            <motion.div key="actions" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <label className="mt-5 block">
                <span className="text-[12.5px] text-muted">Controller note (optional)</span>
                <input
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="e.g. shorten B-108, suburban stock working Sunday morning"
                  className="mt-1.5 w-full rounded-panel border border-line bg-deep/40 px-3 py-2.5 text-[13.5px] placeholder:text-faint focus:border-merge/50 focus:outline-none"
                />
              </label>

              <div className="mt-4 flex flex-wrap gap-2">
                <Button onClick={approve}>
                  <Check size={15} />
                  Approve recommendation
                </Button>
                <Button variant="ghost" onClick={revise}>
                  <PencilLine size={15} />
                  Request revision
                </Button>
              </div>
              <p className="mt-3 text-[12px] leading-relaxed text-faint">
                {complete
                  ? 'Every block has been signed individually. Approving here records the plan as a whole.'
                  : `Approving accepts all ${total} blocks at once. Individual blocks can be signed from the timeline above.`}
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </section>
  )
}
