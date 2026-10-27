import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  X,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Clock,
  PlayCircle,
  Check,
  XCircle,
  ShieldAlert,
  MapPin,
  Calendar,
  Layers,
  Wrench,
  Sparkles,
  Loader2
} from 'lucide-react'

const STEPPER_STAGES = [
  { key: 'REPORTED', label: 'Reported' },
  { key: 'VERIFIED', label: 'Verified & Scored' },
  { key: 'SCHEDULED', label: 'Authorized / Scheduled' },
  { key: 'IN_PROGRESS', label: 'Work in Progress' },
  { key: 'COMPLETED', label: 'Resolved / Done' }
]

function getStageIndex(status) {
  const s = (status || '').toUpperCase()
  if (s === 'COMPLETED' || s === 'RESOLVED') return 5
  if (s === 'IN_PROGRESS') return 3
  if (s === 'SCHEDULED' || s === 'ESCALATED') return 2
  if (s === 'PENDING' || s === 'SCORED') return 1
  if (s === 'REJECTED' || s === 'CANCELLED') return -1
  return 0
}

export default function DepartmentTaskModal({ isOpen, onClose, task, onStatusChange }) {
  const [updatingStatus, setUpdatingStatus] = useState(null)
  const [successMsg, setSuccessMsg] = useState(null)
  const [errorMsg, setErrorMsg] = useState(null)

  useEffect(() => {
    setSuccessMsg(null)
    setErrorMsg(null)
  }, [task?.id, isOpen])

  // Close on Escape key
  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === 'Escape') onClose()
    }
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown)
    }
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen || !task) return null

  const stageIndex = getStageIndex(task.status)
  const isRejected = task.status === 'REJECTED' || task.status === 'CANCELLED'

  const severity = (task.severity || task.raw_severity || 'MEDIUM').toUpperCase()
  const isCritical = severity === 'CRITICAL' || severity === 'EMERGENCY'
  const isHigh = severity === 'HIGH'

  const severityBadgeClass = isCritical
    ? 'bg-red-500/10 text-red-600 border-red-500/30'
    : isHigh
    ? 'bg-amber-500/10 text-amber-600 border-amber-500/30'
    : 'bg-blue-500/10 text-blue-600 border-blue-500/30'

  const handleAction = async (targetStatus, label) => {
    setUpdatingStatus(targetStatus)
    setSuccessMsg(null)
    setErrorMsg(null)
    try {
      await onStatusChange(task.id, targetStatus)
      setSuccessMsg(`Task successfully updated to ${label}`)
      setTimeout(() => setSuccessMsg(null), 3500)
    } catch (err) {
      console.error('Failed to update task:', err)
      setErrorMsg('Failed to update status. Please try again.')
    } finally {
      setUpdatingStatus(null)
    }
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-task-title"
          className="fixed inset-0 z-[99999] flex items-center justify-center p-4 overflow-y-auto"
        >
          {/* Backdrop click */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/75 backdrop-blur-md"
            onClick={onClose}
            aria-hidden="true"
          />

          <motion.div
            initial={{ opacity: 0, scale: 0.92, y: 25 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: 15 }}
            transition={{ type: 'spring', damping: 25, stiffness: 350 }}
            className="relative w-full max-w-3xl rounded-[28px] border border-line/80 bg-surface shadow-[0_25px_60px_rgba(0,0,0,0.35)] overflow-hidden z-10 my-8"
          >
            {/* Header */}
        <div className="border-b border-line bg-surface px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-line bg-raised text-ink">
              <Wrench size={20} />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold text-ink">{task.id}</span>
                <span className={`rounded px-2 py-0.5 text-[11px] font-bold uppercase border ${severityBadgeClass}`}>
                  {severity}
                </span>
                <span className="rounded bg-raised px-2 py-0.5 text-[11px] font-semibold text-muted uppercase">
                  {task.department || 'DEPT'}
                </span>
                {task.isSafetyCritical && (
                  <span className="flex items-center gap-1 rounded bg-red-600 text-white px-2 py-0.5 text-[10px] font-bold uppercase">
                    <ShieldAlert size={12} /> Safety Critical
                  </span>
                )}
              </div>
              <h2 id="modal-task-title" className="text-xl font-bold tracking-tight text-gradient-brand mt-0.5">
                {task.defectType || task.type || 'Maintenance Defect Details'}
              </h2>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close modal"
            className="rounded-lg p-1.5 text-muted hover:bg-raised hover:text-ink transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Feedback alert banners */}
        {successMsg && (
          <div className="bg-emerald-500/10 border-b border-emerald-500/30 px-6 py-2.5 flex items-center gap-2 text-xs font-semibold text-emerald-600 animate-in fade-in duration-150">
            <CheckCircle2 size={16} />
            <span>{successMsg}</span>
          </div>
        )}
        {errorMsg && (
          <div className="bg-red-500/10 border-b border-red-500/30 px-6 py-2.5 flex items-center gap-2 text-xs font-semibold text-red-600 animate-in fade-in duration-150">
            <AlertCircle size={16} />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Stepper Progress */}
        <div className="bg-raised/40 px-6 py-4 border-b border-line">
          <p className="text-[11px] font-bold uppercase tracking-wider text-muted mb-3 flex items-center justify-between">
            <span>Lifecycle Progress</span>
            <span className="text-ink font-semibold">Current Status: <span className="uppercase text-info">{task.status}</span></span>
          </p>

          {isRejected ? (
            <div className="rounded-lg bg-red-500/10 border border-red-500/30 p-3 text-center text-xs font-semibold text-red-600 flex items-center justify-center gap-2">
              <XCircle size={16} />
              This task has been marked as REJECTED / CANCELLED.
            </div>
          ) : (
            <div className="flex items-center justify-between relative px-2">
              <div className="absolute top-3.5 left-6 right-6 h-[2px] bg-line -z-0" />
              {STEPPER_STAGES.map((st, i) => {
                const isPassed = i < stageIndex
                const isCurrent = i === stageIndex
                return (
                  <div key={st.key} className="flex flex-col items-center flex-1 text-center relative z-10">
                    <div
                      className={`w-7 h-7 rounded-full border-2 flex items-center justify-center text-xs font-bold transition-all shadow-sm ${
                        isPassed
                          ? 'bg-emerald-500 border-emerald-500 text-white'
                          : isCurrent
                          ? 'bg-surface border-blue-500 text-blue-600 ring-4 ring-blue-500/20'
                          : 'bg-raised border-line text-faint'
                      }`}
                    >
                      {isPassed ? <Check size={14} /> : i + 1}
                    </div>
                    <span
                      className={`text-[10px] font-bold uppercase tracking-wider mt-1.5 ${
                        isCurrent ? 'text-blue-600' : isPassed ? 'text-ink' : 'text-faint'
                      }`}
                    >
                      {st.label}
                    </span>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Modal Body Details */}
        <div className="p-6 space-y-6 max-h-[55vh] overflow-y-auto">
          {/* 1. What Happened */}
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-muted mb-2">1. Defect Description & Remarks</h3>
            <div className="rounded-lg border border-line bg-raised/30 p-4">
              <p className="text-sm font-medium text-ink leading-relaxed">
                {task.what || task.inspector_remarks || task.details?.what || 'Automated defect report logged in system.'}
              </p>
              <div className="mt-3 flex flex-wrap gap-4 text-xs text-muted pt-3 border-t border-line/60">
                <span className="flex items-center gap-1.5">
                  <Calendar size={14} /> Reported: <strong>{task.reported_date || task.time || 'Today'}</strong>
                </span>
                <span className="flex items-center gap-1.5">
                  <Clock size={14} /> Est. Duration: <strong>{task.estDuration || task.ml_predicted_duration_hours || 2} hrs</strong>
                </span>
                <span className="flex items-center gap-1.5">
                  <Layers size={14} /> Overdue: <strong>{task.daysOverdue ?? 0} days</strong>
                </span>
              </div>
            </div>
          </div>

          {/* 2. Impact Breakdown */}
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-muted mb-2">2. Operational & Safety Impact</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="rounded-lg border border-line bg-raised/30 p-3.5">
                <span className="text-[10px] font-bold uppercase tracking-wider text-muted block mb-1">Safety Assessment</span>
                <p className="text-xs font-semibold text-ink">
                  {task.impact?.safety || (task.isSafetyCritical ? 'Critical safety risk — requires immediate mitigation.' : 'Standard defect within normal tolerance.')}
                </p>
              </div>

              <div className="rounded-lg border border-line bg-raised/30 p-3.5">
                <span className="text-[10px] font-bold uppercase tracking-wider text-muted block mb-1">Traffic Delay Impact</span>
                <p className="text-xs font-semibold text-ink">
                  {task.impact?.operations || `Estimated ${task.ml_predicted_duration_hours || task.estDuration || 2} hr speed restriction delay.`}
                </p>
              </div>

              <div className="rounded-lg border border-line bg-raised/30 p-3.5">
                <span className="text-[10px] font-bold uppercase tracking-wider text-muted block mb-1">Maintenance Requirement</span>
                <p className="text-xs font-semibold text-ink">
                  {task.impact?.maintenance || 'Requires department maintenance block via Optimizer.'}
                </p>
              </div>

              <div className="rounded-lg border border-line bg-raised/30 p-3.5">
                <span className="text-[10px] font-bold uppercase tracking-wider text-muted block mb-1">Exact Location</span>
                <p className="text-xs font-semibold text-ink flex items-center gap-1">
                  <MapPin size={13} className="text-muted shrink-0" />
                  {task.exactLocation || `${task.corridorId || task.locationName || 'Mainline'} · KM ${task.km_location || '—'}`}
                </p>
              </div>
            </div>
          </div>

          {/* 3. AI Optimizer Recommendation */}
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-muted mb-2">3. RailOpt AI Recommendation</h3>
            <div className="rounded-lg border border-info/30 bg-info/5 p-4 flex items-start gap-3">
              <Sparkles size={18} className="text-info shrink-0 mt-0.5" />
              <div>
                <p className="text-xs font-semibold text-ink">
                  {task.recommendation || 'Authorize maintenance request and integrate into upcoming 4-hour corridor block.'}
                </p>
                <p className="text-[11px] text-muted mt-1">
                  Automated constraint analyzer verifies zero conflicting traffic on adjacent track during off-peak interval.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Footer Lifecycle Actions */}
        <div className="border-t border-line bg-surface px-6 py-4 flex flex-wrap items-center justify-between gap-3">
          <span className="text-xs text-muted font-medium">Department Lifecycle Actions:</span>

          <div className="flex flex-wrap items-center gap-2">
            {/* Authorize */}
            <button
              type="button"
              disabled={updatingStatus !== null || task.status === 'SCHEDULED'}
              onClick={() => handleAction('SCHEDULED', 'Authorized')}
              className={`flex items-center gap-1.5 rounded-full border px-4 py-2 text-xs font-bold uppercase tracking-wider transition-all shadow-sm ${
                task.status === 'SCHEDULED'
                  ? 'bg-blue-600 text-white border-blue-600 ring-2 ring-blue-500/30'
                  : 'bg-surface border-line text-ink hover:border-blue-500 hover:text-blue-600'
              } disabled:opacity-50`}
            >
              {updatingStatus === 'SCHEDULED' ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
              Authorize
            </button>

            {/* Start Action / In Progress */}
            <button
              type="button"
              disabled={updatingStatus !== null || task.status === 'IN_PROGRESS'}
              onClick={() => handleAction('IN_PROGRESS', 'In Progress')}
              className={`flex items-center gap-1.5 rounded-full border px-4 py-2 text-xs font-bold uppercase tracking-wider transition-all shadow-sm ${
                task.status === 'IN_PROGRESS'
                  ? 'bg-amber-600 text-white border-amber-600 ring-2 ring-amber-500/30'
                  : 'bg-surface border-line text-ink hover:border-amber-500 hover:text-amber-600'
              } disabled:opacity-50`}
            >
              {updatingStatus === 'IN_PROGRESS' ? <Loader2 size={14} className="animate-spin" /> : <PlayCircle size={14} />}
              Start Action
            </button>

            {/* Mark Resolved / Done */}
            <button
              type="button"
              disabled={updatingStatus !== null || task.status === 'COMPLETED'}
              onClick={() => handleAction('COMPLETED', 'Resolved')}
              className={`flex items-center gap-1.5 rounded-full border px-4 py-2 text-xs font-bold uppercase tracking-wider transition-all shadow-sm ${
                task.status === 'COMPLETED'
                  ? 'bg-emerald-600 text-white border-emerald-600 ring-2 ring-emerald-500/30'
                  : 'bg-surface border-line text-ink hover:border-emerald-500 hover:text-emerald-600'
              } disabled:opacity-50`}
            >
              {updatingStatus === 'COMPLETED' ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
              Done
            </button>

            {/* Reject */}
            <button
              type="button"
              disabled={updatingStatus !== null || task.status === 'REJECTED'}
              onClick={() => handleAction('REJECTED', 'Rejected')}
              className={`flex items-center gap-1.5 rounded-full border px-4 py-2 text-xs font-bold uppercase tracking-wider transition-all shadow-sm ${
                task.status === 'REJECTED'
                  ? 'bg-red-600 text-white border-red-600'
                  : 'bg-surface border-line text-muted hover:border-red-500 hover:text-red-600'
              } disabled:opacity-50`}
            >
              {updatingStatus === 'REJECTED' ? <Loader2 size={14} className="animate-spin" /> : <XCircle size={14} />}
              Reject
            </button>

            <button
              type="button"
              onClick={onClose}
              className="rounded-full border border-line bg-raised px-4 py-2 text-xs font-semibold text-muted hover:text-ink transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  )}
</AnimatePresence>
  )
}
