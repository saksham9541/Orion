import { useState, useRef, useEffect } from 'react'
import { Bell, Check, CheckCheck, AlertTriangle, AlertCircle, ExternalLink, X } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useNotifications } from '@/state/NotificationContext'
import { useAppState } from '@/state/AppState'
import { useLiveSync } from '@/state/LiveSyncStore'

export default function NotificationBell() {
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef(null)
  const navigate = useNavigate()
  const { currentUser } = useAppState()
  const { notifications, unreadCount, markAsRead, acknowledge, isConnected } = useNotifications()
  const { acknowledge: liveAcknowledge, decline: liveDecline } = useLiveSync()

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleNotificationClick = (notif) => {
    if (!notif.read_at) {
      markAsRead(notif.id)
    }
    setIsOpen(false)
    const issueId = notif.issue_id || ''
    const roleId = currentUser?.id

    if (roleId && roleId !== 'admin') {
      navigate(`/${roleId}${issueId ? `?issue=${issueId}` : ''}`)
    } else if (roleId === 'admin') {
      navigate(issueId ? `/admin?issue=${issueId}` : '/admin')
    } else {
      navigate(issueId ? `/tasks?search=${issueId}` : '/tasks')
    }
  }

  const handleAcknowledge = async (e, notif) => {
    e.stopPropagation()
    const targetTaskId = notif.issue_id || notif.task_id
    if (targetTaskId) {
      const res = await liveAcknowledge(targetTaskId)
      if (!res.success) {
        if (res.error?.toLowerCase().includes('already acknowledged')) {
          markAsRead(notif.id)
        } else {
          alert(res.error || 'Acknowledgement rejected')
        }
      } else {
        markAsRead(notif.id)
      }
    } else {
      acknowledge(notif.id)
    }
  }

  const handleDecline = async (e, notif) => {
    e.stopPropagation()
    const targetTaskId = notif.issue_id || notif.task_id
    if (!targetTaskId) return
    const reason = window.prompt(
      'Enter decline reason for this defect report:',
      'Invalid or duplicate defect report'
    )
    if (!reason || !reason.trim()) return
    const res = await liveDecline(targetTaskId, reason.trim())
    if (!res.success) {
      alert(res.error || 'Decline rejected')
    }
  }

  const handleMarkAllRead = () => {
    notifications.forEach((n) => {
      if (!n.read_at) markAsRead(n.id)
    })
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        aria-label={`Notifications, ${unreadCount} unread`}
        className="btn-quiet relative flex h-9 w-9 items-center justify-center rounded-lg p-0 transition-colors"
      >
        <Bell size={17} className={unreadCount > 0 ? 'text-ink' : 'text-muted'} />
        {/* Live connection dot */}
        <span
          className={`absolute bottom-1 right-1 h-2 w-2 rounded-full border border-surface ${
            isConnected ? 'bg-emerald-500' : 'bg-amber-500'
          }`}
          title={isConnected ? 'Live WebSocket Active' : 'Connecting to notification server...'}
        />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-bold text-white shadow-sm animate-pulse">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 sm:w-96 rounded-xl border border-line bg-surface shadow-2xl z-50 overflow-hidden animate-in fade-in duration-150">
          <div className="flex items-center justify-between border-b border-line px-4 py-3 bg-surface">
            <div className="flex items-center gap-2">
              <span className="text-[14px] font-bold text-ink">Notifications</span>
              {unreadCount > 0 && (
                <span className="rounded-full bg-red-500/10 px-2 py-0.5 text-[11px] font-bold text-red-500">
                  {unreadCount} new
                </span>
              )}
            </div>

            <div className="flex items-center gap-2">
              <span
                className={`h-2 w-2 rounded-full ${isConnected ? 'bg-emerald-500' : 'bg-amber-500'}`}
                title={isConnected ? 'Live WebSocket Connected' : 'Reconnecting...'}
              />
              {unreadCount > 0 && (
                <button
                  type="button"
                  onClick={handleMarkAllRead}
                  className="text-[12px] font-medium text-muted hover:text-ink flex items-center gap-1"
                >
                  <CheckCheck size={14} />
                  Mark all read
                </button>
              )}
            </div>
          </div>

          <div className="max-h-[380px] overflow-y-auto divide-y divide-line/60">
            {notifications.length === 0 ? (
              <div className="py-8 text-center text-muted">
                <Bell size={24} className="mx-auto mb-2 opacity-30" />
                <p className="text-[13px]">No notifications yet</p>
                <p className="text-[11px] text-faint">Issue alerts and updates will appear here</p>
              </div>
            ) : (
              notifications.map((notif) => {
                const isUnread = !notif.read_at
                const isEmergency = notif.severity === 'EMERGENCY'
                const isHigh = notif.severity === 'HIGH'

                return (
                  <div
                    key={notif.id}
                    onClick={() => handleNotificationClick(notif)}
                    className={`group flex items-start gap-3 p-3.5 transition-colors cursor-pointer ${
                      isUnread ? 'bg-raised/60 hover:bg-raised' : 'hover:bg-raised/30'
                    }`}
                  >
                    <span
                      className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md border ${
                        isEmergency
                          ? 'border-red-500/30 bg-red-500/10 text-red-500'
                          : isHigh
                          ? 'border-amber-500/30 bg-amber-500/10 text-amber-500'
                          : 'border-blue-500/30 bg-blue-500/10 text-blue-500'
                      }`}
                    >
                      {isEmergency ? <AlertCircle size={15} /> : <AlertTriangle size={15} />}
                    </span>

                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-1">
                        <p className="text-[13px] font-semibold text-ink truncate">{notif.title}</p>
                        <span className="shrink-0 text-[10px] text-faint">
                          {notif.created_at
                            ? new Date(notif.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                            : ''}
                        </span>
                      </div>

                      <p className="mt-0.5 text-[12px] text-muted line-clamp-2">{notif.message}</p>

                      <div className="mt-2 flex items-center justify-between gap-2">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-faint">
                          {notif.severity} {notif.department_designated ? `• ${notif.department_designated}` : ''}
                        </span>

                        {(notif.acknowledged_at || notif.action_taken === 'ACKNOWLEDGED' || notif.resolved_by) ? (
                          <span className="rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 px-2 py-0.5 text-[11px] font-semibold flex items-center gap-1 shadow-sm">
                            <Check size={12} />
                            <span>Acknowledged{notif.resolved_by ? ` by ${notif.resolved_by.split('@')[0]}` : ''}</span>
                          </span>
                        ) : notif.action_taken === 'DECLINED' ? (
                          <span className="rounded bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/30 px-2 py-0.5 text-[11px] font-semibold flex items-center gap-1 shadow-sm">
                            <X size={12} />
                            <span>Declined</span>
                          </span>
                        ) : (
                          <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
                            <button
                              type="button"
                              onClick={(e) => handleAcknowledge(e, notif)}
                              className="rounded bg-emerald-600 hover:bg-emerald-700 text-white px-2 py-0.5 text-[11px] font-semibold flex items-center gap-1 transition-colors shadow-sm"
                              title="Acknowledge defect report"
                            >
                              <Check size={12} />
                              Ack
                            </button>
                            {(notif.issue_id || notif.task_id) && (
                              <button
                                type="button"
                                onClick={(e) => handleDecline(e, notif)}
                                className="rounded bg-surface px-2 py-0.5 text-[11px] font-medium border border-line text-muted hover:text-red-600 hover:border-red-300 flex items-center gap-0.5 transition-colors"
                                title="Decline defect report"
                              >
                                <X size={12} />
                                Decline
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    </div>

                    {isUnread && (
                      <span className="mt-2 h-2 w-2 shrink-0 rounded-full bg-blue-500" aria-label="Unread" />
                    )}
                  </div>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}
