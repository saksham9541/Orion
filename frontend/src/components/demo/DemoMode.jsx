import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import { useAppState } from '@/state/AppState'
import {
  baseline,
  conflicts,
  headlineConflict,
  optimised,
} from '@/lib/optimizer'
import { tasks } from '@/data/tasks'

/**
 * A scripted run through the argument, for a room with a clock on it.
 *
 * Nine stops, each one a real screen — the walkthrough navigates the actual
 * product rather than playing a recording, so any question from the floor can
 * be answered by stopping and using it. Roughly four minutes at a steady pace.
 */
export const DEMO_STEPS = [
  {
    title: '1 · Problem',
    body: `${tasks.length} open jobs across three departments, each raised in its own system, each asking for track time on its own terms. Nobody holds all three request books at once.`,
    to: '/app/tasks',
  },
  {
    title: '2 · Conflict',
    body: `${conflicts.length} sections have two or more departments asking for the same track on the same night. On ${headlineConflict.section} ${headlineConflict.requests.length} requests overlap by ${headlineConflict.overlapMinutes} minutes — no control office can grant them as they stand.`,
    to: '/app/dashboard',
  },
  {
    title: '3 · Optimisation',
    body: 'Press Run RailOpt optimisation. The pipeline reports real counts as it passes: requests in, conflicts found, constraints checked, windows priced, combinations found, impact simulated.',
    to: '/app/dashboard',
  },
  {
    title: '4 · Coordination',
    body: `${optimised.mergedBlocks} blocks now carry work from more than one department. Open B-101 to see why: two jobs, one section, one possession instead of two.`,
    to: '/app/plan',
  },
  {
    title: '5 · Impact',
    body: 'Play the week through on the twin. Sections change state because the plan says a possession starts — a replay of the schedule, not telemetry.',
    to: '/app/network',
  },
  {
    title: '6 · Explainability',
    body: 'Open any job and ask why. Request, conflict, constraint, decision, impact — five beats, each read out of the data rather than narrated.',
    to: '/app/tasks',
  },
  {
    title: '7 · Scenario',
    body: `Festival traffic, a restricted night window, merging switched off. Every preset re-plans the week; switch merging off and the simulator returns the ${baseline.blocks}-block baseline on its own.`,
    to: '/app/simulator',
  },
  {
    title: '8 · Emergency',
    body: `A cracked OHE mast foundation is raised mid-week. Re-plan and the week grows by a block, with the displaced feeder work flagged as running late.`,
    to: '/app/simulator',
  },
  {
    title: '9 · Approval',
    body: 'The plan ends as a recommendation. A section controller approves it or sends it back with a note. RailOpt never grants a possession.',
    to: '/app/plan',
  },
]

export default function DemoMode() {
  const { demoStep, setDemoStep } = useAppState()
  const navigate = useNavigate()
  const active = demoStep !== null
  const step = active ? DEMO_STEPS[demoStep] : null

  useEffect(() => {
    if (!active) return
    navigate(DEMO_STEPS[demoStep].to)
  }, [demoStep, active, navigate])

  useEffect(() => {
    if (!active) return
    const onKey = (e) => {
      if (e.key === 'Escape') setDemoStep(null)
      if (e.key === 'ArrowRight') setDemoStep((s) => Math.min(DEMO_STEPS.length - 1, s + 1))
      if (e.key === 'ArrowLeft') setDemoStep((s) => Math.max(0, s - 1))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [active, setDemoStep])

  return (
    <AnimatePresence>
      {active && (
        <motion.aside
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 24 }}
          transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
          className="fixed inset-x-3 bottom-4 z-[70] mx-auto max-w-[680px] rounded-panel-lg border border-merge/35 bg-surface/95 px-4 py-3.5 shadow-lift backdrop-blur-xl sm:px-5"
          role="region"
          aria-label="Presentation walkthrough"
        >
          <div className="flex items-start gap-4">
            <span className="tnum mt-0.5 shrink-0 rounded-[3px] bg-merge px-2 py-1 font-mono text-[11px] text-deep">
              {demoStep + 1}/{DEMO_STEPS.length}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[14.5px] font-medium">{step.title}</p>
              <p className="mt-1 text-[13px] leading-relaxed text-muted">{step.body}</p>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              <button
                onClick={() => setDemoStep((s) => Math.max(0, s - 1))}
                disabled={demoStep === 0}
                className="rounded-panel border border-line p-2 text-muted transition-colors hover:text-ink disabled:opacity-25"
                aria-label="Previous step"
              >
                <ChevronLeft size={15} />
              </button>
              <button
                onClick={() =>
                  demoStep === DEMO_STEPS.length - 1
                    ? setDemoStep(null)
                    : setDemoStep((s) => s + 1)
                }
                className="rounded-panel bg-merge p-2 text-deep transition-opacity hover:opacity-90"
                aria-label={demoStep === DEMO_STEPS.length - 1 ? 'Finish' : 'Next step'}
              >
                <ChevronRight size={15} />
              </button>
              <button
                onClick={() => setDemoStep(null)}
                className="rounded-panel border border-line p-2 text-muted transition-colors hover:text-ink"
                aria-label="Exit presentation mode"
              >
                <X size={15} />
              </button>
            </div>
          </div>

          <div className="mt-3 flex gap-1">
            {DEMO_STEPS.map((s, i) => (
              <button
                key={s.title}
                onClick={() => setDemoStep(i)}
                aria-label={`Go to step ${i + 1}: ${s.title}`}
                className={`h-[3px] flex-1 rounded-full transition-colors ${
                  i <= demoStep ? 'bg-merge' : 'bg-hair'
                }`}
              />
            ))}
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  )
}
