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
    ? 'bg-[#FCE8E8] border-[#DC3030]/40 text-[#DC3030]'
    : isHigh
    ? 'bg-[#FFF3D9] border-[#D99019]/40 text-[#D99019]'
    : 'bg-[#F4F4F1] border-[#E1E3DE] text-[#252A27]'

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

  const formattedTitle = (activePopup.title || 'New Operational Alert')
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase())

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
            className="relative w-full max-w-lg rounded-2xl border border-[#E1E3DE] bg-white p-6 shadow-[0_24px_50px_rgba(40,45,42,0.18)] z-10 my-8"
          >
            {/* Pulsing indicator for Emergency */}
            {isEmergency && (
              <div className="absolute -top-3 left-6 flex items-center gap-1.5 rounded-full bg-[#DC3030] px-3 py-1 text-[10px] font-mono font-bold uppercase tracking-widest text-white shadow-lg animate-pulse">
                <AlertCircle size={13} />
                IMMEDIATE SAFETY INTERLOCK
              </div>
            )}

            <div className="flex items-start justify-between gap-4">
              <div className="flex items-center gap-3">
                <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border ${severityBg}`}>
                  {isEmergency ? <AlertCircle size={22} /> : <AlertTriangle size={22} />}
                </span>
                <div>
                  <div className="flex items-center gap-2">
                    <span className={`inline-block rounded px-2 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider border ${severityBg}`}>
                      {severity}
                    </span>
                    {activePopup.department_designated && (
                      <span className="rounded bg-[#F4F4F1] border border-[#E1E3DE] px-2 py-0.5 text-[10px] font-mono font-bold text-[#656A66] uppercase">
                        DEPT: {activePopup.department_designated}
                      </span>
                    )}
                    <span className="text-[11px] font-mono text-[#656A66]">{formattedTime}</span>
                  </div>
                  <h2 id="issue-alert-title" className="mt-1 text-lg font-bold tracking-tight text-[#252A27]">
                    {formattedTitle}
                  </h2>
                </div>
              </div>

              <button
                type="button"
                onClick={dismissPopup}
                aria-label="Close alert"
                className="rounded-lg p-2 text-[#656A66] hover:bg-[#F4F4F1] hover:text-[#252A27] transition-colors border border-transparent hover:border-[#E1E3DE]"
              >
                <X size={16} />
              </button>
            </div>

            <div className="mt-4 rounded-xl border border-[#E1E3DE] bg-[#F4F4F1]/60 p-4 text-[13px] leading-relaxed text-[#252A27] font-sans">
              <p>{activePopup.message}</p>
              {activePopup.issue_id && (
                <p className="mt-2.5 font-mono text-[11px] text-[#656A66] font-medium flex items-center gap-2">
                  <span className="text-[#656A66]">REF:</span>
                  <span className="text-[#252A27] font-bold bg-white border border-[#E1E3DE] px-2 py-0.5 rounded">{activePopup.issue_id}</span>
                </p>
              )}
            </div>

            <div className="mt-6 flex flex-wrap items-center justify-end gap-2.5">
              <button
                type="button"
                onClick={dismissPopup}
                className="rounded-lg border border-[#E1E3DE] bg-[#F4F4F1] px-4 py-2 text-xs font-mono font-bold uppercase tracking-wider text-[#656A66] hover:text-[#252A27] hover:bg-[#E1E3DE]/40 transition-all"
              >
                Dismiss
              </button>

              <button
                type="button"
                onClick={handleViewIssue}
                className="rounded-lg border border-[#E1E3DE] bg-white px-4 py-2 text-xs font-mono font-bold uppercase tracking-wider text-[#252A27] hover:border-[#252A27] transition-all flex items-center gap-1.5"
              >
                <ExternalLink size={13} />
                View Issue
              </button>

              <button
                type="button"
                onClick={handleAcknowledge}
                className={`rounded-lg px-5 py-2 text-xs font-mono font-bold uppercase tracking-wider text-white transition-all flex items-center gap-1.5 shadow-sm active:scale-[0.98] ${
                  isEmergency ? 'bg-[#DC3030] hover:bg-[#B92424]' : 'bg-[#282D2A] hover:bg-[#3A403B]'
                }`}
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
