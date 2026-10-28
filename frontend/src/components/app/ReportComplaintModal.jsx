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
  const [errorMsg, setErrorMsg] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setErrorMsg(null)
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
        try {
          localStorage.setItem('railopt_task_sync', Date.now().toString())
        } catch (_) {}
      }
      setTimeout(() => {
        setSuccess(false)
        setDesc('')
        onClose()
      }, 1500)
    } catch (err) {
      console.error(err)
      const detail = err.response?.data?.detail || err.message || "Failed to submit issue. Please check server connection."
      setErrorMsg(detail)
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
            className="relative w-full max-w-lg rounded-2xl border border-[#E1E3DE] bg-white p-6 shadow-[0_24px_50px_rgba(40,45,42,0.18)] z-10 my-8"
          >
            {/* Header */}
            <div className="mb-5 flex items-center justify-between border-b border-[#E1E3DE] pb-4">
              <div className="flex items-center gap-3">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#FCE8E8] text-[#DC3030] border border-[#DC3030]/30">
                  <AlertTriangle size={20} />
                </span>
                <div>
                  <h2 className="text-base font-bold tracking-tight text-[#252A27]">
                    Report Track Defect
                  </h2>
                  <p className="text-[11px] text-[#656A66] font-mono">DISPATCH REAL-TIME RAIL ALERT</p>
                </div>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg p-2 text-[#656A66] hover:bg-[#F4F4F1] hover:text-[#252A27] transition-colors border border-transparent hover:border-[#E1E3DE]"
              >
                <X size={16} />
              </button>
            </div>

            {success ? (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="rounded-xl border border-[#0D996B]/30 bg-[#E5F5EC] p-6 text-center space-y-2.5 my-4"
              >
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-[#0D996B]/15 text-[#0D996B] border border-[#0D996B]/30">
                  <BellRing size={22} className="animate-bounce" />
                </div>
                <p className="text-sm font-bold text-[#0D996B] tracking-tight">
                  Alert Dispatched Successfully
                </p>
                <p className="text-xs text-[#656A66] font-mono">
                  Live alert sent via WebSocket to {department} officers & Super Admins.
                </p>
              </motion.div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Designated Department */}
                <div>
                  <label className="mb-1.5 flex items-center gap-1.5 text-[11px] font-mono font-bold uppercase tracking-wider text-[#656A66]">
                    <Building2 size={13} className="text-[#D99A2B]" />
                    Target Department
                  </label>
                  <select
                    value={department}
                    onChange={e => setDepartment(e.target.value)}
                    className="w-full rounded-xl border border-[#E1E3DE] bg-[#F4F4F1] px-3.5 py-2.5 text-xs font-semibold text-[#252A27] outline-none focus:border-[#D99A2B] transition-colors"
                  >
                    <option value="ENGINEERING">ENGINEERING (Track, Rails, Sleepers, Ballast)</option>
                    <option value="SNT">S&T (Signaling, Point Machines, Interlocking)</option>
                    <option value="TRD">TRD (Traction Distribution, OHE Wires, Power Feeders)</option>
                  </select>
                </div>

                {/* Severity Level */}
                <div>
                  <label className="mb-1.5 block text-[11px] font-mono font-bold uppercase tracking-wider text-[#656A66]">
                    Severity Priority Level
                  </label>
                  <div className="grid grid-cols-4 gap-2">
                    {[
                      { id: 'EMERGENCY', label: 'EMERGENCY', border: 'border-[#DC3030]/40', text: 'text-[#DC3030]', bg: 'bg-[#FCE8E8]' },
                      { id: 'HIGH', label: 'HIGH', border: 'border-[#D99019]/40', text: 'text-[#D99019]', bg: 'bg-[#FFF3D9]' },
                      { id: 'MEDIUM', label: 'MEDIUM', border: 'border-[#E1E3DE]', text: 'text-[#252A27]', bg: 'bg-[#F4F4F1]' },
                      { id: 'LOW', label: 'LOW', border: 'border-[#E1E3DE]', text: 'text-[#656A66]', bg: 'bg-white' },
                    ].map(lvl => (
                      <button
                        key={lvl.id}
                        type="button"
                        onClick={() => setSeverity(lvl.id)}
                        className={`rounded-xl border px-2 py-2 text-[10px] font-mono font-bold uppercase tracking-wider transition-all text-center ${
                          severity === lvl.id
                            ? `${lvl.border} ${lvl.bg} ${lvl.text} ring-2 ring-[#D99A2B]/40 font-extrabold`
                            : 'border-[#E1E3DE] bg-[#F4F4F1] text-[#656A66] hover:border-[#282D2A]'
                        }`}
                      >
                        {lvl.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Description */}
                <div>
                  <label className="mb-1.5 block text-[11px] font-mono font-bold uppercase tracking-wider text-[#656A66]">
                    Defect Description & Remarks
                  </label>
                  <textarea
                    required
                    className="w-full rounded-xl border border-[#E1E3DE] bg-[#F4F4F1] p-3 text-xs text-[#252A27] outline-none focus:border-[#D99A2B] transition-colors placeholder:text-[#656A66]/60 font-sans"
                    rows={3}
                    placeholder="e.g. Broken rail joint / sparking in catenary wire near signal pole..."
                    value={desc}
                    onChange={e => setDesc(e.target.value)}
                  />
                </div>

                {/* Corridor & Section */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="mb-1.5 block text-[11px] font-mono font-bold uppercase tracking-wider text-[#656A66]">Corridor ID</label>
                    <input
                      type="text"
                      required
                      className="w-full rounded-xl border border-[#E1E3DE] bg-[#F4F4F1] px-3 py-2 text-xs font-mono text-[#252A27] outline-none focus:border-[#D99A2B]"
                      value={corridor}
                      onChange={e => setCorridor(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-[11px] font-mono font-bold uppercase tracking-wider text-[#656A66]">Section ID</label>
                    <input
                      type="text"
                      required
                      className="w-full rounded-xl border border-[#E1E3DE] bg-[#F4F4F1] px-3 py-2 text-xs font-mono text-[#252A27] outline-none focus:border-[#D99A2B]"
                      value={section}
                      onChange={e => setSection(e.target.value)}
                    />
                  </div>
                </div>

                {/* KM Location */}
                <div>
                  <label className="mb-1.5 block text-[11px] font-mono font-bold uppercase tracking-wider text-[#656A66]">Track KM Location</label>
                  <input
                    type="number"
                    step="0.1"
                    required
                    className="w-full rounded-xl border border-[#E1E3DE] bg-[#F4F4F1] px-3 py-2 text-xs font-mono text-[#252A27] outline-none focus:border-[#D99A2B]"
                    value={km}
                    onChange={e => setKm(e.target.value)}
                  />
                </div>
                
                {errorMsg && (
                  <div className="rounded-xl border border-[#DC3030]/30 bg-[#FCE8E8] p-3 text-xs text-[#DC3030] font-mono flex items-center gap-2">
                    <AlertTriangle size={14} className="shrink-0" />
                    <span>{errorMsg}</span>
                  </div>
                )}
                
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full mt-2 flex items-center justify-center gap-2 rounded-xl bg-[#DC3030] hover:bg-[#B92424] py-3 text-xs font-bold font-mono uppercase tracking-widest text-white shadow-sm transition-all disabled:opacity-50 active:scale-[0.98]"
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
