import { useEffect, useState } from 'react'
import DepartmentDashboard from '@/components/app/DepartmentDashboard'
import { fetchTasks } from '@/api'

export default function EngineeringDashboard() {
  const [task, setTask] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoading(true)
    fetchTasks({ department: 'ENGINEERING' })
      .then(res => {
        const t = res.data[0]
        if (!t) {
          setError('No engineering tasks found. Click Setup Server to generate data.')
          setLoading(false)
          return
        }
        setTask({
          id: t.task_id,
          status: t.status,
          what: t.inspector_remarks || "Track deviation detected.",
          causes: [{ level: "CONFIRMED", text: "Automated analysis flag." }],
          timeline: [{ desc: `Reported on ${t.reported_date}` }],
          seriousness: t.ml_predicted_severity || t.raw_severity || 'MEDIUM',
          impact: {
            safety: t.is_safety_critical ? "Safety critical defect." : "Standard defect.",
            operations: `Potential ${t.ml_predicted_duration_hours ?? 0} hr delay.`,
            maintenance: "Requires maintenance block.",
            location: t.corridor_id
          },
          exactLocation: `KM ${t.km_location ?? '—'} - ${t.km_end ?? '—'}`,
          actions: ["Inspect", "Coordinate work", "Schedule maintenance"],
          recommendation: "Schedule maintenance block via Optimizer.",
          supporting: [
            { label: "Overdue", value: (t.days_overdue ?? 0) + " days" },
            { label: "Historical", value: (t.historical_failure_count ?? 0) + " past failures" }
          ],
          priorityReasons: ["Safety-related issue"]
        })
        setError(null)
      })
      .catch(err => {
        console.error('Failed to fetch engineering tasks:', err)
        setError('Could not load tasks. Click Setup Server to initialize.')
      })
      .finally(() => setLoading(false))
  }, [])

  const activeTask = task || {
    id: 'ENG-STANDBY',
    status: 'ACTIVE',
    what: 'Civil & Track engineering telemetry monitoring active. Standing by for incoming defect reports.',
    causes: [{ level: 'CONFIRMED', text: 'Telemetry feeds nominal.' }],
    timeline: [{ desc: 'Live monitoring online' }],
    seriousness: 'LOW',
    impact: {
      safety: 'Track geometry nominal.',
      operations: 'No active line delays.',
      maintenance: 'Ready for reported defect assignments.',
      location: 'Mainline Corridor'
    },
    exactLocation: 'Division-wide',
    actions: ['Monitor telemetry', 'Standby for reported issues'],
    recommendation: 'Ready to receive real-time defect alerts.',
    supporting: [
      { label: 'Status', value: 'Monitoring' },
      { label: 'Channel', value: 'Live WebSocket' }
    ],
    priorityReasons: ['Routine operational standby']
  }

  return (
    <DepartmentDashboard 
      deptId="engineering" 
      title="Engineering Maintenance"
      taskName="Engineering Tasks"
      issueData={activeTask}
    />
  )
}
