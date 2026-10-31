import React, { useEffect, useState } from 'react'
import { AlertTriangle, Clock, RefreshCw, X, ShieldAlert } from 'lucide-react'
import Button from '@/components/common/Button'

/**
 * CannotStartModal
 *
 * Enforced popup when a technician or department user attempts to start a task outside
 * the approved start window or when unapproved (HTTP 409).
 *
 * Displays:
 * - Title: "Cannot start now"
 * - Warning: "Starting outside the approved period can disrupt train running."
 * - Designated start period in 12-hour AM/PM IST clock times
 * - Planned finish by clock time
 * - Current server time (IST)
 * - Specific reasons:
 *   - WINDOW_TOO_EARLY: Real-time countdown until the window opens
 *   - WINDOW_TOO_LATE: Window ended + "Request new window" action
 *   - WINDOW_NOT_APPROVED: "This task has not been approved by the controller."
 */
export default function CannotStartModal({
  isOpen,
  onClose,
  errorData,
  onRequestNewWindow,
  onOpenControllerOverride,
}) {
  if (!isOpen || !errorData) return null

  const {
    code = 'START_BLOCKED',
    message = 'Execution start is blocked outside approved window.',
    server_now_clock,
    designated_period_clock,
    planned_end_clock,
    seconds_until_open: initialSeconds = 0,
    start_allowed_from_ist,
    start_allowed_until_ist,
    planned_end_ist,
  } = errorData

  const [secondsRemaining, setSecondsRemaining] = useState(Math.max(0, Math.floor(initialSeconds)))

  useEffect(() => {
    if (code !== 'WINDOW_TOO_EARLY' || secondsRemaining <= 0) return
    const interval = setInterval(() => {
      setSecondsRemaining((prev) => Math.max(0, prev - 1))
    }, 1000)
    return () => clearInterval(interval)
  }, [code, secondsRemaining])

  const formatCountdown = (totalSec) => {
    const mins = Math.floor(totalSec / 60)
    const secs = totalSec % 60
    return `${mins}m ${secs < 10 ? '0' : ''}${secs}s`
  }

  const periodDisplay = designated_period_clock || 
    (start_allowed_from_ist && start_allowed_until_ist ? `${start_allowed_from_ist} – ${start_allowed_until_ist}` : 'Not designated')
  const finishDisplay = planned_end_clock || planned_end_ist || 'N/A'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-md rounded-xl border border-rose-500/40 bg-surface p-6 shadow-2xl">
        <div className="flex items-start justify-between border-b border-hair pb-3.5">
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-rose-500/15 text-rose-500">
              <ShieldAlert size={22} />
            </div>
            <div>
              <h3 className="text-base font-bold text-ink">Cannot start now</h3>
              <p className="text-xs text-rose-500 font-medium">Start Gate Enforcement</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded p-1 text-muted hover:text-ink hover:bg-raised transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        <div className="my-4 space-y-4 text-xs">
          <div className="rounded-lg border border-rose-500/20 bg-rose-500/10 p-3 text-rose-300">
            <p className="font-semibold text-rose-200">
              Starting outside the approved period can disrupt train running.
            </p>
            <p className="mt-1 text-muted leading-relaxed">
              {message}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2 text-ink">
            <div className="rounded-lg border border-line bg-surface/50 p-2.5">
              <span className="text-[11px] text-muted flex items-center gap-1">
                <Clock size={12} className="text-accent" /> Designated Period
              </span>
              <p className="font-mono font-bold text-sm mt-1 text-ink">{periodDisplay}</p>
            </div>

            <div className="rounded-lg border border-line bg-surface/50 p-2.5">
              <span className="text-[11px] text-muted flex items-center gap-1">
                <Clock size={12} className="text-emerald-500" /> Planned Finish
              </span>
              <p className="font-mono font-bold text-sm mt-1 text-ink">{finishDisplay}</p>
            </div>
          </div>

          <div className="flex items-center justify-between rounded-lg border border-line bg-surface/30 px-3 py-2 font-mono">
            <span className="text-muted text-[11px]">Current Server Time (IST):</span>
            <span className="font-bold text-ink">{server_now_clock || 'Just now'}</span>
          </div>

          {code === 'WINDOW_TOO_EARLY' && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-amber-200">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-amber-300">Window opens in:</span>
                <span className="font-mono text-base font-bold text-amber-100">
                  {formatCountdown(secondsRemaining)}
                </span>
              </div>
              <p className="text-[11px] text-muted mt-1">
                Please standby on site with tools prepared until the block start time.
              </p>
            </div>
          )}

          {code === 'WINDOW_TOO_LATE' && (
            <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-rose-200">
              <span className="font-semibold text-rose-300 block">The approved start window has ended.</span>
              <p className="text-[11px] text-muted mt-1">
                Train dispatching cannot hold the section past tolerance. Please request a new window through your supervisor.
              </p>
            </div>
          )}

          {code === 'WINDOW_NOT_APPROVED' && (
            <div className="rounded-lg border border-line bg-raised p-3 text-muted">
              <p className="font-semibold text-ink">Window Not Approved</p>
              <p className="text-[11px] mt-1">
                This task has not been approved by the controller. Execution is strictly locked until formal block grant.
              </p>
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2.5 border-t border-hair pt-3.5">
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>

          {onOpenControllerOverride && (
            <Button
              variant='secondary'
              onClick={() => {
                onClose()
                onOpenControllerOverride()
              }}
              className='flex items-center gap-1.5 border-[#D99A2B] text-[#D99A2B] hover:bg-[#D99A2B]/10'
            >
              <ShieldAlert size={13} />
              <span>Controller Override</span>
            </Button>
          )}

          {code === 'WINDOW_TOO_LATE' && onRequestNewWindow && (
            <Button
              variant="default"
              onClick={() => {
                onClose()
                onRequestNewWindow()
              }}
              className="flex items-center gap-1.5"
            >
              <RefreshCw size={13} />
              <span>Request new window</span>
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
