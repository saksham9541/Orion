import { useLocation, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowLeft, ArrowRight, Sparkles } from 'lucide-react'
import { useAppState } from '@/state/AppState'
import { STAGES } from './StageNav'

/**
 * Two-way stage progression: gives operators an explicit previous/back button
 * and a forward "next stage" button with justification.
 */
export default function StageFooter({ reason }) {
  const location = useLocation()
  const navigate = useNavigate()
  const { currentUser } = useAppState()

  const i = STAGES.findIndex((s) => location.pathname.startsWith(s.to))
  const prev = i > 0 ? STAGES[i - 1] : null
  const next = i >= 0 && i < STAGES.length - 1 ? STAGES[i + 1] : null

  const handlePrev = () => {
    if (prev) {
      navigate(prev.to)
    } else if (currentUser?.id && currentUser.id !== 'admin') {
      navigate(`/${currentUser.id}`)
    } else if (currentUser?.id === 'admin') {
      navigate('/admin')
    } else {
      navigate(-1)
    }
  }

  const prevLabel = prev
    ? prev.name || prev.label
    : currentUser?.id === 'admin'
    ? 'Super Admin Control Room'
    : currentUser?.id
    ? `${currentUser.label || 'Department'} Portal`
    : 'Dashboard'

  return (
    <div className="mx-5 mb-8 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 sm:mx-8 pt-4 border-t border-hair">
      {/* Back / Previous Stage Button */}
      <motion.button
        type="button"
        onClick={handlePrev}
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4, duration: 0.4 }}
        whileHover={{ x: -3 }}
        className="group flex items-center gap-3 rounded-panel border border-line bg-surface/70 px-4 py-3.5 text-left transition-all hover:border-line hover:bg-raised shadow-sm"
      >
        <span className="flex shrink-0 items-center justify-center rounded-panel bg-raised p-2 text-ink group-hover:bg-line transition-colors">
          <ArrowLeft size={15} />
        </span>
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wider text-faint">
            {prev ? 'Previous Stage' : 'Back to Dashboard'}
          </p>
          <p className="text-[13.5px] font-medium text-ink">
            {prevLabel}
          </p>
        </div>
      </motion.button>

      {/* Next Stage Button */}
      {next && (
        <motion.button
          type="button"
          onClick={() => navigate(next.to)}
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5, duration: 0.4 }}
          whileHover={{ x: 3 }}
          className="group glow-border flex items-center justify-between gap-4 rounded-panel border border-line bg-surface/70 px-5 py-3.5 text-left transition-all hover:border-merge/40 hover:shadow-lg sm:ml-auto"
        >
          <div>
            <p className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-faint">
              <Sparkles size={11} className="text-eng/60" />
              Next stage
            </p>
            <p className="mt-0.5 text-[14px] font-medium text-ink">
              {next.name || next.label}
              {reason && <span className="ml-2 font-normal text-muted">— {reason}</span>}
            </p>
          </div>
          <span className="flex shrink-0 items-center gap-1.5 rounded-panel bg-raised px-2.5 py-1.5 text-[13px] text-ink transition-all group-hover:bg-merge group-hover:text-deep shadow-sm">
            <ArrowRight size={14} className="transition-transform group-hover:translate-x-0.5" />
          </span>
        </motion.button>
      )}
    </div>
  )
}
