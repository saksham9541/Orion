import { useState, useEffect, useCallback } from 'react'
import {
  fetchMyBlocks,
  respondToBlock,
  fetchSectionWindows,
  fetchTaskAffectedTrains,
} from '@/api'
import {
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  RotateCcw,
  ShieldAlert,
  ChevronRight,
  Eye,
  Train,
  Layers,
} from 'lucide-react'

const REJECT_REASONS = [
  { code: 'RESOURCE_UNAVAILABLE', label: 'Resource / gang unavailable' },
  { code: 'SAFETY_CONCERN', label: 'Safety / weather condition concern' },
  { code: 'INSUFFICIENT_DURATION', label: 'Insufficient window duration for task' },
  { code: 'INTER_DEPARTMENT_CONFLICT', label: 'Inter-department coordination conflict' },
  { code: 'EQUIPMENT_BREAKDOWN', label: 'Specialized machinery / tower wagon unavailable' },
  { code: 'OPERATIONAL_PRIORITY', label: 'Conflicting operational priority' },
]

export default function DepartmentBlockReview({
  planId,
  department,
  onStatusChange,
}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [actingBlockId, setActingBlockId] = useState(null)

  // Dialog states for Reject / Counter
  const [rejectDialogBlock, setRejectDialogBlock] = useState(null)
  const [rejectReasonCode, setRejectReasonCode] = useState(REJECT_REASONS[0].code)
  const [rejectReasonText, setRejectReasonText] = useState('')
  const [controllerOverride, setControllerOverride] = useState(false)

  // Counter proposal state
  const [counterDialogBlock, setCounterDialogBlock] = useState(null)
  const [availableWindows, setAvailableWindows] = useState([])
  const [selectedCounterWindow, setSelectedCounterWindow] = useState('')

  // Impact preview state
  const [previewImpact, setPreviewImpact] = useState(null)
  const [loadingImpact, setLoadingImpact] = useState(false)

  const loadBlocks = useCallback(async () => {
    if (!planId) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetchMyBlocks(planId, department)
      setData(res.data)
      if (onStatusChange && res.data.plan_status) {
        onStatusChange(res.data.plan_status)
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load department blocks')
    } finally {
      setLoading(false)
    }
  }, [planId, department, onStatusChange])

  useEffect(() => {
    loadBlocks()
  }, [loadBlocks])

  // Handle Accept
  const handleAccept = async (blockId) => {
    setActingBlockId(blockId)
    try {
      await respondToBlock(planId, blockId, {
        decision: 'ACCEPT',
        department: department,
      })
      await loadBlocks()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to accept block')
    } finally {
      setActingBlockId(null)
    }
  }

  // Handle Reject Submit
  const handleRejectSubmit = async () => {
    if (!rejectDialogBlock) return
    if (!rejectReasonText.trim()) {
      alert('Please enter an explanatory reason text for rejection.')
      return
    }

    setActingBlockId(rejectDialogBlock.block_id)
    try {
      await respondToBlock(planId, rejectDialogBlock.block_id, {
        decision: 'REJECT',
        reason_code: rejectReasonCode,
        reason: rejectReasonText,
        controller_override: controllerOverride,
        department: department,
      })
      setRejectDialogBlock(null)
      setRejectReasonText('')
      await loadBlocks()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to reject block')
    } finally {
      setActingBlockId(null)
    }
  }

  // Open Counter dialog & load alternative windows
  const openCounterDialog = async (block) => {
    setCounterDialogBlock(block)
    setSelectedCounterWindow('')
    try {
      const res = await fetchSectionWindows(block.section_id, block.date)
      const wins = res.data?.windows || []
      setAvailableWindows(wins.filter((w) => w.window_id !== block.window_id))
    } catch {
      setAvailableWindows([])
    }
  }

  // Handle Counter Submit
  const handleCounterSubmit = async () => {
    if (!counterDialogBlock || !selectedCounterWindow) {
      alert('Please select an alternative candidate window.')
      return
    }

    setActingBlockId(counterDialogBlock.block_id)
    try {
      await respondToBlock(planId, counterDialogBlock.block_id, {
        decision: 'COUNTER',
        counter_window_id: selectedCounterWindow,
        reason: `Proposed shift to candidate window ${selectedCounterWindow}`,
        department: department,
      })
      setCounterDialogBlock(null)
      await loadBlocks()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to submit counter-proposal')
    } finally {
      setActingBlockId(null)
    }
  }

  // Preview impact of a block
  const handlePreviewImpact = async (block) => {
    const firstTask = block.my_tasks?.[0]
    if (!firstTask) return
    setLoadingImpact(true)
    setPreviewImpact(null)
    try {
      const res = await fetchTaskAffectedTrains(firstTask.task_id, block.window_id)
      setPreviewImpact(res.data)
    } catch (err) {
      alert(err.response?.data?.detail || 'Could not fetch impact preview')
    } finally {
      setLoadingImpact(false)
    }
  }

  if (loading) {
    return (
      <div className="flex h-32 items-center justify-center text-xs text-muted">
        <Clock className="mr-2 h-4 w-4 animate-spin text-info" />
        Loading department block proposals...
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-600">
        <AlertTriangle className="mr-1.5 inline h-4 w-4" /> {error}
      </div>
    )
  }

  const blocks = data?.blocks || []
  const planStatus = data?.plan_status || 'PROPOSED'

  return (
    <div className="space-y-4">
      {/* Header & Status Banner */}
      <div className="flex items-center justify-between rounded-2xl border border-line bg-surface/80 p-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-ink">Department Block Governance</h3>
            <span
              className={`rounded-full px-2.5 py-0.5 font-mono text-[10px] font-bold uppercase border ${
                planStatus === 'APPROVED'
                  ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-600'
                  : planStatus === 'CONFLICT'
                  ? 'border-rose-500/40 bg-rose-500/15 text-rose-600 animate-pulse'
                  : planStatus === 'READY_FOR_CONTROLLER'
                  ? 'border-purple-500/40 bg-purple-500/15 text-purple-600'
                  : 'border-amber-500/40 bg-amber-500/15 text-amber-600'
              }`}
            >
              Plan State: {planStatus}
            </span>
          </div>
          <p className="mt-1 text-xs text-muted">
            Review proposed blocks for <strong className="text-ink">{data?.department}</strong>.
            Coordinate shared possessions with other departments and submit decisions.
          </p>
        </div>

        <button
          onClick={loadBlocks}
          className="rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-medium text-muted hover:text-ink hover:bg-raised transition-colors flex items-center gap-1.5"
        >
          <RotateCcw className="h-3.5 w-3.5" /> Refresh
        </button>
      </div>

      {blocks.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-line p-8 text-center text-xs text-muted">
          No scheduled blocks for this department in plan {planId}.
        </div>
      ) : (
        <div className="space-y-3">
          {blocks.map((block) => {
            const resp = block.my_response
            const isActing = actingBlockId === block.block_id

            return (
              <div
                key={block.block_id}
                className={`rounded-2xl border transition-all p-4 ${
                  resp?.decision === 'ACCEPT'
                    ? 'border-emerald-500/40 bg-emerald-500/[0.04]'
                    : resp?.decision === 'REJECT'
                    ? 'border-rose-500/40 bg-rose-500/[0.04]'
                    : resp?.decision === 'COUNTER'
                    ? 'border-amber-500/40 bg-amber-500/[0.04]'
                    : 'border-line bg-surface/70 hover:border-line/80'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-ink">
                        {block.block_id}
                      </span>
                      <span className="rounded bg-raised px-2 py-0.5 font-mono text-[10px] text-muted">
                        {block.section_name} ({block.section_id})
                      </span>
                      {block.is_merged && (
                        <span className="flex items-center gap-1 rounded bg-purple-500/15 px-2 py-0.5 text-[10px] font-bold text-purple-600">
                          <Layers className="h-3 w-3" /> Shared Possession
                        </span>
                      )}
                      {block.is_safety_critical && (
                        <span className="flex items-center gap-1 rounded bg-rose-500/15 px-2 py-0.5 text-[10px] font-bold text-rose-600">
                          <ShieldAlert className="h-3 w-3" /> Safety Critical
                        </span>
                      )}
                    </div>

                    <div className="mt-1 flex items-center gap-4 text-xs text-muted">
                      <span>Date: <strong className="text-ink">{block.date}</strong></span>
                      <span>Window: <strong className="text-ink">{block.start_time} - {block.end_time}</strong> ({block.duration_hours}h)</span>
                      <span>Disruption: <strong className="text-ink">{block.trains_affected} trains</strong> ({block.cumulative_delay_minutes}m delay)</span>
                    </div>
                  </div>

                  {/* Decision status badge or action buttons */}
                  <div className="flex items-center gap-2">
                    {resp ? (
                      <div className="flex items-center gap-1.5 rounded-xl border border-line bg-raised px-3 py-1.5 text-xs font-bold">
                        {resp.decision === 'ACCEPT' && (
                          <span className="text-emerald-600 flex items-center gap-1">
                            <CheckCircle2 className="h-4 w-4" /> ACCEPTED
                          </span>
                        )}
                        {resp.decision === 'REJECT' && (
                          <span className="text-rose-600 flex items-center gap-1">
                            <XCircle className="h-4 w-4" /> REJECTED: {resp.reason_code}
                          </span>
                        )}
                        {resp.decision === 'COUNTER' && (
                          <span className="text-amber-600 flex items-center gap-1">
                            <RotateCcw className="h-4 w-4" /> COUNTER ({resp.counter_window_id})
                          </span>
                        )}
                      </div>
                    ) : (
                      <div className="flex items-center gap-1.5">
                        <button
                          disabled={isActing}
                          onClick={() => handleAccept(block.block_id)}
                          className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-emerald-700 disabled:opacity-50 transition-colors flex items-center gap-1"
                        >
                          <CheckCircle2 className="h-3.5 w-3.5" /> Accept
                        </button>

                        <button
                          disabled={isActing}
                          onClick={() => setRejectDialogBlock(block)}
                          className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-1.5 text-xs font-bold text-rose-600 hover:bg-rose-500/20 disabled:opacity-50 transition-colors flex items-center gap-1"
                        >
                          <XCircle className="h-3.5 w-3.5" /> Reject
                        </button>

                        <button
                          disabled={isActing}
                          onClick={() => openCounterDialog(block)}
                          className="rounded-lg border border-line bg-raised px-3 py-1.5 text-xs font-bold text-ink hover:bg-line/60 disabled:opacity-50 transition-colors flex items-center gap-1"
                        >
                          <RotateCcw className="h-3.5 w-3.5" /> Counter
                        </button>
                      </div>
                    )}

                    <button
                      onClick={() => handlePreviewImpact(block)}
                      className="rounded-lg border border-line bg-surface p-1.5 text-muted hover:text-ink hover:bg-raised transition-colors"
                      title="Preview Traffic Impact"
                    >
                      <Eye className="h-4 w-4" />
                    </button>
                  </div>
                </div>

                {/* Tasks inside block */}
                <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                  <div className="rounded-xl border border-line/50 bg-deep/30 p-2.5">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-muted mb-1">
                      My Department Tasks ({block.my_tasks.length})
                    </p>
                    <div className="space-y-1">
                      {block.my_tasks.map((t) => (
                        <div key={t.task_id} className="flex items-center justify-between">
                          <span className="font-mono text-ink">{t.task_id}</span>
                          <span className="text-muted truncate max-w-[200px]">{t.defect_category}</span>
                          <span className="text-faint">{t.estimated_duration_hours}h</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {block.shared_tasks.length > 0 && (
                    <div className="rounded-xl border border-purple-500/30 bg-purple-500/[0.04] p-2.5">
                      <p className="text-[10px] font-bold uppercase tracking-wider text-purple-600 mb-1">
                        Shared Coordination Tasks ({block.shared_tasks.length})
                      </p>
                      <div className="space-y-1">
                        {block.shared_tasks.map((t) => (
                          <div key={t.task_id} className="flex items-center justify-between">
                            <span className="font-bold text-purple-700 dark:text-purple-300">
                              [{t.department}]
                            </span>
                            <span className="font-mono text-muted">{t.task_id}</span>
                            <span className="text-faint truncate max-w-[160px]">{t.defect_category}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Reject Modal */}
      {rejectDialogBlock && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl border border-line bg-surface p-6 shadow-2xl">
            <h4 className="text-base font-bold text-ink flex items-center gap-2">
              <XCircle className="h-5 w-5 text-rose-600" />
              Reject Scheduled Block ({rejectDialogBlock.block_id})
            </h4>

            {rejectDialogBlock.is_safety_critical && (
              <div className="mt-3 rounded-xl border border-rose-500/40 bg-rose-500/10 p-3 text-xs text-rose-600">
                <AlertTriangle className="mr-1.5 inline h-4 w-4" />
                <strong>Safety Critical Guard:</strong> This block contains safety-critical defects. Rejection requires Controller authorization override.
                <div className="mt-2 flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="override_check"
                    checked={controllerOverride}
                    onChange={(e) => setControllerOverride(e.target.checked)}
                    className="rounded border-rose-500"
                  />
                  <label htmlFor="override_check" className="font-bold text-ink">
                    I have Controller Authorization Override
                  </label>
                </div>
              </div>
            )}

            <div className="mt-4 space-y-3 text-xs">
              <div>
                <label className="font-bold text-ink">Reason Code *</label>
                <select
                  value={rejectReasonCode}
                  onChange={(e) => setRejectReasonCode(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-line bg-raised px-3 py-2 text-ink"
                >
                  {REJECT_REASONS.map((r) => (
                    <option key={r.code} value={r.code}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="font-bold text-ink">Explanatory Reason *</label>
                <textarea
                  rows={3}
                  value={rejectReasonText}
                  onChange={(e) => setRejectReasonText(e.target.value)}
                  placeholder="Detail operational constraints requiring block rejection..."
                  className="mt-1 w-full rounded-xl border border-line bg-raised px-3 py-2 text-ink"
                />
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <button
                onClick={() => setRejectDialogBlock(null)}
                className="rounded-lg border border-line bg-surface px-4 py-2 text-xs font-medium text-muted hover:text-ink"
              >
                Cancel
              </button>
              <button
                onClick={handleRejectSubmit}
                className="rounded-lg bg-rose-600 px-4 py-2 text-xs font-bold text-white hover:bg-rose-700"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Counter Modal */}
      {counterDialogBlock && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl border border-line bg-surface p-6 shadow-2xl">
            <h4 className="text-base font-bold text-ink flex items-center gap-2">
              <RotateCcw className="h-5 w-5 text-amber-600" />
              Counter-Propose Alternative Window
            </h4>

            <p className="mt-1 text-xs text-muted">
              Select an alternative free timetable window on section {counterDialogBlock.section_id}:
            </p>

            <div className="mt-4 max-h-48 overflow-y-auto space-y-2 text-xs">
              {availableWindows.length === 0 ? (
                <div className="text-muted p-2 text-center">
                  No other free windows available on this section date.
                </div>
              ) : (
                availableWindows.map((w) => (
                  <label
                    key={w.window_id}
                    className={`flex items-center justify-between p-2.5 rounded-xl border cursor-pointer ${
                      selectedCounterWindow === w.window_id
                        ? 'border-info bg-info/10 text-ink'
                        : 'border-line hover:bg-raised text-muted'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <input
                        type="radio"
                        name="counter_win"
                        value={w.window_id}
                        checked={selectedCounterWindow === w.window_id}
                        onChange={() => setSelectedCounterWindow(w.window_id)}
                      />
                      <span className="font-mono">{w.start_time} - {w.end_time}</span>
                      <span>({w.duration_hours}h)</span>
                    </div>
                    <span className="text-[10px] font-bold">Impact: {w.ml_traffic_impact_score || 0}</span>
                  </label>
                ))
              )}
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <button
                onClick={() => setCounterDialogBlock(null)}
                className="rounded-lg border border-line bg-surface px-4 py-2 text-xs font-medium text-muted hover:text-ink"
              >
                Cancel
              </button>
              <button
                disabled={!selectedCounterWindow}
                onClick={handleCounterSubmit}
                className="rounded-lg bg-amber-600 px-4 py-2 text-xs font-bold text-white hover:bg-amber-700 disabled:opacity-50"
              >
                Submit Counter-Proposal
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Impact Preview Modal */}
      {previewImpact && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-2xl border border-line bg-surface p-6 shadow-2xl">
            <h4 className="text-base font-bold text-ink flex items-center gap-2">
              <Train className="h-5 w-5 text-info" />
              Traffic Impact &amp; Cascade Preview
            </h4>

            <div className="mt-3 flex items-center justify-between rounded-xl bg-deep/40 p-3 text-xs">
              <span>Section: <strong>{previewImpact.section_id}</strong></span>
              <span>Window: <strong>{previewImpact.window_times}</strong></span>
              <span>Affected: <strong className="text-rose-600">{previewImpact.trains_affected} trains</strong></span>
            </div>

            <div className="mt-4 space-y-2 max-h-56 overflow-y-auto text-xs">
              {previewImpact.train_details?.length === 0 ? (
                <div className="text-muted text-center py-4">
                  Zero trains affected. Clean free maintenance window.
                </div>
              ) : (
                previewImpact.train_details?.map((t) => (
                  <div key={t.train_no} className="flex items-center justify-between rounded-lg border border-line/50 p-2 text-[11px]">
                    <div>
                      <span className="font-bold text-ink">{t.train_no}</span> · {t.train_name} ({t.train_type})
                      <p className="text-[10px] text-muted">{t.reason}</p>
                    </div>
                    <div className="text-right">
                      <span className="font-bold text-rose-600">+{t.delay_minutes}m delay</span>
                      <span className="block text-[9px] uppercase font-bold text-muted">{t.status}</span>
                    </div>
                  </div>
                ))
              )}
            </div>

            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setPreviewImpact(null)}
                className="rounded-lg bg-raised px-4 py-2 text-xs font-medium text-ink hover:bg-line/60"
              >
                Close Preview
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
