import { useMemo } from 'react'
import { motion } from 'framer-motion'
import { DataTag } from '@/components/common/StatusChip'
import { SCENARIOS, currentPlanAsResult, simulate } from '@/lib/optimizer'
import { duration } from '@/lib/format'

/**
 * Every preset re-planned, side by side.
 *
 * The figures are produced by running the same scheduling logic five times
 * with different constraints — not read from a table of expected answers. At
 * the default settings the Normal week column reproduces the published plan
 * exactly, which is the check that says the simulator and the plan agree.
 */
const ROWS = [
  { key: 'blocksCount', label: 'Blocks', format: (v) => v, better: 'lower' },
  { key: 'downtime', label: 'Downtime', format: (v) => `${v} min`, better: 'lower' },
  { key: 'trainsAffected', label: 'Est. movements impacted', format: (v) => v, better: 'lower' },
  { key: 'slaBreaches', label: 'Past deferral limit', format: (v) => v, better: 'lower' },
  { key: 'merged', label: 'Shared blocks', format: (v) => v, better: 'higher' },
  {
    key: 'overrunMinutes',
    label: 'Overrun into service hours',
    format: (v) => (v ? duration(v) : '—'),
    better: 'lower',
  },
]

export default function ScenarioComparison({ current = null }) {
  const results = useMemo(
    () => SCENARIOS.map((s) => ({ scenario: s, result: simulate(s.settings) })),
    []
  )

  return (
    <section className="panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hair px-5 py-4 sm:px-6">
        <div>
          <h2 className="text-[15px] font-semibold">Compare scenarios</h2>
          <p className="mt-0.5 text-[12.5px] text-muted">
            The same {currentPlanAsResult.tasksCovered} jobs re-planned under each set of constraints.
          </p>
        </div>
        <DataTag kind="simulation" />
      </div>

      <div className="scrollbar-thin overflow-x-auto">
        <table className="w-full min-w-[640px] text-left">
          <thead>
            <tr className="border-b border-line bg-surface">
              <th className="px-5 py-3 text-[12px] font-normal text-faint">Outcome</th>
              {results.map(({ scenario }) => (
                <th
                  key={scenario.id}
                  className="px-4 py-3 text-[12.5px] font-medium"
                  scope="col"
                >
                  {scenario.name}
                  <span className="mt-0.5 block text-[11px] font-normal leading-snug text-faint">
                    {scenario.note}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row, i) => {
              const values = results.map(({ result }) => result[row.key])
              const best = row.better === 'lower' ? Math.min(...values) : Math.max(...values)
              const worst = row.better === 'lower' ? Math.max(...values) : Math.min(...values)
              return (
                <motion.tr
                  key={row.key}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05, duration: 0.35 }}
                  className="border-b border-hair/60 bg-surface/50 last:border-0"
                >
                  <th
                    scope="row"
                    className="px-5 py-3.5 text-[13.5px] font-normal text-muted"
                  >
                    {row.label}
                  </th>
                  {results.map(({ scenario, result }) => {
                    const v = result[row.key]
                    const isBest = v === best && best !== worst
                    const isWorst = v === worst && best !== worst
                    return (
                      <td
                        key={scenario.id}
                        className={`tnum px-4 py-3.5 font-mono text-[13.5px] ${
                          isBest ? 'text-ok' : isWorst ? 'text-warn' : ''
                        }`}
                      >
                        {row.format(v)}
                      </td>
                    )
                  })}
                </motion.tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <p className="border-t border-hair px-5 py-3.5 text-[12px] leading-relaxed text-faint sm:px-6">
        Green is the best column for that row, amber the worst. Nothing here is hard-coded: change
        the scheduling logic and every cell moves. Demonstration data throughout.
      </p>
    </section>
  )
}
