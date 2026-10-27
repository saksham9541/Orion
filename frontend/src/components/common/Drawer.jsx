import { useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { X } from 'lucide-react'

/**
 * Side panel for detail views. Motion here answers the user's click and shows
 * where the panel came from, so it earns its place.
 */
export default function Drawer({ open, onClose, title, subtitle, children }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    if (open) window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 z-40 bg-deep/60 backdrop-blur-md"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            onClick={onClose}
          />
          <motion.aside
            className="fixed right-0 top-0 z-50 h-full w-full max-w-[520px] bg-surface border-l border-line shadow-lift flex flex-col"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 320, damping: 34 }}
            role="dialog"
            aria-modal="true"
            aria-label={title}
          >
            <header className="flex items-start justify-between gap-4 px-6 py-5 border-b border-hair">
              <div>
                <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
                {subtitle && <p className="text-[13px] text-muted mt-1">{subtitle}</p>}
              </div>
              <button
                onClick={onClose}
                className="p-1.5 rounded-panel text-muted hover:text-ink hover:bg-raised transition-colors"
                aria-label="Close panel"
              >
                <X size={18} />
              </button>
            </header>
            <div className="flex-1 overflow-y-auto scrollbar-thin px-6 py-5">{children}</div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  )
}
