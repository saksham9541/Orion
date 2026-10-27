/**
 * The control room copilot's question bank.
 *
 * There is no language model and no database behind this prototype. Every
 * answer below is written against the plan the optimiser actually produced,
 * matched by keyword, and shown to the user marked as a demonstration
 * response. Where a figure appears in an answer it is the figure the engine
 * computes — see lib/optimizer.js — not a number invented for the script.
 *
 * In the running system this is a retrieval call against the plan store.
 * Until that exists, the interface says so rather than implying otherwise.
 */

export const copilotSuggestions = [
  'Why was TMS-4521 prioritised?',
  'Why was TMS-4655 deferred?',
  'Which maintenance blocks can be merged?',
  'What happens if traffic increases by 25%?',
  'Which sections have the highest scheduling risk?',
  'What changed between the baseline and the optimised plan?',
]

/**
 * Reason codes are the copilot's citations: each answer names the constraints
 * that actually bound the decision, using the same vocabulary the block
 * detail panel and the task explainer use.
 */
export const copilotAnswers = [
  {
    match: ['4521', 'prioritised', 'prioritized', 'rail flaw'],
    answer:
      'TMS-4521 is an IMR-class rail flaw on DER–KRJ carrying a 30 kmph speed restriction. It scores 94 on the shared urgency scale and is three days past its deferral limit, so it was force-scheduled into the earliest window of the week rather than left to compete for a slot. RailOpt placed it Monday 01:00–04:45 and put the point machine job SMMS-2210 inside the same possession, because both need access to the same section. That removes one closure from a section running 188 trains a day.',
    codes: ['SLA_FORCED', 'MERGED_CROSS_DEPT', 'LOW_TRAFFIC_WINDOW'],
    sources: ['TMS-4521 / urgency 94', 'PLAN-2026-W38 / B-101', 'Deferral limit: 3 days over'],
  },
  {
    match: ['4655', 'deferred', 'pushed', 'next month', 'points and crossing'],
    answer:
      'TMS-4655, the points and crossing renewal at Mumbai Central, scores 58 and has 26 days left before its deferral limit. It needs five hours of track time, and no window that long exists on BCT–BVI inside this week without cutting into suburban services. RailOpt moved it to the Week 41 consolidation block, where a longer closure is already planned and it can share the possession with other work. Nothing about the job is safety-critical for train movement.',
    codes: ['DEFERRED_LOW_IMPACT', 'CORRIDOR_CONFLICT'],
    sources: ['TMS-4655 / urgency 58', 'Monthly plan / Week 41', 'Window constraint: 345 min required'],
  },
  {
    match: ['merge', 'merged', 'shared', 'combine', 'more than one department', 'cross'],
    answer:
      'Three blocks carry work from more than one department this week. B-101 on DER–KRJ combines the rail flaw with the point machine job on Monday. B-113 on BVI–BSR combines OHE mast work with curve realignment on Wednesday. B-108 on BSR–PLG combines ballast screening with track circuit work on Sunday. Each merge removes a separate closure from the calendar, and together they account for the difference between nineteen possessions and sixteen.',
    codes: ['MERGED_CROSS_DEPT'],
    sources: ['PLAN-2026-W38 / B-101', 'PLAN-2026-W38 / B-113', 'PLAN-2026-W38 / B-108'],
  },
  {
    match: ['traffic', '25', 'increase', 'busier', 'festival'],
    answer:
      'Raising traffic 25 per cent does not change which blocks are taken — the same sixteen possessions still fit the same windows, because the night window is the binding constraint, not the number of trains. What changes is what those possessions cost: the movements held rise with the traffic, and the long Sunday block on BSR–PLG overruns further into service hours. The Festival week preset in the Scenario Lab applies exactly this change.',
    codes: ['LOW_TRAFFIC_WINDOW', 'GOODS_PEAK_AVOIDED'],
    sources: ['Scenario Lab / Festival week', 'Corridor traffic profiles'],
  },
  {
    match: ['risk', 'highest', 'scheduling risk', 'contested', 'conflict'],
    answer:
      'Four sections had two or more departments asking for the same track at the same time: DER–KRJ and SHDM–GZB on Monday night with three requests each, BSR–PLG on Tuesday with three, and BCT–BVI on Monday with two. DER–KRJ is the worst of them — three departments, one section, and 135 minutes where all three requested windows sit on top of each other. All four are resolved in the current plan.',
    codes: ['CORRIDOR_CONFLICT', 'MERGED_CROSS_DEPT'],
    sources: ['Conflict radar / 4 contested sections', 'PLAN-2026-W38 / summary'],
  },
  {
    match: ['changed', 'baseline', 'difference', 'before', 'after', 'optimised', 'optimized'],
    answer:
      'Taken as raised, the nineteen requests would have meant nineteen separate possessions and 57 hours of closure. The coordinated plan does the same work in sixteen blocks and 45 hours 35 minutes, holds fewer train movements, and leaves nothing past its deferral limit. The saving comes from three merges and from moving blocks into the quietest window each section has — not from doing less work. Every one of the nineteen jobs is still in the plan.',
    codes: ['MERGED_CROSS_DEPT', 'LOW_TRAFFIC_WINDOW', 'SLA_FORCED'],
    sources: ['Baseline / 19 as-raised requests', 'PLAN-2026-W38 / 16 blocks'],
  },
  {
    match: ['sla', 'deferral', 'overdue', 'breach', 'past', 'limit'],
    answer:
      'Four jobs are already past their deferral limit: TMS-4521, TDMS-1203, SMMS-2401 and TDMS-1444. Uncoordinated, each of the four sits in a window another department had also asked for, so none could be granted and all four would have slipped further. In the coordinated plan all four are scheduled inside their limits, which is why the plan ends the week with no breaches.',
    codes: ['SLA_FORCED'],
    sources: ['Deferral engine / 4 jobs over limit', 'PLAN-2026-W38 / 0 breaches'],
  },
  {
    match: ['emergency', 'critical', 're-optimise', 'reoptimise', 'reoptimize', '1501'],
    answer:
      'Inserting a critical job mid-week is handled in the Scenario Lab. The worked example is TDMS-1501, a cracked OHE mast foundation on BSR–PLG: the plan goes from sixteen blocks to seventeen, the section that already had a Monday possession gives it up to the critical job, and the displaced feeder work moves out by a day and is flagged as running late. RailOpt re-prices the whole week rather than patching the one block.',
    codes: ['SLA_FORCED', 'CORRIDOR_CONFLICT'],
    sources: ['Scenario Lab / emergency re-plan', 'TDMS-1501 / urgency 97'],
  },
]

export const copilotFallback = {
  answer:
    'Nothing in the current plan matches that. This prototype answers from the week 38 plan, the task scores and the reason codes it can actually look up — try naming a task ID, a section, or one of the suggested questions.',
  codes: [],
  sources: [],
}

/** What-if control ranges, kept here so the lab and the engine agree. */
export const scenarioControls = {
  trafficDelta: { min: -20, max: 50, step: 5 },
  windowEnd: { min: 180, max: 420, step: 30 },
  maxParallel: { min: 1, max: 6, step: 1 },
}
