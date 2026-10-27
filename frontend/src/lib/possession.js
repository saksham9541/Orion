/**
 * Possession arithmetic — the one place block durations are defined.
 *
 * A block is longer than the work inside it. Before a gang can touch the
 * track the section has to be protected and the caution order issued, and
 * afterwards the work has to be tested and the line handed back before
 * traffic resumes. That fixed cost is paid once per possession, which is
 * precisely why merging two jobs into one closure saves time: the second
 * job's protection and handback disappear, and the two gangs work in
 * parallel under the same block.
 *
 * Every downtime figure in the product resolves to these two functions.
 */

/** Protection + caution order + testing + handback, in minutes. */
export const POSSESSION_OVERHEAD = 45

/**
 * How long a closure lasts if it carries this set of jobs.
 *
 * Jobs sharing a block work concurrently, so the block is governed by the
 * longest of them — not the sum. One job on its own is just itself.
 */
export function possessionMinutes(tasks) {
  if (!tasks.length) return 0
  const longest = Math.max(...tasks.map((t) => t.estDuration))
  return longest + POSSESSION_OVERHEAD
}

/** Minutes saved by putting `tasks` in one block rather than one block each. */
export function mergeSaving(tasks) {
  if (tasks.length < 2) return 0
  const separate = tasks.reduce((sum, t) => sum + t.estDuration + POSSESSION_OVERHEAD, 0)
  return separate - possessionMinutes(tasks)
}

/** Do two windows on the same section overlap at all? */
export function overlaps(a, b) {
  return a.day === b.day && a.start < b.end && b.start < a.end
}
