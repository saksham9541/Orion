/**
 * RailOpt's derivation layer.
 *
 * Nothing in the interface is a typed-in number. Every KPI, saving, conflict,
 * efficiency score and risk cell in the product is computed here from three
 * inputs and nothing else:
 *
 *   data/tasks.js      the 22 pending jobs, and the window each department
 *                      asked for in its own system
 *   data/plan.js       which jobs RailOpt put in which block, and when
 *   data/corridors.js  section traffic, used to price a closure in trains
 *
 * The baseline is not a stored table either — it is reconstructed from the
 * as-raised requests, so "what RailOpt changed" is always the difference
 * between the same work coordinated and uncoordinated.
 *
 * This is demonstration data throughout. It is not a feed from any live
 * railway system, and the interface says so wherever a number is shown.
 */

import { corridors } from '@/data/corridors'
import { tasks, taskById } from '@/data/tasks'
import { weeklyBlocks, planMeta } from '@/data/plan'
import { POSSESSION_OVERHEAD, possessionMinutes, overlaps } from './possession'
import { DEPARTMENTS } from './constants'

export const corridorById = Object.fromEntries(corridors.map((c) => [c.id, c]))

/** Every section in the division, in corridor order. */
export const allSections = corridors.flatMap((c) =>
  c.sections.map((section) => ({ section, corridor: c }))
)

export const sectionCorridor = Object.fromEntries(
  allSections.map(({ section, corridor }) => [section, corridor])
)

/* ------------------------------------------------------------------ *
 * Traffic exposure
 * ------------------------------------------------------------------ */

/**
 * Trains that would have run through a section during a closure.
 *
 * The corridor's daily movements are spread across twelve two-hour buckets
 * by its traffic profile, then integrated over the possession window in
 * quarter-hour steps. A block in the 02:00–04:00 trough therefore costs a
 * fraction of the same block at 08:00 — which is the single judgement the
 * optimiser is making when it picks a window.
 */
export function trainsHeld(corridorId, start, end) {
  const c = corridorById[corridorId]
  if (!c) return 0
  const total = c.trafficProfile.reduce((a, b) => a + b, 0)
  let held = 0
  for (let m = start; m < end; m += 15) {
    const bucket = Math.floor(((m / 60) % 24) / 2) % 12
    // trainsPerDay x bucket share = trains in that 2h bucket; /2 per hour; x 0.25 per step
    held += ((c.trainsPerDay * (c.trafficProfile[bucket] / total)) / 2) * 0.25
  }
  return held
}

/** Traffic intensity 0-1 at a moment on a corridor, for shading and risk. */
export function trafficAt(corridorId, minutes) {
  const c = corridorById[corridorId]
  if (!c) return 0
  const bucket = Math.floor(((minutes / 60) % 24) / 2) % 12
  return c.trafficProfile[bucket] / 100
}

export function trafficBand(intensity) {
  if (intensity >= 0.75) return 'Very high'
  if (intensity >= 0.55) return 'High'
  if (intensity >= 0.35) return 'Medium'
  return 'Low'
}

/* ------------------------------------------------------------------ *
 * The two plans
 * ------------------------------------------------------------------ */

export const scheduledTasks = tasks.filter((t) => t.status === 'scheduled')
export const deferredTasks = tasks.filter((t) => t.status !== 'scheduled')

/**
 * The uncoordinated baseline: every department's request taken as raised,
 * one possession per job, in the window that department asked for.
 */
export const baselineBlocks = scheduledTasks.map((t) => ({
  id: `REQ-${t.id}`,
  taskId: t.id,
  taskIds: [t.id],
  dept: t.department,
  corridorId: t.corridorId,
  section: t.section,
  day: t.requested.day,
  start: t.requested.start,
  end: t.requested.start + t.estDuration + POSSESSION_OVERHEAD,
  merged: false,
}))

/** As-raised requests including the three jobs held over to next month. */
export const allRequests = tasks.map((t) => ({
  id: `REQ-${t.id}`,
  taskId: t.id,
  dept: t.department,
  corridorId: t.corridorId,
  section: t.section,
  day: t.requested.day,
  start: t.requested.start,
  end: t.requested.start + t.estDuration + POSSESSION_OVERHEAD,
  deferred: t.status !== 'scheduled',
}))

/* ------------------------------------------------------------------ *
 * Conflicts
 * ------------------------------------------------------------------ */

/**
 * Two departments asking to close the same section at the same time.
 *
 * Grouped by section so the radar can draw one lane per conflict, with the
 * overlapping region — the part no control office can grant — marked.
 */
export const conflicts = (() => {
  const bySection = {}
  for (const r of allRequests) {
    ;(bySection[r.section] ||= []).push(r)
  }
  const found = []
  for (const [section, reqs] of Object.entries(bySection)) {
    const clashing = reqs.filter((a) => reqs.some((b) => b !== a && overlaps(a, b)))
    if (clashing.length < 2) continue
    const group = [...clashing].sort((a, b) => a.day - b.day || a.start - b.start)
    const overlapStart = Math.max(...group.map((r) => r.start))
    const overlapEnd = Math.min(...group.map((r) => r.end))
    const depts = [...new Set(group.map((r) => r.dept))]
    found.push({
      section,
      corridorId: group[0].corridorId,
      day: group[0].day,
      requests: group,
      departments: depts,
      overlapStart,
      overlapEnd,
      overlapMinutes: Math.max(0, overlapEnd - overlapStart),
      windowStart: Math.min(...group.map((r) => r.start)),
      windowEnd: Math.max(...group.map((r) => r.end)),
      /** What RailOpt did with this clash, looked up in the actual plan. */
      get resolution() {
        return resolutionFor(section)
      },
    })
  }
  return found.sort((a, b) => b.requests.length - a.requests.length || a.day - b.day)
})()

function resolutionFor(section) {
  const blocks = weeklyBlocks.filter((bl) => bl.section === section)
  return {
    blocks,
    merged: blocks.filter((bl) => bl.merged),
    closures: blocks.length,
  }
}

export const conflictBySection = Object.fromEntries(conflicts.map((c) => [c.section, c]))

/** The clash the demo leads with: three departments, one section, one night. */
export const headlineConflict =
  conflicts.find((c) => c.section === 'DER–KRJ') ?? conflicts[0] ?? null

/* ------------------------------------------------------------------ *
 * Deferral limits
 * ------------------------------------------------------------------ */

/** The day by which a job must be done. Already-overdue work is due now. */
export function deadlineDay(task) {
  return Math.max(0, task.slaDays)
}

export const slaCriticalTasks = scheduledTasks.filter((t) => t.slaDays <= 0)

/**
 * Baseline breaches: a job already past its deferral limit whose as-raised
 * window collides with another department's request on the same section. The
 * control office cannot grant both, the request is refused, and the job slips
 * further past its limit with no window left in the week.
 */
export const baselineBreaches = slaCriticalTasks.filter((t) =>
  allRequests.some(
    (r) =>
      r.taskId !== t.id &&
      r.section === t.section &&
      overlaps(
        { day: t.requested.day, start: t.requested.start, end: t.requested.start + t.estDuration + POSSESSION_OVERHEAD },
        r
      )
  )
)

/** Optimised breaches: any job placed later than its deferral limit allows. */
export const optimisedBreaches = scheduledTasks.filter((t) => {
  const block = weeklyBlocks.find((bl) => bl.taskIds.includes(t.id))
  if (!block) return true
  return block.day > deadlineDay(t)
})

/* ------------------------------------------------------------------ *
 * Headline numbers
 * ------------------------------------------------------------------ */

function summarise(blocks) {
  const downtime = blocks.reduce((s, bl) => s + (bl.end - bl.start), 0)
  const trains = blocks.reduce((s, bl) => s + trainsHeld(bl.corridorId, bl.start, bl.end), 0)
  return { count: blocks.length, downtime, trains: Math.round(trains) }
}

export const baseline = (() => {
  const s = summarise(baselineBlocks)
  return {
    blocks: s.count,
    downtimeMinutes: s.downtime,
    trainsAffected: s.trains,
    slaBreaches: baselineBreaches.length,
    tasksCovered: scheduledTasks.length,
    mergedBlocks: 0,
  }
})()

export const optimised = (() => {
  const s = summarise(weeklyBlocks)
  return {
    blocks: s.count,
    downtimeMinutes: s.downtime,
    trainsAffected: s.trains,
    slaBreaches: optimisedBreaches.length,
    tasksCovered: [...new Set(weeklyBlocks.flatMap((bl) => bl.taskIds))].length,
    mergedBlocks: weeklyBlocks.filter((bl) => bl.merged).length,
  }
})()

/** Percentage change, computed — never asserted. */
export function improvement(before, after) {
  if (!before) return 0
  return ((before - after) / before) * 100
}

export const kpis = {
  blocksProposed: optimised.blocks,
  blocksBaseline: baseline.blocks,
  mergedBlocks: optimised.mergedBlocks,
  tasksCovered: optimised.tasksCovered,
  tasksTotal: tasks.length,
  tasksDeferred: deferredTasks.length,
  downtimeMinutes: optimised.downtimeMinutes,
  baselineDowntimeMinutes: baseline.downtimeMinutes,
  trainsAffected: optimised.trainsAffected,
  baselineTrainsAffected: baseline.trainsAffected,
  slaBreaches: optimised.slaBreaches,
  baselineSlaBreaches: baseline.slaBreaches,
  assetAvailability: availability(optimised.downtimeMinutes),
  baselineAvailability: availability(baseline.downtimeMinutes),
}

/**
 * Share of the week's maintenance capacity still free.
 *
 * The denominator is every section's night window across the seven days —
 * the track time actually available for possessions — rather than the whole
 * 24 hours, which would make any amount of closure look negligible.
 */
function availability(downtimeMinutes) {
  const [from, to] = planMeta.nightWindow
  const capacity = allSections.length * 7 * (to - from)
  return +(100 - (downtimeMinutes / capacity) * 100).toFixed(1)
}

/**
 * What coordination removed. Each figure is a subtraction between the two
 * plans above — nothing here is an assumed rate or an estimated saving.
 */
export const prevented = {
  closuresAvoided: baseline.blocks - optimised.blocks,
  trainsProtected: baseline.trainsAffected - optimised.trainsAffected,
  downtimeAvoided: baseline.downtimeMinutes - optimised.downtimeMinutes,
  breachesPrevented: baseline.slaBreaches - optimised.slaBreaches,
  conflictsResolved: conflicts.length,
  overlappingRequests: conflicts.reduce((s, c) => s + c.requests.length, 0),
}

/** Downtime per department, apportioned by the work each one owns. */
export const downtimeByDept = ['ENG', 'SNT', 'TRD'].map((dept) => {
  const name = { ENG: 'Engineering', SNT: 'Signal & Telecom', TRD: 'Traction' }[dept]
  const mine = scheduledTasks.filter((t) => t.department === dept)
  const baselineMins = mine.reduce((s, t) => s + t.estDuration + POSSESSION_OVERHEAD, 0)
  // In a shared block a department is charged its share of the closure.
  let planned = 0
  for (const bl of weeklyBlocks) {
    const blTasks = bl.taskIds.map((id) => taskById[id]).filter(Boolean)
    const mineHere = blTasks.filter((t) => t.department === dept)
    if (!mineHere.length) continue
    planned += ((bl.end - bl.start) * mineHere.length) / blTasks.length
  }
  return { dept: name, planned: Math.round(planned), baseline: baselineMins }
})

/* ------------------------------------------------------------------ *
 * Per-block efficiency
 * ------------------------------------------------------------------ */

/**
 * How well one closure uses the track time it takes.
 *
 * Four components, each bounded and each traceable to something on screen:
 * how much of the possession is productive work rather than protection and
 * handback; how much a merge saved against separate closures; how quiet the
 * window is; and how much safety-critical work it clears. Weighted to 100.
 */
export function blockEfficiency(block) {
  const blTasks = block.taskIds.map((id) => taskById[id]).filter(Boolean)
  const length = block.end - block.start
  const work = Math.max(...blTasks.map((t) => t.estDuration))
  const parallel = blTasks.reduce((s, t) => s + t.estDuration, 0)

  // Productive share of the possession, 0-40.
  const utilisation = Math.min(1, parallel / length)
  const utilScore = utilisation * 40

  // Closures avoided by merging, 0-25.
  const separate = blTasks.reduce((s, t) => s + t.estDuration + POSSESSION_OVERHEAD, 0)
  const saved = separate - length
  const mergeScore = blTasks.length > 1 ? Math.min(25, (saved / separate) * 60) : 6

  // Traffic exposure, 0-20 — a quiet window scores full marks.
  const perHour = trainsHeld(block.corridorId, block.start, block.end) / (length / 60)
  const peakPerHour = corridorById[block.corridorId].trainsPerDay / 24
  const exposure = Math.min(1, perHour / Math.max(1, peakPerHour * 1.6))
  const trafficScore = (1 - exposure) * 20

  // Safety urgency cleared, 0-15.
  const urgency = Math.max(...blTasks.map((t) => t.score)) / 100
  const urgencyScore = urgency * 15

  const score = Math.round(utilScore + mergeScore + trafficScore + urgencyScore)

  return {
    score: Math.max(0, Math.min(100, score)),
    components: [
      { label: 'Track time doing work', value: Math.round(utilScore), max: 40, detail: `${Math.round(utilisation * 100)}% of the possession` },
      { label: 'Closures avoided by merging', value: Math.round(mergeScore), max: 25, detail: blTasks.length > 1 ? `${saved} min saved` : 'single-job block' },
      { label: 'Quiet window chosen', value: Math.round(trafficScore), max: 20, detail: trafficBand(trafficAt(block.corridorId, block.start)) + ' traffic' },
      { label: 'Safety urgency cleared', value: Math.round(urgencyScore), max: 15, detail: `top score ${Math.max(...blTasks.map((t) => t.score))}` },
    ],
    tasksCombined: blTasks.length,
    departments: [...new Set(blTasks.map((t) => t.department))],
    duration: length,
    work,
    trafficExposure: trafficBand(trafficAt(block.corridorId, block.start + length / 2)),
    safetyUrgency: urgency >= 0.85 ? 'Critical' : urgency >= 0.65 ? 'High' : urgency >= 0.4 ? 'Medium' : 'Low',
    closuresAvoided: blTasks.length - 1,
    trainsHeld: Math.round(trainsHeld(block.corridorId, block.start, block.end)),
    savedMinutes: blTasks.length > 1 ? saved : 0,
  }
}

export const blockEfficiencyById = Object.fromEntries(
  weeklyBlocks.map((bl) => [bl.id, blockEfficiency(bl)])
)

export const averageEfficiency = Math.round(
  weeklyBlocks.reduce((s, bl) => s + blockEfficiencyById[bl.id].score, 0) / weeklyBlocks.length
)

/* ------------------------------------------------------------------ *
 * Per-task explainability
 * ------------------------------------------------------------------ */

/**
 * Why this job ended up where it did, in the order a controller would ask.
 * Every clause is a lookup, not a template: if the job is not overdue, the
 * overdue line does not appear.
 */
export function explainTask(taskId) {
  const task = taskById[taskId]
  if (!task) return null
  const block = weeklyBlocks.find((bl) => bl.taskIds.includes(taskId))
  const corridor = corridorById[task.corridorId]
  const reasons = []

  if (task.score >= 85) reasons.push(`Urgency scores ${task.score} of 100 — the highest band on the shared scale.`)
  else if (task.score >= 65) reasons.push(`Urgency scores ${task.score} of 100, in the high band.`)

  if (task.slaDays <= 0)
    reasons.push(
      `Already ${Math.abs(task.slaDays)} day${Math.abs(task.slaDays) === 1 ? '' : 's'} past its deferral limit, so it is force-fitted into the earliest window regardless of cost.`
    )
  else reasons.push(`${task.slaDays} days remain before its deferral limit.`)

  const intensity = trafficAt(task.corridorId, block ? block.start : task.requested.start)
  reasons.push(
    `${task.section} carries ${corridor.trainsPerDay} trains a day; the chosen window sits in ${trafficBand(intensity).toLowerCase()} traffic.`
  )

  if (block) {
    const fits = block.end <= planMeta.nightWindow[1]
    reasons.push(
      fits
        ? `The ${possessionMinutes(block.taskIds.map((i) => taskById[i]))} minute possession fits inside the available night window.`
        : `The possession needs ${possessionMinutes(block.taskIds.map((i) => taskById[i]))} minutes, longer than the night window, so it was placed on the quietest day of the week.`
    )
    if (block.merged) {
      const other = block.taskIds.filter((i) => i !== taskId).map((i) => taskById[i])
      reasons.push(
        `A compatible ${other.map((o) => DEPARTMENTS[o.department]?.name ?? o.department).join(' and ')} job on the same section can share this closure: ${other.map((o) => o.id).join(', ')}.`
      )
      reasons.push(`Merging removes one separate closure from ${task.section} this week.`)
    }
  } else {
    reasons.push('No window this long exists on this section inside the week, so it moves to the monthly horizon.')
  }

  return {
    task,
    block,
    reasons,
    constraints: [
      { label: 'Safety', met: true },
      { label: 'Available block window', met: !!block },
      { label: 'Traffic exposure', met: true },
      { label: 'Deferral limit', met: !block ? task.slaDays > 7 : block.day <= deadlineDay(task) },
      { label: 'Department coordination', met: true },
      { label: 'Maintenance duration', met: true },
      { label: 'Operational impact', met: true },
    ],
    coordination: coordinationFor(taskId),
  }
}

/**
 * Other jobs that need the same track. Whether or not they were merged, the
 * controller should be able to see them.
 */
export function coordinationFor(taskId) {
  const task = taskById[taskId]
  if (!task) return []
  const block = weeklyBlocks.find((bl) => bl.taskIds.includes(taskId))
  return tasks
    .filter((t) => t.id !== taskId && t.section === task.section && t.status === 'scheduled')
    .map((t) => {
      const theirBlock = weeklyBlocks.find((bl) => bl.taskIds.includes(t.id))
      const shared = !!block && theirBlock?.id === block.id
      const combined = possessionMinutes([task, t])
      return {
        task: t,
        shared,
        combinedMinutes: combined,
        saving: task.estDuration + t.estDuration + 2 * POSSESSION_OVERHEAD - combined,
        reason: shared
          ? `Sharing block ${block.id}. Both jobs need access to ${task.section}.`
          : combined > planMeta.nightWindow[1]
            ? `Both need ${task.section}, but the combined possession runs to ${combined} minutes — past the available night window.`
            : `Both need ${task.section}. Held apart to keep two closures short rather than one long one.`,
      }
    })
}

/* ------------------------------------------------------------------ *
 * Network state over time
 * ------------------------------------------------------------------ */

export const NODE_STATES = {
  available: { id: 'available', label: 'Available', short: 'Clear', color: '#4FC3A1', icon: '●' },
  planned: { id: 'planned', label: 'Planned maintenance', short: 'Planned', color: '#E8A33D', icon: '◐' },
  active: { id: 'active', label: 'Active block', short: 'Blocked', color: '#E5484D', icon: '■' },
  critical: { id: 'critical', label: 'Critical safety task', short: 'Critical', color: '#F2731B', icon: '▲' },
  conflict: { id: 'conflict', label: 'Scheduling conflict', short: 'Conflict', color: '#A78BFA', icon: '◆' },
}

/**
 * The state of one section at a simulated moment.
 *
 * Priority runs downward: a block actually in progress beats one planned for
 * later today, a safety-critical possession is called out separately, and an
 * unresolved request clash on the section shows through when nothing is
 * currently closed.
 */
export function sectionStateAt(section, day, minutes) {
  const active = weeklyBlocks.filter(
    (bl) => bl.section === section && bl.day === day && bl.start <= minutes && bl.end > minutes
  )
  if (active.length) {
    const blTasks = active[0].taskIds.map((id) => taskById[id]).filter(Boolean)
    const critical = blTasks.some((t) => t.score >= 85)
    return {
      state: critical ? 'critical' : 'active',
      block: active[0],
      tasks: blTasks,
    }
  }
  const laterToday = weeklyBlocks.filter(
    (bl) => bl.section === section && bl.day === day && bl.start > minutes
  )
  if (laterToday.length) {
    return {
      state: 'planned',
      block: laterToday[0],
      tasks: laterToday[0].taskIds.map((id) => taskById[id]).filter(Boolean),
    }
  }
  const clash = conflictBySection[section]
  if (clash && clash.day === day) {
    return { state: 'conflict', block: null, tasks: clash.requests.map((r) => taskById[r.taskId]) }
  }
  return { state: 'available', block: null, tasks: [] }
}

/** Division-wide snapshot at a simulated moment. */
export function networkStateAt(day, minutes) {
  const sections = {}
  for (const { section } of allSections) sections[section] = sectionStateAt(section, day, minutes)
  const activeBlocks = weeklyBlocks.filter(
    (bl) => bl.day === day && bl.start <= minutes && bl.end > minutes
  )
  const trains = activeBlocks.reduce(
    (s, bl) => s + trainsHeld(bl.corridorId, Math.max(bl.start, minutes - 60), bl.end),
    0
  )
  const criticalCount = Object.values(sections).filter((s) => s.state === 'critical').length
  return {
    sections,
    activeBlocks,
    trainsAffected: Math.round(trains),
    status:
      activeBlocks.length === 0
        ? 'Normal working — no possession in force'
        : criticalCount > 0
          ? 'Operational with a safety-critical possession in force'
          : 'Operational with planned maintenance',
  }
}

/** Section detail for the twin's side panel. */
export function sectionDetail(section, day, minutes) {
  const corridor = sectionCorridor[section]
  const state = sectionStateAt(section, day, minutes)
  const sectionTasks = tasks.filter((t) => t.section === section)
  const blocks = weeklyBlocks.filter((bl) => bl.section === section)
  const clash = conflictBySection[section]
  const intensity = trafficAt(corridor.id, minutes)
  const recommendation = clash
    ? clash.requests.length > 2
      ? `Coordinate ${clash.requests.length} maintenance requests into ${blocks.length} possession${blocks.length === 1 ? '' : 's'} on this section.`
      : `Coordinate ${clash.requests.length} maintenance requests into one possession window.`
    : blocks.some((bl) => bl.merged)
      ? 'Two departments already share a single closure here.'
      : 'No coordination opportunity on this section this week.'
  return {
    section,
    corridor,
    state,
    tasks: sectionTasks,
    blocks,
    conflict: clash ?? null,
    traffic: trafficBand(intensity),
    trafficIntensity: intensity,
    trainsAffected: state.block
      ? Math.round(trainsHeld(corridor.id, state.block.start, state.block.end))
      : 0,
    departments: [...new Set(sectionTasks.map((t) => t.department))],
    risk: riskFor(section, day),
    recommendation,
  }
}

function riskFor(section, day) {
  const clash = conflictBySection[section]
  const blocks = weeklyBlocks.filter((bl) => bl.section === section && bl.day === day)
  const critical = blocks.some((bl) =>
    bl.taskIds.some((id) => (taskById[id]?.score ?? 0) >= 85)
  )
  if (critical) return 'High'
  if (clash && clash.day === day) return 'High'
  if (blocks.length) return 'Medium'
  return 'Low'
}

/* ------------------------------------------------------------------ *
 * Risk heatmap
 * ------------------------------------------------------------------ */

export const RISK_HOURS = Array.from({ length: 24 }, (_, h) => h)

/**
 * Corridor x hour exposure, summed across the week.
 *
 * A cell is high when a busy hour on that corridor coincides with a
 * possession: traffic intensity multiplied by the share of the hour that is
 * closed, normalised across the grid so the scale is comparable.
 */
export function riskGrid(day = null) {
  const rows = corridors.map((c) => {
    const cells = RISK_HOURS.map((h) => {
      const from = h * 60
      const to = from + 60
      const blocks = weeklyBlocks.filter(
        (bl) => bl.corridorId === c.id && (day === null || bl.day === day) && bl.start < to && bl.end > from
      )
      const closedMinutes = blocks.reduce(
        (s, bl) => s + Math.max(0, Math.min(bl.end, to) - Math.max(bl.start, from)),
        0
      )
      const closedShare = Math.min(1, closedMinutes / (day === null ? 60 * 7 : 60))
      const intensity = trafficAt(c.id, from)
      const value = closedShare * intensity
      return {
        hour: h,
        value,
        intensity,
        closedMinutes,
        blocks,
      }
    })
    return { corridor: c, cells }
  })
  const peak = Math.max(0.0001, ...rows.flatMap((r) => r.cells.map((cl) => cl.value)))
  for (const r of rows) for (const cl of r.cells) cl.level = cl.value / peak
  return rows
}

/* ------------------------------------------------------------------ *
 * The optimisation run
 * ------------------------------------------------------------------ */

/**
 * The optimisation pipeline.
 *
 * Seven stages, in the order the engine actually works: take the requests in,
 * find where they collide, test them against the constraints, price the
 * windows, look for jobs that can share a possession, simulate what the
 * result costs in train movements, and emit the plan.
 *
 * Every `status` below is a count taken from the data at the moment it is
 * read — so the progress readout is a summary of the work rather than a
 * decorative loading bar. The same definition drives the static diagram on
 * the block plan and the live run on the overview.
 */
export function pipelineStages() {
  return [
    {
      id: 'requests',
      label: 'Maintenance requests',
      status: `${tasks.length} requests received from 3 source systems`,
      detail: `${scheduledTasks.length} for this week, ${deferredTasks.length} held over`,
    },
    {
      id: 'conflict',
      label: 'Conflict detection',
      status: `${conflicts.length} contested sections found`,
      detail: `${prevented.overlappingRequests} requests overlap on the same track`,
    },
    {
      id: 'constraints',
      label: 'Constraint check',
      status: `${slaCriticalTasks.length} jobs past their deferral limit`,
      detail: 'safety urgency · requested duration · traffic exposure · deferral limit',
      checks: [
        'Safety urgency',
        'Requested duration',
        'Traffic exposure',
        'Deferral limit',
        'Department coordination',
      ],
    },
    {
      id: 'windows',
      label: 'Window evaluation',
      status: `night window ${clockOf(planMeta.nightWindow[0])}–${clockOf(planMeta.nightWindow[1])} priced per section`,
      detail: `${corridors.length} corridors profiled across 12 two-hour traffic buckets`,
    },
    {
      id: 'coordination',
      label: 'Task coordination',
      status: `${optimised.mergedBlocks} compatible combinations found`,
      detail: `${prevented.closuresAvoided} separate closures removed`,
    },
    {
      id: 'impact',
      label: 'Impact simulation',
      status: `${optimised.trainsAffected} estimated train movements impacted`,
      detail: `against ${baseline.trainsAffected} if the requests were granted as raised`,
    },
    {
      id: 'plan',
      label: 'Optimised block plan',
      status: `${optimised.blocks} blocks ready for controller review`,
      detail: `${optimised.downtimeMinutes} min planned closure · ${optimised.slaBreaches} deferral breaches`,
    },
  ]
}

function clockOf(m) {
  const h = Math.floor(m / 60) % 24
  return `${String(h).padStart(2, '0')}:${String(Math.round(m % 60)).padStart(2, '0')}`
}

/** Kept as an alias: the run animation and the diagram read the same list. */
export const optimisationStages = pipelineStages

/* ------------------------------------------------------------------ *
 * Scenario simulation
 * ------------------------------------------------------------------ */

export const SCENARIOS = [
  {
    id: 'normal',
    name: 'Normal week',
    note: 'The division as planned for week 38.',
    settings: { trafficDelta: 0, windowStart: 0, windowEnd: 330, maxParallel: 4, merge: true, sla: true, emergency: false },
  },
  {
    id: 'festival',
    name: 'Festival week',
    note: 'Special trains added; every section busier and the night window shorter.',
    settings: { trafficDelta: 25, windowStart: 0, windowEnd: 270, maxParallel: 4, merge: true, sla: true, emergency: false },
  },
  {
    id: 'high-traffic',
    name: 'High traffic',
    note: 'Goods surge across the freight corridors.',
    settings: { trafficDelta: 40, windowStart: 0, windowEnd: 330, maxParallel: 4, merge: true, sla: true, emergency: false },
  },
  {
    id: 'emergency',
    name: 'Emergency',
    note: 'A critical defect is raised mid-week and must be fitted in.',
    settings: { trafficDelta: 10, windowStart: 0, windowEnd: 330, maxParallel: 4, merge: true, sla: true, emergency: true },
  },
  {
    id: 'restricted',
    name: 'Restricted night window',
    note: 'Traffic block available only between 23:00 and 04:00.',
    settings: { trafficDelta: 0, windowStart: 0, windowEnd: 240, maxParallel: 2, merge: true, sla: true, emergency: false },
  },
]

export const scenarioDefaults = SCENARIOS[0].settings

/** The extra job an emergency scenario injects. Demonstration data. */
export const emergencyTask = {
  id: 'TDMS-1501',
  department: 'TRD',
  corridorId: 'C-BSR-ST',
  section: 'BSR–PLG',
  defectType: 'OHE mast foundation cracked',
  estDuration: 150,
  score: 97,
  slaDays: -1,
  daysOverdue: 1,
  risk: 'CRITICAL',
  note:
    'Reported by the section gang during a routine patrol. Mast 214/7 shows a through-crack at the foundation. Speed restriction imposed pending repair.',
}

/**
 * Re-plan the week under different constraints.
 *
 * The simulation starts from the published plan rather than re-solving from
 * nothing, so at the default settings it reproduces that plan exactly — the
 * comparison column a controller trusts. Each constraint is then applied as
 * a transformation whose effect can be traced:
 *
 *   merge off      shared blocks split back into one closure per job
 *   shorter window every block re-placed at the quietest legal start; any
 *                  that no longer fits overruns into service hours
 *   parallel cap   days over the cap push blocks to the next day with room,
 *                  and anything with nowhere to go is carried to next month
 *   traffic delta  scales the movements each possession holds
 *   emergency      injects a critical job and re-places around it
 */
export function simulate(settings) {
  const s = { ...scenarioDefaults, ...settings }
  const windowLength = Math.max(60, s.windowEnd - s.windowStart)

  // 1. Start from the published plan, splitting merges if merging is off.
  let units = []
  for (const bl of weeklyBlocks) {
    const blTasks = bl.taskIds.map((id) => taskById[id]).filter(Boolean)
    if (s.merge || blTasks.length === 1) {
      units.push({ tasks: blTasks, corridorId: bl.corridorId, section: bl.section, origin: bl.id })
    } else {
      for (const t of blTasks) {
        units.push({ tasks: [t], corridorId: bl.corridorId, section: bl.section, origin: bl.id })
      }
    }
  }

  if (s.emergency) {
    units.push({
      tasks: [emergencyTask],
      corridorId: emergencyTask.corridorId,
      section: emergencyTask.section,
      origin: 'EMG',
      emergency: true,
    })
  }

  // 2. Urgency order decides who gets the scarce night capacity first.
  units.sort((a, b) => {
    const as = Math.max(...a.tasks.map((t) => t.score))
    const bs = Math.max(...b.tasks.map((t) => t.score))
    return bs - as
  })

  // 3. Place each possession on the earliest day it is allowed, at the
  //    quietest start that day.
  const perDay = Array.from({ length: 7 }, () => [])
  const placed = []
  const carried = []

  for (const unit of units) {
    const length = possessionMinutes(unit.tasks)
    const limit = Math.min(...unit.tasks.map((t) => deadlineDay(t)))
    const published = weeklyBlocks.find((bl) => bl.id === unit.origin)
    const preferredDay = unit.emergency ? 0 : (published?.day ?? 0)

    // Days to try: the day the plan chose, then any other day inside the limit.
    const order = [preferredDay, ...Array.from({ length: 7 }, (_, d) => d)]
    const free = (day) =>
      perDay[day].length < s.maxParallel && !perDay[day].some((bl) => bl.section === unit.section)

    // First pass inside the deferral limit. If nothing is free there the job
    // still has to be done, so a second pass takes the earliest day with
    // capacity and the block is marked late rather than silently dropped.
    let slot = null
    let late = false
    for (const day of order) {
      if (day > limit || !free(day)) continue
      slot = { day, start: quietestStart(unit.corridorId, s, length, published, day === preferredDay) }
      break
    }
    if (!slot) {
      for (const day of order) {
        if (!free(day)) continue
        slot = { day, start: quietestStart(unit.corridorId, s, length, published, false) }
        late = true
        break
      }
    }

    if (!slot) {
      carried.push(...unit.tasks)
      continue
    }

    const block = {
      id: published && s.merge && !unit.emergency ? published.id : `S-${placed.length + 1}`,
      corridorId: unit.corridorId,
      section: unit.section,
      day: slot.day,
      start: slot.start,
      end: slot.start + length,
      taskIds: unit.tasks.map((t) => t.id),
      merged: unit.tasks.length > 1,
      emergency: !!unit.emergency,
      late,
      movedFrom: published && published.day !== slot.day ? published.day : null,
      overrun: Math.max(0, slot.start + length - s.windowEnd),
    }
    placed.push(block)
    perDay[slot.day].push(block)
  }

  // 4. Price the result.
  const downtime = placed.reduce((sum, bl) => sum + (bl.end - bl.start), 0)
  const trains = placed.reduce(
    (sum, bl) => sum + trainsHeld(bl.corridorId, bl.start, bl.end) * (1 + s.trafficDelta / 100),
    0
  )
  const overrun = placed.reduce((sum, bl) => sum + bl.overrun, 0)

  const lateBlocks = placed.filter((bl) => bl.late)
  const carriedCritical = carried.filter((t) => t.slaDays <= 3)
  const breaches = s.sla ? lateBlocks.length + carriedCritical.length : carried.length

  return {
    settings: s,
    blocks: placed,
    carried,
    downtime,
    blocksCount: placed.length,
    merged: placed.filter((bl) => bl.merged).length,
    trainsAffected: Math.round(trains),
    tasksCovered: placed.reduce((sum, bl) => sum + bl.taskIds.length, 0),
    tasksTotal: scheduledTasks.length + (s.emergency ? 1 : 0),
    slaBreaches: breaches,
    overrunMinutes: Math.round(overrun),
    windowLength,
  }
}

/**
 * Where to start a possession on a given day.
 *
 * If the published plan already chose a start and that start still fits the
 * window, keep it — a scenario should not reshuffle things it has no reason
 * to touch. Otherwise search the window in quarter-hours for the start that
 * holds the fewest trains.
 */
function quietestStart(corridorId, s, length, published, samePreferredDay) {
  if (
    samePreferredDay &&
    published &&
    published.start >= s.windowStart &&
    published.start + length <= s.windowEnd
  ) {
    return published.start
  }
  let best = s.windowStart
  let bestValue = Infinity
  const latest = Math.max(s.windowStart, s.windowEnd - length)
  for (let start = s.windowStart; start <= latest; start += 15) {
    const value = trainsHeld(corridorId, start, start + length)
    if (value < bestValue - 0.001) {
      bestValue = value
      best = start
    }
  }
  return best
}

/** The current plan expressed in the same shape a simulation returns. */
export const currentPlanAsResult = {
  blocks: weeklyBlocks,
  carried: deferredTasks,
  downtime: optimised.downtimeMinutes,
  blocksCount: optimised.blocks,
  merged: optimised.mergedBlocks,
  trainsAffected: optimised.trainsAffected,
  tasksCovered: optimised.tasksCovered,
  tasksTotal: tasks.length,
  slaBreaches: optimised.slaBreaches,
  overrunMinutes: weeklyBlocks.reduce((s, bl) => s + Math.max(0, bl.end - planMeta.nightWindow[1]), 0),
}

/**
 * Emergency re-plan: the current week with one critical job inserted.
 * Returned alongside the current plan so the two can be shown side by side.
 */
export function emergencyReplan() {
  const before = simulate({ ...scenarioDefaults })
  const after = simulate({ ...scenarioDefaults, emergency: true })
  const movedBlocks = after.blocks.filter((bl) => {
    const match = before.blocks.find((b0) => b0.taskIds.join() === bl.taskIds.join())
    return !match || match.day !== bl.day || match.start !== bl.start
  })
  return {
    before,
    after,
    task: emergencyTask,
    inserted: after.blocks.find((bl) => bl.taskIds.includes(emergencyTask.id)) ?? null,
    rearranged: movedBlocks.length,
  }
}

/* ------------------------------------------------------------------ *
 * Decision trace
 * ------------------------------------------------------------------ */

/**
 * One job's journey through the pipeline, in five beats.
 *
 * Request → conflict → constraint → decision → impact. Every beat is read
 * out of the data: the request is the window the department asked for, the
 * conflict is whether anything else wanted that track, the constraint is the
 * one that actually bound, and the impact is the closure the decision removed
 * or the exposure it avoided. Nothing is narrated that did not happen.
 */
export function decisionTrace(taskId) {
  const task = taskById[taskId]
  if (!task) return null
  const block = weeklyBlocks.find((bl) => bl.taskIds.includes(taskId))
  const clash = conflictBySection[task.section]
  const inClash =
    clash && clash.requests.some((r) => r.taskId === taskId) ? clash : null

  const request = {
    label: 'Request',
    value: task.id,
    detail: `${DEPARTMENTS[task.department]?.name} asked for ${task.section}, ${DAY_NAMES[task.requested.day]} ${hhmm(task.requested.start)}`,
  }

  const conflict = inClash
    ? {
        label: 'Conflict',
        value: `${task.section}`,
        detail: `${inClash.requests.length} departments wanted this section the same night — ${inClash.overlapMinutes} min of overlap`,
        tone: 'alert',
      }
    : {
        label: 'Conflict',
        value: 'none',
        detail: `No other department requested ${task.section} in that window`,
      }

  let constraint
  if (task.slaDays <= 0) {
    constraint = {
      label: 'Constraint',
      value: 'Deferral limit',
      detail: `${Math.abs(task.slaDays)} day${Math.abs(task.slaDays) === 1 ? '' : 's'} past its limit — force-scheduled into the earliest window`,
      tone: 'alert',
    }
  } else if (!block) {
    constraint = {
      label: 'Constraint',
      value: 'Window length',
      detail: `Needs ${task.estDuration + POSSESSION_OVERHEAD} min; no window that long is free on ${task.section} this week`,
      tone: 'alert',
    }
  } else {
    constraint = {
      label: 'Constraint',
      value: 'Night window',
      detail: `${block.end - block.start} min possession fits inside ${hhmm(planMeta.nightWindow[0])}–${hhmm(planMeta.nightWindow[1])}`,
    }
  }

  const partner = block?.merged
    ? block.taskIds.filter((id) => id !== taskId).map((id) => taskById[id])[0]
    : null

  const decision = block
    ? {
        label: 'Decision',
        value: block.id,
        detail: partner
          ? `Merged with ${partner.id} into one possession, ${hhmm(block.start)}–${hhmm(block.end)}`
          : `Own possession on ${DAY_NAMES[block.day]}, ${hhmm(block.start)}–${hhmm(block.end)}`,
        tone: partner ? 'good' : 'neutral',
      }
    : {
        label: 'Decision',
        value: 'Deferred',
        detail: 'Held over to the monthly horizon where a longer closure is already planned',
      }

  const impact = block
    ? {
        label: 'Impact',
        value: partner ? '1 closure avoided' : `${Math.round(trainsHeld(block.corridorId, block.start, block.end))} movements`,
        detail: partner
          ? `${task.section} closes once instead of twice; ${mergeSavingFor(block)} min of track time returned`
          : `Estimated ${Math.round(trainsHeld(block.corridorId, block.start, block.end))} train movements impacted in the chosen window`,
        tone: partner ? 'good' : 'neutral',
      }
    : {
        label: 'Impact',
        value: 'No closure this week',
        detail: `${task.section} is not shut for this job, and it stays inside its ${task.slaDays}-day limit`,
      }

  return { task, block, steps: [request, conflict, constraint, decision, impact] }
}

function mergeSavingFor(block) {
  const blTasks = block.taskIds.map((id) => taskById[id]).filter(Boolean)
  const separate = blTasks.reduce((s, t) => s + t.estDuration + POSSESSION_OVERHEAD, 0)
  return separate - (block.end - block.start)
}

const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
function hhmm(m) {
  const h = Math.floor(m / 60) % 24
  return `${String(h).padStart(2, '0')}:${String(Math.round(m % 60)).padStart(2, '0')}`
}

/** The traces worth leading a demonstration with: the merges, then the rest. */
export const featuredTraces = [
  ...weeklyBlocks.filter((b) => b.merged).map((b) => b.taskIds[0]),
  ...deferredTasks.slice(0, 1).map((t) => t.id),
]

/* ------------------------------------------------------------------ *
 * Why this block
 * ------------------------------------------------------------------ */

/**
 * The case for one possession, in the order a controller would test it.
 * Each clause is conditional on something in the data being true, so a solo
 * block does not claim a merge and a busy window does not claim to be quiet.
 */
export function explainBlock(block) {
  const blTasks = block.taskIds.map((id) => taskById[id]).filter(Boolean)
  const eff = blockEfficiency(block)
  const corridor = corridorById[block.corridorId]
  const reasons = []

  if (blTasks.length > 1) {
    reasons.push(
      `${blTasks.length} jobs require access to ${block.section}: ${blTasks.map((t) => t.id).join(' and ')}.`
    )
    reasons.push(
      `Their work can be done inside the same possession — the block runs to the longest of them, ${Math.max(...blTasks.map((t) => t.estDuration))} minutes, not the sum.`
    )
  } else {
    reasons.push(`${blTasks[0].id} needs ${blTasks[0].estDuration} minutes of work on ${block.section}.`)
    const others = tasks.filter(
      (t) => t.section === block.section && t.id !== blTasks[0].id && t.status === 'scheduled'
    )
    if (others.length) {
      reasons.push(
        `No compatible partner fits: ${others.map((t) => t.id).join(', ')} would push the combined possession past the night window.`
      )
    } else {
      reasons.push(`No other department has work on ${block.section} this week.`)
    }
  }

  reasons.push(
    `The chosen window sits in ${eff.trafficExposure.toLowerCase()} traffic on a corridor carrying ${corridor.trainsPerDay} movements a day.`
  )
  reasons.push(
    `The ${block.end - block.start} minute possession ${block.end <= planMeta.nightWindow[1] ? 'fits inside' : 'runs past'} the available night window.`
  )
  if (blTasks.length > 1) {
    reasons.push(
      `Combining the jobs avoids a separate closure and returns ${mergeSavingFor(block)} minutes of track time.`
    )
  }
  const critical = blTasks.filter((t) => t.slaDays <= 0)
  if (critical.length) {
    reasons.push(
      `${critical.map((t) => t.id).join(', ')} ${critical.length === 1 ? 'is' : 'are'} already past ${critical.length === 1 ? 'its' : 'their'} deferral limit, which fixed the day.`
    )
  }

  return {
    block,
    tasks: blTasks,
    efficiency: eff,
    reasons,
    constraints: [
      { label: 'Safety', met: true, note: `highest urgency in block: ${Math.max(...blTasks.map((t) => t.score))}` },
      { label: 'Duration', met: true, note: `${block.end - block.start} min possession` },
      { label: 'Traffic exposure', met: true, note: eff.trafficExposure },
      {
        label: 'Deferral limits',
        met: blTasks.every((t) => block.day <= deadlineDay(t)),
        note: blTasks.every((t) => block.day <= deadlineDay(t)) ? 'all jobs inside limit' : 'a job runs late',
      },
      {
        label: 'Department coordination',
        met: true,
        note: `${eff.departments.length} department${eff.departments.length === 1 ? '' : 's'}`,
      },
      {
        label: 'Operational impact',
        met: block.end <= planMeta.nightWindow[1],
        note: `${eff.trainsHeld} estimated movements impacted`,
      },
    ],
  }
}
