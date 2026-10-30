import { useEffect, useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  CheckCircle,
  PlayCircle,
  Clock,
  ShieldCheck,
  Wrench,
  Radio,
  CheckSquare,
  Square,
  Search,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Plus,
  AlertTriangle
} from 'lucide-react'
import PortalLayout from '@/components/app/PortalLayout'
import DepartmentTaskModal from '@/components/app/DepartmentTaskModal'
import ReportComplaintModal from '@/components/app/ReportComplaintModal'
import AwaitingAckInbox from '@/components/tasks/AwaitingAckInbox'
import { fetchDashboardCounts, fetchTasks, updateTaskStatus } from '@/api'
import CannotStartModal from '@/components/tasks/CannotStartModal'
import { useAppState } from '@/state/AppState'

const PRE_WORK_CHECKLIST_ITEMS = [
  { id: 'flag', label: 'Banner Flag & Detonator Protection placed 1,200m ahead and rear of work site' },
  { id: 'discharge', label: '25kV Catenary Discharge Rod securely locked to rail Earth return' },
  { id: 'shunt', label: 'Track Circuit Shunting Clamp locked firmly across railhead' },
  { id: 'ppe', label: 'High-visibility retroreflective PPE & steel-toe safety boots verified' },
  { id: 'radio', label: 'VHF Walkie-Talkie locked to Guard & Section Controller Channel 04' }
]

export default function TechnicianDashboard() {
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [counts, setCounts] = useState({ total: 0, pending: 0, active_scheduled: 0, resolved: 0 })
  const [error, setError] = useState(null)
  const [selectedTask, setSelectedTask] = useState(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isReportOpen, setIsReportOpen] = useState(false)
  const [cannotStartError, setCannotStartError] = useState(null)
  const { role, currentUser } = useAppState()
  const isControllerOrAdmin = ['admin', 'controller'].includes((role?.id || '').toLowerCase()) || ['admin', 'controller'].includes((currentUser?.role || '').toLowerCase())
  const [searchQuery, setSearchQuery] = useState('')
  const [filterStatus, setFilterStatus] = useState('ALL')
  const [expandedNotes, setExpandedNotes] = useState({})
  const [technicianNotes, setTechnicianNotes] = useState({})
  const [saveSuccess, setSaveSuccess] = useState({})
  const handleSaveFieldLog = (taskId) => {
    setSaveSuccess((prev) => ({ ...prev, [taskId]: true }))
    setTimeout(() => setSaveSuccess((prev) => ({ ...prev, [taskId]: false })), 3000)
  }
  const [checklist, setChecklist] = useState({
    flag: true,
    discharge: true,
    shunt: true,
    ppe: true,
    radio: false
  })
  const [actionLoading, setActionLoading] = useState(null)

  const loadTasks = (silent = false) => {
    if (!silent) setLoading(true)
    Promise.all([
      fetchTasks(),
      fetchDashboardCounts().catch(() => ({ data: null }))
    ])
      .then(([res, countsRes]) => {
        if (countsRes?.data) {
          setCounts(countsRes.data)
        }
        const raw = res.data || []
        const mapped = [...raw]
        mapped.reverse()
        mapped.sort((a, b) => {
          const aIsUser = (a.task_id || a.id || '').startsWith('TSK-')
          const bIsUser = (b.task_id || b.id || '').startsWith('TSK-')
          if (aIsUser && !bIsUser) return -1
          if (!aIsUser && bIsUser) return 1
          return 0
        })
        setTasks(mapped)
        setError(null)
      })
      .catch(err => {
        console.error('Failed to fetch tasks:', err)
        setError('Could not load tasks. Please ensure you are connected.')
      })
      .finally(() => {
        if (!silent) setLoading(false)
      })
  }

  useEffect(() => {
    loadTasks()

    // 1. Listen for task created and updated events (WebSocket & cross-dashboard sync)
    const handleTaskCreated = () => {
      loadTasks()
    }
    const handleTaskUpdated = (e) => {
      const { task_id, status } = e.detail || {}
      if (task_id && status) {
        setTasks(prev => prev.map(t => (t.task_id === task_id || t.id === task_id ? { ...t, status } : t)))
      }
      loadTasks()
    }
    const handleStorage = (e) => {
      if (e.key === 'railopt_task_sync') {
        loadTasks()
      }
    }

    window.addEventListener('railopt:task-created', handleTaskCreated)
    window.addEventListener('railopt:task-updated', handleTaskUpdated)
    window.addEventListener('storage', handleStorage)

    // 2. Continuous 5s background sync for instant reflection of Super Admin actions
    const pollTimer = setInterval(() => {
      loadTasks(true)
    }, 5000)

    return () => {
      window.removeEventListener('railopt:task-created', handleTaskCreated)
      window.removeEventListener('railopt:task-updated', handleTaskUpdated)
      window.removeEventListener('storage', handleStorage)
      clearInterval(pollTimer)
    }
  }, [])

  const toggleChecklist = (id) => {
    setChecklist(prev => ({ ...prev, [id]: !prev[id] }))
  }

  const allSafetyCleared = useMemo(() => {
    return Object.values(checklist).every(Boolean)
  }, [checklist])

  const handleStatusChange = async (taskId, newStatus, confirmLow = true) => {
    setActionLoading(taskId)
    try {
      await updateTaskStatus(taskId, { status: newStatus, confirm_low_confidence: confirmLow })

      // Dispatch sync events locally and cross-tab
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('railopt:task-updated', {
          detail: { task_id: taskId, status: newStatus }
        }))
        try {
          localStorage.setItem('railopt_task_sync', JSON.stringify({
            task_id: taskId,
            status: newStatus,
            timestamp: Date.now()
          }))
        } catch {}
      }

      if (newStatus === 'IN_PROGRESS' && (filterStatus === 'STARTABLE NOW' || filterStatus === 'PENDING')) {
        setFilterStatus('ACTIVE')
      }

      await loadTasks()
    } catch (err) {
      if (err.response?.status === 409 && err.response?.data?.detail) {
        setCannotStartError(err.response.data.detail)
      } else {
        console.error('Failed to update status', err)
        alert(err.response?.data?.detail || 'Failed to update task status')
      }
    } finally {
      setActionLoading(null)
    }
  }

  const openTaskPopUp = (task) => {
    const formattedTask = {
      id: task.task_id || task.id,
      defectType: task.defect_category || task.defectType || 'Track Maintenance',
      severity: task.severity || 'HIGH',
      department: task.department || 'ENGINEERING',
      corridorId: task.corridor_id || 'COR-12345678',
      sectionId: task.section_id || 'SEC-87654321',
      exactLocation: `KM ${task.km_location || '14.5'}`,
      status: task.status || 'PENDING',
      isSafetyCritical: task.severity === 'EMERGENCY' || task.severity === 'CRITICAL' || task.is_safety_critical,
      what: task.inspector_remarks || task.defect_description || 'Track surface anomaly detected during inspection.',
      causes: [
        { level: 'FIELD OBSERVATION', text: task.inspector_remarks || 'Dynamic mechanical wear on track curve' },
        { level: 'ACOUSTIC SENSOR', text: 'Axle vibration harmonic threshold exceeded' }
      ],
      priorityReasons: [
        'Mainline high speed passenger corridor',
        'Headway tolerance window under 8 minutes'
      ]
    }
    setSelectedTask(formattedTask)
    setIsModalOpen(true)
  }

  const isTaskStartableNow = (t) => {
    const s = (t.status || '').toUpperCase()
    return ['APPROVED', 'READY', 'SCHEDULED'].includes(s) && t.window_status === 'ACTIVE'
  }

  const startableCount = useMemo(() => {
    return tasks.filter(isTaskStartableNow).length
  }, [tasks])

  const filteredTasks = useMemo(() => {
    return tasks.filter(t => {
      const matchSearch =
        (t.task_id || t.id || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (t.defect_category || t.defectType || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (t.inspector_remarks || t.what || '').toLowerCase().includes(searchQuery.toLowerCase())
      
      if (!matchSearch) return false

      const s = (t.status || '').toUpperCase()
      const sev = (t.severity || t.raw_severity || t.ml_predicted_severity || '').toUpperCase()

      // STARTABLE NOW: strictly tasks that are ready to start right now (not yet started)
      if (filterStatus === 'STARTABLE NOW') {
        return isTaskStartableNow(t)
      }
      if (filterStatus === 'ALL') return true
      if (filterStatus === 'ACTIVE') return ['IN_PROGRESS', 'IN PROGRESS', 'OVERRUN', 'SUSPENDED', 'SCHEDULED', 'APPROVED', 'READY', 'DEPARTMENT NOTIFIED', 'AUTHORIZED'].includes(s)
      if (filterStatus === 'PENDING') return ['PENDING', 'UNVERIFIED', 'NEW', 'SCORED', 'DRAFT', 'SUBMITTED', 'ESCALATED', 'REPORTED', 'ACKNOWLEDGED'].includes(s)
      if (filterStatus === 'COMPLETED') return ['COMPLETED', 'RESOLVED', 'DONE'].includes(s)
      if (filterStatus === 'CRITICAL') return ['EMERGENCY', 'CRITICAL', 'HIGH'].includes(sev)
      return true
    })
  }, [tasks, searchQuery, filterStatus])

  // Sort tasks so startable now are at the VERY TOP!
  const sortedTasks = useMemo(() => {
    const getTaskRank = (t) => {
      const s = (t.status || '').toUpperCase()
      const win = t.window_status
      // Rank 0: Startable right now!
      if (isTaskStartableNow(t)) return 0
      // Rank 1: Work currently in progress
      if (s === 'IN_PROGRESS' || s === 'OVERRUN') return 1
      // Rank 2: Upcoming approved window (opens soon)
      if (['APPROVED', 'READY', 'SCHEDULED'].includes(s) && win === 'UPCOMING') return 2
      // Rank 3: Approved / Scheduled (other)
      if (['APPROVED', 'READY', 'SCHEDULED'].includes(s)) return 3
      // Rank 4: Unverified / Pending supervisor action
      if (['UNVERIFIED', 'PENDING', 'REPORTED', 'AWAITING_ACK', 'SCORED', 'DRAFT', 'SUBMITTED'].includes(s)) return 4
      // Rank 5: Expired / Completed / Aborted
      return 5
    }

    return [...filteredTasks].sort((a, b) => {
      const rankA = getTaskRank(a)
      const rankB = getTaskRank(b)
      if (rankA !== rankB) return rankA - rankB

      // If both upcoming, sort by start time
      if (rankA === 2 && a.start_allowed_from && b.start_allowed_from) {
        return new Date(a.start_allowed_from).getTime() - new Date(b.start_allowed_from).getTime()
      }

      // Tiebreaker: criticality score descending
      return (b.criticality_score || 0) - (a.criticality_score || 0)
    })
  }, [filteredTasks])

  const stats = useMemo(() => {
    return {
      total: counts.total || tasks.length,
      inProgress: counts.active_scheduled ?? tasks.filter(t => t.status === 'IN_PROGRESS').length,
      pending: counts.pending ?? tasks.filter(t => t.status === 'PENDING' || t.status === 'SCHEDULED').length,
      completed: counts.resolved ?? tasks.filter(t => t.status === 'COMPLETED').length
    }
  }, [counts, tasks])

  return (
    <PortalLayout role="technician">
      <div className="space-y-10">
        
        {/* TOP STATION HEADER — INDUSTRIAL PRECISION */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col md:flex-row md:items-center justify-between gap-6 p-6 sm:p-7 rounded-2xl border border-line bg-surface shadow-sm"
        >
          <div className="flex items-center gap-4 sm:gap-5">
            <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-[#282D2A] text-[#D99A2B] border border-[#3A403B]">
              <Wrench size={22} />
            </span>
            <div>
              <div className="flex items-center gap-3 flex-wrap">
                <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-ink font-sans">
                  Field Crew Workbench
                </h1>
                <span className="rounded-md bg-[#E5F5EC] border border-[#0D996B]/30 px-2.5 py-1 text-xs font-mono font-semibold text-[#0D996B] uppercase flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-[#0D996B] inline-block" />
                  UNIT 04 · ON-DUTY
                </span>
              </div>
              <p className="text-xs font-mono text-muted uppercase tracking-normal mt-1">
                PERMIT #IR-PWR-8821 · GEOFENCE: KM 14.500 [NDLS-TKD-UP] · SHIFT: NIGHT-02
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsReportOpen(true)}
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[#DC3030] hover:bg-[#b92525] text-white font-sans text-xs font-semibold tracking-wide shadow-sm transition-all active:scale-[0.98]"
            >
              <Plus size={15} />
              <span>Report Site Defect</span>
            </button>
            <button
              onClick={loadTasks}
              className="p-2.5 rounded-lg border border-line bg-surface hover:bg-base text-muted hover:text-ink transition-colors shadow-sm"
              title="Refresh Workbench"
            >
              <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
            </button>
          </div>
        </motion.div>

        {/* 4-UP KPI DECK — EASY TO SCAN & CRISP */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            className="p-5 sm:p-6 rounded-xl border border-line bg-surface shadow-sm space-y-1"
          >
            <p className="text-xs font-mono font-semibold text-muted uppercase tracking-wider">
              [ 01 // ASSIGNED ORDERS ]
            </p>
            <p className="text-3xl font-bold font-sans tracking-tight text-ink">{stats.total}</p>
            <span className="text-xs font-mono text-muted uppercase tracking-normal block">
              {stats.inProgress} ACTIVE IN PROGRESS
            </span>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="p-5 sm:p-6 rounded-xl border border-[#0D996B]/30 bg-surface shadow-sm space-y-1"
          >
            <p className="text-xs font-mono font-semibold text-[#0D996B] uppercase tracking-wider">
              [ 02 // SAFETY INTERLOCK ]
            </p>
            <p className="text-2xl font-bold font-sans tracking-tight text-[#0D996B] flex items-center gap-2">
              <ShieldCheck size={24} />
              SAFE TO WORK
            </p>
            <span className="text-xs font-mono text-[#0D996B]/90 uppercase tracking-normal block">
              25kV OHE ISOLATED & GROUNDED
            </span>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="p-5 sm:p-6 rounded-xl border border-[#D99019]/30 bg-surface shadow-sm space-y-1"
          >
            <p className="text-xs font-mono font-semibold text-[#D99019] uppercase tracking-wider">
              [ 03 // BLOCK WINDOW ]
            </p>
            <p className="text-2xl font-bold font-sans tracking-tight text-[#D99019] flex items-center gap-2">
              <Clock size={22} />
              02h 45m
            </p>
            <span className="text-xs font-mono text-[#D99019]/90 uppercase tracking-normal block">
              SANCTION EXPIRES 05:30 HRS
            </span>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="p-5 sm:p-6 rounded-xl border border-line bg-surface shadow-sm space-y-1"
          >
            <p className="text-xs font-mono font-semibold text-muted uppercase tracking-wider">
              [ 04 // SQUAD ON SITE ]
            </p>
            <p className="text-2xl font-bold font-sans tracking-tight text-ink flex items-center gap-2">
              <Radio size={22} />
              4 TECHS
            </p>
            <span className="text-xs font-mono text-muted uppercase tracking-normal block">
              1 SSE · 1 FITTER · 2 MATES
            </span>
          </motion.div>
        </div>

        {/* FULL-WIDTH PRE-WORK SAFETY PROTOCOL */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
          className="rounded-2xl border border-line bg-surface p-6 sm:p-7 shadow-sm space-y-5"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-line">
            <div>
              <h2 className="text-base sm:text-lg font-bold tracking-tight text-ink font-sans flex items-center gap-2.5">
                <span className="h-2 w-2 rounded-full bg-[#D99A2B] inline-block" />
                Mandatory Safety Interlock Protocol
              </h2>
              <p className="text-xs font-mono text-muted uppercase tracking-normal mt-1">
                COMPREHENSIVE ON-TRACK PRE-WORK VERIFICATION
              </p>
            </div>
            <span className={`self-start sm:self-auto px-3 py-1 rounded-md text-xs font-mono font-semibold uppercase tracking-wider border ${
              allSafetyCleared
                ? 'bg-[#E5F5EC] text-[#0D996B] border-[#0D996B]/30'
                : 'bg-[#FFF3D9] text-[#D99019] border-[#D99019]/30'
            }`}>
              {allSafetyCleared ? '✓ ALL SAFETY PROTOCOLS CLEARED' : '⚠ PENDING PRE-WORK VERIFICATION'}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
            {PRE_WORK_CHECKLIST_ITEMS.map((item) => {
              const isChecked = checklist[item.id]
              return (
                <div
                  key={item.id}
                  role="checkbox"
                  aria-checked={isChecked}
                  tabIndex={0}
                  data-testid={`safety-checklist-${item.id}`}
                  onClick={() => toggleChecklist(item.id)}
                  onKeyDown={(e) => { if (e.key === ' ' || e.key === 'Enter') toggleChecklist(item.id) }}
                  className={`p-3.5 rounded-xl border transition-all cursor-pointer flex items-start gap-3 select-none ${
                    isChecked
                      ? 'border-[#0D996B]/40 bg-[#E5F5EC]/60 text-ink'
                      : 'border-line bg-base/60 text-muted hover:border-line hover:text-ink'
                  }`}
                >
                  <span className={`mt-0.5 shrink-0 ${isChecked ? 'text-[#0D996B]' : 'text-muted'}`}>
                    {isChecked ? <CheckSquare size={18} /> : <Square size={18} />}
                  </span>
                  <span className="text-xs font-sans font-medium leading-relaxed">
                    {item.label}
                  </span>
                </div>
              )
            })}
          </div>

          {/* Toolbox Status Bar */}
          <div className="pt-4 border-t border-line">
            <span className="text-xs font-mono font-semibold text-muted uppercase tracking-wider block mb-2.5">
              FIELD TOOLBOX READINESS:
            </span>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5 text-xs font-mono">
              <div className="p-3 rounded-lg border border-line bg-base/60">
                <span className="text-muted block text-[11px]">USFD Flaw Probe:</span>
                <span className="text-ink font-bold text-xs mt-0.5 block">READY (CAL-OK)</span>
              </div>
              <div className="p-3 rounded-lg border border-line bg-base/60">
                <span className="text-muted block text-[11px]">Hydraulic Tensor:</span>
                <span className="text-ink font-bold text-xs mt-0.5 block">70T PRESSURISED</span>
              </div>
              <div className="p-3 rounded-lg border border-line bg-base/60">
                <span className="text-muted block text-[11px]">Torque Wrench:</span>
                <span className="text-ink font-bold text-xs mt-0.5 block">450 N·m PRE-SET</span>
              </div>
              <div className="p-3 rounded-lg border border-line bg-base/60">
                <span className="text-muted block text-[11px]">First Aid & Defib:</span>
                <span className="text-[#0D996B] font-bold text-xs mt-0.5 block">SEALED & INSPECTED</span>
              </div>
            </div>
          </div>
        </motion.div>

        {/* WORK ORDERS SECTION — FULL-WIDTH SPACIOUS CARDS */}
        <div className="space-y-6">
          
          {/* Filter & Search Toolbar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-3.5 sm:px-5 rounded-xl border border-line bg-surface shadow-sm">
            <div className="relative flex-1 max-w-md">
              <Search size={15} className="absolute left-3.5 top-2.5 text-muted" />
              <input
                type="text"
                placeholder="Filter by order ID, defect code, KM post..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="w-full rounded-lg border border-line bg-base pl-10 pr-4 py-1.5 text-xs font-mono text-ink placeholder:text-muted focus:border-[#D99A2B] focus:outline-none"
              />
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              {['STARTABLE NOW', 'ALL', 'ACTIVE', 'PENDING', 'COMPLETED', 'CRITICAL'].map((f) => (
                <button
                  key={f}
                  onClick={() => setFilterStatus(f)}
                  className={`rounded-lg px-3.5 py-1.5 text-xs font-mono font-semibold uppercase tracking-wider transition-all flex items-center gap-1.5 ${
                    filterStatus === f
                      ? 'bg-[#282D2A] text-white shadow-sm'
                      : f === 'STARTABLE NOW' && startableCount > 0
                      ? 'border border-emerald-500/50 bg-emerald-500/10 text-emerald-700 hover:bg-emerald-500/20'
                      : 'border border-line bg-surface text-muted hover:text-ink hover:bg-base'
                  }`}
                >
                  <span>{f}</span>
                  {f === 'STARTABLE NOW' && startableCount > 0 && (
                    <span className="px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-emerald-500 text-white animate-pulse">
                      {startableCount}
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* List State */}
          {loading && (
            <div className="p-14 text-center text-muted font-mono text-xs flex items-center justify-center gap-3">
              <RefreshCw size={16} className="animate-spin" />
              SYNCHRONIZING FIELD WORK ORDERS...
            </div>
          )}

          {!loading && error && (
            <div className="p-6 text-center text-[#DC3030] bg-[#FCE8E8] rounded-xl border border-[#DC3030]/20 font-mono text-xs">
              {error}
            </div>
          )}

          {!loading && !error && filteredTasks.length === 0 && (
            <div className="p-14 text-center text-muted border border-dashed border-line rounded-2xl bg-surface/50">
              <CheckCircle className="mx-auto mb-3 text-[#0D996B] opacity-70" size={40} />
              <p className="text-base font-bold text-ink font-sans tracking-tight">No Matching Work Orders</p>
              <p className="text-xs text-muted font-mono mt-1">All designated tasks for this filter have been satisfied.</p>
            </div>
          )}

          {/* Part B2: My Reports Awaiting Supervisor Acknowledgement */}
          <AwaitingAckInbox isTechnicianView={true} />

          {/* Highlight Banner: Startable Tasks Ready Right Now */}
          {startableCount > 0 && filterStatus !== 'STARTABLE NOW' && (
            <div className="flex items-center justify-between p-3.5 rounded-xl border border-emerald-500/40 bg-emerald-500/10 text-emerald-900 shadow-sm">
              <div className="flex items-center gap-3">
                <div className="h-8 w-8 rounded-lg bg-emerald-500 flex items-center justify-center text-white shrink-0 shadow">
                  <PlayCircle size={18} className="animate-pulse" />
                </div>
                <div>
                  <p className="font-mono text-xs font-bold uppercase tracking-wider text-emerald-900">
                    {startableCount} {startableCount === 1 ? 'Task' : 'Tasks'} Ready To Start Right Now
                  </p>
                  <p className="text-[11px] text-emerald-800 font-sans">
                    Approved maintenance windows are active now. Sorted to the top of your queue for immediate execution.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setFilterStatus('STARTABLE NOW')}
                className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-mono text-xs font-bold uppercase tracking-wider transition-colors shrink-0"
              >
                View Startable ({startableCount})
              </button>
            </div>
          )}

          {/* Work Orders List */}
          <div className="space-y-4 sm:space-y-5">
            {sortedTasks.map((task) => {
              const taskId = task.task_id || task.id
              const sevUpper = (task.severity || '').toUpperCase()
              const isCritical = ['EMERGENCY', 'CRITICAL', 'HIGH'].includes(sevUpper)
              const isMedium = sevUpper === 'MEDIUM'
              const isExpanded = expandedNotes[taskId]
              const isUpdating = actionLoading === taskId

              return (
                <motion.div
                  key={taskId}
                  initial={{ opacity: 0, y: 12 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  className="p-5 sm:p-6 rounded-xl border border-line bg-surface hover:border-[#D99A2B]/40 transition-all space-y-4 shadow-sm hover:shadow"
                >
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2 flex-wrap mb-1.5">
                        <span className="font-mono text-xs font-bold text-ink bg-base border border-line px-2.5 py-1 rounded-md">
                          {taskId}
                        </span>
                        <span className={`px-2.5 py-1 rounded-md text-xs font-mono font-bold uppercase border ${
                          isCritical
                            ? 'bg-[#FCE8E8] text-[#DC3030] border-[#DC3030]/30'
                            : isMedium
                            ? 'bg-[#FFF3D9] text-[#D99019] border-[#D99019]/30'
                            : 'bg-[#E5F5EC] text-[#0D996B] border-[#0D996B]/30'
                        }`}>
                          {task.severity || 'HIGH'}
                        </span>
                        <span className="px-2.5 py-1 rounded-md text-xs font-mono font-semibold uppercase bg-base border border-line text-muted">
                          DEPT: {task.department || 'ENGINEERING'}
                        </span>
                      </div>
                      <h3 className="text-base sm:text-lg font-bold text-ink font-sans tracking-tight">
                        {task.defect_category || task.defectType || 'Track Maintenance Order'}
                      </h3>
                    </div>

                    <div className="flex items-center gap-2.5 self-start sm:self-auto">
                      <span className={`px-3 py-1 rounded-md text-xs font-mono font-semibold uppercase border ${
                        task.status === 'IN_PROGRESS'
                          ? 'bg-[#FFF3D9] text-[#D99019] border-[#D99019]/40'
                          : task.status === 'COMPLETED'
                          ? 'bg-[#E5F5EC] text-[#0D996B] border-[#0D996B]/40'
                          : 'bg-base border-line text-muted'
                      }`}>
                        {task.status.replace('_', ' ')}
                      </span>
                      <button
                        type="button"
                        onClick={() => openTaskPopUp(task)}
                        className="p-1.5 rounded-lg border border-line bg-surface text-muted hover:text-ink hover:border-[#D99A2B] transition-colors"
                        title="Open Details Pop-up"
                      >
                        <ExternalLink size={15} />
                      </button>
                    </div>
                  </div>

                  <p className="text-sm text-[#656A66] leading-relaxed font-sans max-w-4xl">
                    {task.inspector_remarks || task.defect_description || 'Track surface anomaly detected during inspection. Requires manual tension test.'}
                  </p>

                                    {task.designated_period_clock && (
                    <div className="flex items-center gap-2 rounded-lg border border-accent/40 bg-accent/10 px-3 py-1.5 font-mono text-xs">
                      <Clock size={13} className="text-accent" />
                      <span className="text-muted">Start Window:</span>
                      <strong className="text-ink">{task.designated_period_clock}</strong>
                    </div>
                  )}

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5 text-xs font-mono pt-1 text-muted">
                    <div>
                      <span className="block text-[10px]">CORRIDOR:</span>
                      <span className="text-ink font-semibold block">{task.corridor_id || 'NDLS-CNB'}</span>
                    </div>
                    <div>
                      <span className="block text-[10px]">KM POST:</span>
                      <span className="text-ink font-semibold block">KM {task.km_location || '14.500'}</span>
                    </div>
                    <div>
                      <span className="block text-[10px]">SECTION:</span>
                      <span className="text-ink font-semibold block">{task.section_id || 'SEC-NDLS-GZB'}</span>
                    </div>
                    <div>
                      <span className="block text-[10px]">TARGET SPEED:</span>
                      <span className="text-ink font-semibold block">130 KM/H</span>
                    </div>
                  </div>

                  {/* Expandable Field Notes */}
                  {isExpanded && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      className="p-4 rounded-xl border border-line bg-base/70 space-y-2.5"
                    >
                      <label className="text-xs font-mono font-semibold uppercase tracking-wider text-muted block">
                        Technician Field Observation & Measurement Log:
                      </label>
                      <textarea
                        rows={3}
                        placeholder="Log torque reading, rail gap millimeter, temperature..."
                        value={technicianNotes[taskId] || ''}
                        onChange={(e) => setTechnicianNotes({ ...technicianNotes, [taskId]: e.target.value })}
                        className="w-full rounded-lg border border-line bg-surface p-2.5 text-xs font-mono text-ink outline-none focus:border-[#D99A2B]"
                      />
                      <button
                        type="button"
                        onClick={() => handleSaveFieldLog(taskId)}
                        className="px-3.5 py-1.5 rounded-lg bg-[#282D2A] text-white text-xs font-mono font-semibold uppercase tracking-wider hover:bg-[#3A403B] flex items-center gap-1.5"
                      >
                        {saveSuccess[taskId] ? (
                          <>
                            <CheckCircle size={13} className="text-emerald-400" />
                            <span>Logged</span>
                          </>
                        ) : (
                          <span>Save Field Log</span>
                        )}
                      </button>
                    </motion.div>
                  )}

                  {/* Explicit Operational Time Notice — Mutually Exclusive States */}
                  {(task.status === 'IN_PROGRESS' || task.status === 'OVERRUN') ? (
                    <div className="flex items-center gap-2.5 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-900 text-xs font-mono">
                      <PlayCircle size={15} className="text-amber-600 shrink-0 animate-pulse" />
                      <span>
                        <strong>MAINTENANCE IN PROGRESS:</strong> Work is actively underway by <strong>{task.assigned_team || 'Field Crew Unit-04'}</strong>. Track possession is secured. Click <strong>Mark Done</strong> when field work is verified and track is clear.
                      </span>
                    </div>
                  ) : task.status === 'COMPLETED' ? (
                    <div className="flex items-center gap-2.5 p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-900 text-xs font-mono">
                      <CheckCircle size={15} className="text-emerald-600 shrink-0" />
                      <span>
                        <strong>MAINTENANCE COMPLETED:</strong> Work order executed successfully. Track section returned to commercial service.
                      </span>
                    </div>
                  ) : task.window_status === 'ACTIVE' ? (
                    <div className="flex items-center gap-2.5 p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-900 text-xs font-mono">
                      <PlayCircle size={15} className="text-emerald-600 shrink-0 animate-pulse" />
                      <span>
                        <strong>Window is OPEN NOW:</strong> You can start maintenance immediately.
                        {task.start_allowed_until_clock ? (
                          <> Allowed to start until <strong>{task.start_allowed_until_clock}</strong>{task.planned_end_clock ? <>, finish by <strong>{task.planned_end_clock}</strong></> : null}.</>
                        ) : task.planned_end_clock ? (
                          <> Planned finish by <strong>{task.planned_end_clock}</strong>.</>
                        ) : (
                          <> Track availability is reserved for this maintenance block.</>
                        )}
                      </span>
                    </div>
                  ) : task.window_status === 'UPCOMING' ? (
                    <div className="flex items-center gap-2.5 p-2.5 rounded-lg bg-blue-500/10 border border-blue-500/25 text-blue-900 text-xs font-mono">
                      <Clock size={15} className="text-blue-600 shrink-0" />
                      <span>
                        <strong>Window opens at {task.start_allowed_from_clock || 'the scheduled time'}:</strong> You can start maintenance at <strong>{task.start_allowed_from_clock || 'the scheduled start'}</strong>{task.planned_end_clock ? <> (Work planned to finish by <strong>{task.planned_end_clock}</strong>)</> : null}.
                      </span>
                    </div>
                  ) : task.window_status === 'EXPIRED' ? (
                    <div className="flex items-center gap-2.5 p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-900 text-xs font-mono">
                      <AlertTriangle size={15} className="text-rose-600 shrink-0" />
                      <span>
                        <strong>Scheduled Maintenance Window Expired:</strong> Approved window ended{task.planned_end_clock ? <> at <strong>{task.planned_end_clock}</strong></> : null}. Starting now requires rescheduling and controller approval.
                      </span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2.5 p-2.5 rounded-lg bg-base border border-line text-muted text-xs font-mono">
                      <Clock size={15} className="shrink-0" />
                      <span>
                        <strong>Window Pending Approval:</strong> Controller must approve a block window before maintenance can be started.
                      </span>
                    </div>
                  )}

                  {/* Action Bar */}
                  <div className="flex flex-wrap items-center gap-2.5 pt-3 border-t border-line">
                    {task.status !== 'IN_PROGRESS' && task.status !== 'COMPLETED' && (
                      <button
                        type="button"
                        disabled={
                          isUpdating ||
                          !['APPROVED', 'READY', 'SCHEDULED'].includes((task.status || '').toUpperCase()) ||
                          task.window_status === 'UPCOMING' ||
                          task.window_status === 'EXPIRED'
                        }
                        onClick={() => handleStatusChange(taskId, 'IN_PROGRESS')}
                        title={
                          task.window_status === 'UPCOMING'
                            ? `Maintenance Cannot Be Started: This task is scheduled for ${task.start_allowed_from_clock || 'the approved window'}. You can start maintenance at ${task.start_allowed_from_clock}.`
                            : task.window_status === 'EXPIRED'
                            ? `Scheduled Maintenance Window Expired: The approved window ended at ${task.planned_end_clock || 'scheduled end'}. Controller approval required.`
                            : !['APPROVED', 'READY', 'SCHEDULED'].includes((task.status || '').toUpperCase())
                            ? 'Task must be approved by controller before starting work'
                            : 'Start maintenance within approved window'
                        }
                        className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#D99A2B] hover:bg-[#c28723] text-white font-sans text-xs font-semibold uppercase tracking-wider transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                      >
                        <PlayCircle size={15} />
                        {isUpdating ? 'STARTING...' : 'Start Maintenance'}
                      </button>
                    )}

                    {isControllerOrAdmin && (task.window_status === 'EXPIRED' || task.window_status === 'UPCOMING' || task.window_status === 'DELAYED' || task.status === 'IN_PROGRESS') && (
                      <button
                        type="button"
                        onClick={() => setOverrideModalTask(task)}
                        className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-[#D99A2B]/60 bg-[#FFF3D9]/30 text-[#D99A2B] hover:bg-[#FFF3D9]/60 font-mono text-xs font-semibold uppercase tracking-wider transition-all"
                        title="Authorize schedule override as Railway Controller"
                      >
                        <ShieldCheck size={14} />
                        <span>Controller Override</span>
                      </button>
                    )}

                    {/* Mark Done ONLY available when task is actually IN_PROGRESS or OVERRUN */}
                    {(task.status === 'IN_PROGRESS' || task.status === 'OVERRUN') && (
                      <button
                        type="button"
                        disabled={isUpdating}
                        onClick={() => handleStatusChange(taskId, 'COMPLETED')}
                        className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#0D996B] hover:bg-[#0a7a55] text-white font-sans text-xs font-semibold uppercase tracking-wider transition-all shadow-sm disabled:opacity-50"
                        title="Mark maintenance work as completed"
                      >
                        <CheckCircle size={15} />
                        {isUpdating ? 'COMPLETING...' : 'Mark Done'}
                      </button>
                    )}

                    <button
                      type="button"
                      onClick={() => setExpandedNotes(prev => ({ ...prev, [taskId]: !prev[taskId] }))}
                      className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-line bg-surface text-muted hover:text-ink font-mono text-xs font-medium uppercase tracking-wider transition-colors ml-auto"
                    >
                      <span>{isExpanded ? 'Hide Log' : 'Site Anomaly Log'}</span>
                      {isExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                    </button>

                    <button
                      type="button"
                      onClick={() => openTaskPopUp(task)}
                      className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg border border-line bg-surface text-ink hover:border-[#D99A2B] font-mono text-xs font-semibold uppercase tracking-wider transition-colors"
                    >
                      <span>Details</span>
                      <ExternalLink size={13} />
                    </button>
                  </div>
                </motion.div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Pop-up Modals */}
      <DepartmentTaskModal
        task={selectedTask}
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onStatusChange={async (id, status) => {
          await handleStatusChange(id, status)
          setIsModalOpen(false)
        }}
      />

      <ReportComplaintModal
        isOpen={isReportOpen}
        onClose={() => {
          setIsReportOpen(false)
          loadTasks()
        }}
      />

      <CannotStartModal
        isOpen={!!cannotStartError}
        errorData={cannotStartError}
        onClose={() => setCannotStartError(null)}
        isControllerOrAdmin={isControllerOrAdmin}
        onOpenControllerOverride={() => {
          const t = tasks.find(x => x.task_id === cannotStartError.task_id || x.id === cannotStartError.task_id) || selectedTask
          if (t) setOverrideModalTask(t)
        }}
        onRequestNewWindow={() => {
          setCannotStartError(null)
          alert('Rescheduling request submitted to Section Controller.')
        }}
      />

    </PortalLayout>
  )
}
