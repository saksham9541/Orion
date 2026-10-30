import React, { useEffect, useState } from 'react'
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Clock,
  ExternalLink,
  Info,
  Radio,
  RefreshCw,
  ShieldAlert,
  Train,
  X,
  Zap,
} from 'lucide-react'
import Button from '@/components/common/Button'
import api from '@/api'

/**
 * EmergencyImpactModal & EmergencyImpactPanel
 *
 * Dedicated modal and persistent panel for EMERGENCY tasks.
 * Evaluates immediate block grant impact:
 * - Total trains affected and cumulative delays (passenger, freight, weighted)
 * - Per-train impact breakdown table sorted by hold / destination delay
 * - What-if recalculation: stop work earlier slider / quick buttons
 * - Data provenance breakdown (LIVE vs ESTIMATED)
 */
export default function EmergencyImpactModal({
  isOpen,
  onClose,
  taskId,
  initialDurationHours = 2.0,
}) {
  if (!isOpen || !taskId) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-xl border border-rose-500/40 bg-surface p-6 shadow-2xl">
        <div className="flex items-start justify-between border-b border-hair pb-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-rose-500/20 text-rose-500">
              <Zap size={22} className="animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-ink">Emergency Block Delay Impact</h2>
                <span className="rounded bg-rose-500/15 px-2 py-0.5 font-mono text-xs font-bold text-rose-500">
                  IMMEDIATE GRANT
                </span>
              </div>
              <p className="text-xs text-muted">
                Task <span className="font-mono text-ink font-semibold">{taskId}</span> · Real-time timetable delay propagation
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded p-1 text-muted hover:text-ink hover:bg-raised transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        <EmergencyImpactPanel taskId={taskId} initialDurationHours={initialDurationHours} />

        <div className="mt-6 flex justify-end border-t border-hair pt-4">
          <Button variant="ghost" onClick={onClose}>
            Close Analysis
          </Button>
        </div>
      </div>
    </div>
  )
}

export function EmergencyImpactPanel({ taskId, initialDurationHours = 2.0 }) {
  const [durationHours, setDurationHours] = useState(initialDurationHours)
  const [impactData, setImpactData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const fetchImpact = async (hours) => {
    if (!taskId) return
    setLoading(true)
    setError(null)
    try {
      const res = await api.get(`/tasks/${taskId}/emergency-impact`, {
        params: { planned_duration_hours: hours },
      })
      setImpactData(res.data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to fetch emergency delay impact')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchImpact(durationHours)
  }, [taskId, durationHours])

  const affectedTrains = impactData?.affected_trains || []
  const summary = impactData?.summary_metrics || {}

  return (
    <div className="my-4 space-y-5">
      {/* Error state */}
      {error && (
        <div className="flex items-start gap-2.5 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
          <AlertCircle size={15} className="mt-0.5 shrink-0 text-rose-400" />
          <div>{error}</div>
        </div>
      )}

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
        <div className="rounded-lg border border-line bg-surface/50 p-3">
          <span className="text-[11px] text-muted flex items-center gap-1">
            <Train size={13} className="text-accent" /> Trains Affected
          </span>
          <p className="font-mono text-2xl font-bold text-ink mt-1">
            {impactData?.trains_affected ?? 0}
          </p>
          <span className="text-[10px] text-muted">
            {impactData?.work_period?.line || 'UP+DN'} Line
          </span>
        </div>

        <div className="rounded-lg border border-line bg-surface/50 p-3">
          <span className="text-[11px] text-muted flex items-center gap-1">
            <Clock size={13} className="text-rose-500" /> Total Primary Delay
          </span>
          <p className="font-mono text-2xl font-bold text-rose-500 mt-1">
            {impactData?.total_delay_minutes ? Math.round(impactData.total_delay_minutes) : 0}
            <span className="text-xs font-normal text-muted ml-1">mins</span>
          </p>
          <span className="text-[10px] text-muted">
            Held outside block
          </span>
        </div>

        <div className="rounded-lg border border-line bg-surface/50 p-3">
          <span className="text-[11px] text-muted flex items-center gap-1">
            <Zap size={13} className="text-amber-500" /> Weighted Penalty
          </span>
          <p className="font-mono text-2xl font-bold text-amber-500 mt-1">
            {summary.weighted_delay_minutes ? Math.round(summary.weighted_delay_minutes) : 0}
          </p>
          <span className="text-[10px] text-muted">
            Priority-factored
          </span>
        </div>

        <div className="rounded-lg border border-line bg-surface/50 p-3">
          <span className="text-[11px] text-muted flex items-center gap-1">
            <Radio size={13} className="text-emerald-500" /> Confidence & Data
          </span>
          <div className="flex items-center gap-1.5 mt-1">
            <p className="font-mono text-xl font-bold text-ink">
              {impactData?.confidence_score ? `${Math.round(impactData.confidence_score * 100)}%` : '85%'}
            </p>
            <span className={`rounded px-1.5 py-0.5 font-mono text-[9px] font-bold ${
              impactData?.provenance_label === 'LIVE_DELAY_ENRICHED' 
                ? 'bg-emerald-500/15 text-emerald-500' 
                : 'bg-amber-500/15 text-amber-500'
            }`}>
              {impactData?.provenance_label === 'LIVE_DELAY_ENRICHED' ? 'LIVE DELAYS' : 'ESTIMATED'}
            </span>
          </div>
          <span className="text-[10px] text-muted">
            {impactData?.work_period?.clock_summary || 'Immediate block'}
          </span>
        </div>
      </div>

      {/* What-If Recalculator Slider */}
      <div className="rounded-xl border border-hair bg-surface/40 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-2.5">
          <div className="flex items-center gap-2">
            <Clock size={15} className="text-accent" />
            <h4 className="text-xs font-semibold text-ink uppercase tracking-wider">
              "Stop Work Earlier" What-If Recalculator
            </h4>
          </div>
          <span className="font-mono text-xs font-bold text-accent">
            Duration: {durationHours.toFixed(1)} hrs ({Math.round(durationHours * 60)} mins)
          </span>
        </div>

        <div className="flex items-center gap-4">
          <input
            type="range"
            min="0.5"
            max="4.0"
            step="0.5"
            value={durationHours}
            onChange={(e) => setDurationHours(parseFloat(e.target.value))}
            className="w-full accent-[#D99A2B] cursor-pointer"
          />
        </div>

        <div className="mt-2.5 flex items-center justify-between text-[11px] text-muted">
          <div className="flex gap-1.5">
            {[0.5, 1.0, 1.5, 2.0, 3.0].map((h) => (
              <button
                key={h}
                type="button"
                onClick={() => setDurationHours(h)}
                className={`rounded px-2 py-0.5 font-mono transition-colors ${
                  durationHours === h
                    ? 'bg-accent text-white font-bold'
                    : 'bg-raised text-muted hover:text-ink'
                }`}
              >
                {h}h
              </button>
            ))}
          </div>
          <span className="italic">
            Adjusting block duration immediately recalculates delay cascades across timetable trains.
          </span>
        </div>
      </div>

      {/* Itemized Affected Trains Table */}
      <div>
        <div className="mb-2 flex items-center justify-between text-xs">
          <span className="font-semibold text-ink flex items-center gap-1.5">
            <Train size={14} className="text-accent" /> Itemized Delayed Trains ({affectedTrains.length})
          </span>
          <span className="text-muted text-[11px]">
            Sorted by destination cascade delay
          </span>
        </div>

        <div className="max-h-64 overflow-y-auto rounded-lg border border-line bg-surface">
          {affectedTrains.length === 0 ? (
            <div className="p-6 text-center text-xs text-faint italic">
              {loading ? 'Evaluating train delay timetable...' : 'No trains directly overlapping this emergency maintenance block.'}
            </div>
          ) : (
            <table className="w-full text-left font-mono text-[11.5px] border-collapse">
              <thead>
                <tr className="border-b border-hair bg-surface/80 text-[10.5px] uppercase tracking-wider text-muted">
                  <th className="p-2.5">Train</th>
                  <th className="p-2.5">Type</th>
                  <th className="p-2.5">Sched Entry</th>
                  <th className="p-2.5">Wait Station</th>
                  <th className="p-2.5">Hold (Min)</th>
                  <th className="p-2.5">Dest Delay</th>
                  <th className="p-2.5">Weighted</th>
                  <th className="p-2.5">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hair">
                {affectedTrains.map((t, idx) => (
                  <tr key={idx} className="hover:bg-raised/40 transition-colors">
                    <td className="p-2.5 font-bold text-ink">
                      <div>{t.train_number}</div>
                      <div className="text-[10px] font-sans font-normal text-muted truncate max-w-[140px]">
                        {t.train_name}
                      </div>
                    </td>
                    <td className="p-2.5 text-muted">
                      <span className="rounded bg-raised px-1.5 py-0.5 text-[10px]">
                        {t.train_type}
                      </span>
                    </td>
                    <td className="p-2.5 text-ink">{t.scheduled_entry_time || '—'}</td>
                    <td className="p-2.5 text-accent font-semibold">{t.wait_station || 'Outer Signal'}</td>
                    <td className="p-2.5 font-bold text-rose-500">
                      +{Math.round(t.hold_minutes || 0)}m
                    </td>
                    <td className="p-2.5 text-ink">
                      +{Math.round(t.expected_destination_delay || 0)}m
                    </td>
                    <td className="p-2.5 font-bold text-amber-500">
                      {Math.round(t.weighted_delay || 0)}
                    </td>
                    <td className="p-2.5">
                      <span className={`rounded px-1.5 py-0.5 text-[9.5px] font-semibold ${
                        t.data_provenance === 'live'
                          ? 'bg-emerald-500/15 text-emerald-500'
                          : 'bg-surface-elevated text-muted'
                      }`}>
                        {t.data_provenance === 'live' ? 'LIVE' : 'EST'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
