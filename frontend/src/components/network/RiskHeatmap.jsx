import { useMemo, useState } from 'react'
import { riskGrid } from '@/lib/optimizer'
import { DAYS, clock } from '@/lib/format'
import { DataTag } from '@/components/common/StatusChip'

/**
 * Where a closure would hurt most: corridor against hour of day.
 *
 * A cell is dark when a busy hour on that corridor is also an hour it is shut.
 * Traffic alone is not risk — a corridor at its morning peak with no
 * possession on it is simply working. Risk is the product of the two, which
 * is why the grid is nearly empty outside the night window, and why that is
 * the right answer rather than a rendering fault.
 */
const BANDS = [
  { min: 0.75, label: 'Severe', block: '█' },
  { min: 0.45, label: 'High', block: '▓' },
  { min: 0.18, label: 'Moderate', block: '▒' },
  { min: 0.001, label: 'Low', block: '░' },
  { min: -1, label: 'None', block: '·' },
]

function band(level) {
  return BANDS.find((b) => level >= b.min) ?? BANDS[BANDS.length - 1]
}

export default function RiskHeatmap({ day = null }) {
  const [hover, setHover] = useState(null)
  const rows = useMemo(() => riskGrid(day), [day])

  return (
    <section className="panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hair px-5 py-4 sm:px-6">
        <div>
          <h2 className="text-[15px] font-semibold">Network risk</h2>
          <p className="mt-0.5 text-[12.5px] text-muted">
            Traffic exposure multiplied by closure, for every corridor hour{' '}
            {day === null ? 'across the week' : `on ${DAYS[day]}`}.
          </p>
        </div>
        <DataTag kind="simulation" />
      </div>

      <div className="scrollbar-thin overflow-x-auto px-5 py-4 sm:px-6">
        <table className="w-full min-w-[720px] border-separate border-spacing-[3px]">
          <caption className="sr-only">
            Risk by corridor and hour of day, on a five-step scale from none to severe.
          </caption>
          <thead>
            <tr>
              <th className="w-[130px] text-left text-[11.5px] font-normal text-faint">Corridor</th>
              {rows[0].cells.map((c) => (
                <th
                  key={c.hour}
                  className="tnum font-mono text-[10px] font-normal text-faint"
                  scope="col"
                >
                  {c.hour % 3 === 0 ? String(c.hour).padStart(2, '0') : ''}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.corridor.id}>
                <th
                  scope="row"
                  className="whitespace-nowrap text-left font-mono text-[11.5px] font-normal text-muted"
                >
                  {row.corridor.name}
                </th>
                {row.cells.map((cell) => {
                  const b = band(cell.level)
                  const key = `${row.corridor.id}-${cell.hour}`
                  const active = hover?.key === key
                  return (
                    <td key={cell.hour} className="p-0">
                      <button
                        onMouseEnter={() => setHover({ key, row, cell, band: b })}
                        onMouseLeave={() => setHover(null)}
                        onFocus={() => setHover({ key, row, cell, band: b })}
                        onBlur={() => setHover(null)}
                        aria-label={`${row.corridor.name} at ${String(cell.hour).padStart(2, '0')}:00, risk ${b.label}`}
                        className={`flex h-7 w-full items-center justify-center rounded-[2px] border text-[9px] transition-transform ${
                          active ? 'scale-110 border-merge' : 'border-transparent'
                        }`}
                        style={{
                          background:
                            cell.level > 0.001
                              ? `rgb(var(--c-danger) / ${(0.12 + cell.level * 0.72).toFixed(3)})`
                              : `rgb(var(--c-line) / 0.35)`,
                          color: cell.level > 0.5 ? 'rgb(var(--c-ink))' : 'rgb(var(--c-faint))',
                        }}
                      >
                        {b.block}
                      </button>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-4 border-t border-hair px-5 py-3.5 sm:px-6">
        <ul className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[11.5px] text-muted">
          {BANDS.slice().reverse().map((b) => (
            <li key={b.label} className="flex items-center gap-1.5">
              <span className="font-mono text-faint">{b.block}</span>
              {b.label}
            </li>
          ))}
        </ul>
        <p className="min-h-[18px] text-[12.5px] text-muted" role="status">
          {hover ? (
            <>
              <span className="font-mono">{hover.row.corridor.name}</span> ·{' '}
              {clock(hover.cell.hour * 60)}–{clock((hover.cell.hour + 1) * 60)} ·{' '}
              <span className="text-ink">{hover.band.label}</span> · traffic{' '}
              {Math.round(hover.cell.intensity * 100)}% ·{' '}
              {hover.cell.closedMinutes > 0
                ? `${hover.cell.closedMinutes} min closed`
                : 'no possession'}
            </>
          ) : (
            'Hover a cell for the hour behind it.'
          )}
        </p>
      </div>
    </section>
  )
}
