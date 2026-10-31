import React, { useState } from 'react'
import { ShieldCheck, Clock, AlertTriangle, X, CheckCircle2 } from 'lucide-react'
import Button from '@/components/common/Button'
import { overrideTaskWindow } from '@/api'

export default function ControllerOverrideModal({
  isOpen,
  onClose,
  task,
  onOverrideSuccess,
}) {
  if (!isOpen || !task) return null

  const taskId = task.task_id || task.id
  const [overrideType, setOverrideType] = useState('EXTEND_WINDOW')
  const [extensionMinutes, setExtensionMinutes] = useState(30)
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [errorMsg, setErrorMsg] = useState(null)

  const handleSubmit = async (e) => {
    e?.preventDefault()
    if (!reason || reason.trim().length < 5) {
      setErrorMsg('A specific operational reason (minimum 5 characters) is required by railway audit policy.')
      return
    }

    setSubmitting(true)
    setErrorMsg(null)
    try {
      const res = await overrideTaskWindow(taskId, {
        override_type: overrideType,
        reason: reason.trim(),
        extension_minutes: parseInt(extensionMinutes, 10),
      })
      onOverrideSuccess?.(res.data)
      onClose()
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || err.message || 'Failed to apply controller override')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-lg rounded-xl border border-[#D99A2B]/40 bg-surface p-6 shadow-2xl">
        <div className="flex items-start justify-between border-b border-hair pb-3.5">
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#D99A2B]/15 text-[#D99A2B]">
              <ShieldCheck size={22} />
            </div>
            <div>
              <h3 className="text-base font-bold text-ink">Controller Schedule Override</h3>
              <p className="text-xs font-mono text-muted">Authorized Railway Controller Protocol</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded p-1 text-muted hover:text-ink hover:bg-raised transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="my-4 space-y-4 text-xs">
          {errorMsg && (
            <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-rose-300">
              <p className="font-semibold">{errorMsg}</p>
            </div>
          )}

          {/* Current schedule banner */}
          <div className="rounded-lg border border-line bg-surface/50 p-3 space-y-1.5 font-mono">
            <div className="flex items-center justify-between text-muted text-[11px]">
              <span>TASK ID: <strong className="text-ink">{taskId}</strong></span>
              <span>DEPT: <strong className="text-ink">{task.department || 'ENGINEERING'}</strong></span>
            </div>
            <div className="flex items-center justify-between text-muted text-[11px]">
              <span>STATUS: <strong className="text-[#D99A2B]">{task.status}</strong></span>
              <span>SECTION: <strong className="text-ink">{task.section_id || 'NDLS-GZB'}</strong></span>
            </div>
            {task.designated_period_clock && (
              <div className="pt-1.5 border-t border-hair flex items-center justify-between text-ink">
                <span className="text-muted">APPROVED WINDOW:</span>
                <span className="font-bold">{task.designated_period_clock}</span>
              </div>
            )}
          </div>

          {/* Override Type */}
          <div>
            <label className="block text-xs font-semibold text-ink mb-1.5">
              Select Override Action:
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setOverrideType('EARLY_START')}
                className={`p-2.5 rounded-lg border text-left transition-all ${
                  overrideType === 'EARLY_START'
                    ? 'border-[#D99A2B] bg-[#FFF3D9]/20 text-ink font-semibold ring-1 ring-[#D99A2B]'
                    : 'border-line bg-surface/40 text-muted hover:text-ink'
                }`}
              >
                <div className="font-bold text-xs">Approve Early Start</div>
                <div className="text-[10px] text-muted mt-0.5">Authorizes technician to start prior to window</div>
              </button>

              <button
                type="button"
                onClick={() => setOverrideType('LATE_START')}
                className={`p-2.5 rounded-lg border text-left transition-all ${
                  overrideType === 'LATE_START'
                    ? 'border-[#D99A2B] bg-[#FFF3D9]/20 text-ink font-semibold ring-1 ring-[#D99A2B]'
                    : 'border-line bg-surface/40 text-muted hover:text-ink'
                }`}
              >
                <div className="font-bold text-xs">Approve Late Start</div>
                <div className="text-[10px] text-muted mt-0.5">Re-opens expired window (+30 min deadline)</div>
              </button>

              <button
                type="button"
                onClick={() => setOverrideType('EXTEND_WINDOW')}
                className={`p-2.5 rounded-lg border text-left transition-all ${
                  overrideType === 'EXTEND_WINDOW'
                    ? 'border-[#D99A2B] bg-[#FFF3D9]/20 text-ink font-semibold ring-1 ring-[#D99A2B]'
                    : 'border-line bg-surface/40 text-muted hover:text-ink'
                }`}
              >
                <div className="font-bold text-xs">Extend Window</div>
                <div className="text-[10px] text-muted mt-0.5">Grants additional duration to prevent overrun</div>
              </button>

              <button
                type="button"
                onClick={() => setOverrideType('FORCE_START')}
                className={`p-2.5 rounded-lg border text-left transition-all ${
                  overrideType === 'FORCE_START'
                    ? 'border-[#DC3030] bg-rose-500/10 text-ink font-semibold ring-1 ring-[#DC3030]'
                    : 'border-line bg-surface/40 text-muted hover:text-ink'
                }`}
              >
                <div className="font-bold text-xs text-[#DC3030]">Emergency Force Start</div>
                <div className="text-[10px] text-muted mt-0.5">Immediately marks task IN PROGRESS</div>
              </button>
            </div>
          </div>

          {/* Extension duration if EXTEND_WINDOW */}
          {overrideType === 'EXTEND_WINDOW' && (
            <div>
              <label className="block text-xs font-semibold text-ink mb-1.5">
                Extension Duration (Minutes):
              </label>
              <div className="flex gap-2 font-mono">
                {[15, 30, 45, 60].map((mins) => (
                  <button
                    key={mins}
                    type="button"
                    onClick={() => setExtensionMinutes(mins)}
                    className={`flex-1 py-1.5 rounded-lg border text-xs font-bold transition-all ${
                      extensionMinutes === mins
                        ? 'border-[#D99A2B] bg-[#D99A2B] text-white'
                        : 'border-line bg-surface text-muted hover:text-ink'
                    }`}
                  >
                    +{mins}m
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Mandatory Reason */}
          <div>
            <label className="block text-xs font-semibold text-ink mb-1.5">
              Operational Justification (Logged to Railway Audit): <span className="text-rose-500">*</span>
            </label>
            <textarea
              rows={3}
              required
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="E.g., Train #12004 held at previous station; corridor free for early track possession."
              className="w-full rounded-lg border border-line bg-surface p-2.5 font-sans text-xs text-ink outline-none focus:border-[#D99A2B]"
            />
            <p className="text-[10px] text-muted mt-1">
              Recorded in task history with your controller email, UTC timestamp, and previous vs. new schedule.
            </p>
          </div>

          <div className="flex items-center justify-end gap-2.5 border-t border-hair pt-3.5">
            <Button variant="ghost" onClick={onClose} disabled={submitting}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant="default"
              disabled={submitting || !reason || reason.trim().length < 5}
              className="flex items-center gap-1.5 bg-[#D99A2B] hover:bg-[#c28723] text-white"
            >
              <ShieldCheck size={14} />
              <span>{submitting ? 'Authorizing...' : 'Authorize Override'}</span>
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
