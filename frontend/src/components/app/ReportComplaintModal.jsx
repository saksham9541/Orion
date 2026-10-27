import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Send, AlertTriangle, Building2, BellRing, Sparkles } from 'lucide-react'
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

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const res = await submitComplaint({
        description: desc,
        corridor_id: corridor,
        section_id: section,
        km_location: parseFloat(km),
        department_designated: department,
        severity: severity,
      })
      setSuccess(true)
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('railopt:task-created', { detail: res.data }))
      }
      setTimeout(() => {
        setSuccess(false)
        onClose()
      }, 1500)
    } catch (err) {
      console.error(err)
      alert("Failed to submit issue. Please check server connection.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[99999] flex items-center justify-center p-4 overflow-y-auto">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/80 backdrop-blur-md"
            aria-hidden="true"
          />

          {/* Modal Container */}
          <motion.div
            initial={{ opacity: 0, scale: 0.92, y: 22 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: 14 }}
            transition={{ type: 'spring', damping: 26, stiffness: 360 }}
            className="relative w-full max-w-lg rounded-[28px] border border-line/90 bg-surface p-7 shadow-[0_30px_70px_rgba(0,0,0,0.45)] z-10 my-8"
          >
            {/* Header */}
            <div className="mb-5 flex items-center justify-between border-b border-line pb-4">
              <div className="flex items-center gap-3">
                <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-red-500/10 text-red-500 border border-red-500/30">
                  <AlertTriangle size={20} />
                </span>
                <div>
                  <h2 className="font-dot text-sm font-bold text-ink uppercase tracking-wider">
                    Report Track Defect
                  </h2>
                  <p className="text-[11px] text-faint font-mono">DISPATCH REAL-TIME RAIL ALERT</p>
                </div>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="rounded-full p-2 text-faint hover:bg-raised hover:text-ink transition-colors border border-transparent hover:border-line"
              >
                <X size={16} />
              </button>
            </div>

            {success ? (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-6 text-center space-y-2.5 my-4"
              >
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-500/20 text-emerald-500 border border-emerald-500/30">
                  <BellRing size={22} className="animate-bounce" />
                </div>
                <p className="font-dot text-sm font-bold text-emerald-500 uppercase tracking-wider">
                  Alert Dispatched Successfully
                </p>
                <p className="text-xs text-muted font-mono">
                  Live alert sent via WebSocket to {department} officers & Super Admins.
                </p>
              </motion.div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Designated Department */}
                <div>
                  <label className="mb-1.5 flex items-center gap-1.5 text-[11px] font-mono font-bold uppercase tracking-wider text-muted">
                    <Building2 size={13} className="text-red-500" />
                    Target Department
                  </label>
                  <select
                    value={department}
                    onChange={e => setDepartment(e.target.value)}
                    className="w-full rounded-2xl border border-line bg-raised px-3.5 py-2.5 text-xs font-semibold text-ink outline-none focus:border-red-500 transition-colors"
                  >
                    <option value="ENGINEERING">ENGINEERING (Track, Rails, Sleepers, Ballast)</option>
                    <option value="SNT">S&T (Signaling, Point Machines, Interlocking)</option>
                    <option value="TRD">TRD (Traction Distribution, OHE Wires, Power Feeders)</option>
                  </select>
                </div>

                {/* Severity Level */}
                <div>
                  <label className="mb-1.5 block text-[11px] font-mono font-bold uppercase tracking-wider text-muted">
                    Severity Priority Level
                  </label>
                  <div className="grid grid-cols-4 gap-2">
                    {[
                      { id: 'EMERGENCY', label: 'EMERGENCY', border: 'border-red-500/40', text: 'text-red-500', bg: 'bg-red-500/10' },
                      { id: 'HIGH', label: 'HIGH', border: 'border-amber-500/40', text: 'text-amber-500', bg: 'bg-amber-500/10' },
                      { id: 'MEDIUM', label: 'MEDIUM', border: 'border-blue-500/40', text: 'text-blue-500', bg: 'bg-blue-500/10' },
                      { id: 'LOW', label: 'LOW', border: 'border-white/20', text: 'text-muted', bg: 'bg-raised' },
                    ].map(lvl => (
                      <button
                        key={lvl.id}
                        type="button"
                        onClick={() => setSeverity(lvl.id)}
                        className={`rounded-xl border px-2 py-2 text-[10px] font-mono font-bold uppercase tracking-wider transition-all text-center ${
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
                  <label className="mb-1.5 block text-[11px] font-mono font-bold uppercase tracking-wider text-muted">
                    Defect Description & Remarks
                  </label>
                  <textarea
                    required
                    className="w-full rounded-2xl border border-line bg-raised p-3 text-xs text-ink outline-none focus:border-red-500 transition-colors placeholder:text-faint font-sans"
                    rows={3}
                    placeholder="e.g. Broken rail joint / sparking in catenary wire near signal pole..."
                    value={desc}
                    onChange={e => setDesc(e.target.value)}
                  />
                </div>

                {/* Corridor & Section */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="mb-1.5 block text-[11px] font-mono font-bold uppercase tracking-wider text-muted">Corridor ID</label>
                    <input
                      type="text"
                      required
                      className="w-full rounded-xl border border-line bg-raised px-3 py-2 text-xs font-mono text-ink outline-none focus:border-red-500"
                      value={corridor}
                      onChange={e => setCorridor(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-[11px] font-mono font-bold uppercase tracking-wider text-muted">Section ID</label>
                    <input
                      type="text"
                      required
                      className="w-full rounded-xl border border-line bg-raised px-3 py-2 text-xs font-mono text-ink outline-none focus:border-red-500"
                      value={section}
                      onChange={e => setSection(e.target.value)}
                    />
                  </div>
                </div>

                {/* KM Location */}
                <div>
                  <label className="mb-1.5 block text-[11px] font-mono font-bold uppercase tracking-wider text-muted">Track KM Location</label>
                  <input
                    type="number"
                    step="0.1"
                    required
                    className="w-full rounded-xl border border-line bg-raised px-3 py-2 text-xs font-mono text-ink outline-none focus:border-red-500"
                    value={km}
                    onChange={e => setKm(e.target.value)}
                  />
                </div>
                
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full mt-2 flex items-center justify-center gap-2 rounded-full bg-red-600 hover:bg-red-700 py-3 text-xs font-bold font-mono uppercase tracking-widest text-white shadow-lg shadow-red-900/20 transition-all disabled:opacity-50 active:scale-[0.98]"
                >
                  <Send size={14} />
                  {loading ? 'BROADCASTING DISPATCH...' : 'SUBMIT & DISPATCH ALERT'}
                </button>
              </form>
            )}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}
