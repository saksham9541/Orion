import { motion } from 'framer-motion'
import { ArrowLeft } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAppState } from '@/state/AppState'

export default function PageHeader({ title, description, showBack = true, onBack, children }) {
  const navigate = useNavigate()
  const { currentUser } = useAppState()

  const handleBack = () => {
    if (onBack) {
      onBack()
      return
    }
    const roleId = currentUser?.id
    if (roleId && roleId !== 'admin') {
      navigate(`/${roleId}`)
    } else if (roleId === 'admin') {
      navigate('/admin')
    } else {
      navigate(-1)
    }
  }

  return (
    <header className="flex flex-col gap-4 border-b border-hair px-5 py-5 sm:px-8 sm:py-6 lg:flex-row lg:items-end lg:justify-between">
      <div className="max-w-[720px]">
        {showBack && (
          <button
            type="button"
            onClick={handleBack}
            className="mb-3 inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-2.5 py-1 text-xs font-semibold text-muted hover:text-ink hover:bg-raised transition-colors shadow-sm"
            aria-label="Go back"
          >
            <ArrowLeft size={13} />
            <span>Back</span>
          </button>
        )}
        <motion.h1
          className="text-[22px] font-semibold tracking-tight sm:text-[26px]"
          initial={{ opacity: 0, x: -12 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        >
          {title}
        </motion.h1>
        {description && (
          <motion.p
            className="mt-2 text-[14px] leading-relaxed text-muted"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.15, duration: 0.5 }}
          >
            {description}
          </motion.p>
        )}
      </div>
      {children && (
        <motion.div
          className="flex shrink-0 flex-wrap items-center gap-2"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.4 }}
        >
          {children}
        </motion.div>
      )}
    </header>
  )
}
