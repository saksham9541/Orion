import { motion } from 'framer-motion'
import { availabilityTrend } from '@/data/plan'
import { kpis } from '@/lib/optimizer'

// Same four hues HeroScene uses for its particle clusters (TMS, SMMS, TDMS,
// and the optimiser itself) — the side panels are meant to read as the
// globe's own legend, not a separate decoration.
const SOURCES = [
  { code: 'TMS', label: 'Engineering', color: '#F2A93B' },
  { code: 'SMMS', label: 'Signal & Telecom', color: '#4FC3A1' },
  { code: 'TDMS', label: 'Traction Distribution', color: '#8B9DFF' },
  { code: 'COA', label: 'Optimiser, resolved', color: '#5FD6E8' },
]

function buildSparkline(values, width, height, pad = 3) {
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const step = (width - pad * 2) / (values.length - 1)
  const points = values.map((v, i) => {
    const x = pad + i * step
    const y = pad + (1 - (v - min) / span) * (height - pad * 2)
    return [x, y]
  })
  const line = points.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const fill = `${line} L${points[points.length - 1][0].toFixed(1)},${height} L${points[0][0].toFixed(1)},${height} Z`
  return { line, fill }
}

const W = 220
const H = 72
const { line, fill } = buildSparkline(
  availabilityTrend.map((d) => d.coordinated),
  W,
  H
)

function Rail({ delay = 0 }) {
  return (
    <svg viewBox="0 0 220 40" width="100%" height="40" className="overflow-visible">
      <line x1="0" y1="11" x2="220" y2="11" stroke="#24384A" strokeWidth="2.5" />
      <line x1="0" y1="29" x2="220" y2="29" stroke="#24384A" strokeWidth="2.5" />
      {Array.from({ length: 12 }).map((_, i) => (
        <line
          key={i}
          x1={i * 19.5 + 3}
          y1="8"
          x2={i * 19.5 + 3}
          y2="32"
          stroke="#1B2A38"
          strokeWidth="3"
        />
      ))}
      <motion.circle
        r="4.4"
        fill="#5FD6E8"
        animate={{ cx: [0, 220], opacity: [0, 1, 1, 0] }}
        transition={{ duration: 3.4, repeat: Infinity, ease: 'linear', delay, times: [0, 0.08, 0.92, 1] }}
        cy="20"
      />
    </svg>
  )
}

const panelReveal = (side, delay, reduce) =>
  reduce
    ? { initial: { opacity: 1 }, animate: { opacity: 1 } }
    : {
        initial: { opacity: 0, x: side === 'left' ? -18 : 18 },
        animate: { opacity: 1, x: 0 },
        transition: { delay, duration: 0.8, ease: [0.16, 1, 0.3, 1] },
      }

/**
 * Fills the flanks either side of the centred title once the globe has
 * resolved — the four source systems feeding it on the left, this cycle's
 * headline results on the right. Wide screens only: on anything narrower
 * than xl there isn't room without crowding the title.
 */
export default function HeroSidePanels({ reduce = false, delay = 1.85 }) {
  return (
    <>
      <motion.div
        {...panelReveal('left', reduce ? 0 : delay, reduce)}
        className="pointer-events-none absolute left-6 top-1/2 hidden w-[270px] -translate-y-1/2 xl:block 2xl:left-14 2xl:w-[310px]"
      >
        <p className="font-mono text-[12px] tracking-[0.24em] text-faint">SOURCE SYSTEMS</p>
        <ul className="mt-5 space-y-4">
          {SOURCES.map((s, i) => (
            <motion.li
              key={s.code}
              initial={reduce ? false : { opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: reduce ? 0 : delay + 0.15 + i * 0.09, duration: 0.5 }}
              className="flex items-center gap-3"
            >
              <span
                className="lamp h-2.5 w-2.5 shrink-0 animate-blink rounded-full"
                style={{ background: s.color, color: s.color, animationDelay: `${i * 0.3}s` }}
              />
              <span className="font-mono text-[13px] text-muted">{s.code}</span>
              <span className="truncate text-[14.5px] text-ink/80">{s.label}</span>
            </motion.li>
          ))}
        </ul>
        <div className="mt-8 border-t border-hair pt-6">
          <p className="font-mono text-[12px] tracking-[0.24em] text-faint">CORRIDOR SYNC</p>
          <div className="mt-4">
            <Rail delay={reduce ? 0 : delay + 0.4} />
          </div>
        </div>
      </motion.div>

      <motion.div
        {...panelReveal('right', reduce ? 0 : delay + 0.1, reduce)}
        className="pointer-events-none absolute right-6 top-1/2 hidden w-[270px] -translate-y-1/2 xl:block 2xl:right-14 2xl:w-[310px]"
      >
        <p className="font-mono text-[12px] tracking-[0.24em] text-faint">PLAN-2026-W38</p>
        <div className="mt-5 space-y-6">
          <div>
            <p className="font-mono text-[40px] font-medium leading-none text-ink tnum">
              {kpis.assetAvailability}
              <span className="text-[16px] text-faint">%</span>
            </p>
            <p className="mt-2 text-[13.5px] text-muted">Night-window capacity still free</p>
          </div>
          <div>
            <p className="font-mono text-[40px] font-medium leading-none text-ink tnum">
              {((kpis.baselineDowntimeMinutes - kpis.downtimeMinutes) / 60).toFixed(1)}
              <span className="text-[16px] text-faint"> h</span>
            </p>
            <p className="mt-2 text-[13.5px] text-muted">Track time returned by coordination</p>
          </div>
        </div>
        <div className="mt-7 border-t border-hair pt-5">
          <p className="font-mono text-[12px] tracking-[0.24em] text-faint">8-WEEK TREND · DEMO</p>
          <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} className="mt-4 overflow-visible">
            <defs>
              <linearGradient id="heroSpark" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#4FC3A1" stopOpacity="0.35" />
                <stop offset="100%" stopColor="#4FC3A1" stopOpacity="0" />
              </linearGradient>
            </defs>
            <motion.path
              d={fill}
              fill="url(#heroSpark)"
              initial={reduce ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: reduce ? 0 : delay + 0.5, duration: 0.8 }}
            />
            <motion.path
              d={line}
              fill="none"
              stroke="#4FC3A1"
              strokeWidth="2.25"
              strokeLinecap="round"
              initial={reduce ? false : { pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ delay: reduce ? 0 : delay + 0.35, duration: 1.1, ease: [0.16, 1, 0.3, 1] }}
            />
          </svg>
        </div>
      </motion.div>
    </>
  )
}
