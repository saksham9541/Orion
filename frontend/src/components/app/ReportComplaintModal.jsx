import { useState } from 'react'
import { X, Send, AlertTriangle, Building2, BellRing } from 'lucide-react'
import { submitComplaint } from '@/api'

export default function ReportComplaintModal({ isOpen, onClose }) {
  const [desc, setDesc] = useState('')
  const [department, setDepartment] = useState('ENGINEERING')
  const [severity, setSeverity] = useState('HIGH')
  const [corridor, setCorridor] = useState('COR-12345678')
  const [section, setSection] = useState('SEC-87654321')
  const [km, setKm] = useState('14.5')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)

  if (!isOpen) return null

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      await submitComplaint({
        description: desc,
        corridor_id: corridor,
        section_id: section,
        km_location: parseFloat(km),
        department_designated: department,
        severity: severity,
      })
      setSuccess(true)
      setTimeout(() => {
        setSuccess(false)
        onClose()
      }, 1800)
    } catch (err) {
      console.error(err)
      alert("Failed to submit issue. Please check server connection.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg rounded-2xl border border-line bg-surface p-6 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
        <div className="mb-4 flex items-center justify-between border-b border-line pb-3">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-red-500/10 text-red-500 border border-red-500/20">
              <AlertTriangle size={18} />
            </span>
            <div>
              <h2 className="text-base font-bold text-ink leading-tight">Report Track Issue / Defect</h2>
              <p className="text-[11px] text-faint">Instant alert will be dispatched to designated department</p>
            </div>
          </div>
          <button onClick={onClose} className="rounded-lg p-1 text-faint hover:bg-raised hover:text-ink transition-colors">
            <X size={18} />
          </button>
        </div>
        
        {success ? (
          <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-6 text-center space-y-2">
            <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-500">
              <BellRing size={20} className="animate-bounce" />
            </div>
            <p className="text-sm font-bold text-emerald-600 dark:text-emerald-400">Issue Dispatched Successfully!</p>
            <p className="text-xs text-muted">
              Live alert sent via WebSocket to {department} officers & Super Admins.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Designated Department */}
            <div>
              <label className="mb-1.5 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-faint">
                <Building2 size={13} className="text-info" />
                Related / Designated Department (Target Dept)
              </label>
              <select
                value={department}
                onChange={e => setDepartment(e.target.value)}
                className="w-full rounded-lg border border-line bg-raised px-3 py-2 text-sm font-medium text-ink outline-none focus:border-info transition-colors"
              >
                <option value="ENGINEERING">ENGINEERING (Track, Rails, Sleepers, Ballast)</option>
                <option value="SNT">S&T (Signaling, Point Machines, Interlocking)</option>
                <option value="TRD">TRD (Traction Distribution, OHE Wires, Power Feeders)</option>
              </select>
              <p className="mt-1 text-[11px] text-faint">
                Officers logged in under this department will receive an immediate popup alert.
              </p>
            </div>

            {/* Severity Level */}
            <div>
              <label className="mb-1.5 block text-[11px] font-bold uppercase tracking-wider text-faint">
                Priority / Severity Level
              </label>
              <div className="grid grid-cols-4 gap-2">
                {[
                  { id: 'EMERGENCY', label: 'Emergency', border: 'border-red-500/40', text: 'text-red-500', bg: 'bg-red-500/10' },
                  { id: 'HIGH', label: 'High', border: 'border-amber-500/40', text: 'text-amber-500', bg: 'bg-amber-500/10' },
                  { id: 'MEDIUM', label: 'Medium', border: 'border-blue-500/40', text: 'text-blue-500', bg: 'bg-blue-500/10' },
                  { id: 'LOW', label: 'Low', border: 'border-slate-500/40', text: 'text-slate-400', bg: 'bg-slate-500/10' },
                ].map(lvl => (
                  <button
                    key={lvl.id}
                    type="button"
                    onClick={() => setSeverity(lvl.id)}
                    className={`rounded-lg border px-2 py-2 text-xs font-bold transition-all text-center ${
                      severity === lvl.id
                        ? `${lvl.border} ${lvl.bg} ${lvl.text} ring-2 ring-current/30`
                        : 'border-line bg-raised text-muted hover:border-line-hover'
                    }`}
                  >
                    {lvl.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Description */}
            <div>
              <label className="mb-1 block text-[11px] font-bold uppercase tracking-wider text-faint">
                Defect Description & Remarks
              </label>
              <textarea
                required
                className="w-full rounded-lg border border-line bg-raised p-2.5 text-sm text-ink outline-none focus:border-info transition-colors placeholder:text-muted/60"
                rows={3}
                placeholder="e.g. Broken rail joint / sparking in catenary wire near signal pole..."
                value={desc}
                onChange={e => setDesc(e.target.value)}
              />
            </div>

            {/* Corridor & Section */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-[11px] font-bold uppercase tracking-wider text-faint">Corridor ID</label>
                <input
                  type="text"
                  required
                  className="w-full rounded-lg border border-line bg-raised px-3 py-2 text-sm text-ink outline-none focus:border-info"
                  value={corridor}
                  onChange={e => setCorridor(e.target.value)}
                />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-bold uppercase tracking-wider text-faint">Section ID</label>
                <input
                  type="text"
                  required
                  className="w-full rounded-lg border border-line bg-raised px-3 py-2 text-sm text-ink outline-none focus:border-info"
                  value={section}
                  onChange={e => setSection(e.target.value)}
                />
              </div>
            </div>

            {/* KM Location */}
            <div>
              <label className="mb-1 block text-[11px] font-bold uppercase tracking-wider text-faint">Track Km Location</label>
              <input
                type="number"
                step="0.1"
                required
                className="w-full rounded-lg border border-line bg-raised px-3 py-2 text-sm text-ink outline-none focus:border-info"
                value={km}
                onChange={e => setKm(e.target.value)}
              />
            </div>
            
            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 rounded-xl bg-red-600 hover:bg-red-700 py-2.5 text-xs font-bold uppercase tracking-widest text-white shadow-lg transition-all disabled:opacity-50"
            >
              <Send size={14} />
              {loading ? 'Broadcasting Alert...' : 'Submit & Dispatch Alert'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
