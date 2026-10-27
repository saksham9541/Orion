import { useEffect, useMemo, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Navigate, useSearchParams } from 'react-router-dom'
import {
  AlertTriangle,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  X,
  Bell,
  ClipboardCheck,
  PlayCircle,
  CircleCheck,
  Flame,
  RefreshCw,
  Clock,
  RotateCcw
} from 'lucide-react'
import PortalLayout from '@/components/app/PortalLayout'
import { useAppState } from '@/state/AppState'
import { useNotifications } from '@/state/NotificationContext'
import IndiaRailwayMap from '@/components/network/IndiaRailwayMap'
import { fetchLiveTrains, fetchTasks, updateTaskStatus } from '@/api'

/**
 * Super Admin operations statuses and transitions.
 */
const STATUS_FLOW = ['NEW', 'ACKNOWLEDGED', 'DEPARTMENT NOTIFIED', 'IN PROGRESS', 'RESOLVED', 'REJECTED']

function statusIndex(status) {
  const i = STATUS_FLOW.indexOf(status)
  return i === -1 ? 0 : i
}

function nextStatus(status) {
  const i = statusIndex(status)
  return STATUS_FLOW[Math.min(i + 1, STATUS_FLOW.length - 1)]
}

/**
 * The primary forward action for an issue.
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
  COMPLETED: 'tag tag-ok',
  REJECTED: 'tag tag-danger',
}

const SEVERITY_FILTERS = ['ALL', 'CRITICAL', 'HIGH', 'MEDIUM']
const DEPT_FILTERS = ['ALL', 'ENGINEERING', 'S&T', 'TRD']

const uiToBackendStatus = {
  'NEW': 'PENDING',
  'ACKNOWLEDGED': 'ESCALATED',
  'DEPARTMENT NOTIFIED': 'SCHEDULED',
  'IN PROGRESS': 'IN_PROGRESS',
  'RESOLVED': 'COMPLETED',
  'COMPLETED': 'COMPLETED',
  'REJECTED': 'REJECTED',
}

const backendToUiStatus = {
  'PENDING': 'NEW',
  'UNVERIFIED': 'NEW',
  'SCORED': 'NEW',
  'SUBMITTED': 'NEW',
  'ESCALATED': 'ACKNOWLEDGED',
  'SCHEDULED': 'DEPARTMENT NOTIFIED',
  'IN_PROGRESS': 'IN PROGRESS',
  'COMPLETED': 'RESOLVED',
  'DEFERRED': 'RESOLVED',
  'REJECTED': 'REJECTED',
}

const VALID_STATION_IDS = ['NDLS', 'LDH', 'ASR', 'JP', 'LKO', 'BCT', 'HWH', 'MAS', 'SBC', 'SC']

function resolveStationId(sectionId, corridorId, taskId) {
  if (VALID_STATION_IDS.includes(sectionId)) return sectionId
  const c = (corridorId || '').toUpperCase()
  if (c.includes('DELHI') || c.includes('NDLS')) return 'NDLS'
  if (c.includes('MUMBAI') || c.includes('BCT')) return 'BCT'
  if (c.includes('KOLKATA') || c.includes('HOWRAH') || c.includes('HWH')) return 'HWH'
  if (c.includes('CHENNAI') || c.includes('MAS')) return 'MAS'
  if (c.includes('LUDHIANA') || c.includes('LDH')) return 'LDH'
  if (c.includes('JAIPUR') || c.includes('JP')) return 'JP'
  if (c.includes('LUCKNOW') || c.includes('LKO')) return 'LKO'
  const hash = (taskId || '').split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)
  return VALID_STATION_IDS[hash % VALID_STATION_IDS.length]
}

function mapTaskForAdmin(t) {
  const stationId = resolveStationId(t.section_id, t.corridor_id, t.task_id)
  const severity = (t.ml_predicted_severity || t.raw_severity || 'MEDIUM').toUpperCase()
  const dept = t.department === 'SNT' ? 'S&T' : (t.department || 'ENGINEERING').toUpperCase()
  const status = backendToUiStatus[t.status] || 'NEW'
  const defectType = t.defect_category ? String(t.defect_category).replace(/_/g, ' ') : 'Track defect'

  return {
    id: t.task_id,
    locationId: stationId,
    locationName: t.corridor_id || 'Mainline Corridor',
    exactLocation: `KM ${t.km_location ?? '—'} (${t.section_id || 'Sector'})`,
    department: dept,
    severity: severity,
    status: status,
    type: defectType,
    time: t.reported_date ? `Reported ${t.reported_date}` : 'Just now',
    details: {
      what: t.inspector_remarks || `${defectType} reported on ${t.corridor_id || 'sector'}.`,
      why: [{ level: 'CONFIRMED', text: `Criticality Score: ${(t.ml_criticality_score ?? 0.85).toFixed(2)}` }],
      how: [],
      impact: 'Predicted Duration: ' + (t.ml_predicted_duration_hours || t.estimated_duration_hours || 2) + ' hrs',
      seriousness: severity,
      recommendation: 'Use RailOpt Optimizer to generate maintenance schedule block.',
      supporting: `Overdue: ${t.days_overdue ?? 0} days. Historical failures: ${t.historical_failure_count ?? 0}.`
    }
  }
}

export default function AdminDashboard() {
  const { currentUser } = useAppState()
  const { notifications } = useNotifications()
  const [searchParams] = useSearchParams()
  const urlIssueId = searchParams.get('issue') || searchParams.get('search')
  const [issues, setIssues] = useState([])
  const [selectedIssueId, setSelectedIssueId] = useState(urlIssueId || null)
  const [severityFilter, setSeverityFilter] = useState('ALL')
  const [deptFilter, setDeptFilter] = useState('ALL')
  const [showHeatmap, setShowHeatmap] = useState(true)
  const [liveTrains, setLiveTrains] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadTasks = useCallback(async () => {
    try {
      const res = await fetchTasks()
      const backendTasks = Array.isArray(res.data) ? res.data : []
      const mapped = backendTasks.map(mapTaskForAdmin)
      // Reverse order so newly reported tasks appear at the very top!
      mapped.reverse()
      setIssues(mapped)
      setError(null)
    } catch (err) {
      console.error('Failed to fetch tasks:', err)
      setError('Could not load tasks. Click Setup Server to initialize.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (urlIssueId) {
      setSelectedIssueId(urlIssueId)
    }
  }, [urlIssueId])

  useEffect(() => {
    loadTasks()

    // 1. Listen for global task created events (from ReportComplaintModal)
    const handleTaskCreated = () => {
      loadTasks()
    }
    window.addEventListener('railopt:task-created', handleTaskCreated)

    // 2. Polling interval (every 3.5s) so reported tasks appear live across browser tabs
    const pollTimer = setInterval(() => {
      loadTasks()
    }, 3500)

    return () => {
      window.removeEventListener('railopt:task-created', handleTaskCreated)
      clearInterval(pollTimer)
    }
  }, [loadTasks])

  // Also auto-reload whenever a new WebSocket alert notification arrives
  useEffect(() => {
    if (notifications.length > 0) {
      loadTasks()
    }
  }, [notifications.length, loadTasks])

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

  const [actionLoading, setActionLoading] = useState(null)
  const [toastMessage, setToastMessage] = useState(null)

  const handleStatusChange = async (id, targetStatus) => {
    setActionLoading(targetStatus)
    // 1. Local state update
    setIssues(prev => prev.map(i => {
      if (i.id === id) {
        return { ...i, status: targetStatus }
      }
      return i
    }))

    // 2. Call real backend API to update database task
    try {
      const backendStatus = uiToBackendStatus[targetStatus] || targetStatus
      await updateTaskStatus(id, { status: backendStatus })
      setToastMessage(`Issue ${id} marked as ${targetStatus}`)
      setTimeout(() => setToastMessage(null), 3000)
    } catch (e) {
      console.error('Failed to update task status:', e)
      setToastMessage(`Failed to update issue status: ${e.message || 'Error'}`)
      setTimeout(() => setToastMessage(null), 3000)
    } finally {
      setActionLoading(null)
    }
  }

  const handleAdvance = async (id) => {
    const issue = issues.find(i => i.id === id)
    if (!issue) return
    const newStatus = nextStatus(issue.status)
    await handleStatusChange(id, newStatus)
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
      <div className="mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-line/60">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-gradient-brand flex items-center gap-2">
              Control Room Operations
              <span className="h-2.5 w-2.5 rounded-full bg-gradient-to-r from-blue-600 to-indigo-600 inline-block animate-pulse" />
            </h1>
            <span className="rounded-full border border-line bg-surface px-2.5 py-0.5 text-[9px] font-mono font-bold uppercase tracking-widest text-muted">
              (01)
            </span>
          </div>
          <p className="text-xs font-mono uppercase tracking-[0.16em] text-muted mt-1">
            [ SYSTEM // NDLS-DIV ] · REAL-TIME DEFECT MONITORING & BLOCK SANCTIONS · (OS.02)
          </p>
        </div>

        {/* Executive Controllers Cluster & Utilities */}
        <div className="flex flex-wrap items-center gap-3 sm:gap-4">
          <div className="flex items-center -space-x-2">
            {[
              { initials: 'CC', name: 'Chief Controller - NDLS', role: 'Head of Operations', badgeColor: 'bg-blue-600', count: 4 },
              { initials: 'DR', name: 'Divisional Railway Mgr', role: 'Executive Authority', badgeColor: 'bg-emerald-600', count: 2 },
              { initials: 'SK', name: 'Senior Section Eng', role: 'Signaling & Interlocking', badgeColor: 'bg-indigo-600', count: 5 },
              { initials: 'PM', name: 'Power & Catenary Lead', role: 'TRD Controller', badgeColor: 'bg-amber-600', count: 1 }
            ].map((member, idx) => (
              <div
                key={idx}
                className="relative group cursor-pointer transition-transform hover:-translate-y-0.5"
                title={`${member.name} (${member.role})`}
              >
                <div className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-surface bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200 text-[10px] font-bold shadow-sm">
                  {member.initials}
                </div>
                <span className={`absolute -bottom-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-bold text-white ${member.badgeColor} ring-1 ring-surface`}>
                  {member.count}
                </span>
              </div>
            ))}
          </div>

          <div className="h-6 w-px bg-line/80 hidden sm:block" />

          <button
            type="button"
            onClick={loadTasks}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1.5 text-xs font-semibold text-muted hover:text-ink hover:bg-raised transition-colors shadow-sm"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            <span>Refresh Feed</span>
          </button>
        </div>
      </div>

      {/* FILTERS — Modern Pill Controls (Matches the screenshot) */}
      <motion.div
        initial={{ opacity: 0, y: -6 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-8 flex flex-wrap items-center gap-x-8 gap-y-4 bg-surface/90 border border-line/80 rounded-[28px] p-4 sm:px-7 shadow-sm"
      >
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono font-bold text-muted uppercase tracking-wider">Severity:</span>
          <div className="flex items-center gap-1.5">
            {SEVERITY_FILTERS.map((s) => (
              <button
                key={s}
                onClick={() => setSeverityFilter(s)}
                aria-pressed={severityFilter === s}
                className={`px-4 py-1.5 rounded-full text-xs font-mono font-bold uppercase tracking-wider transition-all ${
                  severityFilter === s
                    ? 'bg-ink text-deep shadow-sm'
                    : 'bg-raised text-muted hover:text-ink'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
        <div className="h-5 w-px bg-line hidden sm:block" />
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono font-bold text-muted uppercase tracking-wider">Department:</span>
          <div className="flex items-center gap-1.5">
            {DEPT_FILTERS.map((d) => (
              <button
                key={d}
                onClick={() => setDeptFilter(d)}
                aria-pressed={deptFilter === d}
                className={`px-4 py-1.5 rounded-full text-xs font-mono font-bold uppercase tracking-wider transition-all ${
                  deptFilter === d
                    ? 'bg-ink text-deep shadow-sm'
                    : 'bg-raised text-muted hover:text-ink'
                }`}
              >
                {d === 'ALL' ? 'ALL DEPARTMENTS' : d}
              </button>
            ))}
          </div>
        </div>
        <div className="ml-auto flex items-center gap-2 text-xs font-mono text-muted">
          <span>{filteredIssues.length} of {issues.length} issues shown</span>
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 15 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.4 }}
        className="flex flex-col lg:flex-row gap-8 min-h-[850px]"
      >
        {/* LEFT/MAIN: MAP & ALERTS */}
        <div className={`flex flex-col gap-8 transition-all duration-300 ${selectedIssue ? 'lg:w-7/12' : 'w-full'}`}>
          {/* INDIA MAP */}
          <div className="bg-surface/90 border border-line/80 rounded-[32px] shadow-sm flex flex-col overflow-hidden min-h-[460px]">
            <div className="bg-bar text-onbar px-6 py-4 flex flex-wrap justify-between items-center gap-y-2 shrink-0">
              <h2 className="text-xs font-bold font-sans uppercase tracking-wider text-onbar">India Railway Control Map</h2>
              <div className="flex items-center gap-4">
                <button
                  onClick={() => setShowHeatmap((v) => !v)}
                  aria-pressed={showHeatmap}
                  className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold uppercase tracking-widest border transition-colors ${
                    showHeatmap
                      ? 'bg-onbar/15 border-onbar/30 text-onbar'
                      : 'bg-transparent border-onbar/25 text-barmuted hover:text-onbar'
                  }`}
                >
                  <Flame size={12} />
                  Risk Heatmap
                </button>
                <div className="flex gap-3 text-xs font-mono font-bold uppercase tracking-widest text-barmuted">
                  <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-green-500"></span> Low</span>
                  <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-yellow-400"></span> Medium</span>
                  <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-orange-500"></span> High</span>
                  <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-red-500"></span> Critical</span>
                </div>
              </div>
            </div>
            {showHeatmap && (
              <div className="bg-raised border-b border-line px-6 py-2 flex items-center justify-between">
                <span className="text-xs font-mono font-bold text-muted uppercase tracking-widest">RailOpt Risk — geographic overlay</span>
                <span className="text-xs font-mono font-bold text-warn uppercase tracking-widest">Simulation Data</span>
              </div>
            )}
            <div className="flex-1 bg-raised relative p-4 min-h-[380px] isolate z-0">
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
          <div className="bg-surface/90 border border-line/80 rounded-[32px] shadow-sm min-h-[380px] flex flex-col shrink-0 overflow-hidden">
             <div className="bg-raised/80 border-b border-line px-6 py-3.5 flex justify-between items-center">
              <h2 className="text-xs font-bold font-sans text-muted uppercase tracking-wider">Alert Center Registry</h2>
              <span className="text-xs font-mono font-bold text-faint uppercase tracking-widest">
                {filteredIssues.length} of {issues.length} active
              </span>
            </div>
            <div className="flex-1 overflow-y-auto">
              <table className="w-full text-left">
                <thead className="bg-raised/50 sticky top-0 border-b border-line text-xs font-mono font-bold text-muted uppercase tracking-wider">
                  <tr>
                    <th className="px-5 py-3">Severity</th>
                    <th className="px-5 py-3">Location</th>
                    <th className="px-5 py-3">Dept</th>
                    <th className="px-5 py-3">Issue</th>
                    <th className="px-5 py-3">Time</th>
                    <th className="px-5 py-3">Status</th>
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
                      <td className="px-5 py-3.5">
                        <span className={getSeverityColor(alert.severity)}>
                          {alert.severity}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 font-bold text-ink">{alert.locationName}</td>
                      <td className="px-5 py-3.5 font-semibold text-muted uppercase font-mono text-xs">{alert.department}</td>
                      <td className="px-5 py-3.5 text-ink">{alert.type}</td>
                      <td className="px-5 py-3.5 text-muted font-mono text-xs whitespace-nowrap">{alert.time}</td>
                      <td className="px-5 py-3.5">
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
          <div className="w-full lg:w-5/12 bg-surface/90 border border-line/80 rounded-[32px] shadow-xl overflow-hidden flex flex-col lg:sticky lg:top-24 max-h-[calc(100vh-120px)]">
            <div className="bg-bar text-onbar px-6 py-4 flex justify-between items-center shrink-0">
              <div>
                <h2 className="text-sm font-bold uppercase tracking-wider font-sans text-onbar">Issue Details</h2>
                <span className="text-xs text-barmuted font-mono mt-0.5 block">{selectedIssue.id}</span>
              </div>
              <button type="button" onClick={() => setSelectedIssueId(null)} aria-label="Close issue details" className="text-barmuted hover:text-onbar transition-colors">
                <X size={20} />
              </button>
            </div>

            {/* SUPER ADMIN QUICK ACTION COMMAND BAR (CLEAN, MINIMALIST MONOCHROME) */}
            <div className="bg-raised/70 border-b border-line px-6 py-3.5 shrink-0 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[10.5px] font-mono font-bold uppercase tracking-widest text-muted">
                  Super Admin Actions
                </span>
                <span className="text-[10px] font-mono font-bold uppercase px-2.5 py-0.5 rounded-full border border-line bg-surface text-muted">
                  {selectedIssue.status}
                </span>
              </div>

              {/* 4 CLEAN MONOCHROMATIC BUTTONS */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {/* 1. Complete / Mark Resolved */}
                <button
                  type="button"
                  onClick={() => handleStatusChange(selectedIssue.id, 'RESOLVED')}
                  disabled={selectedIssue.status === 'RESOLVED' || actionLoading}
                  className={`flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl border text-[11px] font-mono font-bold uppercase tracking-wider transition-all shadow-sm active:scale-95 ${
                    selectedIssue.status === 'RESOLVED'
                      ? 'bg-ink text-deep border-transparent'
                      : 'bg-surface border-line text-ink hover:bg-raised hover:border-line-hover'
                  } disabled:opacity-40`}
                  title="Mark this issue as Completed / Resolved"
                >
                  <CheckCircle2 size={13} className={selectedIssue.status === 'RESOLVED' ? 'text-deep' : 'text-muted'} />
                  <span>Complete</span>
                </button>

                {/* 2. Reject */}
                <button
                  type="button"
                  onClick={() => handleStatusChange(selectedIssue.id, 'REJECTED')}
                  disabled={selectedIssue.status === 'REJECTED' || actionLoading}
                  className={`flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl border text-[11px] font-mono font-bold uppercase tracking-wider transition-all shadow-sm active:scale-95 ${
                    selectedIssue.status === 'REJECTED'
                      ? 'bg-ink text-deep border-transparent'
                      : 'bg-surface border-line text-ink hover:bg-raised hover:border-line-hover'
                  } disabled:opacity-40`}
                  title="Reject or close this issue as invalid / duplicate"
                >
                  <XCircle size={13} className={selectedIssue.status === 'REJECTED' ? 'text-deep' : 'text-muted'} />
                  <span>Reject</span>
                </button>

                {/* 3. In Progress */}
                <button
                  type="button"
                  onClick={() => handleStatusChange(selectedIssue.id, 'IN PROGRESS')}
                  disabled={selectedIssue.status === 'IN PROGRESS' || actionLoading}
                  className={`flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl border text-[11px] font-mono font-bold uppercase tracking-wider transition-all shadow-sm active:scale-95 ${
                    selectedIssue.status === 'IN PROGRESS'
                      ? 'bg-ink text-deep border-transparent'
                      : 'bg-surface border-line text-ink hover:bg-raised hover:border-line-hover'
                  } disabled:opacity-40`}
                  title="Set issue to In Progress"
                >
                  <PlayCircle size={13} className={selectedIssue.status === 'IN PROGRESS' ? 'text-deep' : 'text-muted'} />
                  <span>In Progress</span>
                </button>

                {/* 4. Sanction / Notify Dept */}
                <button
                  type="button"
                  onClick={() => handleStatusChange(selectedIssue.id, 'DEPARTMENT NOTIFIED')}
                  disabled={selectedIssue.status === 'DEPARTMENT NOTIFIED' || actionLoading}
                  className={`flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl border text-[11px] font-mono font-bold uppercase tracking-wider transition-all shadow-sm active:scale-95 ${
                    selectedIssue.status === 'DEPARTMENT NOTIFIED'
                      ? 'bg-ink text-deep border-transparent'
                      : 'bg-surface border-line text-ink hover:bg-raised hover:border-line-hover'
                  } disabled:opacity-40`}
                  title="Sanction & notify designated department"
                >
                  <Bell size={13} className={selectedIssue.status === 'DEPARTMENT NOTIFIED' ? 'text-deep' : 'text-muted'} />
                  <span>Notify</span>
                </button>
              </div>

              {(selectedIssue.status === 'RESOLVED' || selectedIssue.status === 'REJECTED') && (
                <button
                  type="button"
                  onClick={() => handleStatusChange(selectedIssue.id, 'NEW')}
                  className="mt-1.5 flex items-center justify-center gap-1.5 w-full text-[11px] font-mono text-muted hover:text-ink transition-colors py-1"
                >
                  <RotateCcw size={12} />
                  <span>Reopen / Reset Issue to New</span>
                </button>
              )}
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

            {/* Footer Summary Bar */}
            <div className="bg-raised/80 border-t border-line px-6 py-3.5 shrink-0 flex items-center justify-between">
              <span className="text-[11px] font-mono text-muted">
                Task Reference: <strong className="text-ink">{selectedIssue.id}</strong>
              </span>
              <span className="text-[11px] font-mono text-muted uppercase">
                Active State: <strong className="text-ink">{selectedIssue.status}</strong>
              </span>
            </div>
          </div>
        )}
      </motion.div>

      {/* Floating Action Confirmation Toast */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-[999999] bg-ink text-deep px-5 py-3 rounded-2xl shadow-2xl font-mono text-xs font-bold flex items-center gap-2.5 border border-line animate-in fade-in slide-in-from-bottom-3 duration-200">
          <CheckCircle2 size={16} className="text-emerald-500" />
          <span>{toastMessage}</span>
        </div>
      )}
    </PortalLayout>
  )
}
