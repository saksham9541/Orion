import { useEffect, useState } from 'react'
import { CheckCircle, PlayCircle, Clock } from 'lucide-react'
import PortalLayout from '@/components/app/PortalLayout'
import { fetchTasks, updateTaskStatus } from '@/api'

export default function TechnicianDashboard() {
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadTasks = () => {
    setLoading(true)
    fetchTasks()
      .then(res => {
        // Show PENDING, SCHEDULED, and IN_PROGRESS tasks for workers
        const activeTasks = res.data.filter(t => 
          ['PENDING', 'SCHEDULED', 'IN_PROGRESS'].includes(t.status)
        )
        setTasks(activeTasks)
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

  const handleStatusChange = async (taskId, newStatus) => {
    try {
      await updateTaskStatus(taskId, { status: newStatus })
      // Reload tasks after update
      loadTasks()
    } catch (err) {
      console.error('Failed to update status', err)
      alert('Failed to update task status')
    }
  }

  return (
    <PortalLayout role="technician">
      <div className="max-w-2xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-semibold mb-2">My Work Orders</h1>
        <p className="text-muted mb-6">View and update your assigned field tasks.</p>

        {loading && <div className="p-8 text-center text-muted">Loading tasks...</div>}
        {error && <div className="p-8 text-center text-warn bg-warn/10 rounded border border-warn/20">{error}</div>}
        
        {!loading && !error && tasks.length === 0 && (
          <div className="p-12 text-center text-faint border border-dashed border-line rounded-lg bg-surface">
            <CheckCircle className="mx-auto mb-3 opacity-20" size={48} />
            <p>No active tasks assigned to you right now.</p>
          </div>
        )}

        <div className="space-y-4">
          {tasks.map(task => (
            <div key={task.task_id} className="bg-surface border border-line rounded-lg p-5 shadow-sm">
              <div className="flex justify-between items-start mb-3">
                <div>
                  <span className="text-xs font-mono text-faint mb-1 block">{task.task_id}</span>
                  <h3 className="font-medium text-lg leading-tight">{task.inspector_remarks || task.defect_category}</h3>
                </div>
                <span className={`px-2.5 py-1 rounded text-[11px] font-bold tracking-wide uppercase ${
                  task.status === 'IN_PROGRESS' ? 'bg-merge/20 text-merge' : 'bg-raised/60 text-muted'
                }`}>
                  {task.status.replace('_', ' ')}
                </span>
              </div>
              
              <div className="text-sm text-muted space-y-1 mb-6">
                <p><strong className="text-ink/80">Location:</strong> {task.corridor_id} (KM {task.km_location})</p>
                <p><strong className="text-ink/80">Department:</strong> {task.department}</p>
                <p><strong className="text-ink/80">Est. Duration:</strong> {task.estimated_duration_hours || 2} hours</p>
              </div>

              <div className="flex gap-3 border-t border-line pt-4">
                {task.status !== 'IN_PROGRESS' && (
                  <button 
                    onClick={() => handleStatusChange(task.task_id, 'IN_PROGRESS')}
                    className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-merge/10 text-merge hover:bg-merge/20 border border-merge/20 rounded font-medium text-sm transition-colors"
                  >
                    <PlayCircle size={16} />
                    Start Work
                  </button>
                )}
                
                <button 
                  onClick={() => handleStatusChange(task.task_id, 'COMPLETED')}
                  className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-ok/10 text-ok hover:bg-ok/20 border border-ok/20 rounded font-medium text-sm transition-colors"
                >
                  <CheckCircle size={16} />
                  Mark Completed
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </PortalLayout>
  )
}
