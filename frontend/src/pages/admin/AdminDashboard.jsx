import { useEffect, useMemo, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { AlertTriangle, ShieldAlert, CheckCircle2, X, Bell, ClipboardCheck, PlayCircle, CircleCheck, Flame } from 'lucide-react'
import PortalLayout from '@/components/app/PortalLayout'
import { useAppState } from '@/state/AppState'
import IndiaRailwayMap from '@/components/network/IndiaRailwayMap'
import { fetchLiveTrains } from '@/api'

/**
 * The status flow every issue moves through. One admin action is available
 * at a time — whichever one advances the issue to the next stage — rather
 * than four buttons sitting there decoratively. Frontend demo state only:
 * nothing here calls a backend, and refreshing the page resets it.
 */
const STATUS_FLOW = ['NEW', 'ACKNOWLEDGED', 'DEPARTMENT NOTIFIED', 'IN PROGRESS', 'RESOLVED']

function statusIndex(status) {
  const i = STATUS_FLOW.indexOf(status)
  return i === -1 ? 0 : i
}

function nextStatus(status) {
  const i = statusIndex(status)
  return STATUS_FLOW[Math.min(i + 1, STATUS_FLOW.length - 1)]
}

/**
 * The one action available for an issue's current status. Returns null at
 * RESOLVED — there is nothing further to do, so no button is shown rather
 * than a disabled or dead one.
 */
function getNextAction(issue) {
  switch (issue.status) {
    case 'NEW':
      return { label: 'ACKNOWLEDGE', icon: ClipboardCheck, next: 'ACKNOWLEDGED' }
    case 'ACKNOWLEDGED':
      return { label: `NOTIFY ${issue.department}`, icon: Bell, next: 'DEPARTMENT NOTIFIED' }
    case 'DEPARTMENT NOTIFIED':
      return { label: 'START ACTION', icon: PlayCircle, next: 'IN PROGRESS' }
    case 'IN PROGRESS':
      return { label: 'MARK RESOLVED', icon: CircleCheck, next: 'RESOLVED' }
    default:
      return null
  }
}

const STATUS_BADGE = {
  NEW: 'tag tag-neutral',
  ACKNOWLEDGED: 'tag tag-info',
  'DEPARTMENT NOTIFIED': 'tag tag-info',
  'IN PROGRESS': 'tag tag-warn',
  RESOLVED: 'tag tag-ok',
}

import { fetchTasks, updateTaskStatus } from '@/api'

const SEVERITY_FILTERS = ['ALL', 'CRITICAL', 'HIGH', 'MEDIUM']
const DEPT_FILTERS = ['ALL', 'ENGINEERING', 'S&T', 'TRD']

const uiToBackendStatus = {
  'NEW': 'PENDING',
  'ACKNOWLEDGED': 'ESCALATED',
  'DEPARTMENT NOTIFIED': 'SCHEDULED',
  'IN PROGRESS': 'IN_PROGRESS',
  'RESOLVED': 'COMPLETED'
}

const backendToUiStatus = {
  'PENDING': 'NEW',
  'ESCALATED': 'ACKNOWLEDGED',
  'SCHEDULED': 'DEPARTMENT NOTIFIED',
  'IN_PROGRESS': 'IN PROGRESS',
  'COMPLETED': 'RESOLVED',
  'DEFERRED': 'RESOLVED' // Fallback
}

export default function AdminDashboard() {
  const { currentUser } = useAppState()
  const [issues, setIssues] = useState([])
  const [selectedIssueId, setSelectedIssueId] = useState(null)
  const [severityFilter, setSeverityFilter] = useState('ALL')
  const [deptFilter, setDeptFilter] = useState('ALL')
  const [showHeatmap, setShowHeatmap] = useState(true)
  const [liveTrains, setLiveTrains] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoading(true)
    fetchTasks().then(res => {
      const mapped = res.data.map(t => ({
        id: t.task_id,
        locationId: t.section_id,
        locationName: t.corridor_id,
        exactLocation: `KM ${t.km_location || '—'}`,
        department: t.department === 'SNT' ? 'S&T' : t.department,
        severity: t.ml_predicted_severity || t.raw_severity || 'MEDIUM',
        status: backendToUiStatus[t.status] || 'NEW',
        type: t.defect_category,
        time: t.reported_date,
        details: {
          what: t.inspector_remarks || 'No remarks provided.',
          why: [{ level: 'CONFIRMED', text: `Criticality Score: ${(t.ml_criticality_score ?? 0).toFixed(1)}` }],
          how: [],
          impact: 'Predicted Duration: ' + (t.ml_predicted_duration_hours ?? 0) + ' hrs',
          seriousness: t.ml_predicted_severity || t.raw_severity || 'MEDIUM',
          recommendation: 'Use RailOpt Optimizer to generate a plan.',
          supporting: `Overdue: ${t.days_overdue ?? 0} days. Historical failures: ${t.historical_failure_count ?? 0}.`
        }
      }))
      setIssues(mapped)
      setError(null)
    }).catch(err => {
      console.error('Failed to fetch tasks:', err)
      setError('Could not load tasks. Click Setup Server to initialize.')
    }).finally(() => {
      setLoading(false)
    })
  }, [])

  useEffect(() => {
    fetchLiveTrains()
      .then(res => setLiveTrains(res.data))
      .catch(err => console.error("Could not load live trains", err))
  }, [])


  // One filtered list, read by the map, the heatmap layer and the alert
  // centre table alike — so "filter to CRITICAL" means the same thing
  // everywhere on the screen, not three separate interpretations of it.
  const filteredIssues = useMemo(
    () =>
      issues.filter(
        (i) =>
          (severityFilter === 'ALL' || i.severity === severityFilter) &&
          (deptFilter === 'ALL' || i.department === deptFilter)
      ),
    [issues, severityFilter, deptFilter]
  )

  const selectedIssue = issues.find(i => i.id === selectedIssueId)

  // Access check sits after every hook so the hook order never changes
  // between renders (e.g. while signing out).
  if (currentUser?.id !== 'admin') {
    return <Navigate to="/restricted" replace />
  }

  const handleAdvance = async (id) => {
    // 1. Local state update
    const issue = issues.find(i => i.id === id)
    const newStatus = nextStatus(issue.status)
    setIssues(issues.map(i => {
      if (i.id === id) {
        return { ...i, status: newStatus }
      }
      return i
    }))

    // 2. Call real backend API to update database task
    try {
      const backendStatus = uiToBackendStatus[newStatus]
      await updateTaskStatus(id, { status: backendStatus })
    } catch (e) {
      console.error(e)
    }
  }

  const getSeverityColor = (severity) => {
    switch(severity) {
      case 'CRITICAL': return 'sev sev-critical'
      case 'HIGH': return 'sev sev-high'
      case 'MEDIUM': return 'sev sev-medium'
      default: return 'sev sev-low'
    }
  }

  const getDeptColor = (dept) => {
    switch(dept) {
      case 'ENGINEERING': return 'border-eng/30 bg-eng/10 text-eng'
      case 'S&T': return 'border-snt/30 bg-snt/10 text-snt'
      case 'TRD': return 'border-trd/30 bg-trd/10 text-trd'
      default: return 'border-line bg-raised text-muted'
    }
  }

  return (
    <PortalLayout role="admin">
      <div className="mb-6 flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink uppercase flex items-center gap-2">
            <span className="w-2.5 h-2.5 bg-info rounded-full inline-block"></span>
            Super Admin Control Room
          </h1>
          <p className="text-[11px] text-muted uppercase tracking-widest mt-1">Railway Network Overview</p>
        </div>
      </div>

      {/* FILTERS — the single source both the map, the heatmap layer and
          the alert centre table read from below. */}
      <div className="mb-4 flex flex-wrap items-center gap-x-6 gap-y-2 bg-surface border border-line rounded-lg px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold text-faint uppercase tracking-widest">Severity</span>
          <div className="flex gap-1">
            {SEVERITY_FILTERS.map((s) => (
              <button
                key={s}
                onClick={() => setSeverityFilter(s)}
                aria-pressed={severityFilter === s}
                className={`px-2.5 py-1 rounded text-[10px] font-bold uppercase tracking-wider border transition-colors ${
                  severityFilter === s
                    ? 'bg-merge text-deep border-merge'
                    : 'bg-surface text-muted border-line hover:bg-raised'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
        <div className="h-4 w-px bg-line hidden sm:block" />
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold text-faint uppercase tracking-widest">Department</span>
          <div className="flex gap-1">
            {DEPT_FILTERS.map((d) => (
              <button
                key={d}
                onClick={() => setDeptFilter(d)}
                aria-pressed={deptFilter === d}
                className={`px-2.5 py-1 rounded text-[10px] font-bold uppercase tracking-wider border transition-colors ${
                  deptFilter === d
                    ? 'bg-merge text-deep border-merge'
                    : 'bg-surface text-muted border-line hover:bg-raised'
                }`}
              >
                {d === 'ALL' ? 'ALL DEPARTMENTS' : d}
              </button>
            ))}
          </div>
        </div>
        <div className="ml-auto flex items-center gap-2 text-[10px] text-faint">
          <span className="font-mono">{filteredIssues.length} of {issues.length} issues shown</span>
        </div>
      </div>

      <div className="flex gap-6 h-[700px]">
        {/* LEFT/MAIN: MAP & ALERTS */}
        <div className={`flex flex-col gap-6 transition-all duration-300 ${selectedIssue ? 'w-1/2' : 'w-full'}`}>
          {/* INDIA MAP */}
          <div className="bg-surface border border-line rounded-lg shadow-sm flex-1 flex flex-col overflow-hidden">
            <div className="bg-bar text-onbar px-4 py-3 flex flex-wrap justify-between items-center gap-y-2 shrink-0">
              <h2 className="text-[11px] font-bold uppercase tracking-wider">India Railway Control Map</h2>
              <div className="flex items-center gap-4">
                <button
                  onClick={() => setShowHeatmap((v) => !v)}
                  aria-pressed={showHeatmap}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[10px] font-bold uppercase tracking-widest border transition-colors ${
                    showHeatmap
                      ? 'bg-onbar/15 border-onbar/30 text-onbar'
                      : 'bg-transparent border-onbar/25 text-barmuted hover:text-onbar'
                  }`}
                >
                  <Flame size={11} />
                  Risk Heatmap
                </button>
                <div className="flex gap-3 text-[10px] font-bold uppercase tracking-widest text-barmuted">
                  <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-green-500"></span> Low</span>
                  <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-yellow-400"></span> Medium</span>
                  <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-orange-500"></span> High</span>
                  <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-red-500"></span> Critical</span>
                </div>
              </div>
            </div>
            {showHeatmap && (
              <div className="bg-raised border-b border-line px-4 py-1.5 flex items-center justify-between">
                <span className="text-[10px] font-bold text-muted uppercase tracking-widest">RailOpt Risk — geographic overlay</span>
                <span className="text-[10px] font-bold text-warn uppercase tracking-widest">Demo / Simulation Data</span>
              </div>
            )}
            <div className="flex-1 bg-raised relative p-4">
              <IndiaRailwayMap
                issues={filteredIssues}
                selectedIssueId={selectedIssueId}
                onSelectIssue={setSelectedIssueId}
                showHeatmap={showHeatmap}
                trains={liveTrains}
              />
            </div>
          </div>

          {/* ALERT CENTER */}
          <div className="bg-surface border border-line rounded-lg shadow-sm h-1/3 flex flex-col shrink-0 overflow-hidden">
             <div className="bg-raised border-b border-line px-4 py-2.5 flex justify-between items-center">
              <h2 className="text-[11px] font-bold text-muted uppercase tracking-wider">Alert Center</h2>
              <span className="text-[10px] font-bold text-faint uppercase tracking-widest">
                {filteredIssues.length} of {issues.length}
              </span>
            </div>
            <div className="flex-1 overflow-y-auto">
              <table className="w-full text-left">
                <thead className="bg-raised sticky top-0 border-b border-line text-[10px] font-bold text-faint uppercase tracking-wider">
                  <tr>
                    <th className="px-4 py-2">Severity</th>
                    <th className="px-4 py-2">Location</th>
                    <th className="px-4 py-2">Dept</th>
                    <th className="px-4 py-2">Issue</th>
                    <th className="px-4 py-2">Time</th>
                    <th className="px-4 py-2">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-hair">
                  {loading && (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-xs text-muted">
                        Loading tasks...
                      </td>
                    </tr>
                  )}
                  {!loading && error && (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-xs text-warn">
                        {error}
                      </td>
                    </tr>
                  )}
                  {!loading && !error && filteredIssues.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-xs text-faint">
                        No issues match the current filters.
                      </td>
                    </tr>
                  )}
                  {filteredIssues.map(alert => (
                    <tr 
                      key={alert.id} 
                      onClick={() => setSelectedIssueId(alert.id)}
                      className={`cursor-pointer transition-colors text-xs ${
                        selectedIssueId === alert.id ? 'bg-info/10' : 'hover:bg-raised'
                      }`}
                    >
                      <td className="px-4 py-3">
                        <span className={getSeverityColor(alert.severity)}>
                          {alert.severity}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-bold text-ink">{alert.locationName}</td>
                      <td className="px-4 py-3 font-semibold text-muted uppercase">{alert.department}</td>
                      <td className="px-4 py-3 text-ink">{alert.type}</td>
                      <td className="px-4 py-3 text-muted font-mono text-[10px] whitespace-nowrap">{alert.time}</td>
                      <td className="px-4 py-3">
                        <span className={STATUS_BADGE[alert.status] || STATUS_BADGE.NEW}>
                          {alert.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* RIGHT: ISSUE DETAIL PANEL */}
        {selectedIssue && (
          <div className="w-1/2 bg-surface border border-line rounded-lg shadow-xl overflow-hidden flex flex-col animate-in slide-in-from-right-4">
            <div className="bg-bar text-onbar px-6 py-4 flex justify-between items-center shrink-0">
              <div>
                <h2 className="text-sm font-bold uppercase tracking-wider">Issue Details</h2>
                <span className="text-[10px] text-barmuted font-mono mt-0.5 block">{selectedIssue.id}</span>
              </div>
              <button type="button" onClick={() => setSelectedIssueId(null)} aria-label="Close issue details" className="text-barmuted hover:text-onbar transition-colors">
                <X size={20} />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6">
              
              {/* Meta Grid */}
              <div className="grid grid-cols-2 gap-4 mb-8">
                <div className="bg-raised p-3 rounded border border-line">
                  <span className="text-[10px] font-bold text-faint uppercase tracking-wider block mb-1">Location</span>
                  <span className="text-sm font-bold text-ink uppercase tracking-wide">{selectedIssue.locationName} Railway Section</span>
                  <span className="text-xs text-muted block mt-1">{selectedIssue.exactLocation}</span>
                </div>
                <div className="bg-raised p-3 rounded border border-line">
                  <span className="text-[10px] font-bold text-faint uppercase tracking-wider block mb-1">Severity</span>
                  <span className={getSeverityColor(selectedIssue.severity)}>
                    {selectedIssue.severity}
                  </span>
                </div>
                <div className="bg-raised p-3 rounded border border-line">
                  <span className="text-[10px] font-bold text-faint uppercase tracking-wider block mb-1">Status</span>
                  <span className={STATUS_BADGE[selectedIssue.status] || STATUS_BADGE.NEW}>
                    {selectedIssue.status}
                  </span>
                </div>
                <div className="bg-raised p-3 rounded border border-line">
                  <span className="text-[10px] font-bold text-faint uppercase tracking-wider block mb-1">Issue Type</span>
                  <span className="text-sm font-bold text-ink">{selectedIssue.type}</span>
                </div>
                <div className={`p-3 rounded border col-span-2 ${getDeptColor(selectedIssue.department)}`}>
                  <span className="text-[10px] font-bold uppercase tracking-wider block mb-1 ">Responsible Department</span>
                  <span className="text-sm font-bold uppercase tracking-wide flex items-center gap-2">
                    {selectedIssue.department}
                  </span>
                </div>
              </div>

              {/* Notification status */}
              <div className={`mb-8 p-3 rounded border flex items-center gap-3 ${
                statusIndex(selectedIssue.status) >= statusIndex('DEPARTMENT NOTIFIED')
                  ? 'bg-ok/10 border-ok/30'
                  : 'bg-raised border-line'
              }`}>
                {statusIndex(selectedIssue.status) >= statusIndex('DEPARTMENT NOTIFIED') ? (
                  <>
                    <CheckCircle2 size={16} className="text-ok shrink-0" />
                    <div>
                      <span className="text-[10px] font-bold text-ok uppercase tracking-wider block">
                        ✓ Department Notified
                      </span>
                      <span className="text-[11px] text-ok">Notification sent.</span>
                    </div>
                  </>
                ) : (
                  <>
                    <Bell size={16} className="text-faint shrink-0" />
                    <div>
                      <span className="text-[10px] font-bold text-muted uppercase tracking-wider block">
                        Notification
                      </span>
                      <span className="text-[11px] text-muted">Not sent.</span>
                    </div>
                  </>
                )}
              </div>

              {/* What Happened */}
              <div className="mb-6">
                <h3 className="text-[11px] font-bold text-faint uppercase tracking-wider mb-2 border-b border-hair pb-2">WHAT HAPPENED?</h3>
                <p className="text-sm text-ink leading-relaxed">{selectedIssue.details.what}</p>
              </div>

              {/* Why */}
              <div className="mb-6">
                <h3 className="text-[11px] font-bold text-faint uppercase tracking-wider mb-2 border-b border-hair pb-2">WHY DID IT HAPPEN?</h3>
                <div className="space-y-2">
                  {selectedIssue.details.why.map((cause, idx) => (
                    <div key={idx} className="flex gap-3 text-sm">
                      <span className={`shrink-0 ${
                        cause.level === 'CONFIRMED' ? 'tag tag-danger' :
                        cause.level === 'LIKELY' ? 'tag tag-high' :
                        'tag tag-warn'
                      }`}>
                        {cause.level}
                      </span>
                      <span className="text-ink">• {cause.text}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* How it developed */}
              <div className="mb-6">
                <h3 className="text-[11px] font-bold text-faint uppercase tracking-wider mb-4 border-b border-hair pb-2">HOW DID IT DEVELOP?</h3>
                <div className="flex justify-between items-center relative px-2">
                  <div className="absolute top-2 left-6 right-6 h-[2px] bg-line -z-10"></div>
                  {selectedIssue.details.how.map((stage, idx) => (
                    <div key={idx} className="flex flex-col items-center gap-2">
                      <div className={`w-4 h-4 rounded-full border-2 ${stage.active ? 'bg-info border-info ring-4 ring-info/15' : 'bg-raised border-line'}`}></div>
                      <span className={`text-[10px] font-bold uppercase tracking-widest ${stage.active ? 'text-info' : 'text-faint'}`}>{stage.state}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* How serious */}
              <div className="mb-6">
                <h3 className="text-[11px] font-bold text-faint uppercase tracking-wider mb-2 border-b border-hair pb-2">HOW SERIOUS IS IT?</h3>
                <p className="text-sm text-ink leading-relaxed">{selectedIssue.details.seriousness}</p>
              </div>

              {/* Impact */}
              <div className="mb-6">
                <h3 className="text-[11px] font-bold text-faint uppercase tracking-wider mb-2 border-b border-hair pb-2">IMPACT</h3>
                <p className="text-sm text-ink leading-relaxed">{selectedIssue.details.impact}</p>
              </div>

              {/* Recommendation */}
              <div className="mb-6 bg-info/10 border border-info/30 rounded p-4">
                <h3 className="text-[10px] font-bold text-info uppercase tracking-wider mb-2">RAILOPT RECOMMENDATION</h3>
                <p className="text-sm text-ink font-medium">{selectedIssue.details.recommendation}</p>
              </div>

              {/* Supporting information */}
              <div className="mb-2">
                <h3 className="text-[11px] font-bold text-faint uppercase tracking-wider mb-2 border-b border-hair pb-2">SUPPORTING INFORMATION</h3>
                <p className="text-sm text-muted leading-relaxed">{selectedIssue.details.supporting}</p>
              </div>

            </div>

            {/* Actions */}
            <div className="bg-raised border-t border-line p-4 shrink-0">
              {(() => {
                const action = getNextAction(selectedIssue)
                if (!action) {
                  return (
                    <div className="w-full bg-ok/10 border border-ok/30 text-ok py-3 rounded-lg text-xs font-bold uppercase tracking-widest flex justify-center items-center gap-2">
                      <CheckCircle2 size={16} />
                      Issue Resolved
                    </div>
                  )
                }
                const Icon = action.icon
                return (
                  <button
                    onClick={() => handleAdvance(selectedIssue.id)}
                    className="btn-action w-full py-3 text-xs"
                  >
                    <Icon size={16} />
                    {action.label}
                  </button>
                )
              })()}
            </div>
          </div>
        )}
      </div>
    </PortalLayout>
  )
}
