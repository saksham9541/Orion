import { motion, AnimatePresence } from 'framer-motion'
import { AlertCircle, AlertTriangle, CheckCircle, ExternalLink, X } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useNotifications } from '@/state/NotificationContext'
import { useAppState } from '@/state/AppState'

export default function IssueAlertModal() {
  const navigate = useNavigate()
  const { currentUser } = useAppState()
  const { activePopup, acknowledge, dismissPopup, markAsRead } = useNotifications()

  if (!activePopup) return null

  const severity = (activePopup.severity || 'MEDIUM').toUpperCase()
  const isEmergency = severity === 'EMERGENCY'
  const isHigh = severity === 'HIGH'

  const severityBg = isEmergency
    ? 'bg-red-500/10 border-red-500/40 text-red-500'
    : isHigh
    ? 'bg-amber-500/10 border-amber-500/40 text-amber-500'
    : 'bg-blue-500/10 border-blue-500/40 text-blue-500'

  const handleViewIssue = () => {
    markAsRead(activePopup.id)
    dismissPopup()
    const issueId = activePopup.issue_id || ''
    const roleId = currentUser?.id

    if (roleId && roleId !== 'admin') {
      navigate(`/${roleId}${issueId ? `?issue=${issueId}` : ''}`)
    } else if (roleId === 'admin') {
      navigate(issueId ? `/admin?issue=${issueId}` : '/admin')
    } else {
      navigate(issueId ? `/tasks?search=${issueId}` : '/tasks')
    }
  }

  const handleAcknowledge = () => {
    acknowledge(activePopup.id)
  }

  const formattedTime = activePopup.created_at
    ? new Date(activePopup.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : 'Just now'

  return (
    <AnimatePresence>
      {activePopup && (
        <div
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="issue-alert-title"
          className="fixed inset-0 z-[99999] flex items-center justify-center p-4 overflow-y-auto"
        >
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={dismissPopup}
            className="fixed inset-0 bg-black/80 backdrop-blur-md"
            aria-hidden="true"
          />

          <motion.div
            initial={{ opacity: 0, scale: 0.92, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: 14 }}
            transition={{ type: 'spring', damping: 25, stiffness: 350 }}
            className="relative w-full max-w-lg rounded-[28px] border border-line/90 bg-surface p-7 shadow-[0_30px_70px_rgba(0,0,0,0.45)] z-10 my-8"
          >
            {/* Pulsing indicator for Emergency */}
            {isEmergency && (
              <div className="absolute -top-3 left-6 flex items-center gap-1.5 rounded-full bg-red-600 px-3 py-1 text-[10px] font-mono font-bold uppercase tracking-widest text-white shadow-lg animate-pulse">
                <AlertCircle size={13} />
                IMMEDIATE SAFETY INTERLOCK
              </div>
            )}

            <div className="flex items-start justify-between gap-4">
              <div className="flex items-center gap-3">
                <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border ${severityBg}`}>
                  {isEmergency ? <AlertCircle size={24} /> : <AlertTriangle size={24} />}
                </span>
                <div>
                  <div className="flex items-center gap-2">
                    <span className={`inline-block rounded-md px-2 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider border ${severityBg}`}>
                      {severity}
                    </span>
                    {activePopup.department_designated && (
                      <span className="rounded-md bg-raised border border-line px-2 py-0.5 text-[10px] font-mono font-bold text-muted uppercase">
                        DEPT: {activePopup.department_designated}
                      </span>
                    )}
                    <span className="text-[11px] font-mono text-faint">{formattedTime}</span>
                  </div>
                  <h2 id="issue-alert-title" className="mt-1 font-dot text-base font-bold text-ink uppercase tracking-wider">
                    {activePopup.title}
                  </h2>
                </div>
              </div>

              <button
                type="button"
                onClick={dismissPopup}
                aria-label="Close alert"
                className="rounded-full p-2 text-faint hover:bg-raised hover:text-ink transition-colors border border-transparent hover:border-line"
              >
                <X size={16} />
              </button>
            </div>

            <div className="mt-4 rounded-2xl border border-line/70 bg-raised/70 p-4 text-[13px] leading-relaxed text-ink/90 font-sans">
              <p>{activePopup.message}</p>
              {activePopup.issue_id && (
                <p className="mt-2.5 font-mono text-[11px] text-muted font-medium flex items-center gap-2">
                  <span className="text-faint">REF:</span>
                  <span className="text-ink font-bold bg-surface border border-line px-2 py-0.5 rounded-md">{activePopup.issue_id}</span>
                </p>
              )}
            </div>

            <div className="mt-6 flex flex-wrap items-center justify-end gap-2.5">
              <button
                type="button"
                onClick={dismissPopup}
                className="rounded-full border border-line bg-raised px-4 py-2 text-xs font-mono font-bold uppercase tracking-wider text-muted hover:text-ink hover:bg-raised/90 transition-all"
              >
                Dismiss
              </button>

              <button
                type="button"
                onClick={handleViewIssue}
                className="rounded-full border border-line bg-surface px-4 py-2 text-xs font-mono font-bold uppercase tracking-wider text-ink hover:border-ink/50 transition-all flex items-center gap-1.5"
              >
                <ExternalLink size={13} />
                View Issue
              </button>

              <button
                type="button"
                onClick={handleAcknowledge}
                className="rounded-full bg-red-600 hover:bg-red-700 text-white px-5 py-2 text-xs font-mono font-bold uppercase tracking-wider transition-all flex items-center gap-1.5 shadow-md shadow-red-900/20 active:scale-[0.98]"
              >
                <CheckCircle size={14} />
                Acknowledge
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}
