import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Bot, CornerDownLeft, FileText, Sparkles } from 'lucide-react'
import PageHeader from '@/components/app/PageHeader'
import StageFooter from '@/components/app/StageFooter'
import { DataTag } from '@/components/common/StatusChip'
import { copilotAnswers, copilotFallback, copilotSuggestions } from '@/data/scenarios'
import { REASON_CODES } from '@/lib/constants'
import {
  baseline,
  conflicts,
  deferredTasks,
  optimised,
  prevented,
  slaCriticalTasks,
} from '@/lib/optimizer'
import { planMeta } from '@/data/plan'
import { duration } from '@/lib/format'

/**
 * The control room copilot.
 *
 * Not a general chatbot: it answers about this plan, from a fixed set of
 * prepared responses, and says plainly that it is doing so. Every answer
 * carries the reason codes that bound the decision and the plan records it
 * was drawn from, which is the part a controller would actually check.
 */
function retrieve(question) {
  const q = question.toLowerCase()
  let best = null
  let bestScore = 0
  for (const a of copilotAnswers) {
    const score = a.match.filter((m) => q.includes(m)).length
    if (score > bestScore) {
      best = a
      bestScore = score
    }
  }
  return bestScore > 0 ? best : copilotFallback
}

const msgVariants = {
  hidden: { opacity: 0, y: 12, scale: 0.97 },
  visible: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] } },
}

export default function Assistant() {
  const [thread, setThread] = useState([])
  const [input, setInput] = useState('')
  const [thinking, setThinking] = useState(false)
  const endRef = useRef(null)

  useEffect(() => {
    document.title = 'Copilot — RailOpt'
  }, [])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [thread, thinking])

  const ask = (question) => {
    const q = question.trim()
    if (!q || thinking) return
    setThread((t) => [...t, { role: 'user', text: q }])
    setInput('')
    setThinking(true)
    setTimeout(() => {
      setThread((t) => [...t, { role: 'assistant', ...retrieve(q) }])
      setThinking(false)
    }, 650)
  }

  return (
    <>
      <PageHeader
        title="RailOpt control room copilot"
        description="Answers about this week's plan, its scores and its reason codes. If a record cannot be looked up, the question goes unanswered rather than guessed at."
      >
        <DataTag kind="prototype" />
      </PageHeader>

      <div className="grid gap-5 px-5 py-6 sm:px-8 xl:grid-cols-[1fr_380px]">
        <motion.section
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
          className="panel flex min-h-[560px] flex-col"
        >
          <div className="flex items-center gap-2 border-b border-hair px-5 py-3 sm:px-6">
            <span className="rounded-[3px] border border-warn/35 bg-warn/10 px-2 py-0.5 font-mono text-[10.5px] tracking-[0.12em] text-warn">
              DEMO / SIMULATION RESPONSE
            </span>
            <span className="text-[12px] text-faint">
              No language model or railway database is connected to this prototype.
            </span>
          </div>

          <div className="scrollbar-thin flex-1 space-y-5 overflow-y-auto px-5 py-5 sm:px-6">
            {thread.length === 0 && !thinking && (
              <div className="py-8 text-center">
                <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full border border-hair bg-raised">
                  <Sparkles size={20} className="text-eng/70" />
                </div>
                <p className="text-[15px] font-medium">Ask about the week 38 plan</p>
                <p className="mt-1 text-[13px] text-muted">
                  A task ID, a section, or one of these.
                </p>
                <div className="mx-auto mt-6 flex max-w-[560px] flex-wrap justify-center gap-2">
                  {copilotSuggestions.map((s) => (
                    <button
                      key={s}
                      onClick={() => ask(s)}
                      className="rounded-panel border border-line px-3 py-2 text-left text-[13px] text-muted transition-colors hover:border-merge/40 hover:text-ink"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <AnimatePresence initial={false}>
              {thread.map((m, i) =>
                m.role === 'user' ? (
                  <motion.div key={i} variants={msgVariants} initial="hidden" animate="visible" className="flex justify-end">
                    <p className="max-w-[80%] rounded-panel rounded-br-[3px] border border-merge/20 bg-merge/10 px-4 py-2.5 text-[14px]">
                      {m.text}
                    </p>
                  </motion.div>
                ) : (
                  <motion.div key={i} variants={msgVariants} initial="hidden" animate="visible" className="max-w-[94%]">
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-hair bg-raised">
                        <Bot size={14} className="text-snt" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-[14.5px] leading-relaxed text-ink/90">{m.answer}</p>

                        {m.codes?.length > 0 && (
                          <div className="mt-3">
                            <p className="font-mono text-[10.5px] tracking-[0.14em] text-faint">
                              REASON CODES
                            </p>
                            <ul className="mt-1.5 space-y-1.5">
                              {m.codes.map((c) => (
                                <li
                                  key={c}
                                  className="rounded-[3px] border border-hair bg-deep/30 px-3 py-2"
                                >
                                  <span className="font-mono text-[11px] text-muted">{c}</span>
                                  <span className="mt-0.5 block text-[12.5px] leading-relaxed text-faint">
                                    {REASON_CODES[c]?.text}
                                  </span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {m.sources?.length > 0 && (
                          <div className="mt-3">
                            <p className="font-mono text-[10.5px] tracking-[0.14em] text-faint">
                              DATA USED
                            </p>
                            <div className="mt-1.5 flex flex-wrap gap-1.5">
                            {m.sources.map((s) => (
                              <span
                                key={s}
                                className="rounded-panel border border-hair bg-raised/40 px-2 py-1 font-mono text-[11px] text-faint"
                              >
                                {s}
                              </span>
                            ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </motion.div>
                )
              )}
            </AnimatePresence>

            {thinking && (
              <div className="flex items-center gap-3 text-[13px] text-faint">
                <div className="flex h-7 w-7 items-center justify-center rounded-full border border-hair bg-raised">
                  <Bot size={14} className="animate-pulse text-snt" />
                </div>
                <div className="flex gap-1">
                  {[0, 150, 300].map((d) => (
                    <span
                      key={d}
                      className="h-1.5 w-1.5 animate-bounce rounded-full bg-merge/60"
                      style={{ animationDelay: `${d}ms` }}
                    />
                  ))}
                </div>
                <span>Looking up plan records</span>
              </div>
            )}
            <div ref={endRef} />
          </div>

          <div className="border-t border-hair p-3 sm:p-4">
            <div className="flex items-center gap-2 rounded-panel border border-line bg-deep/40 px-3 py-2.5 focus-within:border-merge/50">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && ask(input)}
                placeholder="Why was TMS-4521 prioritised?"
                className="min-w-0 flex-1 bg-transparent py-1 text-[14px] placeholder:text-faint focus:outline-none"
                aria-label="Ask about the plan"
              />
              <button
                onClick={() => ask(input)}
                disabled={!input.trim() || thinking}
                className="rounded-panel p-2 text-muted transition-colors hover:bg-raised hover:text-ink disabled:opacity-30"
                aria-label="Send question"
              >
                <CornerDownLeft size={16} />
              </button>
            </div>
          </div>
        </motion.section>

        <Briefing />
      </div>

      <StageFooter reason="check the data these answers come from" />
    </>
  )
}

/**
 * The week in prose, assembled from the engine's own figures rather than
 * stored as text — so it cannot drift away from the plan it describes.
 */
function Briefing() {
  const paragraphs = useMemo(
    () => [
      `${optimised.blocks} blocks are proposed for ${planMeta.window} across five corridors, covering ${optimised.tasksCovered} of the ${optimised.tasksCovered + deferredTasks.length} jobs on the books. Total planned closure is ${duration(optimised.downtimeMinutes)}, which is ${duration(prevented.downtimeAvoided)} below the ${duration(baseline.downtimeMinutes)} the three departments would have taken had their requests been granted as raised.`,
      `${optimised.mergedBlocks} blocks carry work from more than one department. Handling those jobs separately would have meant ${prevented.closuresAvoided} additional closures on sections that already carry heavy traffic, and ${prevented.trainsProtected} more train movements exposed to closure across the week.`,
      `${conflicts.length} sections were contested: ${conflicts.map((c) => c.section).join(', ')}. Between them the departments raised ${prevented.overlappingRequests} requests that overlap in time on the same track — none of which a control office could have granted as they stood.`,
      `${slaCriticalTasks.length} jobs are past their deferral limit and were force-scheduled regardless of cost. Uncoordinated, all ${baseline.slaBreaches} of them sat inside a clash and would have slipped further. ${deferredTasks.length} lower-consequence jobs were held over to the monthly horizon: ${deferredTasks.map((t) => t.id).join(', ')}.`,
    ],
    []
  )

  return (
    <motion.section
      initial={{ opacity: 0, x: 14 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: 0.15, duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
      className="panel h-fit p-5 sm:p-6"
    >
      <div className="flex items-center gap-2.5">
        <FileText size={16} className="text-merge" strokeWidth={1.7} />
        <h2 className="text-[15px] font-semibold">Week 38 briefing</h2>
      </div>
      <p className="mt-1 font-mono text-[11.5px] text-faint">
        {planMeta.planId} · composed from the plan record
      </p>

      <div className="mt-5 space-y-3.5">
        {paragraphs.map((p, i) => (
          <motion.p
            key={i}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.25 + i * 0.1, duration: 0.4 }}
            className="text-[13.5px] leading-relaxed text-muted"
          >
            {p}
          </motion.p>
        ))}
      </div>

      <p className="mt-6 border-t border-hair pt-4 text-[12px] leading-relaxed text-faint">
        Every figure above is read from the same engine that draws the timeline and the KPI cards.
        Change the plan and this paragraph changes with it.
      </p>
    </motion.section>
  )
}
