export const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

/** Minutes past midnight -> 24h clock, the way a control office writes it. */
export function clock(mins) {
  const h = Math.floor(mins / 60) % 24
  const m = Math.round(mins % 60)
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

export function duration(mins) {
  const h = Math.floor(mins / 60)
  const m = Math.round(mins % 60)
  if (h === 0) return `${m}m`
  if (m === 0) return `${h}h`
  return `${h}h ${m}m`
}

export function hours(mins, digits = 1) {
  return (mins / 60).toFixed(digits)
}

export function compact(n) {
  if (Math.abs(n) >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

export function pct(n, digits = 0) {
  return `${n > 0 ? '' : ''}${n.toFixed(digits)}%`
}

export function relativeDay(offset) {
  if (offset === 0) return 'today'
  if (offset === 1) return 'tomorrow'
  return `in ${offset} days`
}
