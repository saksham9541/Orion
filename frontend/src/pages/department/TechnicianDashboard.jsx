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
        setTasks(res.data || [])
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
        (t.task_id || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (t.defect_category || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (t.inspector_remarks || '').toLowerCase().includes(searchQuery.toLowerCase())
      
      if (!matchSearch) return false

      if (filterStatus === 'ALL') return true
      if (filterStatus === 'ACTIVE') return ['IN_PROGRESS', 'SCHEDULED'].includes(t.status)
      if (filterStatus === 'PENDING') return t.status === 'PENDING'
      if (filterStatus === 'COMPLETED') return t.status === 'COMPLETED'
      if (filterStatus === 'CRITICAL') return ['EMERGENCY', 'CRITICAL', 'HIGH'].includes(t.severity)
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
        
        {/* TOP STATION HEADER — AIRY & SPACIOUS */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col md:flex-row md:items-center justify-between gap-6 p-7 sm:p-8 rounded-[32px] border border-line/70 bg-surface/90 shadow-sm"
        >
          <div className="flex items-center gap-5">
            <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-red-500/10 text-red-500 border border-red-500/30">
              <Wrench size={26} />
            </span>
            <div>
              <div className="flex items-center gap-3 flex-wrap">
                <h1 className="font-dot text-xl sm:text-2xl font-bold text-ink uppercase tracking-wider">
                  FIELD CREW WORKBENCH
                </h1>
                <span className="rounded-full bg-emerald-500/15 border border-emerald-500/30 px-3 py-1 text-xs font-mono font-bold text-emerald-500 uppercase flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-emerald-500 animate-ping inline-block" />
                  UNIT 04 · ON-DUTY
                </span>
              </div>
              <p className="text-xs font-mono text-muted uppercase tracking-widest mt-1.5">
                PERMIT #IR-PWR-8821 · GEOFENCE: KM 14.500 [NDLS-TKD-UP] · SHIFT: NIGHT-02
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3.5">
            <button
              onClick={() => setIsReportOpen(true)}
              className="flex items-center gap-2.5 px-6 py-3 rounded-full bg-red-600 hover:bg-red-700 text-white font-mono text-xs font-bold uppercase tracking-wider shadow-md shadow-red-900/20 transition-all active:scale-[0.98]"
            >
              <Plus size={16} />
              <span>Report Site Defect</span>
            </button>
            <button
              onClick={loadTasks}
              className="p-3 rounded-full border border-line bg-raised hover:bg-surface text-muted hover:text-ink transition-colors shadow-sm"
              title="Refresh Workbench"
            >
              <RefreshCw size={17} className={loading ? 'animate-spin' : ''} />
            </button>
          </div>
        </motion.div>

        {/* 4-UP BENTO KPI DECK — GENEROUS GAPS & BREATHING SPACE */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            className="p-6 sm:p-7 rounded-[28px] border border-line/80 bg-surface/80 backdrop-blur-md shadow-sm space-y-2"
          >
            <p className="text-xs font-mono font-bold text-muted uppercase tracking-[0.18em]">
              [ 01 // ASSIGNED ORDERS ]
            </p>
            <p className="text-3xl sm:text-4xl font-dot tracking-tight text-ink">{stats.total}</p>
            <span className="text-xs font-mono text-muted uppercase tracking-wider block">
              {stats.inProgress} ACTIVE IN PROGRESS
            </span>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="p-6 sm:p-7 rounded-[28px] border border-line/80 bg-surface/80 backdrop-blur-md shadow-sm space-y-2"
          >
            <p className="text-xs font-mono font-bold text-emerald-500 uppercase tracking-[0.18em]">
              [ 02 // SAFETY INTERLOCK ]
            </p>
            <p className="text-2xl sm:text-3xl font-dot tracking-tight text-emerald-500 flex items-center gap-2">
              <ShieldCheck size={26} />
              SAFE TO WORK
            </p>
            <span className="text-xs font-mono text-emerald-500/80 uppercase tracking-wider block">
              25kV OHE ISOLATED & GROUNDED
            </span>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="p-6 sm:p-7 rounded-[28px] border border-line/80 bg-surface/80 backdrop-blur-md shadow-sm space-y-2"
          >
            <p className="text-xs font-mono font-bold text-amber-500 uppercase tracking-[0.18em]">
              [ 03 // BLOCK WINDOW ]
            </p>
            <p className="text-2xl sm:text-3xl font-dot tracking-tight text-amber-500 flex items-center gap-2">
              <Clock size={24} />
              02h 45m
            </p>
            <span className="text-xs font-mono text-amber-500/80 uppercase tracking-wider block">
              SANCTION EXPIRES 05:30 HRS
            </span>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="p-6 sm:p-7 rounded-[28px] border border-line/80 bg-surface/80 backdrop-blur-md shadow-sm space-y-2"
          >
            <p className="text-xs font-mono font-bold text-info uppercase tracking-[0.18em]">
              [ 04 // SQUAD ON SITE ]
            </p>
            <p className="text-2xl sm:text-3xl font-dot tracking-tight text-info flex items-center gap-2">
              <Radio size={24} />
              4 TECHS
            </p>
            <span className="text-xs font-mono text-info/80 uppercase tracking-wider block">
              1 SSE · 1 FITTER · 2 MATES
            </span>
          </motion.div>
        </div>

        {/* FULL-WIDTH PRE-WORK SAFETY PROTOCOL (UNCLUTTERED, HORIZONTAL TILES) */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="rounded-[32px] border border-line/80 bg-surface/90 p-7 sm:p-8 shadow-sm space-y-6"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-line">
            <div>
              <h2 className="font-dot text-base sm:text-lg font-bold text-ink uppercase tracking-wider flex items-center gap-2.5">
                <span className="h-2.5 w-2.5 rounded-full bg-[#d71920] inline-block" />
                MANDATORY SAFETY INTERLOCK PROTOCOL
              </h2>
              <p className="text-xs font-mono text-muted uppercase tracking-widest mt-1">
                COMPREHENSIVE ON-TRACK PRE-WORK VERIFICATION
              </p>
            </div>
            <span className={`self-start sm:self-auto px-3.5 py-1 rounded-full text-xs font-mono font-bold uppercase tracking-wider border ${
              allSafetyCleared
                ? 'bg-emerald-500/15 text-emerald-500 border-emerald-500/30'
                : 'bg-amber-500/15 text-amber-500 border-amber-500/30'
            }`}>
              {allSafetyCleared ? '✓ ALL SAFETY PROTOCOLS CLEARED' : '⚠ PENDING PRE-WORK VERIFICATION'}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {PRE_WORK_CHECKLIST_ITEMS.map((item) => {
              const isChecked = checklist[item.id]
              return (
                <div
                  key={item.id}
                  onClick={() => toggleChecklist(item.id)}
                  className={`p-4 rounded-2xl border transition-all cursor-pointer flex items-start gap-3.5 select-none ${
                    isChecked
                      ? 'border-emerald-500/40 bg-emerald-500/5 text-ink'
                      : 'border-line bg-raised/40 text-muted hover:border-line-hover'
                  }`}
                >
                  <span className={`mt-0.5 shrink-0 ${isChecked ? 'text-emerald-500' : 'text-muted'}`}>
                    {isChecked ? <CheckSquare size={19} /> : <Square size={19} />}
                  </span>
                  <span className="text-xs font-medium leading-relaxed">
                    {item.label}
                  </span>
                </div>
              )
            })}
          </div>

          {/* Toolbox Status Bar */}
          <div className="pt-4 border-t border-line">
            <span className="text-xs font-mono font-bold text-muted uppercase tracking-wider block mb-3">
              FIELD TOOLBOX READINESS:
            </span>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono">
              <div className="p-3 rounded-2xl border border-line bg-raised/60">
                <span className="text-muted block text-[11px]">USFD Flaw Probe:</span>
                <span className="text-ink font-bold text-xs mt-0.5 block">READY (CAL-OK)</span>
              </div>
              <div className="p-3 rounded-2xl border border-line bg-raised/60">
                <span className="text-muted block text-[11px]">Hydraulic Tensor:</span>
                <span className="text-ink font-bold text-xs mt-0.5 block">70T PRESSURISED</span>
              </div>
              <div className="p-3 rounded-2xl border border-line bg-raised/60">
                <span className="text-muted block text-[11px]">Torque Wrench:</span>
                <span className="text-ink font-bold text-xs mt-0.5 block">450 N·m PRE-SET</span>
              </div>
              <div className="p-3 rounded-2xl border border-line bg-raised/60">
                <span className="text-muted block text-[11px]">First Aid & Defib:</span>
                <span className="text-emerald-500 font-bold text-xs mt-0.5 block">SEALED & INSPECTED</span>
              </div>
            </div>
          </div>
        </motion.div>

        {/* WORK ORDERS SECTION — FULL-WIDTH SPACIOUS CARDS */}
        <div className="space-y-6">
          
          {/* Filter & Search Toolbar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 sm:px-6 rounded-2xl border border-line/80 bg-surface shadow-sm">
            <div className="relative flex-1 max-w-md">
              <Search size={16} className="absolute left-4 top-3 text-muted" />
              <input
                type="text"
                placeholder="Filter by order ID, defect code, KM post..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="w-full rounded-full border border-line bg-raised pl-11 pr-4 py-2 text-xs font-mono text-ink placeholder:text-muted focus:border-red-500 focus:outline-none"
              />
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              {['ALL', 'ACTIVE', 'PENDING', 'COMPLETED', 'CRITICAL'].map((f) => (
                <button
                  key={f}
                  onClick={() => setFilterStatus(f)}
                  className={`rounded-full px-4 py-1.5 text-xs font-mono font-bold uppercase tracking-wider transition-all ${
                    filterStatus === f
                      ? 'bg-ink text-deep shadow-sm'
                      : 'border border-line bg-raised text-muted hover:text-ink'
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          {/* List State */}
          {loading && (
            <div className="p-16 text-center text-muted font-mono text-xs flex items-center justify-center gap-3">
              <RefreshCw size={18} className="animate-spin" />
              SYNCHRONIZING FIELD WORK ORDERS...
            </div>
          )}

          {!loading && error && (
            <div className="p-8 text-center text-warn bg-warn/10 rounded-3xl border border-warn/20 font-mono text-xs">
              {error}
            </div>
          )}

          {!loading && !error && filteredTasks.length === 0 && (
            <div className="p-16 text-center text-muted border border-dashed border-line rounded-[32px] bg-surface/50">
              <CheckCircle className="mx-auto mb-3 text-emerald-500 opacity-60" size={44} />
              <p className="font-dot text-base font-bold text-ink uppercase">No Matching Work Orders</p>
              <p className="text-xs text-muted font-mono mt-1">All designated tasks for this filter have been satisfied.</p>
            </div>
          )}

          {/* Work Orders List */}
          <div className="space-y-6">
            {filteredTasks.map((task) => {
              const taskId = task.task_id || task.id
              const isCritical = ['EMERGENCY', 'CRITICAL', 'HIGH'].includes((task.severity || '').toUpperCase())
              const isExpanded = expandedNotes[taskId]
              const isUpdating = actionLoading === taskId

              return (
                <motion.div
                  key={taskId}
                  initial={{ opacity: 0, y: 15 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  className="p-7 sm:p-8 rounded-[32px] border border-line/80 bg-surface/90 hover:bg-surface transition-all space-y-5 group shadow-sm hover:shadow-md"
                >
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2.5 flex-wrap mb-2">
                        <span className="font-mono text-xs font-bold text-ink bg-raised border border-line px-3 py-1 rounded-md">
                          {taskId}
                        </span>
                        <span className={`px-2.5 py-1 rounded-md text-xs font-mono font-bold uppercase border ${
                          isCritical
                            ? 'bg-red-500/10 text-red-500 border-red-500/30'
                            : 'bg-blue-500/10 text-blue-500 border-blue-500/30'
                        }`}>
                          {task.severity || 'HIGH'}
                        </span>
                        <span className="px-2.5 py-1 rounded-md text-xs font-mono font-bold uppercase bg-raised border border-line text-muted">
                          DEPT: {task.department || 'ENGINEERING'}
                        </span>
                      </div>
                      <h3 className="font-dot text-base sm:text-lg font-bold text-ink uppercase tracking-wider">
                        {task.defect_category || task.defectType || 'Track Maintenance Order'}
                      </h3>
                    </div>

                    <div className="flex items-center gap-3 self-start sm:self-auto">
                      <span className={`px-3 py-1.5 rounded-full text-xs font-mono font-bold tracking-wider uppercase border ${
                        task.status === 'IN_PROGRESS'
                          ? 'bg-amber-500/15 text-amber-500 border-amber-500/30 animate-pulse'
                          : task.status === 'COMPLETED'
                          ? 'bg-emerald-500/15 text-emerald-500 border-emerald-500/30'
                          : 'bg-raised border-line text-muted'
                      }`}>
                        {task.status.replace('_', ' ')}
                      </span>
                      <button
                        type="button"
                        onClick={() => openTaskPopUp(task)}
                        className="p-2 rounded-full border border-line bg-surface text-muted hover:text-ink hover:border-line-hover transition-colors"
                        title="Open Pop-up"
                      >
                        <ExternalLink size={16} />
                      </button>
                    </div>
                  </div>

                  <p className="text-sm text-muted leading-relaxed font-sans max-w-4xl">
                    {task.inspector_remarks || task.defect_description || 'Track surface anomaly detected during inspection. Requires manual tension test.'}
                  </p>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono pt-4 border-t border-line/60">
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
                      className="p-5 rounded-2xl border border-line bg-raised/70 space-y-3"
                    >
                      <label className="text-xs font-mono font-bold uppercase tracking-wider text-muted block">
                        Technician Field Observation & Measurement Log:
                      </label>
                      <textarea
                        rows={3}
                        placeholder="Log torque reading, rail gap millimeter, temperature..."
                        value={technicianNotes[taskId] || ''}
                        onChange={(e) => setTechnicianNotes({ ...technicianNotes, [taskId]: e.target.value })}
                        className="w-full rounded-xl border border-line bg-surface p-3 text-xs font-mono text-ink outline-none focus:border-red-500"
                      />
                      <button
                        type="button"
                        onClick={() => alert(`Logged remarks for ${taskId}`)}
                        className="px-4 py-2 rounded-full bg-ink text-deep text-xs font-mono font-bold uppercase tracking-wider"
                      >
                        Save Field Log
                      </button>
                    </motion.div>
                  )}

                  {/* Action Bar */}
                  <div className="flex flex-wrap items-center gap-3 pt-3 border-t border-line">
                    {task.status !== 'IN_PROGRESS' && task.status !== 'COMPLETED' && (
                      <button
                        type="button"
                        disabled={isUpdating}
                        onClick={() => handleStatusChange(taskId, 'IN_PROGRESS')}
                        className="flex items-center gap-2 px-5 py-2.5 rounded-full bg-amber-500 hover:bg-amber-600 text-black font-mono text-xs font-bold uppercase tracking-wider transition-all disabled:opacity-50"
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
                        className="flex items-center gap-2 px-5 py-2.5 rounded-full bg-emerald-600 hover:bg-emerald-700 text-white font-mono text-xs font-bold uppercase tracking-wider transition-all disabled:opacity-50"
                      >
                        <CheckCircle size={15} />
                        {isUpdating ? 'UPDATING...' : 'Mark Done'}
                      </button>
                    )}

                    <button
                      type="button"
                      onClick={() => setExpandedNotes(prev => ({ ...prev, [taskId]: !prev[taskId] }))}
                      className="flex items-center gap-1.5 px-4 py-2.5 rounded-full border border-line bg-surface text-muted hover:text-ink font-mono text-xs font-semibold uppercase tracking-wider transition-colors ml-auto"
                    >
                      <span>{isExpanded ? 'Hide Log' : 'Site Anomaly Log'}</span>
                      {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>

                    <button
                      type="button"
                      onClick={() => openTaskPopUp(task)}
                      className="flex items-center gap-1.5 px-4 py-2.5 rounded-full border border-line bg-surface text-ink hover:border-red-500 font-mono text-xs font-bold uppercase tracking-wider transition-colors"
                    >
                      <span>Details</span>
                      <ExternalLink size={14} />
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
