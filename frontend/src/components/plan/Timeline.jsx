import { useMemo } from 'react'
import { motion } from 'framer-motion'
import { corridors } from '@/data/corridors'
import { taskById } from '@/data/tasks'
import { DEPARTMENTS } from '@/lib/constants'
import { DAYS, clock, duration } from '@/lib/format'

/**
 * Corridor timeline. Rows are sections, the x axis is the seven days of the
 * planning week at hour resolution.
 *
 * Background shading is the section's traffic density, so a controller can see
 * at a glance whether a block sits in a quiet window or a busy one — the single
 * judgement they make most often.
 */
export default function Timeline({
  blocks,
  hourWidth = 9,
  selectedId,
  onSelect,
  deptFilter = null,
}) {
  const dayWidth = hourWidth * 24
  const totalWidth = dayWidth * 7

  const rows = useMemo(
    () =>
      corridors.flatMap((c) =>
        c.sections.map((section, i) => ({
          corridor: c,
          section,
          first: i === 0,
        }))
      ),
    []
  )

  const visible = useMemo(() => {
    if (!deptFilter) return blocks
    return blocks.filter((b) => b.taskIds.some((id) => taskById[id]?.department === deptFilter))
  }, [blocks, deptFilter])

  return (
    <div className="flex overflow-hidden rounded-panel border border-line bg-surface/50">
      {/* Section labels stay put while the timeline scrolls. */}
      <div className="w-[152px] shrink-0 border-r border-line bg-surface sm:w-[186px]">
        <div className="h-[46px] border-b border-hair px-4 py-3 text-[12px] text-faint">
          Corridor &amp; section
        </div>
        {rows.map((r) => (
          <div
            key={r.corridor.id + r.section}
            className={`h-[46px] px-4 ${r.first ? 'border-t border-line' : 'border-t border-hair/60'}`}
          >
            {r.first && (
              <p className="pt-1.5 text-[12px] font-medium leading-none text-ink">
                {r.corridor.name}
              </p>
            )}
            <p className={`font-mono text-[11.5px] text-muted ${r.first ? 'mt-1' : 'pt-3.5'}`}>
              {r.section}
            </p>
          </div>
        ))}
      </div>

      <div className="scrollbar-thin min-w-0 flex-1 overflow-x-auto">
        <div style={{ width: totalWidth, minWidth: '100%' }}>
          {/* Day header */}
          <div className="flex h-[46px] border-b border-hair">
            {DAYS.map((d, i) => (
              <div
                key={d}
                className="relative shrink-0 border-r border-hair/60 px-2 py-2"
                style={{ width: dayWidth }}
              >
                <p className="text-[12px] font-medium leading-none">{d}</p>
                <p className="mt-1 font-mono text-[11px] text-faint">{14 + i} Sep</p>
                {hourWidth >= 9 && (
                  <div className="absolute inset-x-0 bottom-0 flex">
                    {[0, 6, 12, 18].map((h) => (
                      <span
                        key={h}
                        className="font-mono text-[9.5px] text-faint/70"
                        style={{ width: hourWidth * 6 }}
                      >
                        {String(h).padStart(2, '0')}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Rows */}
          {rows.map((r) => {
            const rowBlocks = visible.filter(
              (b) => b.corridorId === r.corridor.id && b.section === r.section
            )
            return (
              <div
                key={r.corridor.id + r.section}
                className={`relative h-[46px] ${
                  r.first ? 'border-t border-line' : 'border-t border-hair/60'
                }`}
              >
                {/* Traffic density behind each day */}
                <div className="absolute inset-0 flex">
                  {DAYS.map((d, dayIndex) => (
                    <div
                      key={d}
                      className="flex shrink-0 border-r border-hair/50"
                      style={{ width: dayWidth }}
                    >
                      {r.corridor.trafficProfile.map((v, bucket) => (
                        <span
                          key={bucket}
                          className="h-full"
                          style={{
                            width: hourWidth * 2,
                            background: `rgba(143,163,181,${(v / 100) * 0.09})`,
                          }}
                        />
                      ))}
                    </div>
                  ))}
                </div>

                {rowBlocks.map((b) => (
                  <BlockBar
                    key={b.id}
                    block={b}
                    hourWidth={hourWidth}
                    selected={selectedId === b.id}
                    onSelect={onSelect}
                  />
                ))}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function BlockBar({ block, hourWidth, selected, onSelect }) {
  const left = (block.day * 24 + block.start / 60) * hourWidth
  const width = Math.max(16, ((block.end - block.start) / 60) * hourWidth)

  const depts = [...new Set(block.taskIds.map((id) => taskById[id]?.department).filter(Boolean))]
  const colors = depts.map((d) => DEPARTMENTS[d].color)

  const background =
    colors.length > 1
      ? `linear-gradient(100deg, ${colors.map((c, i) => `${c}33 ${(i / colors.length) * 100}%`).join(', ')})`
      : `${colors[0]}30`

  const label = block.merged ? `${depts.length} depts` : depts[0]

  return (
    <motion.button
      layout
      onClick={() => onSelect(block)}
      className={`absolute top-[7px] flex h-[32px] items-center overflow-hidden rounded-[3px] px-1.5 text-left transition-shadow ${
        selected ? 'ring-2 ring-merge ring-offset-1 ring-offset-base' : ''
      }`}
      style={{
        left,
        width,
        background,
        borderLeft: `2px solid ${colors[0]}`,
        boxShadow: block.merged ? `inset -2px 0 0 0 ${colors[colors.length - 1]}` : undefined,
      }}
      title={`${block.id} · ${clock(block.start)}–${clock(block.end)} · ${duration(
        block.end - block.start
      )}`}
    >
      <span className="truncate font-mono text-[10.5px] leading-none text-ink/90">
        {width > 52 ? label : ''}
      </span>
      {block.status === 'approved' && (
        <span className="ml-auto h-1.5 w-1.5 shrink-0 rounded-full bg-ok" />
      )}
    </motion.button>
  )
}
