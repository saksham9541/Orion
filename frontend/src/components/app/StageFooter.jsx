import { useLocation, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, Sparkles } from 'lucide-react'
import { STAGES } from './StageNav'

/**
 * The forward motion the user asked for: each stage ends by pointing at the
 * next one, by name, with a reason to go there — rather than leaving them to
 * find it in a menu. Now with premium hover glow.
 */
export default function StageFooter({ reason }) {
  const location = useLocation()
  const navigate = useNavigate()
  const i = STAGES.findIndex((s) => location.pathname.startsWith(s.to))
  const next = STAGES[i + 1]
  if (!next) return null

  return (
    <motion.button
      onClick={() => navigate(next.to)}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.6, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      whileHover={{ x: 4, scale: 1.005 }}
      className="group glow-border mx-5 mb-8 flex items-center justify-between gap-4 rounded-panel border border-line bg-surface/60 px-5 py-4 text-left transition-all duration-300 hover:border-merge/40 hover:shadow-lg sm:mx-8"
    >
      <div>
        <p className="flex items-center gap-1.5 text-[11.5px] text-faint">
          <Sparkles size={11} className="text-eng/60" />
          Next stage
        </p>
        <p className="mt-0.5 text-[15px] font-medium">
          {next.name || next.label}
          {reason && <span className="ml-2 font-normal text-muted">— {reason}</span>}
        </p>
      </div>
      <span className="flex shrink-0 items-center gap-1.5 rounded-panel bg-raised px-3 py-2 text-[13px] text-ink transition-all duration-300 group-hover:bg-merge group-hover:text-deep group-hover:shadow-md">
        <ArrowRight size={14} className="transition-transform group-hover:translate-x-0.5" />
      </span>
    </motion.button>
  )
}
