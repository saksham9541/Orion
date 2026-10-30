import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Clock,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  AlertCircle,
  ShieldAlert,
  ChevronDown,
  ChevronUp,
  User,
  MapPin,
  Building2,
} from 'lucide-react'
import { useLiveSync } from '@/state/LiveSyncStore'
import { useAppState } from '@/state/AppState'

export default function AwaitingAckInbox({ departmentFilter = null, isTechnicianView = false }) {
  const { pendingAckTasks, acknowledge, decline } = useLiveSync()
  const { currentUser } = useAppState()
  const [isExpanded, setIsExpanded] = useState(true)
  const [loadingTaskId, setLoadingTaskId] = useState(null)
  const [errorMessage, setErrorMessage] = useState(null)

  // Filter tasks: if departmentFilter provided, match department; otherwise show all
  const filteredTasks = pendingAckTasks.filter((t) => {
    if (!departmentFilter || departmentFilter === 'ALL') return true
    const deptNorm = (t.department || '').toUpperCase()
    const filterNorm = departmentFilter.toUpperCase()
    if (filterNorm === 'S&T' || filterNorm === 'SNT') {
      return deptNorm === 'SNT' || deptNorm === 'S&T'
    }
    return deptNorm === filterNorm
  })

  if (filteredTasks.length === 0) {
    if (isTechnicianView) {
      return null
    }
    return null // Keep UI clean when no reports are awaiting acknowledgement
  }

  const handleAcknowledge = async (taskId) => {
    setLoadingTaskId(taskId)
    setErrorMessage(null)
    const res = await acknowledge(taskId)
    setLoadingTaskId(null)
    if (!res.success) {
      setErrorMessage(res.error || 'Acknowledgement rejected by server')
      setTimeout(() => setErrorMessage(null), 5000)
    }
  }

  const handleDecline = async (taskId) => {
    const reason = window.prompt(
      'Enter decline reason for this defect report:',
      'Invalid or duplicate defect report'
    )
    if (!reason || !reason.trim()) return

    setLoadingTaskId(taskId)
    setErrorMessage(null)
    const res = await decline(taskId, reason.trim())
    setLoadingTaskId(null)
    if (!res.success) {
      setErrorMessage(res.error || 'Decline rejected by server')
      setTimeout(() => setErrorMessage(null), 5000)
    }
  }

  return (
    <div className="mb-6 rounded-2xl border border-amber-500/30 bg-amber-500/5 p-4 sm:p-5 shadow-sm">
      {/* Header Banner */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-500/20 text-amber-600 dark:text-amber-400">
            <Clock size={16} className="animate-pulse" />
          </span>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold tracking-tight text-ink">
                {isTechnicianView ? 'My Submitted Reports Awaiting Acknowledgement' : 'Defect Reports Awaiting Acknowledgement'}
              </h3>
              <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-xs font-mono font-bold text-amber-700 dark:text-amber-300">
                {filteredTasks.length} pending
              </span>
            </div>
            <p className="text-[11px] text-muted font-sans">
              {isTechnicianView
                ? 'Saved safely in database. Excluded from active schedules until acknowledged by supervisor.'
                : 'First acknowledgement enlists task into active lifecycle and pipeline. Declining rejects the report.'}
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="rounded-lg p-1.5 text-muted hover:text-ink hover:bg-surface/50 transition-colors"
          aria-label={isExpanded ? 'Collapse' : 'Expand'}
        >
          {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      </div>

      {errorMessage && (
        <div className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 p-2.5 text-xs text-red-600 dark:text-red-400 flex items-center gap-2">
          <AlertCircle size={14} className="shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Task Cards */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-4 space-y-3"
          >
            {filteredTasks.map((t) => {
              const taskId = t.task_id || t.id
              const isUrgent = (t.severity || '').toUpperCase() === 'EMERGENCY' || (t.severity || '').toUpperCase() === 'CRITICAL'
              const isLoading = loadingTaskId === taskId

              return (
                <div
                  key={taskId}
                  className="rounded-xl border border-line bg-surface p-3.5 shadow-sm hover:border-line-hover transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3.5"
                >
                  <div className="min-w-0 flex-1 space-y-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs font-bold text-ink">{taskId}</span>
                      <span
                        className={`rounded px-1.5 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider ${
                          isUrgent
                            ? 'bg-red-500/15 text-red-600 dark:text-red-400 border border-red-500/30'
                            : 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30'
                        }`}
                      >
                        {t.severity || 'HIGH'}
                      </span>
                      <span className="rounded bg-raised px-1.5 py-0.5 text-[10px] font-mono font-semibold text-muted">
                        {t.department}
                      </span>
                      <span className="text-[11px] text-faint">
                        {t.created_at ? new Date(t.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Just now'}
                      </span>
                    </div>

                    <p className="text-xs text-ink font-medium leading-relaxed">
                      {t.inspector_remarks || t.description || 'Track defect inspection report.'}
                    </p>

                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted">
                      <span className="flex items-center gap-1 font-mono">
                        <MapPin size={12} className="text-faint" />
                        {t.section_id || 'Corridor'}{t.km_location ? ` @ KM ${t.km_location}` : ''}
                      </span>
                      {t.created_by && (
                        <span className="flex items-center gap-1">
                          <User size={12} className="text-faint" />
                          Reported by: <span className="font-mono text-ink">{t.created_by}</span>
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  {!isTechnicianView && (
                    <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                      <button
                        type="button"
                        disabled={isLoading}
                        onClick={() => handleAcknowledge(taskId)}
                        className="rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white px-3 py-1.5 text-xs font-sans font-semibold flex items-center gap-1.5 shadow-sm transition-all active:scale-95"
                      >
                        <CheckCircle2 size={13} />
                        <span>Acknowledge</span>
                      </button>

                      <button
                        type="button"
                        disabled={isLoading}
                        onClick={() => handleDecline(taskId)}
                        className="rounded-lg border border-line bg-surface hover:border-red-300 hover:text-red-600 disabled:opacity-50 text-muted px-2.5 py-1.5 text-xs font-sans font-medium flex items-center gap-1 transition-colors"
                      >
                        <XCircle size={13} />
                        <span>Decline</span>
                      </button>
                    </div>
                  )}

                  {isTechnicianView && (
                    <span className="rounded-full bg-amber-500/10 border border-amber-500/20 px-2.5 py-1 text-[11px] font-mono text-amber-700 dark:text-amber-300 self-start sm:self-center">
                      Awaiting Supervisor Acknowledgement
                    </span>
                  )}
                </div>
              )
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
