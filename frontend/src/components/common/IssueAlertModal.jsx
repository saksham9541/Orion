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
    <div
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="issue-alert-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200"
    >
      <div className="relative w-full max-w-lg rounded-xl border border-line bg-surface p-6 shadow-2xl">
        {/* Pulsing indicator for Emergency */}
        {isEmergency && (
          <div className="absolute -top-3 left-6 flex items-center gap-1.5 rounded-full bg-red-600 px-3 py-0.5 text-[11px] font-bold uppercase tracking-wider text-white shadow-md animate-pulse">
            <AlertCircle size={13} />
            Immediate Safety Alert
          </div>
        )}

        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border ${severityBg}`}>
              {isEmergency ? <AlertCircle size={22} /> : <AlertTriangle size={22} />}
            </span>
            <div>
              <div className="flex items-center gap-2">
                <span className={`inline-block rounded px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide border ${severityBg}`}>
                  {severity}
                </span>
                {activePopup.department_designated && (
                  <span className="rounded bg-raised px-2 py-0.5 text-[11px] font-semibold text-muted uppercase">
                    Dept: {activePopup.department_designated}
                  </span>
                )}
                <span className="text-[12px] text-faint">{formattedTime}</span>
              </div>
              <h2 id="issue-alert-title" className="mt-1 text-[18px] font-bold text-ink">
                {activePopup.title}
              </h2>
            </div>
          </div>

          <button
            type="button"
            onClick={dismissPopup}
            aria-label="Close alert"
            className="rounded p-1 text-faint hover:bg-raised hover:text-ink transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        <div className="mt-4 rounded-lg border border-line/60 bg-raised/50 p-3.5 text-[14px] leading-relaxed text-ink/90">
          <p>{activePopup.message}</p>
          {activePopup.issue_id && (
            <p className="mt-2 font-mono text-[12px] text-muted font-medium">
              Reference: <span className="text-ink">{activePopup.issue_id}</span>
            </p>
          )}
        </div>

        <div className="mt-6 flex flex-wrap items-center justify-end gap-3">
          <button
            type="button"
            onClick={dismissPopup}
            className="btn-quiet px-4 py-2 text-[13px] font-medium"
          >
            Dismiss
          </button>

          <button
            type="button"
            onClick={handleViewIssue}
            className="btn-quiet px-4 py-2 text-[13px] font-medium flex items-center gap-2"
          >
            <ExternalLink size={15} />
            View Issue
          </button>

          <button
            type="button"
            onClick={handleAcknowledge}
            className="btn-action px-5 py-2 text-[13px] font-bold uppercase tracking-wider flex items-center gap-2 shadow-sm"
          >
            <CheckCircle size={15} />
            Acknowledge
          </button>
        </div>
      </div>
    </div>
  )
}
