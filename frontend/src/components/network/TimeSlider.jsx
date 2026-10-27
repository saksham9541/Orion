import { useEffect, useRef } from 'react'
import { Pause, Play, SkipBack } from 'lucide-react'
import { weeklyBlocks } from '@/data/plan'
import { DAYS, clock } from '@/lib/format'

const WEEK_MINUTES = 7 * 24 * 60

/**
 * The week on one axis.
 *
 * Dragging moves simulated time; everything downstream — section states,
 * active blocks, estimated operational impact — is recomputed from the plan at that
 * moment. The ticks below the rail are the actual blocks, so the operator
 * can see where the interesting moments are before scrubbing to them.
 *
 * This is a replay of a plan, not railway telemetry.
 */
export default function TimeSlider({ minutes, onChange, playing, onTogglePlay }) {
  const raf = useRef()
  const last = useRef(0)

  useEffect(() => {
    if (!playing) return
    last.current = performance.now()
    const tick = (now) => {
      const dt = now - last.current
      last.current = now
      // One real second covers about forty simulated minutes.
      onChange((m) => (m + (dt / 1000) * 40) % WEEK_MINUTES)
      raf.current = requestAnimationFrame(tick)
    }
    raf.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf.current)
  }, [playing, onChange])

  const day = Math.floor(minutes / 1440)
  const timeOfDay = Math.floor(minutes % 1440)

  return (
    <div className="rounded-panel border border-line bg-surface/60 px-4 py-4 sm:px-5">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5">
          <button
            onClick={onTogglePlay}
            className="rounded-panel border border-line p-2 text-muted transition-colors hover:border-merge/50 hover:text-ink"
            aria-label={playing ? 'Pause the simulation' : 'Play the simulation'}
          >
            {playing ? <Pause size={14} /> : <Play size={14} />}
          </button>
          <button
            onClick={() => onChange(0)}
            className="rounded-panel border border-line p-2 text-muted transition-colors hover:border-merge/50 hover:text-ink"
            aria-label="Back to Monday 00:00"
          >
            <SkipBack size={14} />
          </button>
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-3 text-[11.5px] text-faint">
            <span className="font-mono">MON 00:00</span>
            <span className="font-mono">SUN 24:00</span>
          </div>
          <input
            type="range"
            min={0}
            max={WEEK_MINUTES - 1}
            step={5}
            value={Math.round(minutes)}
            onChange={(e) => onChange(Number(e.target.value))}
            className="mt-1.5 h-1.5 w-full cursor-pointer appearance-none rounded-full bg-line accent-merge"
            aria-label="Simulated time"
            aria-valuetext={`${DAYS[day]} ${clock(timeOfDay)}`}
          />
          {/* Where the blocks are, so scrubbing has landmarks */}
          <div className="relative mt-1.5 h-4">
            {DAYS.map((d, i) => (
              <span
                key={d}
                className="absolute top-0 font-mono text-[10px] text-faint/70"
                style={{ left: `${((i * 1440) / WEEK_MINUTES) * 100}%` }}
              >
                {d}
              </span>
            ))}
            {weeklyBlocks.map((b) => (
              <span
                key={b.id}
                title={`${b.id} · ${b.section}`}
                className="absolute bottom-0 h-[5px] rounded-full bg-merge/45"
                style={{
                  left: `${(((b.day * 1440 + b.start) / WEEK_MINUTES) * 100).toFixed(3)}%`,
                  width: `${Math.max(0.35, ((b.end - b.start) / WEEK_MINUTES) * 100).toFixed(3)}%`,
                }}
              />
            ))}
          </div>
        </div>

        <div className="shrink-0 text-right">
          <p className="font-mono text-[11px] tracking-[0.16em] text-faint">SIMULATION TIME</p>
          <p className="tnum font-mono text-[19px] leading-tight">
            {DAYS[day]} {clock(timeOfDay)}
          </p>
        </div>
      </div>

      {/* Moments worth stopping at on Monday night: the shared block starting,
          the middle of it, handback, and the network clear again. */}
      <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-hair pt-3">
        <span className="mr-1 font-mono text-[10.5px] tracking-[0.14em] text-faint">JUMP TO</span>
        {JUMPS.map((j) => {
          const active = Math.abs(minutes - j.at) < 3
          return (
            <button
              key={j.label}
              onClick={() => onChange(j.at)}
              aria-pressed={active}
              title={j.note}
              className={`rounded-panel border px-2.5 py-1 font-mono text-[11.5px] transition-colors ${
                active
                  ? 'border-merge/50 bg-raised text-ink'
                  : 'border-line text-muted hover:text-ink'
              }`}
            >
              {j.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}

const JUMPS = [
  { label: 'MON 01:00', at: 60, note: 'The shared block on DER–KRJ takes the section' },
  { label: 'MON 02:15', at: 135, note: 'Four possessions in force across the division' },
  { label: 'MON 04:45', at: 285, note: 'DER–KRJ handed back' },
  { label: 'MON 05:30', at: 330, note: 'Night window closes, network clear' },
  { label: 'SUN 03:00', at: 6 * 1440 + 180, note: 'The long Sunday block on BSR–PLG' },
]
