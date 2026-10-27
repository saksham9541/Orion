import { useEffect, useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  CheckCircle,
  PlayCircle,
  Clock,
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  Wrench,
  Radio,
  MapPin,
  CheckSquare,
  Square,
  Search,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Zap,
  Activity,
  Plus
} from 'lucide-react'
import PortalLayout from '@/components/app/PortalLayout'
import DepartmentTaskModal from '@/components/app/DepartmentTaskModal'
import ReportComplaintModal from '@/components/app/ReportComplaintModal'
import { fetchTasks, updateTaskStatus } from '@/api'

const PRE_WORK_CHECKLIST_ITEMS = [
  { id: 'flag', label: 'Banner Flag & Detonators placed 1,200m ahead & rear' },
  { id: 'discharge', label: '25kV Catenary Discharge Rod connected to rail Earth' },
  { id: 'shunt', label: 'Track Circuit Shunting Clamp locked across railhead' },
  { id: 'ppe', label: 'High-visibility retroreflective vest & safety boots worn' },
  { id: 'radio', label: 'VHF Walkie-Talkie locked to Guard/Driver Channel 04' }
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
    // Format task to match modal expectations
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
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6">
        
        {/* TOP STATUS BAR: NOTHING OS STYLE */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-[24px] border border-line bg-surface shadow-sm"
        >
          <div className="flex items-center gap-3.5">
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-red-500/10 text-red-500 border border-red-500/30">
              <Wrench size={22} />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-dot text-base sm:text-lg font-bold text-ink uppercase tracking-wider">
                  FIELD CREW WORKBENCH
                </h1>
                <span className="rounded-full bg-emerald-500/15 border border-emerald-500/30 px-2.5 py-0.5 text-[10px] font-mono font-bold text-emerald-500 uppercase flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-ping inline-block" />
                  UNIT 04 · ON-DUTY
                </span>
              </div>
              <p className="text-[11px] font-mono text-muted uppercase tracking-widest mt-0.5">
                PERMIT #IR-PWR-8821 · GEOFENCE: KM 14.500 [NDLS-TKD-UP] · SHIFT: NIGHT-02
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={() => setIsReportOpen(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-full bg-red-600 hover:bg-red-700 text-white font-mono text-xs font-bold uppercase tracking-wider shadow-sm transition-all active:scale-[0.98]"
            >
              <Plus size={14} />
              <span>Report Site Defect</span>
            </button>
            <button
              onClick={loadTasks}
              className="p-2.5 rounded-full border border-line bg-raised hover:bg-surface text-muted hover:text-ink transition-colors"
              title="Refresh Workbench"
            >
              <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
            </button>
          </div>
        </motion.div>

        {/* BENTO KPI DECK (NOTHING OS 4-UP) */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5">
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            className="p-4 rounded-2xl border border-line bg-surface/80 backdrop-blur-md shadow-sm"
          >
            <p className="text-[9.5px] font-mono font-bold text-muted uppercase tracking-[0.16em] mb-1">
              [ 01 // ASSIGNED ORDERS ]
            </p>
            <p className="text-2xl font-dot tracking-tight text-ink">{stats.total}</p>
            <span className="text-[10px] font-mono text-muted uppercase tracking-wider">
              {stats.inProgress} ACTIVE IN PROGRESS
            </span>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="p-4 rounded-2xl border border-line bg-surface/80 backdrop-blur-md shadow-sm"
          >
            <p className="text-[9.5px] font-mono font-bold text-emerald-500 uppercase tracking-[0.16em] mb-1">
              [ 02 // SAFETY INTERLOCK ]
            </p>
            <p className="text-xl font-dot tracking-tight text-emerald-500 flex items-center gap-2">
              <ShieldCheck size={20} />
              SAFE TO WORK
            </p>
            <span className="text-[10px] font-mono text-emerald-500/80 uppercase tracking-wider">
              25kV OHE ISOLATED & GROUNDED
            </span>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="p-4 rounded-2xl border border-line bg-surface/80 backdrop-blur-md shadow-sm"
          >
            <p className="text-[9.5px] font-mono font-bold text-amber-500 uppercase tracking-[0.16em] mb-1">
              [ 03 // BLOCK WINDOW ]
            </p>
            <p className="text-2xl font-dot tracking-tight text-amber-500 flex items-center gap-2">
              <Clock size={20} />
              02h 45m
            </p>
            <span className="text-[10px] font-mono text-amber-500/80 uppercase tracking-wider">
              SANCTION EXPIRES 05:30 HRS
            </span>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="p-4 rounded-2xl border border-line bg-surface/80 backdrop-blur-md shadow-sm"
          >
            <p className="text-[9.5px] font-mono font-bold text-info uppercase tracking-[0.16em] mb-1">
              [ 04 // SQUAD ON SITE ]
            </p>
            <p className="text-2xl font-dot tracking-tight text-info flex items-center gap-2">
              <Radio size={20} />
              4 TECHS
            </p>
            <span className="text-[10px] font-mono text-info/80 uppercase tracking-wider">
              1 SSE · 1 FITTER · 2 MATES
            </span>
          </motion.div>
        </div>

        {/* TWO-COLUMN WORKBENCH: SAFETY CHECKLIST + WORK ORDERS */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          
          {/* LEFT (4 cols): MANDATORY PRE-WORK PROTOCOL */}
          <motion.div
            initial={{ opacity: 0, x: -15 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            className="lg:col-span-4 rounded-[28px] border border-line bg-surface p-5 shadow-sm space-y-4"
          >
            <div className="flex items-center justify-between pb-3 border-b border-line">
              <div>
                <h2 className="font-dot text-sm font-bold text-ink uppercase tracking-wider flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-[#d71920] inline-block" />
                  SAFETY INTERLOCK PROTOCOL
                </h2>
                <p className="text-[10px] font-mono text-muted uppercase tracking-widest mt-0.5">
                  MANDATORY BEFORE TRACK OCCUPATION
                </p>
              </div>
              <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${
                allSafetyCleared ? 'bg-emerald-500/15 text-emerald-500 border border-emerald-500/30' : 'bg-amber-500/15 text-amber-500 border border-amber-500/30'
              }`}>
                {allSafetyCleared ? 'ALL CLEARED' : 'PENDING CHECK'}
              </span>
            </div>

            <div className="space-y-2.5">
              {PRE_WORK_CHECKLIST_ITEMS.map((item) => {
                const isChecked = checklist[item.id]
                return (
                  <div
                    key={item.id}
                    onClick={() => toggleChecklist(item.id)}
                    className={`p-3 rounded-2xl border transition-all cursor-pointer flex items-start gap-3 select-none ${
                      isChecked
                        ? 'border-emerald-500/40 bg-emerald-500/5 text-ink'
                        : 'border-line bg-raised/50 text-muted hover:border-line-hover'
                    }`}
                  >
                    <span className={`mt-0.5 ${isChecked ? 'text-emerald-500' : 'text-muted'}`}>
                      {isChecked ? <CheckSquare size={17} /> : <Square size={17} />}
                    </span>
                    <span className="text-xs font-medium leading-snug">
                      {item.label}
                    </span>
                  </div>
                )
              })}
            </div>

            {/* Field Tool Box status */}
            <div className="mt-4 pt-4 border-t border-line space-y-2">
              <span className="text-[10px] font-mono font-bold text-muted uppercase tracking-wider block">
                FIELD TOOLBOX STATUS:
              </span>
              <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
                <div className="p-2 rounded-xl border border-line bg-raised/70">
                  <span className="text-faint block">USFD Probe:</span>
                  <span className="text-ink font-bold">READY (CAL-OK)</span>
                </div>
                <div className="p-2 rounded-xl border border-line bg-raised/70">
                  <span className="text-faint block">Hydraulic Tensor:</span>
                  <span className="text-ink font-bold">70T PRESSURISED</span>
                </div>
                <div className="p-2 rounded-xl border border-line bg-raised/70">
                  <span className="text-faint block">Torque Wrench:</span>
                  <span className="text-ink font-bold">450 N·m SET</span>
                </div>
                <div className="p-2 rounded-xl border border-line bg-raised/70">
                  <span className="text-faint block">First Aid Kit:</span>
                  <span className="text-emerald-500 font-bold">SEALED / VERIFIED</span>
                </div>
              </div>
            </div>
          </motion.div>

          {/* RIGHT (8 cols): ACTIVE WORK ORDERS */}
          <motion.div
            initial={{ opacity: 0, x: 15 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            className="lg:col-span-8 rounded-[28px] border border-line bg-surface p-5 shadow-sm space-y-4"
          >
            {/* Filter and Search Bar */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-line">
              <div className="relative flex-1">
                <Search size={14} className="absolute left-3.5 top-2.5 text-muted" />
                <input
                  type="text"
                  placeholder="Filter work order ID, category, KM..."
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  className="w-full rounded-full border border-line bg-raised pl-9 pr-4 py-1.5 text-xs font-mono text-ink placeholder:text-muted focus:border-red-500 focus:outline-none"
                />
              </div>

              <div className="flex items-center gap-1.5 flex-wrap">
                {['ALL', 'ACTIVE', 'PENDING', 'COMPLETED', 'CRITICAL'].map((f) => (
                  <button
                    key={f}
                    onClick={() => setFilterStatus(f)}
                    className={`rounded-full px-3 py-1 text-[10px] font-mono font-bold uppercase tracking-wider transition-all ${
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

            {/* List of Tasks */}
            {loading && (
              <div className="p-12 text-center text-muted font-mono text-xs flex items-center justify-center gap-2">
                <RefreshCw size={16} className="animate-spin" />
                SYNCHRONIZING FIELD WORK ORDERS...
              </div>
            )}

            {!loading && error && (
              <div className="p-6 text-center text-warn bg-warn/10 rounded-2xl border border-warn/20 font-mono text-xs">
                {error}
              </div>
            )}

            {!loading && !error && filteredTasks.length === 0 && (
              <div className="p-12 text-center text-muted border border-dashed border-line rounded-2xl bg-raised/30">
                <CheckCircle className="mx-auto mb-2 text-emerald-500 opacity-60" size={36} />
                <p className="font-dot text-sm font-bold text-ink uppercase">No Matching Work Orders</p>
                <p className="text-xs text-muted font-mono mt-1">All designated tasks for this filter have been satisfied.</p>
              </div>
            )}

            <div className="space-y-3.5">
              {filteredTasks.map((task) => {
                const taskId = task.task_id || task.id
                const isCritical = ['EMERGENCY', 'CRITICAL', 'HIGH'].includes((task.severity || '').toUpperCase())
                const isExpanded = expandedNotes[taskId]
                const isUpdating = actionLoading === taskId

                return (
                  <motion.div
                    key={taskId}
                    initial={{ opacity: 0, y: 10 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    className="p-5 rounded-[24px] border border-line bg-raised/40 hover:bg-raised/70 transition-all space-y-3.5 group shadow-sm hover:shadow-md"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-mono text-xs font-bold text-ink bg-surface border border-line px-2 py-0.5 rounded-md">
                            {taskId}
                          </span>
                          <span className={`px-2 py-0.5 rounded-md text-[10px] font-mono font-bold uppercase border ${
                            isCritical
                              ? 'bg-red-500/10 text-red-500 border-red-500/30'
                              : 'bg-blue-500/10 text-blue-500 border-blue-500/30'
                          }`}>
                            {task.severity || 'HIGH'}
                          </span>
                          <span className="px-2 py-0.5 rounded-md text-[10px] font-mono font-bold uppercase bg-surface border border-line text-muted">
                            DEPT: {task.department || 'ENGINEERING'}
                          </span>
                        </div>
                        <h3 className="font-dot text-sm font-bold text-ink uppercase tracking-wider mt-1.5">
                          {task.defect_category || task.defectType || 'Track Maintenance Order'}
                        </h3>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className={`px-2.5 py-1 rounded-full text-[10px] font-mono font-bold tracking-wider uppercase border ${
                          task.status === 'IN_PROGRESS'
                            ? 'bg-amber-500/15 text-amber-500 border-amber-500/30 animate-pulse'
                            : task.status === 'COMPLETED'
                            ? 'bg-emerald-500/15 text-emerald-500 border-emerald-500/30'
                            : 'bg-surface border-line text-muted'
                        }`}>
                          {task.status.replace('_', ' ')}
                        </span>
                        <button
                          type="button"
                          onClick={() => openTaskPopUp(task)}
                          className="p-1.5 rounded-full border border-line bg-surface text-muted hover:text-ink hover:border-line-hover transition-colors"
                          title="Open Pop-up"
                        >
                          <ExternalLink size={14} />
                        </button>
                      </div>
                    </div>

                    <p className="text-xs text-muted leading-relaxed font-sans">
                      {task.inspector_remarks || task.defect_description || 'Track surface anomaly detected during inspection. Requires manual tension test.'}
                    </p>

                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] font-mono pt-2 border-t border-line/60">
                      <div>
                        <span className="text-faint block">CORRIDOR:</span>
                        <span className="text-ink font-semibold">{task.corridor_id || 'NDLS-CNB'}</span>
                      </div>
                      <div>
                        <span className="text-faint block">KM POST:</span>
                        <span className="text-ink font-semibold">KM {task.km_location || '14.500'}</span>
                      </div>
                      <div>
                        <span className="text-faint block">EST TIME:</span>
                        <span className="text-ink font-semibold">{task.estimated_duration_hours || 2} HOURS</span>
                      </div>
                      <div>
                        <span className="text-faint block">TARGET SPEED:</span>
                        <span className="text-ink font-semibold">130 KM/H</span>
                      </div>
                    </div>

                    {/* Expandable Anomaly Notes */}
                    {isExpanded && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        className="p-3 rounded-xl border border-line bg-surface space-y-2"
                      >
                        <label className="text-[10px] font-mono font-bold uppercase tracking-wider text-muted block">
                          Technician Field Observation & Log:
                        </label>
                        <textarea
                          rows={2}
                          placeholder="Log torque reading, rail gap millimeter, temperature..."
                          value={technicianNotes[taskId] || ''}
                          onChange={(e) => setTechnicianNotes({ ...technicianNotes, [taskId]: e.target.value })}
                          className="w-full rounded-lg border border-line bg-raised p-2 text-xs font-mono text-ink outline-none focus:border-red-500"
                        />
                        <button
                          type="button"
                          onClick={() => alert(`Logged remarks for ${taskId}`)}
                          className="px-3 py-1 rounded-md bg-ink text-deep text-[10px] font-mono font-bold uppercase tracking-wider"
                        >
                          Save Field Log
                        </button>
                      </motion.div>
                    )}

                    {/* Action Bar */}
                    <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-line">
                      {task.status !== 'IN_PROGRESS' && task.status !== 'COMPLETED' && (
                        <button
                          type="button"
                          disabled={isUpdating}
                          onClick={() => handleStatusChange(taskId, 'IN_PROGRESS')}
                          className="flex items-center gap-1.5 px-4 py-2 rounded-full bg-amber-500 hover:bg-amber-600 text-black font-mono text-xs font-bold uppercase tracking-wider transition-all disabled:opacity-50"
                        >
                          <PlayCircle size={14} />
                          {isUpdating ? 'STARTING...' : 'Start Action'}
                        </button>
                      )}

                      {task.status !== 'COMPLETED' && (
                        <button
                          type="button"
                          disabled={isUpdating}
                          onClick={() => handleStatusChange(taskId, 'COMPLETED')}
                          className="flex items-center gap-1.5 px-4 py-2 rounded-full bg-emerald-600 hover:bg-emerald-700 text-white font-mono text-xs font-bold uppercase tracking-wider transition-all disabled:opacity-50"
                        >
                          <CheckCircle size={14} />
                          {isUpdating ? 'UPDATING...' : 'Mark Done'}
                        </button>
                      )}

                      <button
                        type="button"
                        onClick={() => setExpandedNotes(prev => ({ ...prev, [taskId]: !prev[taskId] }))}
                        className="flex items-center gap-1 px-3 py-2 rounded-full border border-line bg-surface text-muted hover:text-ink font-mono text-xs font-semibold uppercase tracking-wider transition-colors ml-auto"
                      >
                        <span>{isExpanded ? 'Hide Log' : 'Site Anomaly Log'}</span>
                        {isExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                      </button>

                      <button
                        type="button"
                        onClick={() => openTaskPopUp(task)}
                        className="flex items-center gap-1 px-3 py-2 rounded-full border border-line bg-surface text-ink hover:border-red-500 font-mono text-xs font-bold uppercase tracking-wider transition-colors"
                      >
                        <span>Details</span>
                        <ExternalLink size={13} />
                      </button>
                    </div>
                  </motion.div>
                )
              })}
            </div>
          </motion.div>
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
