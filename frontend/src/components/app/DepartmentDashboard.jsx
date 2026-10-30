import { useState, useEffect, useMemo, useCallback } from 'react'
import { motion } from 'framer-motion'
import { Navigate, useSearchParams } from 'react-router-dom'
import {
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Clock,
  PlayCircle,
  Check,
  XCircle,
  ShieldAlert,
  Search,
  Filter,
  ExternalLink,
  ChevronRight,
  Loader2,
  Sparkles,
  MapPin,
  RefreshCw,
  Wrench,
  Layers,
  ArrowUpDown,
  MoreHorizontal,
  Calendar,
  Plus,
  Share2,
  FileText
} from 'lucide-react'
import PortalLayout from '@/components/app/PortalLayout'
import { useAppState } from '@/state/AppState'
import { useLiveSync } from '@/state/LiveSyncStore'
import IndiaRailwayMap from '@/components/network/IndiaRailwayMap'
import DepartmentTaskModal from '@/components/app/DepartmentTaskModal'
import DepartmentBlockReview from '@/components/plan/DepartmentBlockReview'
import AwaitingAckInbox from '@/components/tasks/AwaitingAckInbox'
import CannotStartModal from '@/components/tasks/CannotStartModal'
import EmergencyImpactModal from '@/components/tasks/EmergencyImpactModal'
import { fetchDashboardCounts, fetchLiveTrains, fetchPlans, fetchTasks, updateTaskStatus } from '@/api'

const DEFAULT_TASKS_BY_DEPT = {
  snt: [
    {
      task_id: 'RO-SNT-042',
      department: 'SNT',
      defect_category: 'POINT_MACHINE_FAILURE',
      raw_severity: 'CRITICAL',
      ml_predicted_severity: 'CRITICAL',
      corridor_id: 'COR_DELHI_MUMBAI',
      section_id: 'NDLS-TKD',
      km_location: 12.4,
      km_end: 12.8,
      is_safety_critical: true,
      status: 'PENDING',
      reported_date: 'Today, 08:30 AM',
      inspector_remarks: 'Intermittent signal failure reported at Main Junction approach. Loss of track circuit continuity.',
      ml_criticality_score: 0.92,
      ml_predicted_duration_hours: 2.5,
      days_overdue: 2,
      historical_failure_count: 4
    },
    {
      task_id: 'RO-SNT-088',
      department: 'SNT',
      defect_category: 'APPROACH_SIGNAL_ANOMALY',
      raw_severity: 'HIGH',
      ml_predicted_severity: 'HIGH',
      corridor_id: 'COR_HOWRAH_DELHI',
      section_id: 'LKO-CNB',
      km_location: 38.6,
      km_end: 39.0,
      is_safety_critical: true,
      status: 'SCHEDULED',
      reported_date: 'Yesterday',
      inspector_remarks: 'Approach signal 4A relay fluctuating during heavy rainfall. Caution order active.',
      ml_criticality_score: 0.81,
      ml_predicted_duration_hours: 2.0,
      days_overdue: 1,
      historical_failure_count: 2
    },
    {
      task_id: 'RO-SNT-103',
      department: 'SNT',
      defect_category: 'TRACK_CIRCUIT_DEGRADATION',
      raw_severity: 'MEDIUM',
      ml_predicted_severity: 'MEDIUM',
      corridor_id: 'COR_DELHI_MUMBAI',
      section_id: 'LDH-PGW',
      km_location: 104.2,
      km_end: 104.5,
      is_safety_critical: false,
      status: 'IN_PROGRESS',
      reported_date: '2 days ago',
      inspector_remarks: 'Audio frequency track circuit receiver voltage dropped 18%. Ground continuity verified.',
      ml_criticality_score: 0.65,
      ml_predicted_duration_hours: 1.5,
      days_overdue: 0,
      historical_failure_count: 1
    },
    {
      task_id: 'RO-SNT-119',
      department: 'SNT',
      defect_category: 'AXLE_COUNTER_RESET',
      raw_severity: 'LOW',
      ml_predicted_severity: 'LOW',
      corridor_id: 'COR_DELHI_MUMBAI',
      section_id: 'JP-FL',
      km_location: 77.0,
      km_end: 77.2,
      is_safety_critical: false,
      status: 'COMPLETED',
      reported_date: '3 days ago',
      inspector_remarks: 'Dual axle counter sensor head calibration completed and verified.',
      ml_criticality_score: 0.35,
      ml_predicted_duration_hours: 1.0,
      days_overdue: 0,
      historical_failure_count: 0
    },
    {
      task_id: 'RO-SNT-145',
      department: 'SNT',
      defect_category: 'TELEMETRY_CABLE_FAULT',
      raw_severity: 'HIGH',
      ml_predicted_severity: 'HIGH',
      corridor_id: 'COR_DELHI_MUMBAI',
      section_id: 'NDLS-TKD',
      km_location: 52.8,
      km_end: 53.1,
      is_safety_critical: true,
      status: 'PENDING',
      reported_date: 'Today, 06:15 AM',
      inspector_remarks: 'Underground 24-core signaling cable insulation resistance dropped below 2M ohm.',
      ml_criticality_score: 0.85,
      ml_predicted_duration_hours: 3.0,
      days_overdue: 0,
      historical_failure_count: 3
    }
  ],
  engineering: [
    {
      task_id: 'RO-ENG-001',
      department: 'ENGINEERING',
      defect_category: 'RAIL_FRACTURE',
      raw_severity: 'CRITICAL',
      ml_predicted_severity: 'CRITICAL',
      corridor_id: 'COR_DELHI_MUMBAI',
      section_id: 'LDH-PGW',
      km_location: 342.1,
      km_end: 342.5,
      is_safety_critical: true,
      status: 'PENDING',
      reported_date: 'Today, 07:15 AM',
      inspector_remarks: 'Mainline ultrasonic testing flagged longitudinal rail defect on outer curve.',
      ml_criticality_score: 0.95,
      ml_predicted_duration_hours: 3.5,
      days_overdue: 1,
      historical_failure_count: 5
    },
    {
      task_id: 'RO-ENG-034',
      department: 'ENGINEERING',
      defect_category: 'GAUGE_IRREGULARITY',
      raw_severity: 'HIGH',
      ml_predicted_severity: 'HIGH',
      corridor_id: 'COR_DELHI_MUMBAI',
      section_id: 'NDLS-TKD',
      km_location: 88.4,
      km_end: 88.9,
      is_safety_critical: true,
      status: 'SCHEDULED',
      reported_date: 'Yesterday',
      inspector_remarks: 'Track gauge widening detected (+7mm) under dynamic axle load. Speed restricted to 45km/h.',
      ml_criticality_score: 0.84,
      ml_predicted_duration_hours: 2.0,
      days_overdue: 2,
      historical_failure_count: 2
    },
    {
      task_id: 'RO-ENG-058',
      department: 'ENGINEERING',
      defect_category: 'BALLAST_DEFICIENCY',
      raw_severity: 'MEDIUM',
      ml_predicted_severity: 'MEDIUM',
      corridor_id: 'COR_HOWRAH_DELHI',
      section_id: 'LKO-CNB',
      km_location: 140.2,
      km_end: 140.8,
      is_safety_critical: false,
      status: 'IN_PROGRESS',
      reported_date: '2 days ago',
      inspector_remarks: 'Ballast shoulder deficiency along 400m curve. Tamping machine unit assigned.',
      ml_criticality_score: 0.62,
      ml_predicted_duration_hours: 2.5,
      days_overdue: 0,
      historical_failure_count: 1
    },
    {
      task_id: 'RO-ENG-082',
      department: 'ENGINEERING',
      defect_category: 'WELD_MISALIGNMENT',
      raw_severity: 'LOW',
      ml_predicted_severity: 'LOW',
      corridor_id: 'COR_DELHI_MUMBAI',
      section_id: 'JP-FL',
      km_location: 19.5,
      km_end: 19.7,
      is_safety_critical: false,
      status: 'COMPLETED',
      reported_date: '3 days ago',
      inspector_remarks: 'Thermit weld grinding completed; surface straight edge alignment nominal.',
      ml_criticality_score: 0.38,
      ml_predicted_duration_hours: 1.5,
      days_overdue: 0,
      historical_failure_count: 0
    },
    {
      task_id: 'RO-ENG-112',
      department: 'ENGINEERING',
      defect_category: 'POINTS_CROSSING_WEAR',
      raw_severity: 'HIGH',
      ml_predicted_severity: 'HIGH',
      corridor_id: 'COR_DELHI_MUMBAI',
      section_id: 'NDLS-TKD',
      km_location: 210.0,
      km_end: 210.3,
      is_safety_critical: true,
      status: 'PENDING',
      reported_date: 'Today, 09:40 AM',
      inspector_remarks: 'Switch blade nose wear exceeds permissible limit on diamond turnout.',
      ml_criticality_score: 0.88,
      ml_predicted_duration_hours: 3.0,
      days_overdue: 1,
      historical_failure_count: 3
    }
  ],
  trd: [
    {
      task_id: 'RO-TRD-088',
      department: 'TRD',
      defect_category: 'OHE_CATENARY_SAG',
      raw_severity: 'CRITICAL',
      ml_predicted_severity: 'CRITICAL',
      corridor_id: 'COR_DELHI_MUMBAI',
      section_id: 'JP-FL',
      km_location: 156.8,
      km_end: 157.2,
      is_safety_critical: true,
      status: 'PENDING',
      reported_date: 'Today, 07:30 AM',
      inspector_remarks: 'Minor voltage fluctuations and dropper sag detected on OHE catenary wire near Mast 156/22.',
      ml_criticality_score: 0.91,
      ml_predicted_duration_hours: 2.5,
      days_overdue: 1,
      historical_failure_count: 3
    },
    {
      task_id: 'RO-TRD-114',
      department: 'TRD',
      defect_category: 'INSULATOR_FLASHOVER',
      raw_severity: 'HIGH',
      ml_predicted_severity: 'HIGH',
      corridor_id: 'COR_DELHI_MUMBAI',
      section_id: 'NDLS-TKD',
      km_location: 45.2,
      km_end: 45.6,
      is_safety_critical: true,
      status: 'SCHEDULED',
      reported_date: 'Yesterday',
      inspector_remarks: 'Heavy industrial pollution buildup on 25kV composite insulator with corona discharge.',
      ml_criticality_score: 0.82,
      ml_predicted_duration_hours: 2.0,
      days_overdue: 2,
      historical_failure_count: 2
    },
    {
      task_id: 'RO-TRD-136',
      department: 'TRD',
      defect_category: 'SUBSTATION_TEMP_SPIKE',
      raw_severity: 'MEDIUM',
      ml_predicted_severity: 'MEDIUM',
      corridor_id: 'COR_DELHI_MUMBAI',
      section_id: 'LDH-PGW',
      km_location: 92.1,
      km_end: 92.3,
      is_safety_critical: false,
      status: 'IN_PROGRESS',
      reported_date: '2 days ago',
      inspector_remarks: 'Traction transformer oil temperature reached 72°C under peak freight load.',
      ml_criticality_score: 0.60,
      ml_predicted_duration_hours: 1.5,
      days_overdue: 0,
      historical_failure_count: 1
    },
    {
      task_id: 'RO-TRD-152',
      department: 'TRD',
      defect_category: 'MAST_GROUNDING_CHECK',
      raw_severity: 'LOW',
      ml_predicted_severity: 'LOW',
      corridor_id: 'COR_HOWRAH_DELHI',
      section_id: 'LKO-CNB',
      km_location: 118.0,
      km_end: 118.2,
      is_safety_critical: false,
      status: 'COMPLETED',
      reported_date: '4 days ago',
      inspector_remarks: 'OHE portal mast structure bond and earth wire continuity verified.',
      ml_criticality_score: 0.32,
      ml_predicted_duration_hours: 1.0,
      days_overdue: 0,
      historical_failure_count: 0
    },
    {
      task_id: 'RO-TRD-175',
      department: 'TRD',
      defect_category: 'PANTOGRAPH_STAGGER_DEFECT',
      raw_severity: 'HIGH',
      ml_predicted_severity: 'HIGH',
      corridor_id: 'COR_DELHI_MUMBAI',
      section_id: 'NDLS-TKD',
      km_location: 64.3,
      km_end: 64.6,
      is_safety_critical: true,
      status: 'PENDING',
      reported_date: 'Today, 08:50 AM',
      inspector_remarks: 'Contact wire stagger exceeds ±200mm limit at crossover, risk of pantograph entanglement.',
      ml_criticality_score: 0.86,
      ml_predicted_duration_hours: 3.0,
      days_overdue: 0,
      historical_failure_count: 2
    }
  ]
}

function mapBackendTask(t, deptId) {
  const severity = (t.ml_predicted_severity || t.raw_severity || 'MEDIUM').toUpperCase()
  const status = (t.status || 'PENDING').toUpperCase()
  const stationMap = {
    COR_DELHI_MUMBAI: 'NDLS',
    COR_MUMBAI_CHENNAI: 'BCT',
    COR_HOWRAH_DELHI: 'HWH',
    COR_CHENNAI_KOLKATA: 'MAS'
  }
  const locationId = stationMap[t.corridor_id] || (deptId === 'snt' ? 'NDLS' : deptId === 'trd' ? 'JP' : 'LDH')

  const defectCategory = t.defect_category ? String(t.defect_category).replace(/_/g, ' ') : 'Track Maintenance'

  return {
    id: t.task_id || t.id,
    task_id: t.task_id || t.id,
    department: t.department === 'SNT' ? 'S&T' : t.department || deptId.toUpperCase(),
    defectType: defectCategory,
    type: defectCategory,
    severity,
    raw_severity: severity,
    status,
    reported_date: t.reported_date || 'Today',
    time: t.reported_date || 'Today, 08:30 AM',
    locationId,
    locationName: t.corridor_id || 'Mainline Corridor',
    corridorId: t.corridor_id || 'COR-NORTH',
    sectionId: t.section_id || 'SEC-01',
    exactLocation: `KM ${t.km_location ?? '44.2'}${t.km_end ? ` - ${t.km_end}` : ''} (${t.corridor_id || 'Sector 7'})`,
    km_location: t.km_location,
    isSafetyCritical: t.is_safety_critical ?? (severity === 'CRITICAL' || severity === 'HIGH'),
    what: t.inspector_remarks || `${defectCategory} detected in sector requiring maintenance inspection.`,
    causes: [
      { level: 'CONFIRMED', text: 'Telemetry alert threshold exceeded.' },
      { level: 'LIKELY', text: `Defect priority: ${t.severity || 'HIGH'} (verified telemetry).` },
      { level: 'POSSIBLE', text: 'Historical degradation pattern.' }
    ],
    timeline: [
      { desc: `Reported on ${t.reported_date || 'Today'}` },
      { desc: 'Telemetry sensor flag registered' },
      { desc: 'AI Risk classification calculated' },
      { desc: 'Real-time alert dispatched to department' },
      { desc: 'Department action pending' },
      { desc: 'Awaiting maintenance closure' }
    ],
    seriousness: severity,
    impact: {
      safety: t.is_safety_critical ? 'Safety critical defect — immediate caution imposed.' : 'Standard defect within operating tolerance.',
      operations: `Potential ${t.ml_predicted_duration_hours ?? t.estimated_duration_hours ?? 2} hr delay.`,
      maintenance: 'Requires maintenance block reservation.',
      location: t.corridor_id || 'Mainline'
    },
    actions: ['Inspect on-site', 'Coordinate crew', 'Schedule maintenance block'],
    recommendation: 'Schedule maintenance block via RailOpt Optimizer during off-peak window.',
    supporting: [
      { label: 'Overdue', value: `${t.days_overdue ?? 0} days` },
      { label: 'Historical Failures', value: `${t.historical_failure_count ?? 0} past records` },
      { label: 'Est. Duration', value: `${t.ml_predicted_duration_hours ?? t.estimated_duration_hours ?? 2} hrs` }
    ],
    priorityReasons: [
      t.is_safety_critical ? 'High safety risk flag' : 'Operational reliability concern',
      `Severity grade: ${t.severity || 'HIGH'}`
    ],
    daysOverdue: t.days_overdue ?? 0,
    estDuration: t.ml_predicted_duration_hours ?? t.estimated_duration_hours ?? 2
  }
}

export default function DepartmentDashboard({ deptId, title, department }) {
  const { currentUser } = useAppState()
  const [searchParams, setSearchParams] = useSearchParams()
  const targetIssueId = searchParams.get('issue') || searchParams.get('search')

  // Robust department code resolution
  const resolvedDept = useMemo(() => {
    if (department) {
      const d = department.toUpperCase().trim()
      if (d === 'S&T') return 'SNT'
      return d
    }
    if (deptId === 'engineering') return 'ENGINEERING'
    if (deptId === 'snt') return 'SNT'
    if (deptId === 'trd') return 'TRD'
    return 'ENGINEERING'
  }, [department, deptId])

  const [tasks, setTasks] = useState([])
  const [selectedTaskId, setSelectedTaskId] = useState(null)
  const [modalTask, setModalTask] = useState(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [counts, setCounts] = useState({ total: 0, pending: 0, active_scheduled: 0, resolved: 0, pipeline_stages: { intake: 0, planning: 0, execution: 0, resolution: 0 } })
  const [actionInProgress, setActionInProgress] = useState(null)
  const [toastMessage, setToastMessage] = useState(null)
  const [liveTrains, setLiveTrains] = useState([])
  const [activeView, setActiveView] = useState('board')
  const [activePlanId, setActivePlanId] = useState(null)
  const [cannotStartError, setCannotStartError] = useState(null)
  const [emergencyModalTaskId, setEmergencyModalTaskId] = useState(null)

  useEffect(() => {
    fetchPlans()
      .then((res) => {
        const plans = res.data || []
        if (plans.length > 0) {
          const candidate = plans.find(p => ['PROPOSED', 'DEPT_REVIEW', 'CONFLICT', 'READY_FOR_CONTROLLER'].includes(p.status)) || plans[plans.length - 1]
          setActivePlanId(candidate.plan_id)
        }
      })
      .catch(() => {})
  }, [])

  // Filter & Search states
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [currentPage, setCurrentPage] = useState(1)
  const pageSize = 10

  // Load Tasks and Counts from API
  const loadTasks = useCallback(async () => {
    try {
      const [res, countsRes] = await Promise.all([
        fetchTasks({ department: resolvedDept }),
        fetchDashboardCounts(resolvedDept).catch(() => ({ data: null }))
      ])
      if (countsRes?.data) {
        setCounts(countsRes.data)
      }
      const backendTasks = Array.isArray(res.data) ? res.data : []

      if (backendTasks.length > 0) {
        const mapped = backendTasks.map((t) => mapBackendTask(t, deptId))
        // Put newest tasks at the top, prioritizing user-reported / active complaint tasks
        mapped.reverse()
        mapped.sort((a, b) => {
          const aIsUser = a.id?.startsWith('TSK-')
          const bIsUser = b.id?.startsWith('TSK-')
          if (aIsUser && !bIsUser) return -1
          if (!aIsUser && bIsUser) return 1
          return 0
        })
        setTasks(mapped)
        if (targetIssueId) {
          const match = mapped.find((m) => m.id === targetIssueId)
          if (match) {
            setSelectedTaskId(match.id)
            setModalTask(match)
            setIsModalOpen(true)
          } else {
            setSelectedTaskId(mapped[0]?.id || null)
          }
        } else {
          setSelectedTaskId((prev) => (mapped.some((m) => m.id === prev) ? prev : mapped[0]?.id || null))
        }
      } else {
        // Fallback to curated default tasks so the dashboard is immediately interactive
        const defaults = (DEFAULT_TASKS_BY_DEPT[deptId] || []).map((t) => mapBackendTask(t, deptId))
        setTasks(defaults)
        if (targetIssueId) {
          const match = defaults.find((m) => m.id === targetIssueId)
          if (match) {
            setSelectedTaskId(match.id)
            setModalTask(match)
            setIsModalOpen(true)
          } else {
            setSelectedTaskId(defaults[0]?.id || null)
          }
        } else {
          setSelectedTaskId(defaults[0]?.id || null)
        }
      }
    } catch (err) {
      console.warn('Backend tasks unavailable, using department defaults:', err)
      const defaults = (DEFAULT_TASKS_BY_DEPT[deptId] || []).map((t) => mapBackendTask(t, deptId))
      setTasks(defaults)
      setSelectedTaskId(defaults[0]?.id || null)
      setCounts({
        total: defaults.length,
        pending: defaults.filter(t => ['DRAFT', 'SUBMITTED', 'REPORTED', 'UNVERIFIED', 'PENDING', 'SCORED', 'ESCALATED', 'DEFERRED'].includes((t.status || '').toUpperCase())).length,
        active_scheduled: defaults.filter(t => ['APPROVED', 'READY', 'SCHEDULED', 'IN_PROGRESS', 'SUSPENDED', 'OVERRUN', 'WINDOWS_PROPOSED', 'WINDOW_SELECTED'].includes((t.status || '').toUpperCase())).length,
        resolved: defaults.filter(t => ['COMPLETED', 'ABORTED', 'CANCELLED', 'REJECTED'].includes((t.status || '').toUpperCase())).length,
        pipeline_stages: {
          intake: defaults.filter(t => ['DRAFT', 'SUBMITTED', 'REPORTED', 'UNVERIFIED', 'DEFERRED', 'ESCALATED'].includes((t.status || '').toUpperCase())).length,
          planning: defaults.filter(t => ['PENDING', 'SCORED', 'WINDOWS_PROPOSED', 'WINDOW_SELECTED'].includes((t.status || '').toUpperCase())).length,
          execution: defaults.filter(t => ['APPROVED', 'READY', 'SCHEDULED', 'IN_PROGRESS', 'SUSPENDED', 'OVERRUN'].includes((t.status || '').toUpperCase())).length,
          resolution: defaults.filter(t => ['COMPLETED', 'ABORTED', 'CANCELLED', 'REJECTED'].includes((t.status || '').toUpperCase())).length,
        }
      })
    } finally {
      setLoading(false)
    }
  }, [resolvedDept, deptId, targetIssueId])

  useEffect(() => {
    loadTasks()

    // 1. Listen for global task creation & updates from WebSockets or local events
    const handleTaskCreated = () => {
      loadTasks()
    }
    const handleTaskUpdated = (e) => {
      const { task_id, status } = e.detail || {}
      if (task_id && status) {
        setTasks((prev) =>
          prev.map((t) => (t.id === task_id ? { ...t, status } : t))
        )
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

    // 2. Real-time polling interval (every 3.5s) to guarantee instant cross-dashboard sync
    const pollTimer = setInterval(() => {
      loadTasks()
    }, 3500)

    return () => {
      window.removeEventListener('railopt:task-created', handleTaskCreated)
      window.removeEventListener('railopt:task-updated', handleTaskUpdated)
      window.removeEventListener('storage', handleStorage)
      clearInterval(pollTimer)
    }
  }, [loadTasks])

  useEffect(() => {
    fetchLiveTrains().then((res) => setLiveTrains(res.data)).catch(console.error)
  }, [])

  useEffect(() => {
    setCurrentPage(1)
  }, [statusFilter, searchQuery])

  // Status Change Handler (works from both the table, dashboard buttons, and pop-up modal!)
  const handleStatusChange = async (taskId, targetStatus) => {
    setActionInProgress(targetStatus)
    try {
      // 1. Optimistic update (skip for IN_PROGRESS to enforce start gate check)
      if (targetStatus !== 'IN_PROGRESS') {
        setTasks((prev) =>
          prev.map((t) => (t.id === taskId ? { ...t, status: targetStatus } : t))
        )
        if (modalTask && modalTask.id === taskId) {
          setModalTask((prev) => ({ ...prev, status: targetStatus }))
        }
      }

      // 2. Persist to Backend API
      await updateTaskStatus(taskId, { status: targetStatus })

      // 3. Broadcast sync event locally & cross-tab
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('railopt:task-updated', {
          detail: { task_id: taskId, status: targetStatus }
        }))
        try {
          localStorage.setItem('railopt_task_sync', JSON.stringify({
            task_id: taskId,
            status: targetStatus,
            timestamp: Date.now()
          }))
        } catch {}
      }

      setToastMessage(`Task ${taskId} marked as ${targetStatus}`)
      setTimeout(() => setToastMessage(null), 3500)
    } catch (err) {
      if (err.response?.status === 409 && err.response?.data?.detail) {
        setCannotStartError(err.response.data.detail)
        throw err
      }
      console.warn('Status update failed:', err)
      setToastMessage(`Failed to update task ${taskId}`)
      setTimeout(() => setToastMessage(null), 3500)
      throw err
    } finally {
      setActionInProgress(null)
    }
  }

  // Quick Action Handler for Journey Board cards
  const handleQuickAction = async (taskId, actionType, note) => {
    let targetStatus = 'SCHEDULED'
    if (actionType === 'START_ACTION') targetStatus = 'IN_PROGRESS'
    if (actionType === 'RESOLVE' || actionType === 'DONE') targetStatus = 'COMPLETED'
    if (actionType === 'AUTHORIZE') targetStatus = 'SCHEDULED'
    await handleStatusChange(taskId, targetStatus)
  }

  // Active Selected Task
  const selectedTask = useMemo(() => {
    return tasks.find((t) => t.id === selectedTaskId) || tasks[0] || null
  }, [tasks, selectedTaskId])

  // Filtered Tasks for the Table
  const filteredTasks = useMemo(() => {
    return tasks.filter((t) => {
      // Status filter
      if (statusFilter !== 'ALL') {
        const s = (t.status || '').toUpperCase()
        if (statusFilter === 'PENDING') {
          if (!['PENDING', 'UNVERIFIED', 'NEW', 'SCORED', 'DRAFT', 'SUBMITTED', 'ESCALATED', 'REPORTED', 'ACKNOWLEDGED'].includes(s)) return false
        } else if (statusFilter === 'SCHEDULED') {
          if (!['SCHEDULED', 'DEPARTMENT NOTIFIED', 'AUTHORIZED'].includes(s)) return false
        } else if (statusFilter === 'IN_PROGRESS') {
          if (!['IN_PROGRESS', 'IN PROGRESS', 'ACTION STARTED'].includes(s)) return false
        } else if (statusFilter === 'COMPLETED') {
          if (!['COMPLETED', 'RESOLVED', 'DONE'].includes(s)) return false
        } else if (statusFilter === 'REJECTED') {
          if (!['REJECTED', 'CANCELLED'].includes(s)) return false
        }
      }
      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase()
        const matchId = t.id.toLowerCase().includes(q)
        const matchDefect = (t.defectType || '').toLowerCase().includes(q)
        const matchWhat = (t.what || '').toLowerCase().includes(q)
        const matchLocation = (t.exactLocation || '').toLowerCase().includes(q)
        if (!matchId && !matchDefect && !matchWhat && !matchLocation) return false
      }
      return true
    })
  }, [tasks, statusFilter, searchQuery])

  // Dynamic Statistics
  const stats = useMemo(() => {
    const total = tasks.length
    const pending = tasks.filter((t) => ['PENDING', 'UNVERIFIED', 'NEW', 'SCORED', 'DRAFT', 'SUBMITTED', 'ESCALATED', 'REPORTED', 'ACKNOWLEDGED'].includes((t.status || '').toUpperCase())).length
    const inProgress = tasks.filter((t) => ['IN_PROGRESS', 'IN PROGRESS', 'SCHEDULED', 'DEPARTMENT NOTIFIED', 'AUTHORIZED'].includes((t.status || '').toUpperCase())).length
    const resolved = tasks.filter((t) => ['COMPLETED', 'RESOLVED', 'DONE'].includes((t.status || '').toUpperCase())).length
    return { total, pending, inProgress, resolved }
  }, [tasks])

  const openTaskModal = (task) => {
    setSelectedTaskId(task.id)
    setModalTask(task)
    setIsModalOpen(true)
  }

  // Colors
  const getSeverityBadge = (level) => {
    const l = (level || '').toUpperCase()
    if (l === 'CRITICAL' || l === 'EMERGENCY') return 'bg-red-500/10 text-red-600 border-red-500/30'
    if (l === 'HIGH') return 'bg-amber-500/10 text-amber-600 border-amber-500/30'
    if (l === 'MEDIUM') return 'bg-blue-500/10 text-blue-600 border-blue-500/30'
    return 'bg-emerald-500/10 text-emerald-600 border-emerald-500/30'
  }

  const getStatusBadge = (status) => {
    const s = (status || '').toUpperCase()
    if (s === 'COMPLETED' || s === 'RESOLVED' || s === 'DONE') return 'bg-emerald-500/15 text-emerald-600 border-emerald-500/30'
    if (s === 'IN_PROGRESS' || s === 'IN PROGRESS') return 'bg-amber-500/15 text-amber-600 border-amber-500/30'
    if (s === 'SCHEDULED' || s === 'ESCALATED' || s === 'DEPARTMENT NOTIFIED' || s === 'AUTHORIZED') return 'bg-blue-500/15 text-blue-600 border-blue-500/30'
    if (s === 'REJECTED' || s === 'CANCELLED') return 'bg-red-500/15 text-red-600 border-red-500/30'
    return 'bg-raised text-muted border-line'
  }

  // Auth Guard sits after all hooks so hook ordering is identical on every render
  if (currentUser?.id !== deptId && currentUser?.id !== 'admin') {
    return <Navigate to="/restricted" replace />
  }

  return (
    <PortalLayout role={deptId}>
      {/* Pop-through Detail Modal */}
      <DepartmentTaskModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        task={modalTask}
        onStatusChange={handleStatusChange}
        onOpenEmergencyImpact={(tid) => setEmergencyModalTaskId(tid)}
      />

      {/* Start Gate Blocked Modal */}
      <CannotStartModal
        isOpen={!!cannotStartError}
        errorData={cannotStartError}
        onClose={() => setCannotStartError(null)}
        onRequestNewWindow={() => {
          setCannotStartError(null)
          alert('Window request submitted to Controller.')
        }}
      />

      {/* Emergency Delay Impact Modal */}
      <EmergencyImpactModal
        isOpen={!!emergencyModalTaskId}
        onClose={() => setEmergencyModalTaskId(null)}
        taskId={emergencyModalTaskId}
      />

      {/* Toast Alert */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-xl border border-emerald-500/40 bg-surface px-4 py-3 shadow-2xl animate-in slide-in-from-bottom duration-200">
          <CheckCircle2 size={18} className="text-emerald-500" />
          <span className="text-xs font-bold text-ink">{toastMessage}</span>
        </div>
      )}

      {/* Header — Modern Gradient Typography */}
      <div className="mb-10 flex flex-col md:flex-row md:items-center justify-between gap-6 pb-6 border-b border-line/60">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gradient-brand flex items-center gap-2.5">
              Maintenance Journeys
              <span className="h-2.5 w-2.5 rounded-full bg-[#D99A2B] inline-block" />
            </h1>
            <span className="rounded-full border border-line bg-surface px-3 py-1 text-[10px] font-mono font-bold uppercase tracking-widest text-muted">
              LIVE RADAR
            </span>
          </div>
          <p className="text-xs font-mono uppercase tracking-[0.18em] text-muted mt-2">
            [ DEPT // {department} ] · SYSTEM TELEMETRY & CROSS-CORRIDOR RESOLUTION FLOW
          </p>
        </div>

        {/* Team Avatars Cluster & Utility Buttons */}
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={loadTasks}
              disabled={loading}
              className="flex h-10 w-10 items-center justify-center rounded-full border border-line bg-surface text-muted hover:text-ink hover:border-[#d71920] transition-colors shadow-sm"
              title="Refresh Tasks"
            >
              <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
            </button>

            <button
              type="button"
              onClick={() => {
                const pending = tasks.find((t) => t.status === 'PENDING')
                if (pending) openTaskModal(pending)
                else if (tasks[0]) openTaskModal(tasks[0])
              }}
              className="flex items-center gap-2 rounded-full bg-ink text-deep px-5 py-2.5 text-xs font-mono font-bold uppercase tracking-wider shadow-sm hover:opacity-90 transition-opacity active:scale-95"
            >
              <span className="h-2 w-2 rounded-full bg-[#d71920] inline-block" />
              <span>Review Urgent</span>
            </button>
          </div>
        </div>
      </div>

      {/* Dynamic Metric Bento Cards — Nothing OS Widget Design (SPACIOUS 4-UP) */}
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.4 }}
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-10"
      >
        <div className="bg-surface/80 backdrop-blur-md p-6 sm:p-7 border border-line/80 rounded-[28px] shadow-sm hover:border-blue-500/40 transition-all space-y-2">
          <p className="text-xs font-mono font-bold text-muted uppercase tracking-[0.18em]">[ 01 // TOTAL TASKS ]</p>
          <p className="text-3xl sm:text-4xl font-bold font-sans tracking-tight text-ink">{counts.total}</p>
          <span className="text-xs font-mono text-muted uppercase tracking-wider block">NETWORK WIDE DEMAND</span>
        </div>
        <div className="bg-surface/80 backdrop-blur-md p-6 sm:p-7 border border-line/80 rounded-[28px] shadow-sm hover:border-amber-500/40 transition-all space-y-2">
          <p className="text-xs font-mono font-bold text-amber-500 uppercase tracking-[0.18em]">[ 02 // PENDING ALLOCATION ]</p>
          <p className="text-3xl sm:text-4xl font-bold font-sans tracking-tight text-amber-500">{counts.pending}</p>
          <span className="text-xs font-mono text-amber-500/80 uppercase tracking-wider block">AWAITING SIGN-OFF</span>
        </div>
        <div className="bg-surface/80 backdrop-blur-md p-6 sm:p-7 border border-line/80 rounded-[28px] shadow-sm hover:border-blue-500/40 transition-all space-y-2">
          <p className="text-xs font-mono font-bold text-info uppercase tracking-[0.18em]">[ 03 // ACTIVE / SCHEDULED ]</p>
          <p className="text-3xl sm:text-4xl font-bold font-sans tracking-tight text-info">{counts.active_scheduled}</p>
          <span className="text-xs font-mono text-info/80 uppercase tracking-wider block">SLOTS RESERVED</span>
        </div>
        <div className="bg-surface/80 backdrop-blur-md p-6 sm:p-7 border border-line/80 rounded-[28px] shadow-sm hover:border-emerald-500/40 transition-all space-y-2">
          <p className="text-xs font-mono font-bold text-emerald-500 uppercase tracking-[0.18em]">[ 04 // RESOLVED & VERIFIED ]</p>
          <p className="text-3xl sm:text-4xl font-bold font-sans tracking-tight text-emerald-500">{counts.resolved}</p>
          <span className="text-xs font-mono text-emerald-500/80 uppercase tracking-wider block">SAFETY VERIFIED</span>
        </div>
      </motion.div>

      {/* THE 4-STAGE WORKFLOW JOURNEY BOARD */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5 }}
        className="mb-10 rounded-[32px] border border-line/80 bg-surface/70 backdrop-blur-md p-8 sm:p-10 shadow-sm"
      >
        
        {/* Journey Board Header with Search & Filter Pills */}
        <div className="mb-5 flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-line/60">
          <div>
            <h2 className="text-base font-bold tracking-tight text-gradient-brand flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-[#D99A2B] inline-block" />
              Lifecycle Pipeline
            </h2>
            <p className="text-[10.5px] font-mono uppercase tracking-widest text-muted mt-0.5">
              [ CORRIDORS IN SCOPE: 5 ] · DYNAMIC ALLOCATION MATRIX · TELEMETRY CONNECTED
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            {/* View Switcher: Journey Board vs Block Governance Review */}
            <div className="flex items-center rounded-full border border-line bg-surface p-0.5 shadow-sm text-xs">
              <button
                type="button"
                onClick={() => setActiveView('board')}
                className={`rounded-full px-3 py-1 text-[10px] font-bold uppercase tracking-wider transition-all ${
                  activeView === 'board'
                    ? 'bg-ink text-deep shadow-sm'
                    : 'text-muted hover:text-ink'
                }`}
              >
                Journey Board
              </button>
              <button
                type="button"
                onClick={() => setActiveView('review')}
                className={`rounded-full px-3 py-1 text-[10px] font-bold uppercase tracking-wider transition-all flex items-center gap-1 ${
                  activeView === 'review'
                    ? 'bg-[#d71920] text-white shadow-sm'
                    : 'text-muted hover:text-ink'
                }`}
              >
                Block Review (Accept/Reject)
              </button>
            </div>

            <div className="relative">
              <Search size={13} className="absolute left-3 top-2.5 text-muted" />
              <input
                type="text"
                placeholder="Search defect code..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-44 sm:w-56 rounded-full border border-line bg-surface pl-8 pr-3 py-1.5 text-xs font-mono text-ink placeholder:text-muted focus:border-[#d71920] focus:outline-none shadow-sm"
              />
            </div>

            <div className="flex items-center rounded-full border border-line bg-surface p-0.5 shadow-sm text-xs">
              {['ALL', 'PENDING', 'SCHEDULED', 'IN_PROGRESS', 'COMPLETED'].map((filterKey) => (
                <button
                  key={filterKey}
                  type="button"
                  onClick={() => setStatusFilter(filterKey)}
                  className={`rounded-full px-2.5 py-1 text-[9.5px] font-mono font-bold uppercase tracking-wider transition-all ${
                    statusFilter === filterKey
                      ? 'bg-ink text-deep shadow-sm'
                      : 'text-muted hover:text-ink'
                  }`}
                >
                  {filterKey.replace('_', ' ')}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Part B2: Reports Awaiting Supervisor Acknowledgement Inbox */}
        <AwaitingAckInbox departmentFilter={resolvedDept} />

        {activeView === 'review' ? (
          <DepartmentBlockReview
            planId={activePlanId || 'active'}
            department={resolvedDept}
          />
        ) : (
          /* 4 Interconnected Columns Grid */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 relative">
          
          {/* Column 1: Case Allocation */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between px-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-muted">
                1. Case Allocation
              </h3>
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-amber-500/10 text-amber-600 text-[10px] font-bold">
                {counts.pipeline_stages?.intake ?? 0}
              </span>
            </div>

            <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
              {tasks
                .filter(t => ['DRAFT', 'SUBMITTED', 'REPORTED', 'UNVERIFIED', 'DEFERRED', 'ESCALATED'].includes((t.status || '').toUpperCase()))
                .map((task) => (
                  <div
                    key={task.id}
                    onClick={() => {
                      setSelectedTaskId(task.id)
                      openTaskModal(task)
                    }}
                    className="group rounded-2xl border border-line bg-surface p-3.5 shadow-sm hover:shadow-md hover:border-amber-500/50 transition-all cursor-pointer"
                  >
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2">
                        <div className="h-7 w-7 rounded-full bg-amber-500/15 text-amber-700 dark:text-amber-300 flex items-center justify-center text-[10px] font-bold shrink-0">
                          {task.id.slice(0, 3)}
                        </div>
                        <div>
                          <p className="text-xs font-bold text-ink leading-tight group-hover:text-info transition-colors">
                            {task.defectType}
                          </p>
                          <span className="text-[10px] font-mono text-muted">{task.id}</span>
                        </div>
                      </div>

                      <div className="flex items-center gap-1 opacity-80 group-hover:opacity-100">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation()
                            handleQuickAction(task.id, 'AUTHORIZE', 'Quick authorized from Journey Board')
                          }}
                          className="flex h-6 w-6 items-center justify-center rounded-full hover:bg-emerald-500/15 text-muted hover:text-emerald-600 transition-colors"
                          title="Authorize Case"
                        >
                          <CheckCircle2 size={13} />
                        </button>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation()
                            openTaskModal(task)
                          }}
                          className="flex h-6 w-6 items-center justify-center rounded-full hover:bg-raised text-muted hover:text-ink transition-colors"
                          title="Options"
                        >
                          <MoreHorizontal size={13} />
                        </button>
                      </div>
                    </div>

                    <div className="flex items-center justify-between text-[10px] pt-2 border-t border-line/40">
                      <span className="text-muted truncate max-w-[120px]">{task.exactLocation}</span>
                      <span className={`rounded-full px-2 py-0.5 font-bold uppercase border ${getSeverityBadge(task.severity)}`}>
                        {task.severity}
                      </span>
                    </div>
                  </div>
                ))}

              {tasks.filter(t => ['PENDING', 'UNVERIFIED', 'NEW', 'SCORED', 'DRAFT', 'SUBMITTED', 'ESCALATED', 'REPORTED', 'ACKNOWLEDGED'].includes((t.status || '').toUpperCase())).length === 0 && (
                <div className="rounded-2xl border border-dashed border-line/80 p-4 text-center text-xs text-muted">
                  No pending cases in intake queue
                </div>
              )}
            </div>
          </div>

          {/* Column 2: Issue Identification */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between px-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-muted">
                2. Issue Identification
              </h3>
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-500/10 text-blue-600 text-[10px] font-bold">
                {counts.pipeline_stages?.planning ?? 0}
              </span>
            </div>

            <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
              {tasks.filter(t => ['PENDING', 'SCORED', 'WINDOWS_PROPOSED', 'WINDOW_SELECTED'].includes((t.status || '').toUpperCase())).map((task) => (
                <div
                  key={`id-${task.id}`}
                  onClick={() => {
                    setSelectedTaskId(task.id)
                    openTaskModal(task)
                  }}
                  className="group rounded-2xl border border-line bg-surface p-3.5 shadow-sm hover:shadow-md hover:border-info/50 transition-all cursor-pointer"
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <div className="h-7 w-7 rounded-full bg-blue-500/15 text-blue-700 dark:text-blue-300 flex items-center justify-center text-[10px] font-bold shrink-0">
                        {task.corridorId ? task.corridorId.slice(0, 3) : 'COR'}
                      </div>
                      <div>
                        <p className="text-xs font-bold text-ink leading-tight group-hover:text-info transition-colors">
                          Identify {task.defectType.replace(/_/g, ' ')}
                        </p>
                        <span className="text-[10px] text-muted">Telemetry Verified</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-1 opacity-80 group-hover:opacity-100">
                      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-600 text-[10px]">
                        ✓
                      </span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          openTaskModal(task)
                        }}
                        className="flex h-6 w-6 items-center justify-center rounded-full hover:bg-raised text-muted hover:text-ink transition-colors"
                      >
                        <MoreHorizontal size={13} />
                      </button>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-[10px] pt-2 border-t border-line/40">
                    <span className="text-muted">Est: {task.estDuration} hrs</span>
                    <span className="font-mono text-info font-bold">{task.id}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Column 3: Technical Resolution */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between px-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-muted">
                3. Technical Resolution
              </h3>
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-purple-500/10 text-purple-600 text-[10px] font-bold">
                {counts.pipeline_stages?.execution ?? 0}
              </span>
            </div>

            <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
              {tasks
                .filter(t => ['APPROVED', 'READY', 'SCHEDULED', 'IN_PROGRESS', 'IN PROGRESS', 'SUSPENDED', 'OVERRUN'].includes((t.status || '').toUpperCase()))
                .map((task) => (
                  <div
                    key={`res-${task.id}`}
                    onClick={() => {
                      setSelectedTaskId(task.id)
                      openTaskModal(task)
                    }}
                    className="group rounded-2xl border border-line bg-surface p-3.5 shadow-sm hover:shadow-md hover:border-purple-500/50 transition-all cursor-pointer"
                  >
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2">
                        <div className="h-7 w-7 rounded-full bg-purple-500/15 text-purple-700 dark:text-purple-300 flex items-center justify-center text-[10px] font-bold shrink-0">
                          TR
                        </div>
                        <div>
                          <p className="text-xs font-bold text-ink leading-tight group-hover:text-purple-600 transition-colors">
                            Coordinate Block Sanction
                          </p>
                          <span className="text-[10px] text-muted">{task.id} · {task.sectionId}</span>
                        </div>
                      </div>

                      <div className="flex items-center gap-1 opacity-80 group-hover:opacity-100">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation()
                            handleQuickAction(task.id, 'START_ACTION', 'Started action from board')
                          }}
                          className="flex h-6 w-6 items-center justify-center rounded-full hover:bg-purple-500/15 text-muted hover:text-purple-600 transition-colors"
                          title="Start Maintenance Action"
                        >
                          <PlayCircle size={13} />
                        </button>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation()
                            openTaskModal(task)
                          }}
                          className="flex h-6 w-6 items-center justify-center rounded-full hover:bg-raised text-muted hover:text-ink transition-colors"
                        >
                          <MoreHorizontal size={13} />
                        </button>
                      </div>
                    </div>

                    <div className="flex items-center justify-between text-[10px] pt-2 border-t border-line/40">
                      <span className="text-muted">Window: 02:00-04:30 AM</span>
                      <span className={`rounded-full px-2 py-0.5 font-bold uppercase border ${getStatusBadge(task.status)}`}>
                        {task.status}
                      </span>
                    </div>
                  </div>
                ))}

              {tasks.filter(t => ['SCHEDULED', 'DEPARTMENT NOTIFIED', 'AUTHORIZED', 'IN_PROGRESS', 'IN PROGRESS', 'ACTION STARTED'].includes((t.status || '').toUpperCase())).length === 0 && (
                <div className="rounded-2xl border border-dashed border-line/80 p-4 text-center text-xs text-muted">
                  No active authorized blocks in progress
                </div>
              )}
            </div>
          </div>

          {/* Column 4: Problem Resolution & Active Execution */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between px-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-muted">
                4. Problem Resolution
              </h3>
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-600 text-[10px] font-bold">
                {counts.pipeline_stages?.resolution ?? 0}
              </span>
            </div>

            <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
              {/* THE SLEEK BLACK CARD */}
              <div
                onClick={() => {
                  const activeTask = tasks.find(t => ['IN_PROGRESS', 'IN PROGRESS'].includes((t.status || '').toUpperCase())) || tasks[0]
                  if (activeTask) {
                    setSelectedTaskId(activeTask.id)
                    openTaskModal(activeTask)
                  }
                }}
                className="rounded-2xl bg-black border border-neutral-800 text-white p-4 shadow-xl cursor-pointer hover:border-[#d71920]/70 transition-all group"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-1.5">
                    <span className="flex h-2 w-2 rounded-full bg-[#d71920] animate-pulse" />
                    <span className="text-[9px] font-mono font-bold uppercase tracking-[0.2em] text-[#d71920]">
                      LIVE POSSESSION
                    </span>
                  </div>
                  <span className="text-[9px] font-mono text-neutral-400">[ REC // 01 ]</span>
                </div>
                <h4 className="text-xs font-bold font-sans tracking-tight uppercase leading-tight">
                  ACTIVE REQUEST PROCESSING
                </h4>
                <p className="text-[10px] font-mono text-neutral-400 mt-1">
                  MAINLINE CORRIDOR TELEMETRY STREAMING LIVE.
                </p>
              </div>

              {/* Resolved / Closed Cards */}
              {tasks
                .filter(t => ['COMPLETED', 'RESOLVED', 'DONE'].includes((t.status || '').toUpperCase()))
                .map((task) => (
                  <div
                    key={`comp-${task.id}`}
                    onClick={() => {
                      setSelectedTaskId(task.id)
                      openTaskModal(task)
                    }}
                    className="group rounded-2xl border border-line bg-surface p-3.5 shadow-sm hover:shadow-md hover:border-emerald-500/50 transition-all cursor-pointer"
                  >
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2">
                        <div className="h-7 w-7 rounded-full bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 flex items-center justify-center text-[10px] font-bold shrink-0">
                          ✓
                        </div>
                        <div>
                          <p className="text-xs font-bold text-ink leading-tight group-hover:text-emerald-600 transition-colors">
                            {task.defectType} Verified
                          </p>
                          <span className="text-[10px] font-mono text-muted">{task.id}</span>
                        </div>
                      </div>
                      <MoreHorizontal size={13} className="text-muted opacity-80" />
                    </div>

                    <div className="flex items-center justify-between text-[10px] pt-2 border-t border-line/40">
                      <span className="text-emerald-600 font-semibold">Ready for reopening</span>
                      <span className="text-muted">Jointly Signed</span>
                    </div>
                  </div>
                ))}
            </div>
          </div>

        </div>
        )}
      </motion.div>

      {/* FULL-WIDTH SUGGESTED KNOWLEDGE & DEFECT REGISTRY TABLE */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5 }}
        className="w-full bg-surface/90 border border-line/80 rounded-[32px] shadow-sm p-7 sm:p-9 flex flex-col mb-10"
      >
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6 pb-4 border-b border-line/60">
          <div>
            <h2 className="text-lg font-bold tracking-tight text-gradient-brand flex items-center gap-2.5">
              <FileText size={20} className="text-blue-500" />
              Suggested Knowledge & Defect Registry
            </h2>
            <p className="text-xs text-muted mt-1 font-sans">
              Official maintenance ledger and active work orders. Click any row or action to pop-through full controls.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-xs font-mono font-bold text-muted bg-raised px-3.5 py-1.5 rounded-full border border-line">
              {filteredTasks.length} Records In Scope
            </span>
          </div>
        </div>

        {/* Full-width responsive table with generous column spacing */}
        <div className="w-full overflow-hidden">
          <table className="w-full text-left text-xs border-collapse table-auto">
            <thead>
              <tr className="border-b border-line bg-raised/60 text-[11px] font-mono font-bold uppercase tracking-wider text-muted">
                <th className="px-5 py-3.5 rounded-l-2xl">Subject / Defect Type</th>
                <th className="px-5 py-3.5">Status</th>
                <th className="px-5 py-3.5">Location & Corridor</th>
                <th className="px-5 py-3.5">Severity</th>
                <th className="px-5 py-3.5 text-right rounded-r-2xl">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/40">
              {filteredTasks.slice((currentPage - 1) * pageSize, currentPage * pageSize).map((task) => {
                const isSelected = selectedTask?.id === task.id
                return (
                  <tr
                    key={`row-${task.id}`}
                    onClick={() => {
                      setSelectedTaskId(task.id)
                      openTaskModal(task)
                    }}
                    className={`cursor-pointer transition-colors group ${
                      isSelected ? 'bg-info/10' : 'hover:bg-raised/70'
                    }`}
                  >
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3 flex-wrap sm:flex-nowrap">
                        <span className="font-mono font-bold text-ink bg-raised px-2.5 py-1 rounded-md border border-line shrink-0">
                          {task.id}
                        </span>
                        <span className="font-semibold text-ink group-hover:text-blue-600 transition-colors">
                          {task.defectType}
                        </span>
                      </div>
                    </td>

                    <td className="px-5 py-4 whitespace-nowrap">
                      <span className={`inline-block rounded-full px-3 py-1 text-[11px] font-mono font-bold uppercase border ${getStatusBadge(task.status)}`}>
                        {task.status}
                      </span>
                    </td>

                    <td className="px-5 py-4 text-muted whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-ink">{task.sectionId}</span>
                        <span className="text-faint">·</span>
                        <span className="font-mono text-xs">{task.exactLocation}</span>
                      </div>
                    </td>

                    <td className="px-5 py-4 whitespace-nowrap">
                      <span className={`inline-block rounded-full px-3 py-1 text-[11px] font-mono font-bold uppercase border ${getSeverityBadge(task.severity)}`}>
                        {task.severity}
                      </span>
                    </td>

                    <td className="px-5 py-4 text-right whitespace-nowrap">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          openTaskModal(task)
                        }}
                        className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface hover:bg-info hover:text-white px-3.5 py-1.5 text-xs font-mono font-bold uppercase text-info transition-all shadow-sm"
                      >
                        <span>Pop-through</span>
                        <ExternalLink size={12} />
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          {filteredTasks.length === 0 && (
            <div className="p-8 text-center text-muted font-mono text-xs">
              No matching records found for this filter.
            </div>
          )}

          {/* Pagination Controls */}
          {filteredTasks.length > pageSize && (
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-5 mt-2 border-t border-line/60">
              <span className="text-xs font-mono text-muted">
                Showing {Math.min((currentPage - 1) * pageSize + 1, filteredTasks.length)} to {Math.min(currentPage * pageSize, filteredTasks.length)} of {filteredTasks.length} work orders
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                  className="rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-mono font-semibold uppercase text-ink hover:bg-raised transition-colors disabled:opacity-40"
                >
                  Prev
                </button>
                <span className="px-2 text-xs font-mono font-bold text-ink">
                  {currentPage} / {Math.ceil(filteredTasks.length / pageSize) || 1}
                </span>
                <button
                  type="button"
                  disabled={currentPage >= Math.ceil(filteredTasks.length / pageSize)}
                  onClick={() => setCurrentPage(prev => Math.min(Math.ceil(filteredTasks.length / pageSize), prev + 1))}
                  className="rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-mono font-semibold uppercase text-ink hover:bg-raised transition-colors disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      </motion.div>

      {/* FULL-WIDTH LIVE RAILWAY NETWORK & TELEMETRY OPENRAILWAYMAP */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5 }}
        className="w-full bg-surface/90 border border-line/80 rounded-[32px] shadow-sm p-7 sm:p-9 flex flex-col mb-10"
      >
        <div className="flex flex-wrap items-center justify-between gap-4 mb-5 pb-4 border-b border-line/60">
          <div>
            <h2 className="text-lg font-bold tracking-tight text-gradient-brand flex items-center gap-2.5">
              <MapPin size={20} className="text-rose-500" />
              Live Railway Network & Telemetry (OpenRailwayMap)
            </h2>
            <p className="text-xs text-muted mt-1 font-sans">
              Geographic OpenRailwayMap track infrastructure, real station coordinates, and corridor defect telemetry.
            </p>
          </div>
          <span className="flex items-center gap-2 text-xs font-mono font-bold uppercase tracking-wider text-ok bg-ok/10 border border-ok/30 px-3.5 py-1 rounded-full">
            <span className="h-2.5 w-2.5 rounded-full bg-ok animate-pulse" /> Live Telemetry Online
          </span>
        </div>

        <div className="h-[460px] sm:h-[500px] w-full overflow-hidden rounded-[24px] border border-line bg-surface shadow-sm relative z-0 isolate">
          <IndiaRailwayMap
            issues={tasks}
            selectedIssueId={selectedTask?.id}
            onSelectIssue={(id) => {
              const found = tasks.find((t) => t.id === id)
              if (found) {
                setSelectedTaskId(id)
                openTaskModal(found)
              }
            }}
            showHeatmap={true}
            trains={liveTrains}
          />
        </div>
      </motion.div>

      {/* SELECTED TASK INTELLIGENCE ANALYSIS SECTION */}
      {selectedTask && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.4 }}
          className="bg-surface/90 border border-line/80 rounded-[32px] shadow-sm overflow-hidden mb-10 flex flex-col"
        >
          <div className="bg-bar text-onbar px-8 py-5 flex flex-wrap justify-between items-center gap-4">
            <div>
              <h2 className="text-sm font-semibold uppercase tracking-wider flex items-center gap-2">
                <span className="w-2 h-2 bg-barmuted rounded-full inline-block" />
                Active Issue Intelligence Analysis: <span className="text-white font-bold">{selectedTask.id}</span>
              </h2>
              <span className="text-[10px] text-barmuted uppercase tracking-widest mt-0.5 block">
                {selectedTask.defectType} · {selectedTask.exactLocation}
              </span>
            </div>

            <div className="flex items-center gap-3">
              <span className="px-3 py-1 bg-onbar/10 rounded border border-onbar/20 text-xs font-bold uppercase tracking-wider">
                Status: {selectedTask.status}
              </span>
              <button
                type="button"
                onClick={() => openTaskModal(selectedTask)}
                className="flex items-center gap-1.5 rounded bg-onbar/15 hover:bg-onbar/25 text-onbar px-3 py-1 text-xs font-bold uppercase transition-colors"
              >
                <span>Pop-through View</span>
                <ExternalLink size={12} />
              </button>
            </div>
          </div>

          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-x-8 gap-y-8">
              {/* 1. Incident Summary */}
              <div className="md:col-span-2">
                <h3 className="text-xs font-bold text-muted uppercase tracking-wider mb-2">1. Incident Summary</h3>
                <p className="text-base font-medium text-ink">{selectedTask.what}</p>
              </div>

              {/* 4. Operational Priority */}
              <div className="md:col-span-1">
                <h3 className="text-xs font-bold text-muted uppercase tracking-wider mb-2">4. Operational Priority</h3>
                <span className={`inline-block rounded-full px-4 py-1.5 text-xs font-bold uppercase tracking-wide border ${getSeverityBadge(selectedTask.severity)}`}>
                  {selectedTask.severity} Priority
                </span>
              </div>

              {/* 2. Root Cause Analysis */}
              <div className="md:col-span-2">
                <h3 className="text-xs font-bold text-muted uppercase tracking-wider mb-3">2. Root Cause Analysis</h3>
                <div className="space-y-2">
                  {(selectedTask.causes || []).map((cause, i) => (
                    <div key={i} className="p-3 rounded-lg border border-line bg-raised/40 text-xs flex gap-3">
                      <span className="font-bold uppercase tracking-wider text-[11px] w-24 shrink-0 text-info">
                        {cause.level}
                      </span>
                      <span className="text-ink">{cause.text}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Priority Drivers */}
              <div className="md:col-span-1">
                <h3 className="text-xs font-bold text-muted uppercase tracking-wider mb-3">Key Priority Drivers</h3>
                <ul className="space-y-1.5">
                  {(selectedTask.priorityReasons || []).map((reason, i) => (
                    <li key={i} className="text-xs text-ink flex items-start gap-2">
                      <span className="text-red-500 font-bold">•</span>
                      <span>{reason}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* 3. Lifecycle Progression */}
              <div className="md:col-span-3 border-t border-line/60 pt-6">
                <h3 className="text-[11px] font-bold text-muted uppercase tracking-wider mb-5">3. Lifecycle Progression</h3>
                <div className="flex justify-between items-start relative px-4">
                  <div className="absolute top-2.5 left-8 right-8 h-[2px] bg-line -z-0" />
                  {['Reported', 'Detected', 'Analysed', 'Alert raised', 'Action req.', 'Resolved'].map((stage, i) => {
                    const statusIdx = selectedTask.status === 'COMPLETED' ? 6 : selectedTask.status === 'IN_PROGRESS' ? 4 : selectedTask.status === 'SCHEDULED' ? 3 : 2
                    const isPast = i < statusIdx
                    const isCurrent = i === statusIdx
                    return (
                      <div key={stage} className="flex flex-col items-center flex-1 text-center relative z-10">
                        <div
                          className={`w-6 h-6 rounded-full border-2 flex items-center justify-center mb-1 text-[10px] font-bold transition-colors ${
                            isPast
                              ? 'bg-emerald-500 border-emerald-500 text-white'
                              : isCurrent
                              ? 'bg-surface border-blue-500 text-blue-600 ring-4 ring-blue-500/15'
                              : 'bg-raised border-line text-faint'
                          }`}
                        >
                          {isPast ? <Check size={12} /> : i + 1}
                        </div>
                        <span className={`text-[10px] font-bold uppercase tracking-wider ${isCurrent ? 'text-blue-600' : 'text-muted'}`}>
                          {stage}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* 5. IMPACT */}
              <div className="md:col-span-2 grid grid-cols-2 gap-3 border-t border-line/60 pt-6">
                <h3 className="col-span-2 text-[11px] font-bold text-muted uppercase tracking-wider">5. WHAT IS THE IMPACT?</h3>
                <div className="bg-raised/40 p-3 rounded-lg border border-line">
                  <span className="text-[10px] uppercase tracking-wider text-muted block mb-1">Safety</span>
                  <span className="text-xs font-semibold text-ink">{selectedTask.impact?.safety}</span>
                </div>
                <div className="bg-raised/40 p-3 rounded-lg border border-line">
                  <span className="text-[10px] uppercase tracking-wider text-muted block mb-1">Operations Delay</span>
                  <span className="text-xs font-semibold text-ink">{selectedTask.impact?.operations}</span>
                </div>
                <div className="bg-raised/40 p-3 rounded-lg border border-line">
                  <span className="text-[10px] uppercase tracking-wider text-muted block mb-1">Maintenance Requirement</span>
                  <span className="text-xs font-semibold text-ink">{selectedTask.impact?.maintenance}</span>
                </div>
                <div className="bg-raised/40 p-3 rounded-lg border border-line">
                  <span className="text-[10px] uppercase tracking-wider text-muted block mb-1">Affected Location</span>
                  <span className="text-xs font-semibold text-ink">{selectedTask.impact?.location}</span>
                  {selectedTask.exactLocation && (
                    <span className="text-[11px] text-muted block mt-0.5">{selectedTask.exactLocation}</span>
                  )}
                </div>
              </div>

              {/* 6. WHAT SHOULD WE DO */}
              <div className="md:col-span-1 border-t border-line/60 pt-6">
                <h3 className="text-xs font-bold text-muted uppercase tracking-wider mb-3">6. WHAT SHOULD WE DO?</h3>
                <div className="flex flex-wrap gap-2">
                  {(selectedTask.actions || []).map((action, i) => (
                    <span key={i} className="bg-info/10 text-info border border-info/30 px-3 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wide">
                      {action}
                    </span>
                  ))}
                </div>
              </div>

              {/* 7. RAILOPT RECOMMENDATION */}
              <div className="md:col-span-2">
                <div className="border border-info/30 rounded-lg overflow-hidden bg-info/5">
                  <div className="bg-info/20 text-info px-4 py-2 flex items-center gap-2">
                    <Sparkles size={14} />
                    <span className="text-[11px] font-bold uppercase tracking-wider">7. RAILOPT RECOMMENDATION</span>
                  </div>
                  <div className="p-4 text-xs font-medium text-ink">
                    {selectedTask.recommendation}
                  </div>
                </div>
              </div>

              {/* 8. SUPPORTING INFORMATION */}
              <div className="md:col-span-1">
                <h3 className="text-xs font-bold text-muted uppercase tracking-wider mb-2">8. SUPPORTING INFORMATION</h3>
                <div className="space-y-2">
                  {(selectedTask.supporting || []).map((item, i) => (
                    <div key={i} className="flex justify-between border-b border-line/40 py-1 text-xs">
                      <span className="text-muted">{item.label}:</span>
                      <span className="font-semibold text-ink">{item.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* DEPARTMENT ACTIONS FOOTER (WORKING BUTTONS FROM SCREENSHOT 2!) */}
          <div className="bg-raised/40 border-t border-line px-6 py-4 flex flex-wrap items-center justify-between gap-3">
            <span className="text-xs font-semibold text-muted uppercase tracking-wider">
              Take Action on {selectedTask.id}:
            </span>

            <div className="flex flex-wrap items-center gap-2">
              {/* Authorize */}
              <button
                type="button"
                disabled={actionInProgress !== null || selectedTask.status === 'SCHEDULED'}
                onClick={() => handleStatusChange(selectedTask.id, 'SCHEDULED')}
                className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all border shadow-sm ${
                  selectedTask.status === 'SCHEDULED'
                    ? 'bg-blue-600 text-white border-blue-600 ring-2 ring-blue-500/30'
                    : 'bg-surface border-line text-ink hover:border-blue-500 hover:text-blue-600'
                } disabled:opacity-50`}
              >
                {actionInProgress === 'SCHEDULED' ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
                AUTHORIZE
              </button>

              {/* Start Action */}
              <button
                type="button"
                disabled={actionInProgress !== null || selectedTask.status === 'IN_PROGRESS' || selectedTask.status === 'COMPLETED'}
                onClick={() => handleStatusChange(selectedTask.id, 'IN_PROGRESS')}
                className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all border shadow-sm ${
                  selectedTask.status === 'IN_PROGRESS'
                    ? 'bg-merge text-deep border-merge'
                    : 'bg-surface border-line text-ink hover:border-merge hover:text-merge'
                } disabled:opacity-50`}
              >
                {actionInProgress === 'IN_PROGRESS' ? <Loader2 size={13} className="animate-spin" /> : <PlayCircle size={13} />}
                START ACTION
              </button>

              {/* Mark in Progress */}
              <button
                type="button"
                disabled={actionInProgress !== null || selectedTask.status === 'IN_PROGRESS'}
                onClick={() => handleStatusChange(selectedTask.id, 'IN_PROGRESS')}
                className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all border shadow-sm ${
                  selectedTask.status === 'IN_PROGRESS'
                    ? 'bg-amber-600 text-white border-amber-600 ring-2 ring-amber-500/30'
                    : 'bg-surface border-line text-info hover:bg-info/10'
                } disabled:opacity-50`}
              >
                {actionInProgress === 'IN_PROGRESS' ? <Loader2 size={13} className="animate-spin" /> : <Wrench size={13} />}
                MARK IN PROGRESS
              </button>

              {/* Mark Resolved / Done */}
              <button
                type="button"
                disabled={actionInProgress !== null || selectedTask.status === 'COMPLETED'}
                onClick={() => handleStatusChange(selectedTask.id, 'COMPLETED')}
                className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all border shadow-sm ${
                  selectedTask.status === 'COMPLETED'
                    ? 'bg-emerald-600 text-white border-emerald-600 ring-2 ring-emerald-500/30'
                    : 'bg-surface border-line text-emerald-600 hover:bg-emerald-50'
                } disabled:opacity-50`}
              >
                {actionInProgress === 'COMPLETED' ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle2 size={13} />}
                MARK RESOLVED / DONE
              </button>

              {/* Reject */}
              <button
                type="button"
                disabled={actionInProgress !== null || selectedTask.status === 'REJECTED'}
                onClick={() => handleStatusChange(selectedTask.id, 'REJECTED')}
                className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all border shadow-sm ${
                  selectedTask.status === 'REJECTED'
                    ? 'bg-red-600 text-white border-red-600'
                    : 'bg-surface border-line text-red-500 hover:bg-red-50'
                } disabled:opacity-50`}
              >
                {actionInProgress === 'REJECTED' ? <Loader2 size={13} className="animate-spin" /> : <XCircle size={13} />}
                REJECT
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </PortalLayout>
  )
}
