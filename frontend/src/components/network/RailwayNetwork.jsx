import { motion } from 'framer-motion'
import { runs, VIEWBOX } from '@/data/network'
import { NODE_STATES } from '@/lib/optimizer'

/**
 * The division as a signalling diagram.
 *
 * Every section between two stations is drawn as a length of track and
 * coloured by what is happening on it at the simulated moment. A station node
 * takes the more serious of the two sections either side of it, the way a
 * panel indication would. Clicking a section opens it.
 *
 * Nothing here is a live position. The states come from the plan the
 * optimiser produced, evaluated at whatever time the slider is showing.
 */

const SEVERITY = ['available', 'planned', 'conflict', 'active', 'critical']

function worseOf(a, b) {
  return SEVERITY.indexOf(a) >= SEVERITY.indexOf(b) ? a : b
}

export default function RailwayNetwork({
  sectionStates,
  selected,
  onSelect,
  compact = false,
}) {
  return (
    <div className="scrollbar-thin overflow-x-auto">
      <svg
        viewBox={`0 0 ${VIEWBOX.width} ${VIEWBOX.height}`}
        className="w-full"
        style={{ minWidth: compact ? 720 : 860, height: compact ? 210 : 300 }}
        role="img"
        aria-label="Railway network schematic. Select a section to see its detail."
      >
        <defs>
          <filter id="lampGlow" x="-120%" y="-120%" width="340%" height="340%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {runs.map((run) => (
          <g key={run.id}>
            <text
              x={12}
              y={run.y - 44}
              className="fill-[rgb(var(--c-faint))] font-mono"
              style={{ fontSize: 12, letterSpacing: '0.16em' }}
            >
              {run.label.toUpperCase()}
            </text>
            <text
              x={12}
              y={run.y - 26}
              className="fill-[rgb(var(--c-muted))]"
              style={{ fontSize: 12.5 }}
            >
              {run.long}
            </text>

            {/* Sections */}
            {run.links.map((link) => {
              const info = sectionStates[link.section]
              const state = info?.state ?? 'available'
              const meta = NODE_STATES[state]
              const isSelected = selected === link.section
              const busy = state !== 'available'
              return (
                <g
                  key={link.section}
                  onClick={() => onSelect?.(link.section)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      onSelect?.(link.section)
                    }
                  }}
                  tabIndex={0}
                  role="button"
                  aria-label={`Section ${link.section}, ${meta.label}`}
                  className="cursor-pointer outline-none focus-visible:opacity-90"
                >
                  {/* Generous invisible hit area */}
                  <rect
                    x={link.from.x}
                    y={link.from.y - 18}
                    width={link.to.x - link.from.x}
                    height={36}
                    fill="transparent"
                  />
                  {/* Sleepers under the rail, so an open section still reads as track */}
                  <line
                    x1={link.from.x + 6}
                    y1={link.from.y}
                    x2={link.to.x - 6}
                    y2={link.to.y}
                    stroke="rgb(var(--c-line))"
                    strokeWidth={9}
                    strokeLinecap="round"
                    opacity={0.55}
                  />
                  <motion.line
                    x1={link.from.x + 6}
                    y1={link.from.y}
                    x2={link.to.x - 6}
                    y2={link.to.y}
                    stroke={meta.color}
                    strokeWidth={isSelected ? 6 : 4}
                    strokeLinecap="round"
                    strokeDasharray={state === 'planned' ? '9 7' : state === 'conflict' ? '3 5' : undefined}
                    animate={{ opacity: busy ? 1 : 0.32 }}
                    transition={{ duration: 0.35 }}
                  />
                  {isSelected && (
                    <line
                      x1={link.from.x + 6}
                      y1={link.from.y + 13}
                      x2={link.to.x - 6}
                      y2={link.to.y + 13}
                      stroke="rgb(var(--c-merge))"
                      strokeWidth={1.5}
                    />
                  )}
                  {/* Section name, only where there is room */}
                  <text
                    x={link.midX}
                    y={link.midY - 14}
                    textAnchor="middle"
                    className={isSelected ? 'fill-[rgb(var(--c-ink))]' : 'fill-[rgb(var(--c-faint))]'}
                    style={{ fontSize: 10.5, fontFamily: 'IBM Plex Mono, monospace' }}
                  >
                    {busy ? link.section : ''}
                  </text>
                  {/* Working marker, so the state is legible without colour */}
                  {busy && (
                    <text
                      x={link.midX}
                      y={link.midY + 24}
                      textAnchor="middle"
                      fill={meta.color}
                      style={{ fontSize: 11 }}
                    >
                      {meta.icon}
                    </text>
                  )}
                </g>
              )
            })}

            {/* Stations */}
            {run.nodes.map((node, i) => {
              const left = run.links[i - 1]
              const right = run.links[i]
              const leftState = left ? sectionStates[left.section]?.state ?? 'available' : 'available'
              const rightState = right ? sectionStates[right.section]?.state ?? 'available' : 'available'
              const state = worseOf(leftState, rightState)
              const meta = NODE_STATES[state]
              const busy = state !== 'available'
              return (
                <g key={node.code}>
                  {busy && (
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={11}
                      fill={meta.color}
                      opacity={0.16}
                      filter="url(#lampGlow)"
                    />
                  )}
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r={6}
                    fill="rgb(var(--c-base))"
                    stroke={busy ? meta.color : 'rgb(var(--c-line))'}
                    strokeWidth={2.2}
                  />
                  <text
                    x={node.x}
                    y={node.y + 30}
                    textAnchor="middle"
                    className="fill-[rgb(var(--c-ink))]"
                    style={{ fontSize: 12, fontFamily: 'IBM Plex Mono, monospace', fontWeight: 500 }}
                  >
                    {node.code}
                  </text>
                  <text
                    x={node.x}
                    y={node.y + 44}
                    textAnchor="middle"
                    className="fill-[rgb(var(--c-faint))]"
                    style={{ fontSize: 10 }}
                  >
                    {node.name}
                  </text>
                </g>
              )
            })}
          </g>
        ))}
      </svg>
    </div>
  )
}
