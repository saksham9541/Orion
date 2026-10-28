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
  Plus
} from 'lucide-react'
import PortalLayout from '@/components/app/PortalLayout'
import DepartmentTaskModal from '@/components/app/DepartmentTaskModal'
import ReportComplaintModal from '@/components/app/ReportComplaintModal'
import { fetchTasks, updateTaskStatus } from '@/api'

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
  const [error, setError] = useState(null)
  const [selectedTask, setSelectedTask] = useState(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isReportOpen, setIsReportOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterStatus, setFilterStatus] = useState('ALL')
  const [expandedNotes, setExpandedNotes] = useState({})
  const [technicianNotes, setTechnicianNotes] = useState({})
  const [checklist, setChecklist] = useState({
    flag: true,
    discharge: true,
    shunt: true,
    ppe: true,
    radio: false
  })
  const [actionLoading, setActionLoading] = useState(null)

  const loadTasks = () => {
    setLoading(true)
    fetchTasks()
      .then(res => {
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
      .finally(() => setLoading(false))
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

    // 2. Continuous 3.5s sync poll for instant reflection of Super Admin actions
    const pollTimer = setInterval(() => {
      loadTasks()
    }, 3500)

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

  const handleStatusChange = async (taskId, newStatus) => {
    setActionLoading(taskId)
    try {
      await updateTaskStatus(taskId, { status: newStatus })

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

      await loadTasks()
    } catch (err) {
      console.error('Failed to update status', err)
      alert('Failed to update task status')
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

  const filteredTasks = useMemo(() => {
    return tasks.filter(t => {
      const matchSearch =
        (t.task_id || t.id || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (t.defect_category || t.defectType || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (t.inspector_remarks || t.what || '').toLowerCase().includes(searchQuery.toLowerCase())
      
      if (!matchSearch) return false

      const s = (t.status || '').toUpperCase()
      const sev = (t.severity || t.raw_severity || t.ml_predicted_severity || '').toUpperCase()

      if (filterStatus === 'ALL') return true
      if (filterStatus === 'ACTIVE') return ['IN_PROGRESS', 'IN PROGRESS', 'SCHEDULED', 'DEPARTMENT NOTIFIED', 'AUTHORIZED'].includes(s)
      if (filterStatus === 'PENDING') return ['PENDING', 'UNVERIFIED', 'NEW', 'SCORED', 'DRAFT', 'SUBMITTED', 'ESCALATED', 'REPORTED', 'ACKNOWLEDGED'].includes(s)
      if (filterStatus === 'COMPLETED') return ['COMPLETED', 'RESOLVED', 'DONE'].includes(s)
      if (filterStatus === 'CRITICAL') return ['EMERGENCY', 'CRITICAL', 'HIGH'].includes(sev)
      return true
    })
  }, [tasks, searchQuery, filterStatus])

  const stats = useMemo(() => {
    const total = tasks.length
    const inProgress = tasks.filter(t => t.status === 'IN_PROGRESS').length
    const pending = tasks.filter(t => t.status === 'PENDING' || t.status === 'SCHEDULED').length
    const completed = tasks.filter(t => t.status === 'COMPLETED').length
    return { total, inProgress, pending, completed }
  }, [tasks])

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
          initial={{ opacity: 0, y: 15 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
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
                  onClick={() => toggleChecklist(item.id)}
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
              {['ALL', 'ACTIVE', 'PENDING', 'COMPLETED', 'CRITICAL'].map((f) => (
                <button
                  key={f}
                  onClick={() => setFilterStatus(f)}
                  className={`rounded-lg px-3.5 py-1.5 text-xs font-mono font-semibold uppercase tracking-wider transition-all ${
                    filterStatus === f
                      ? 'bg-[#282D2A] text-white shadow-sm'
                      : 'border border-line bg-surface text-muted hover:text-ink hover:bg-base'
                  }`}
                >
                  {f}
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

          {/* Work Orders List */}
          <div className="space-y-4 sm:space-y-5">
            {filteredTasks.map((task) => {
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

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5 text-xs font-mono pt-3.5 border-t border-line">
                    <div>
                      <span className="text-muted block text-[11px]">CORRIDOR:</span>
                      <span className="text-ink font-semibold mt-0.5 block">{task.corridor_id || 'NDLS-CNB'}</span>
                    </div>
                    <div>
                      <span className="text-muted block text-[11px]">KM POST:</span>
                      <span className="text-ink font-semibold mt-0.5 block">KM {task.km_location || '14.500'}</span>
                    </div>
                    <div>
                      <span className="text-muted block text-[11px]">EST TIME:</span>
                      <span className="text-ink font-semibold mt-0.5 block">{task.estimated_duration_hours || 2} HOURS</span>
                    </div>
                    <div>
                      <span className="text-muted block text-[11px]">TARGET SPEED:</span>
                      <span className="text-ink font-semibold mt-0.5 block">130 KM/H</span>
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
                        onClick={() => alert(`Logged remarks for ${taskId}`)}
                        className="px-3.5 py-1.5 rounded-lg bg-[#282D2A] text-white text-xs font-mono font-semibold uppercase tracking-wider hover:bg-[#3A403B]"
                      >
                        Save Field Log
                      </button>
                    </motion.div>
                  )}

                  {/* Action Bar */}
                  <div className="flex flex-wrap items-center gap-2.5 pt-3 border-t border-line">
                    {task.status !== 'IN_PROGRESS' && task.status !== 'COMPLETED' && (
                      <button
                        type="button"
                        disabled={isUpdating}
                        onClick={() => handleStatusChange(taskId, 'IN_PROGRESS')}
                        className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#D99A2B] hover:bg-[#c28723] text-white font-sans text-xs font-semibold uppercase tracking-wider transition-all disabled:opacity-50"
                      >
                        <PlayCircle size={15} />
                        {isUpdating ? 'STARTING...' : 'Start Action'}
                      </button>
                    )}

                    {task.status !== 'COMPLETED' && (
                      <button
                        type="button"
                        disabled={isUpdating}
                        onClick={() => handleStatusChange(taskId, 'COMPLETED')}
                        className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#0D996B] hover:bg-[#0a7a55] text-white font-sans text-xs font-semibold uppercase tracking-wider transition-all disabled:opacity-50"
                      >
                        <CheckCircle size={15} />
                        {isUpdating ? 'UPDATING...' : 'Mark Done'}
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
    </PortalLayout>
  )
}
