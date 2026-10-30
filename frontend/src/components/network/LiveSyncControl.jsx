import { useEffect, useState } from 'react'
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Clock,
  KeyRound,
  Radio,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Train,
  X,
} from 'lucide-react'
import Button from '@/components/common/Button'
import { useAppState } from '@/state/AppState'
import { fetchApiBudget, fetchSyncPreview, syncLiveTrains } from '@/api'

/**
 * LiveSyncControl
 *
 * Dedicated live train synchronization control for CONTROLLER and ADMIN on Overview.
 * - Displays API budget breakdown (used/limit per key, safety reserve, available quota)
 * - Pre-sync confirmation modal: call count, covered trains on pilot corridor, per-key remaining budget
 * - Post-sync summary: trains updated, calls used, IST timestamp, itemized failures
 * - Enforces server-side cooldown (min 60m) & reserved budget (30 calls) guards
 */
export default function LiveSyncControl({ sectionId = 'SEC-93135bb9', onSynced }) {
  const { role, currentUser } = useAppState()
  const roleId = (role?.id || '').toLowerCase()
  const userRole = (currentUser?.role || role?.role || '').toLowerCase()
  const isAuthorized =
    roleId === 'admin' ||
    roleId === 'controller' ||
    userRole === 'admin' ||
    userRole === 'controller'

  const [preview, setPreview] = useState(null)
  const [budget, setBudget] = useState(null)
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [errorMsg, setErrorMsg] = useState(null)

  // Modals state
  const [showConfirmModal, setShowConfirmModal] = useState(false)
  const [syncResult, setSyncResult] = useState(null)

  const loadData = async () => {
    if (!isAuthorized) return
    setLoading(true)
    setErrorMsg(null)
    try {
      const [prevRes, budRes] = await Promise.all([
        fetchSyncPreview(sectionId).catch(err => ({ data: null, error: err })),
        fetchApiBudget().catch(err => ({ data: null, error: err })),
      ])
      if (prevRes.data) setPreview(prevRes.data)
      if (budRes.data) setBudget(budRes.data)
    } catch (err) {
      setErrorMsg('Failed to load live sync status: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (isAuthorized) {
      loadData()
    }
  }, [isAuthorized, sectionId])

  if (!isAuthorized) {
    return null
  }

  const handleOpenConfirm = async () => {
    setErrorMsg(null)
    // Refresh latest preview before prompting
    try {
      setLoading(true)
      const res = await fetchSyncPreview(sectionId)
      setPreview(res.data)
      setShowConfirmModal(true)
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || err.message || 'Failed to prepare sync preview')
    } finally {
      setLoading(false)
    }
  }

  const handleExecuteSync = async (force = false) => {
    setSyncing(true)
    setErrorMsg(null)
    try {
      const res = await syncLiveTrains(sectionId, force)
      setSyncResult(res.data)
      setShowConfirmModal(false)
      // Refresh preview and budget after sync
      await loadData()
      onSynced?.(res.data)
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Live sync request failed'
      setErrorMsg(detail)
      setShowConfirmModal(false)
    } finally {
      setSyncing(false)
    }
  }

  const keysBudget = preview?.keys_budget || budget?.keys || []
  const availableForSync = preview?.available_for_sync ?? budget?.available_for_sync ?? 0
  const reservedBudget = preview?.reserved_budget ?? budget?.reserved_budget ?? 30
  const cooldownActive = preview?.cooldown_active || false
  const cooldownMins = preview?.cooldown_minutes_remaining || 0
  const lastSyncedIst = preview?.last_synced_ist || 'Never'
  const callsNeeded = preview?.calls_needed || 0
  const coveredTrains = preview?.covered_trains || []

  return (
    <section className="panel overflow-hidden border border-hair">
      {/* Panel Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hair px-5 py-3.5 bg-surface/40">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-accent/10 text-accent">
            <Radio size={16} className={syncing ? 'animate-pulse text-warn' : ''} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-[14px] font-semibold tracking-tight text-white">Live Train Sync & API Budget</h2>
              <span className="rounded bg-accent/15 px-1.5 py-0.5 font-mono text-[10px] font-medium text-accent">
                {role.id.toUpperCase()}
              </span>
            </div>
            <p className="text-[12px] text-muted">
              RailRadar delay sync for pilot corridor ({preview?.corridor_name || 'New Delhi — Ghaziabad'})
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            size="sm"
            variant="ghost"
            onClick={loadData}
            disabled={loading || syncing}
            title="Refresh budget & preview"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          </Button>

          <Button
            size="sm"
            variant="default"
            onClick={handleOpenConfirm}
            disabled={syncing || loading || (cooldownActive && availableForSync === 0)}
            className="flex items-center gap-1.5 font-medium"
          >
            <Train size={13} />
            <span>Sync live trains</span>
          </Button>
        </div>
      </div>

      {/* Error / Alert banner */}
      {errorMsg && (
        <div className="flex items-start gap-2.5 border-b border-rose-500/20 bg-rose-500/10 px-5 py-3 text-[12.5px] text-rose-300">
          <AlertCircle size={15} className="mt-0.5 shrink-0 text-rose-400" />
          <div className="flex-1">
            <span className="font-medium text-rose-200">Sync Notice: </span>
            {errorMsg}
          </div>
          <button
            onClick={() => setErrorMsg(null)}
            className="text-rose-400 hover:text-rose-200"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Main Budget & Guard Overview Body */}
      <div className="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-hair bg-surface/20 text-[13px]">
        {/* Metric 1: Monthly Per-Key Quota */}
        <div className="p-4 sm:p-5">
          <div className="flex items-center justify-between text-muted text-[12px] mb-2.5">
            <span className="flex items-center gap-1.5 font-medium">
              <KeyRound size={13} className="text-accent" />
              API Key Quotas (This Month)
            </span>
            <span className="font-mono text-[11px] text-faint">
              {budget?.year_month || new Date().toISOString().slice(0, 7)}
            </span>
          </div>

          <div className="space-y-2.5">
            {keysBudget.length === 0 ? (
              <p className="text-[12px] text-faint italic">No API keys registered.</p>
            ) : (
              keysBudget.map((kb, idx) => {
                const pct = Math.min(100, Math.round((kb.used / (kb.limit || 1)) * 100))
                return (
                  <div key={idx} className="rounded bg-surface/60 p-2.5 border border-hair/50">
                    <div className="flex items-center justify-between font-mono text-[11.5px] mb-1">
                      <span className="text-white font-medium">{kb.key_suffix}</span>
                      <span className="text-muted">
                        <strong className="text-white">{kb.used}</strong> / {kb.limit} calls ({kb.remaining} left)
                      </span>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-hair/60">
                      <div
                        className={`h-full transition-all duration-300 ${
                          pct > 80 ? 'bg-rose-500' : pct > 60 ? 'bg-amber-400' : 'bg-emerald-400'
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* Metric 2: Safety Reserve & Available Calls */}
        <div className="p-4 sm:p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-muted text-[12px] mb-2.5">
              <span className="flex items-center gap-1.5 font-medium">
                <ShieldCheck size={13} className="text-emerald-400" />
                Reserve & Spendable Budget
              </span>
              <span className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10.5px] font-mono text-emerald-300">
                Guarded
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 mt-2">
              <div className="rounded border border-hair/60 bg-surface/40 p-2.5">
                <div className="text-[11px] text-muted">Spendable Quota</div>
                <div className="mt-1 font-mono text-[18px] font-semibold text-white">
                  {availableForSync}
                  <span className="ml-1 text-[11px] font-normal text-muted">calls</span>
                </div>
                <div className="text-[10px] text-faint mt-0.5">Above safe reserve</div>
              </div>

              <div className="rounded border border-hair/60 bg-surface/40 p-2.5">
                <div className="text-[11px] text-muted">Mandatory Reserve</div>
                <div className="mt-1 font-mono text-[18px] font-semibold text-amber-300">
                  {reservedBudget}
                  <span className="ml-1 text-[11px] font-normal text-muted">calls</span>
                </div>
                <div className="text-[10px] text-faint mt-0.5">Protected from sync</div>
              </div>
            </div>
          </div>

          <p className="mt-3 text-[11.5px] text-muted leading-relaxed">
            Live sync operations are locked when available balance reaches the {reservedBudget}-call safety threshold to prevent budget exhaustion.
          </p>
        </div>

        {/* Metric 3: Sync Cooldown & Last Synced Timestamp */}
        <div className="p-4 sm:p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-muted text-[12px] mb-2.5">
              <span className="flex items-center gap-1.5 font-medium">
                <Clock size={13} className="text-cyan-400" />
                Sync Cooldown & Status
              </span>
              <span className="font-mono text-[11px] text-faint">Min {preview?.min_interval_minutes || 60}m</span>
            </div>

            <div className="rounded border border-hair/60 bg-surface/40 p-3 mt-1">
              <div className="flex items-center justify-between text-[12px]">
                <span className="text-muted">Cooldown:</span>
                {cooldownActive ? (
                  <span className="inline-flex items-center gap-1 rounded bg-amber-500/10 px-2 py-0.5 font-mono text-[11.5px] font-medium text-amber-300">
                    <Clock size={11} />
                    {cooldownMins}m remaining
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 rounded bg-emerald-500/10 px-2 py-0.5 font-mono text-[11.5px] font-medium text-emerald-300">
                    <CheckCircle2 size={11} />
                    Ready to sync
                  </span>
                )}
              </div>

              <div className="mt-2.5 flex items-center justify-between border-t border-hair/50 pt-2 text-[12px]">
                <span className="text-muted">Last Synced (IST):</span>
                <span className="font-mono text-[11.5px] text-white font-medium">{lastSyncedIst}</span>
              </div>
            </div>
          </div>

          <div className="mt-3 flex items-center justify-between text-[11px] text-faint">
            <span>Pilot: {preview?.section_name || 'NDLS — GZB (19 km)'}</span>
            <span>{coveredTrains.length} timetable trains</span>
          </div>
        </div>
      </div>

      {/* Confirmation Modal */}
      {showConfirmModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-xl border border-hair bg-surface p-6 shadow-2xl">
            <div className="flex items-start justify-between border-b border-hair pb-3.5">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/15 text-accent">
                  <Train size={18} />
                </div>
                <div>
                  <h3 className="text-[16px] font-semibold text-white">Confirm Live Train Sync</h3>
                  <p className="text-[12px] text-muted">
                    Fetch real-time RailRadar delays for {preview?.corridor_name || 'pilot corridor'}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowConfirmModal(false)}
                className="rounded p-1 text-muted hover:text-white hover:bg-surface-elevated"
              >
                <X size={16} />
              </button>
            </div>

            <div className="my-4 space-y-4 text-[13px]">
              {/* Cooldown warning if active */}
              {cooldownActive && (
                <div className="flex items-start gap-2.5 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-[12.5px] text-amber-200">
                  <AlertTriangle size={16} className="mt-0.5 shrink-0 text-amber-400" />
                  <div>
                    <span className="font-semibold">Cooldown Alert: </span>
                    A sync was performed recently. Normal policy enforces a {preview?.min_interval_minutes || 60}-minute
                    interval ({cooldownMins}m remaining). Syncing now requires override confirmation.
                  </div>
                </div>
              )}

              {/* Call requirement summary */}
              <div className="rounded-lg border border-hair bg-surface/50 p-3.5">
                <div className="flex items-center justify-between">
                  <span className="text-muted">Total RailRadar calls to make:</span>
                  <span className="font-mono text-[15px] font-bold text-accent">
                    {callsNeeded} call{callsNeeded === 1 ? '' : 's'}
                  </span>
                </div>
                <div className="mt-1 flex items-center justify-between text-[12px]">
                  <span className="text-muted">Available budget above reserve:</span>
                  <span className={`font-mono font-medium ${availableForSync >= callsNeeded ? 'text-emerald-300' : 'text-rose-400'}`}>
                    {availableForSync} call{availableForSync === 1 ? '' : 's'}
                  </span>
                </div>
              </div>

              {/* Covered trains list */}
              <div>
                <div className="mb-1.5 flex items-center justify-between text-[12px]">
                  <span className="font-medium text-white">Covered Trains with Timetable Snapshots:</span>
                  <span className="font-mono text-faint">({coveredTrains.length} trains)</span>
                </div>
                <div className="flex max-h-24 flex-wrap gap-1.5 overflow-y-auto rounded-lg border border-hair bg-surface/30 p-2.5">
                  {coveredTrains.length === 0 ? (
                    <span className="text-faint text-[12px] italic">No pilot corridor timetable snapshots found.</span>
                  ) : (
                    coveredTrains.map((tid) => (
                      <span
                        key={tid}
                        className="rounded border border-hair/80 bg-surface/70 px-2 py-0.5 font-mono text-[11px] font-semibold text-white"
                      >
                        {tid}
                      </span>
                    ))
                  )}
                </div>
                <p className="mt-1 text-[11px] text-faint">
                  Strictly limited to trains operating through the pilot corridor with existing timetable snapshots.
                </p>
              </div>

              {/* Remaining monthly budget per key */}
              <div>
                <div className="mb-1.5 text-[12px] font-medium text-white">Remaining Monthly Budget Per Key:</div>
                <div className="space-y-1.5">
                  {keysBudget.map((kb, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between rounded border border-hair/60 bg-surface/40 px-3 py-1.5 font-mono text-[12px]"
                    >
                      <span className="text-white font-medium">Key {kb.key_suffix}</span>
                      <span className="text-muted">
                        Used <strong className="text-white">{kb.used}</strong> / {kb.limit} ·{' '}
                        <span className="text-emerald-400 font-semibold">{kb.remaining} remaining</span>
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2.5 border-t border-hair pt-3.5">
              <Button
                variant="ghost"
                onClick={() => setShowConfirmModal(false)}
                disabled={syncing}
              >
                Cancel
              </Button>
              <Button
                variant="default"
                onClick={() => handleExecuteSync(cooldownActive)}
                disabled={syncing || (availableForSync < callsNeeded)}
                className="flex items-center gap-1.5"
              >
                {syncing ? (
                  <>
                    <RefreshCw size={13} className="animate-spin" />
                    <span>Syncing delays...</span>
                  </>
                ) : (
                  <>
                    <Train size={13} />
                    <span>{cooldownActive ? 'Force sync anyway' : 'Confirm & Sync'}</span>
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Sync Result Summary Modal */}
      {syncResult && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-xl border border-hair bg-surface p-6 shadow-2xl">
            <div className="flex items-start justify-between border-b border-hair pb-3.5">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500/15 text-emerald-400">
                  <CheckCircle2 size={18} />
                </div>
                <div>
                  <h3 className="text-[16px] font-semibold text-white">Live Sync Complete</h3>
                  <p className="text-[12px] text-muted">RailRadar real-time delays updated</p>
                </div>
              </div>
              <button
                onClick={() => setSyncResult(null)}
                className="rounded p-1 text-muted hover:text-white hover:bg-surface-elevated"
              >
                <X size={16} />
              </button>
            </div>

            <div className="my-4 space-y-3 text-[13px]">
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-lg border border-hair bg-surface/50 p-3">
                  <div className="text-[11px] text-muted">Trains Updated</div>
                  <div className="mt-1 font-mono text-[20px] font-bold text-emerald-400">
                    {syncResult.trains_updated}
                  </div>
                </div>

                <div className="rounded-lg border border-hair bg-surface/50 p-3">
                  <div className="text-[11px] text-muted">API Calls Used</div>
                  <div className="mt-1 font-mono text-[20px] font-bold text-accent">
                    {syncResult.calls_used}
                  </div>
                </div>
              </div>

              <div className="rounded-lg border border-hair bg-surface/40 p-3">
                <div className="text-[11px] text-muted">Last Synced Time (IST)</div>
                <div className="mt-1 font-mono text-[13px] font-semibold text-white">
                  {syncResult.last_synced_time_ist}
                </div>
              </div>

              {/* Failures list if any */}
              <div>
                <div className="text-[12px] font-medium text-white mb-1">Status & Failures:</div>
                {syncResult.failures && syncResult.failures.length > 0 ? (
                  <div className="max-h-28 overflow-y-auto rounded border border-rose-500/30 bg-rose-500/10 p-2.5 text-[11.5px] space-y-1">
                    {syncResult.failures.map((f, i) => (
                      <div key={i} className="text-rose-200">
                        <strong className="text-white font-mono">{f.train_number}:</strong> {f.error}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex items-center gap-1.5 text-emerald-400 text-[12px] bg-emerald-500/10 border border-emerald-500/20 rounded p-2.5">
                    <CheckCircle2 size={14} />
                    <span>All covered corridor trains updated without errors.</span>
                  </div>
                )}
              </div>
            </div>

            <div className="flex justify-end border-t border-hair pt-3.5">
              <Button variant="default" onClick={() => setSyncResult(null)}>
                Dismiss
              </Button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
