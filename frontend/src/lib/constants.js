export const DEPARTMENTS = {
  ENG: {
    id: 'ENG',
    name: 'Engineering',
    long: 'Permanent way & track',
    source: 'TMS',
    color: '#F2A93B',
    tw: 'eng',
  },
  SNT: {
    id: 'SNT',
    name: 'Signal & Telecom',
    long: 'Signalling and telecom assets',
    source: 'SMMS',
    color: '#4FC3A1',
    tw: 'snt',
  },
  TRD: {
    id: 'TRD',
    name: 'Traction Distribution',
    long: 'OHE and power supply',
    source: 'TDMS',
    color: '#8B9DFF',
    tw: 'trd',
  },
}

export const DEPT_LIST = Object.values(DEPARTMENTS)

export const URGENCY = {
  EMERGENCY: { label: 'Emergency', color: '#E5484D', min: 85 },
  HIGH: { label: 'High', color: '#F2A93B', min: 65 },
  MEDIUM: { label: 'Medium', color: '#4FC3A1', min: 40 },
  LOW: { label: 'Low', color: '#8FA3B5', min: 0 },
}

export function urgencyClass(score) {
  if (score >= URGENCY.EMERGENCY.min) return URGENCY.EMERGENCY
  if (score >= URGENCY.HIGH.min) return URGENCY.HIGH
  if (score >= URGENCY.MEDIUM.min) return URGENCY.MEDIUM
  return URGENCY.LOW
}

/**
 * Reason codes emitted by the optimiser when a constraint binds. Each one maps
 * to a sentence a section controller can read without knowing what CP-SAT is.
 */
export const REASON_CODES = {
  MERGED_CROSS_DEPT: {
    tone: 'good',
    text: 'Scheduled inside a block another department had already requested on this section.',
  },
  SLA_FORCED: {
    tone: 'alert',
    text: 'Past its deferral limit, so it was force-fitted into the next window regardless of cost.',
  },
  DEFERRED_LOW_IMPACT: {
    tone: 'neutral',
    text: 'Held back to a later window — low predicted consequence if it waits.',
  },
  LOW_TRAFFIC_WINDOW: {
    tone: 'good',
    text: 'Placed in the quietest window available on this section.',
  },
  CORRIDOR_CONFLICT: {
    tone: 'neutral',
    text: 'Moved off its preferred slot because the section was already closed for other work.',
  },
  GOODS_PEAK_AVOIDED: {
    tone: 'good',
    text: 'Shifted clear of a forecast goods-traffic peak.',
  },
  CREW_LIMIT: {
    tone: 'neutral',
    text: 'Limited by the number of gangs available on that shift.',
  },
}

export const HORIZONS = [
  { id: 'weekly', label: 'Weekly plan', note: 'Slot-level, 7 days' },
  { id: 'monthly', label: 'Monthly plan', note: 'Coarse, 4 weeks' },
]
