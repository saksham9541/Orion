import { useState, useEffect } from 'react'
import { fetchSectionWindows } from '@/api'
import { Clock, ShieldCheck, AlertCircle, Train, ChevronRight } from 'lucide-react'

export default function SectionTimeline({ sectionId, sectionName, date }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [selectedItem, setSelectedItem] = useState(null)

  useEffect(() => {
    if (!sectionId) return
    setLoading(true)
    setError(null)
    fetchSectionWindows(sectionId, date)
      .then((res) => {
        setData(res.data)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message || 'Failed to load timeline')
        setLoading(false)
      })
  }, [sectionId, date])

  if (loading) {
    return (
      <div className="flex h-28 items-center justify-center rounded-xl border border-line bg-surface/40 p-4 text-xs text-muted">
        <Clock className="mr-2 h-4 w-4 animate-spin text-info" />
        Loading real track timetable &amp; section passages...
      </div>
    )
  }

  if (error || !data) {
    return null
  }

  const cov = data.coverage || {}
  const windows = data.windows || []
  const isPilot = (cov.coverage_pct || 0) > 0

  return (
    <div className="rounded-2xl border border-line bg-surface/70 p-4 shadow-sm backdrop-blur-sm">
      <div className="flex items-center justify-between gap-2 border-b border-line/40 pb-3">
        <div className="flex items-center gap-2">
          <Train className="h-4 w-4 text-info" />
          <span className="text-xs font-bold uppercase tracking-wider text-ink">
            Section Timetable Timeline
          </span>
          <span className="rounded-full bg-raised px-2 py-0.5 font-mono text-[10px] text-muted">
            {data.section_name || sectionName || sectionId}
          </span>
        </div>

        {/* Coverage pill */}
        <div className="flex items-center gap-1.5">
          <span
            className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
              isPilot
                ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30'
                : 'bg-zinc-500/15 text-zinc-600 dark:text-zinc-400 border border-zinc-500/30'
            }`}
          >
            <ShieldCheck className="h-3 w-3" />
            {isPilot ? `${cov.coverage_pct}% Real Timetable` : 'Synthetic Timeline'}
          </span>
          {isPilot && (
            <span className="text-[10px] text-muted">
              ({cov.real_trains} real / {cov.total_trains} total daily trains)
            </span>
          )}
        </div>
      </div>

      {/* 24-hour visual bar */}
      <div className="mt-3">
        <div className="flex justify-between text-[9px] font-mono text-muted mb-1 px-1">
          <span>00:00</span>
          <span>04:00</span>
          <span>08:00</span>
          <span>12:00</span>
          <span>16:00</span>
          <span>20:00</span>
          <span>24:00</span>
        </div>

        <div className="relative h-9 w-full rounded-lg bg-deep/60 p-1 border border-line/50 overflow-hidden flex items-center">
          {/* Hour tick marks */}
          <div className="absolute inset-0 flex justify-between pointer-events-none opacity-20">
            {Array.from({ length: 24 }).map((_, i) => (
              <div key={i} className="h-full border-r border-line" style={{ width: '4.166%' }} />
            ))}
          </div>

          {/* Windows / Gaps */}
          {windows.map((w, idx) => {
            const startHour = parseInt(w.start_time.split(':')[0], 10) + parseInt(w.start_time.split(':')[1], 10) / 60
            const leftPct = (startHour / 24) * 100
            const widthPct = Math.max(3, (w.duration_hours / 24) * 100)

            return (
              <div
                key={w.window_id || idx}
                onClick={() => setSelectedItem(w)}
                style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
                className="absolute top-1 bottom-1 rounded bg-info/25 border border-info/60 hover:bg-info/40 cursor-pointer flex items-center justify-center transition-all z-10 group"
                title={`Free Window: ${w.start_time} - ${w.end_time} (${w.duration_hours}h)`}
              >
                <span className="text-[8px] font-bold text-info font-mono truncate px-1 group-hover:scale-105">
                  {w.duration_hours}h FREE
                </span>
              </div>
            )
          })}
        </div>

        <div className="mt-2 flex items-center justify-between text-[10px] text-muted">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-info/60" /> Free Maintenance Window
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-deep" /> Occupied Train Passages
            </span>
          </div>
          <span>{windows.length} free candidate windows detected</span>
        </div>
      </div>

      {selectedItem && (
        <div className="mt-3 rounded-xl border border-info/30 bg-info/10 p-2.5 text-xs">
          <div className="flex items-center justify-between">
            <span className="font-bold text-ink">Window Details: {selectedItem.window_id}</span>
            <button
              onClick={() => setSelectedItem(null)}
              className="text-[10px] text-muted hover:text-ink"
            >
              Close
            </button>
          </div>
          <p className="mt-1 text-[11px] text-muted">
            Interval: <strong className="text-ink">{selectedItem.start_time} - {selectedItem.end_time}</strong> ({selectedItem.duration_hours} hrs)
            · Computed Impact: <strong className="text-ink">{selectedItem.ml_traffic_impact_score || 0}</strong> / 100
            · Delay Source: <strong className="text-ink font-mono">{selectedItem.delay_source}</strong>
          </p>
        </div>
      )}
    </div>
  )
}
