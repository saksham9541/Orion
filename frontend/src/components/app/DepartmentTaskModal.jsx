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
    ? 'bg-[#FCE8E8] text-[#DC3030] border-[#DC3030]/30'
    : isHigh
    ? 'bg-[#FFF3D9] text-[#D99019] border-[#D99019]/30'
    : 'bg-[#F4F4F1] text-[#252A27] border-[#E1E3DE]'

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
            className="relative w-full max-w-3xl rounded-2xl border border-[#E1E3DE] bg-white shadow-[0_24px_50px_rgba(40,45,42,0.18)] overflow-hidden z-10 my-8"
          >
            {/* Header */}
        <div className="border-b border-[#E1E3DE] bg-white px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#E1E3DE] bg-[#F4F4F1] text-[#252A27]">
              <Wrench size={20} className="text-[#D99A2B]" />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold text-[#252A27]">{task.id}</span>
                <span className={`rounded px-2 py-0.5 text-[11px] font-mono font-bold uppercase border ${severityBadgeClass}`}>
                  {severity}
                </span>
                <span className="rounded bg-[#F4F4F1] border border-[#E1E3DE] px-2 py-0.5 text-[11px] font-mono font-semibold text-[#656A66] uppercase">
                  {task.department || 'DEPT'}
                </span>
                {task.isSafetyCritical && (
                  <span className="flex items-center gap-1 rounded bg-[#DC3030] text-white px-2 py-0.5 text-[10px] font-mono font-bold uppercase">
                    <ShieldAlert size={12} /> Safety Critical
                  </span>
                )}
              </div>
              <h2 id="modal-task-title" className="text-xl font-bold tracking-tight text-[#252A27] mt-0.5">
                {task.defectType || task.type || 'Maintenance Defect Details'}
              </h2>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close modal"
            className="rounded-lg p-1.5 text-[#656A66] hover:bg-[#F4F4F1] hover:text-[#252A27] transition-colors border border-transparent hover:border-[#E1E3DE]"
          >
            <X size={20} />
          </button>
        </div>

        {/* Feedback alert banners */}
        {successMsg && (
          <div className="bg-[#E5F5EC] border-b border-[#0D996B]/30 px-6 py-2.5 flex items-center gap-2 text-xs font-semibold text-[#0D996B] animate-in fade-in duration-150">
            <CheckCircle2 size={16} />
            <span>{successMsg}</span>
          </div>
        )}
        {errorMsg && (
          <div className="bg-[#FCE8E8] border-b border-[#DC3030]/30 px-6 py-2.5 flex items-center gap-2 text-xs font-semibold text-[#DC3030] animate-in fade-in duration-150">
            <AlertCircle size={16} />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Stepper Progress */}
        <div className="bg-[#F4F4F1]/60 px-6 py-4 border-b border-[#E1E3DE]">
          <p className="text-[11px] font-mono font-bold uppercase tracking-wider text-[#656A66] mb-3 flex items-center justify-between">
            <span>Lifecycle Progress</span>
            <span className="text-[#252A27] font-semibold">Current Status: <span className="uppercase text-[#D99A2B]">{task.status}</span></span>
          </p>

          {isRejected ? (
            <div className="rounded-xl bg-[#FCE8E8] border border-[#DC3030]/30 p-3 text-center text-xs font-semibold text-[#DC3030] flex items-center justify-center gap-2">
              <XCircle size={16} />
              This task has been marked as REJECTED / CANCELLED.
            </div>
          ) : (
            <div className="flex items-center justify-between relative px-2">
              <div className="absolute top-3.5 left-6 right-6 h-[2px] bg-[#E1E3DE] -z-0" />
              {STEPPER_STAGES.map((st, i) => {
                const isPassed = i < stageIndex
                const isCurrent = i === stageIndex
                return (
                  <div key={st.key} className="flex flex-col items-center flex-1 text-center relative z-10">
                    <div
                      className={`w-7 h-7 rounded-full border-2 flex items-center justify-center text-xs font-mono font-bold transition-all shadow-sm ${
                        isPassed
                          ? 'bg-[#0D996B] border-[#0D996B] text-white'
                          : isCurrent
                          ? 'bg-white border-[#D99A2B] text-[#D99A2B] ring-4 ring-[#D99A2B]/20'
                          : 'bg-[#F4F4F1] border-[#E1E3DE] text-[#656A66]'
                      }`}
                    >
                      {isPassed ? <Check size={14} /> : i + 1}
                    </div>
                    <span
                      className={`text-[10px] font-mono font-bold uppercase tracking-wider mt-1.5 ${
                        isCurrent ? 'text-[#D99A2B]' : isPassed ? 'text-[#252A27]' : 'text-[#656A66]'
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
            <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-[#656A66] mb-2">1. Defect Description & Remarks</h3>
            <div className="rounded-xl border border-[#E1E3DE] bg-[#F4F4F1]/40 p-4">
              <p className="text-sm font-medium text-[#252A27] leading-relaxed">
                {task.what || task.inspector_remarks || task.details?.what || 'Automated defect report logged in system.'}
              </p>
              <div className="mt-3 flex flex-wrap gap-4 text-xs font-mono text-[#656A66] pt-3 border-t border-[#E1E3DE]">
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
            <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-[#656A66] mb-2">2. Operational & Safety Impact</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="rounded-xl border border-[#E1E3DE] bg-[#F4F4F1]/40 p-3.5">
                <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#656A66] block mb-1">Safety Assessment</span>
                <p className="text-xs font-semibold text-[#252A27]">
                  {task.impact?.safety || (task.isSafetyCritical ? 'Critical safety risk — requires immediate mitigation.' : 'Standard defect within normal tolerance.')}
                </p>
              </div>

              <div className="rounded-xl border border-[#E1E3DE] bg-[#F4F4F1]/40 p-3.5">
                <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#656A66] block mb-1">Traffic Delay Impact</span>
                <p className="text-xs font-semibold text-[#252A27]">
                  {task.impact?.operations || `Estimated ${task.ml_predicted_duration_hours || task.estDuration || 2} hr speed restriction delay.`}
                </p>
              </div>

              <div className="rounded-xl border border-[#E1E3DE] bg-[#F4F4F1]/40 p-3.5">
                <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#656A66] block mb-1">Maintenance Requirement</span>
                <p className="text-xs font-semibold text-[#252A27]">
                  {task.impact?.maintenance || 'Requires department maintenance block via Optimizer.'}
                </p>
              </div>

              <div className="rounded-xl border border-[#E1E3DE] bg-[#F4F4F1]/40 p-3.5">
                <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#656A66] block mb-1">Exact Location</span>
                <p className="text-xs font-semibold text-[#252A27] flex items-center gap-1 font-mono">
                  <MapPin size={13} className="text-[#656A66] shrink-0" />
                  {task.exactLocation || `${task.corridorId || task.locationName || 'Mainline'} · KM ${task.km_location || '—'}`}
                </p>
              </div>
            </div>
          </div>

          {/* 3. AI Optimizer Recommendation */}
          <div>
            <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-[#656A66] mb-2">3. RailOpt AI Recommendation</h3>
            <div className="rounded-xl border border-[#D99A2B]/30 bg-[#FFF3D9]/40 p-4 flex items-start gap-3">
              <Sparkles size={18} className="text-[#D99A2B] shrink-0 mt-0.5" />
              <div>
                <p className="text-xs font-semibold text-[#252A27]">
                  {task.recommendation || 'Authorize maintenance request and integrate into upcoming 4-hour corridor block.'}
                </p>
                <p className="text-[11px] text-[#656A66] mt-1 font-mono">
                  Automated constraint analyzer verifies zero conflicting traffic on adjacent track during off-peak interval.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Footer Lifecycle Actions */}
        <div className="border-t border-[#E1E3DE] bg-white px-6 py-4 flex flex-wrap items-center justify-between gap-3">
          <span className="text-xs text-[#656A66] font-mono uppercase tracking-wider">Department Lifecycle Actions:</span>

          <div className="flex flex-wrap items-center gap-2">
            {/* Authorize */}
            <button
              type="button"
              disabled={updatingStatus !== null || task.status === 'SCHEDULED'}
              onClick={() => handleAction('SCHEDULED', 'Authorized')}
              className={`flex items-center gap-1.5 rounded-xl border px-4 py-2 text-xs font-mono font-bold uppercase tracking-wider transition-all shadow-sm ${
                task.status === 'SCHEDULED'
                  ? 'bg-[#282D2A] text-white border-[#282D2A]'
                  : 'bg-white border-[#E1E3DE] text-[#252A27] hover:border-[#282D2A]'
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
              className={`flex items-center gap-1.5 rounded-xl border px-4 py-2 text-xs font-mono font-bold uppercase tracking-wider transition-all shadow-sm ${
                task.status === 'IN_PROGRESS'
                  ? 'bg-[#D99A2B] text-white border-[#D99A2B]'
                  : 'bg-white border-[#E1E3DE] text-[#252A27] hover:border-[#D99A2B] hover:text-[#D99A2B]'
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
              className={`flex items-center gap-1.5 rounded-xl border px-4 py-2 text-xs font-mono font-bold uppercase tracking-wider transition-all shadow-sm ${
                task.status === 'COMPLETED'
                  ? 'bg-[#0D996B] text-white border-[#0D996B]'
                  : 'bg-white border-[#E1E3DE] text-[#252A27] hover:border-[#0D996B] hover:text-[#0D996B]'
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
              className={`flex items-center gap-1.5 rounded-xl border px-4 py-2 text-xs font-mono font-bold uppercase tracking-wider transition-all shadow-sm ${
                task.status === 'REJECTED'
                  ? 'bg-[#DC3030] text-white border-[#DC3030]'
                  : 'bg-white border-[#E1E3DE] text-[#656A66] hover:border-[#DC3030] hover:text-[#DC3030]'
              } disabled:opacity-50`}
            >
              {updatingStatus === 'REJECTED' ? <Loader2 size={14} className="animate-spin" /> : <XCircle size={14} />}
              Reject
            </button>

            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-[#E1E3DE] bg-[#F4F4F1] px-4 py-2 text-xs font-mono font-semibold text-[#656A66] hover:text-[#252A27] transition-colors"
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
