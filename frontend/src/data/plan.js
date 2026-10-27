/**
 * The optimiser's output for the current planning cycle.
 *
 * Only the decisions are stored here — which jobs share a closure, on which
 * section, starting when. Every duration, end time and headline number is
 * derived from that plus the task list, so the plan can never drift out of
 * step with the work it schedules. See lib/possession.js for the arithmetic
 * and lib/optimizer.js for everything computed on top of it.
 *
 * A block can carry jobs from more than one department. That merge is the
 * whole point of the system, so `merged` is a first-class state in the UI.
 */

import { taskById } from './tasks'
import { possessionMinutes } from '@/lib/possession'

const b = (id, corridorId, section, day, start, taskIds, reasonCodes, status = 'proposed') => {
  const blockTasks = taskIds.map((t) => taskById[t]).filter(Boolean)
  return {
    id,
    corridorId,
    section,
    day,
    start,
    end: start + possessionMinutes(blockTasks),
    taskIds,
    reasonCodes,
    status,
    merged: taskIds.length > 1,
  }
}

/**
 * Sixteen blocks covering nineteen jobs. Three of them are shared: the rail
 * flaw and the point machine on DER–KRJ, the OHE and curve work on BVI–BSR,
 * and the ballast and track-circuit work on BSR–PLG.
 */
export const weeklyBlocks = [
  b('B-101', 'C-GZB-ALJN', 'DER–KRJ', 0, 60, ['TMS-4521', 'SMMS-2210'], [
    'SLA_FORCED',
    'MERGED_CROSS_DEPT',
    'LOW_TRAFFIC_WINDOW',
  ]),
  b('B-102', 'C-GZB-ALJN', 'DER–KRJ', 2, 135, ['TDMS-1177'], [
    'CORRIDOR_CONFLICT',
    'LOW_TRAFFIC_WINDOW',
  ]),
  b('B-103', 'C-NDLS-GZB', 'SHDM–GZB', 0, 120, ['TDMS-1203'], [
    'SLA_FORCED',
    'LOW_TRAFFIC_WINDOW',
  ]),
  b('B-104', 'C-NDLS-GZB', 'SHDM–GZB', 1, 120, ['TMS-4488'], [
    'CORRIDOR_CONFLICT',
    'LOW_TRAFFIC_WINDOW',
  ]),
  b('B-105', 'C-NDLS-GZB', 'SHDM–GZB', 3, 120, ['SMMS-2044'], [
    'CORRIDOR_CONFLICT',
    'GOODS_PEAK_AVOIDED',
  ]),
  b('B-106', 'C-BCT-BSR', 'BCT–BVI', 0, 120, ['SMMS-2401'], [
    'SLA_FORCED',
    'GOODS_PEAK_AVOIDED',
  ]),
  b('B-107', 'C-BSR-ST', 'BSR–PLG', 0, 180, ['TDMS-1444'], ['SLA_FORCED', 'LOW_TRAFFIC_WINDOW']),
  b('B-108', 'C-BSR-ST', 'BSR–PLG', 6, 0, ['TMS-4710', 'SMMS-2455'], [
    'MERGED_CROSS_DEPT',
    'CREW_LIMIT',
    'LOW_TRAFFIC_WINDOW',
  ]),
  b('B-109', 'C-ALJN-CNB', 'TDL–ETW', 1, 150, ['TMS-4602'], ['LOW_TRAFFIC_WINDOW']),
  b('B-110', 'C-ALJN-CNB', 'TDL–ETW', 3, 240, ['SMMS-2318'], ['DEFERRED_LOW_IMPACT']),
  b('B-111', 'C-ALJN-CNB', 'ETW–CNB', 2, 165, ['TDMS-1290'], ['LOW_TRAFFIC_WINDOW']),
  b('B-112', 'C-ALJN-CNB', 'ETW–CNB', 4, 195, ['SMMS-2560'], ['DEFERRED_LOW_IMPACT']),
  b('B-113', 'C-BCT-BSR', 'BVI–BSR', 2, 45, ['TDMS-1322', 'TMS-4801'], [
    'MERGED_CROSS_DEPT',
    'GOODS_PEAK_AVOIDED',
  ]),
  b('B-114', 'C-BSR-ST', 'BL–ST', 3, 180, ['TDMS-1388'], ['LOW_TRAFFIC_WINDOW']),
  b('B-115', 'C-GZB-ALJN', 'KRJ–ALJN', 1, 165, ['TDMS-1401'], [
    'SLA_FORCED',
    'LOW_TRAFFIC_WINDOW',
  ]),
  b('B-116', 'C-GZB-ALJN', 'KRJ–ALJN', 5, 225, ['SMMS-2502'], ['CREW_LIMIT']),
]

export const planMeta = {
  planId: 'PLAN-2026-W38',
  horizon: 'weekly',
  window: '14 – 20 Sep 2026',
  generatedAt: '15 Sep 2026, 04:38',
  solverStatus: 'OPTIMAL',
  solveSeconds: 6.4,
  division: 'Northern & Western — 5 corridors',
  nightWindow: [0, 330],
}

/**
 * Weekly trend. Demonstration figures for the preceding cycles: this
 * prototype only solves week 38, so earlier weeks are illustrative history
 * rather than derived output, and the UI labels them as such.
 */
export const availabilityTrend = [
  { week: 'W31', coordinated: 92.1, uncoordinated: 91.4 },
  { week: 'W32', coordinated: 93.0, uncoordinated: 91.1 },
  { week: 'W33', coordinated: 93.8, uncoordinated: 91.9 },
  { week: 'W34', coordinated: 94.4, uncoordinated: 91.2 },
  { week: 'W35', coordinated: 95.1, uncoordinated: 92.0 },
  { week: 'W36', coordinated: 95.6, uncoordinated: 91.6 },
  { week: 'W37', coordinated: 96.0, uncoordinated: 91.7 },
  { week: 'W38', coordinated: 96.4, uncoordinated: 91.8 },
]

export const monthlyPlan = [
  {
    week: 'Week 38',
    window: '14 – 20 Sep',
    blocks: 16,
    downtime: 2735,
    merged: 3,
    focus: 'Rail flaw clearance on GZB–ALJN, feeder termination at Vasai',
    status: 'in review',
  },
  {
    week: 'Week 39',
    window: '21 – 27 Sep',
    blocks: 14,
    downtime: 2380,
    merged: 4,
    focus: 'Suburban points renewal, OHE dropper runs on ETW–CNB',
    status: 'draft',
  },
  {
    week: 'Week 40',
    window: '28 Sep – 4 Oct',
    blocks: 12,
    downtime: 2050,
    merged: 2,
    focus: 'Ballast screening BSR–PLG, relay room works',
    status: 'draft',
  },
  {
    week: 'Week 41',
    window: '5 – 11 Oct',
    blocks: 15,
    downtime: 2610,
    merged: 5,
    focus: 'Pre-festival consolidation block across BCT–BSR',
    status: 'draft',
  },
]
