import { useState } from 'react'
import { X } from 'lucide-react'
import { submitComplaint } from '@/api'

export default function ReportComplaintModal({ isOpen, onClose }) {
  const [desc, setDesc] = useState('')
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
        km_location: parseFloat(km)
      })
      setSuccess(true)
      setTimeout(() => {
        setSuccess(false)
        onClose()
      }, 2000)
    } catch (err) {
      console.error(err)
      alert("Failed to submit complaint")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-xl border border-line bg-surface p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-bold uppercase tracking-tight text-ink">Report Defect</h2>
          <button onClick={onClose} className="text-faint hover:text-ink">
            <X size={20} />
          </button>
        </div>
        
        {success ? (
          <div className="rounded border border-ok/30 bg-ok/10 p-4 text-center text-ok font-bold uppercase tracking-widest text-sm">
            Defect Submitted Successfully!
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="mb-1 block text-[10px] font-bold uppercase tracking-widest text-faint">Description</label>
              <textarea
                required
                className="w-full rounded border border-line bg-raised p-2 text-sm text-ink outline-none focus:border-info"
                rows={3}
                placeholder="e.g. Heavy sparking and overhead wire snapped..."
                value={desc}
                onChange={e => setDesc(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-[10px] font-bold uppercase tracking-widest text-faint">Corridor ID</label>
                <input
                  type="text"
                  required
                  className="w-full rounded border border-line bg-raised p-2 text-sm text-ink outline-none focus:border-info"
                  value={corridor}
                  onChange={e => setCorridor(e.target.value)}
                />
              </div>
              <div>
                <label className="mb-1 block text-[10px] font-bold uppercase tracking-widest text-faint">Section ID</label>
                <input
                  type="text"
                  required
                  className="w-full rounded border border-line bg-raised p-2 text-sm text-ink outline-none focus:border-info"
                  value={section}
                  onChange={e => setSection(e.target.value)}
                />
              </div>
            </div>
            <div>
              <label className="mb-1 block text-[10px] font-bold uppercase tracking-widest text-faint">Km Location</label>
              <input
                type="number"
                step="0.1"
                required
                className="w-full rounded border border-line bg-raised p-2 text-sm text-ink outline-none focus:border-info"
                value={km}
                onChange={e => setKm(e.target.value)}
              />
            </div>
            
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded bg-info py-2 text-xs font-bold uppercase tracking-widest text-white hover:bg-info/90 disabled:opacity-50"
            >
              {loading ? 'Submitting...' : 'Submit Defect'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
