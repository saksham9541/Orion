import { AnimatePresence, motion } from 'framer-motion'
import { Check } from 'lucide-react'

export default function Toast({ message }) {
  return (
    <AnimatePresence>
      {message && (
        <motion.div
          className="fixed bottom-6 left-1/2 z-[60] -translate-x-1/2 panel px-4 py-3 flex items-center gap-2.5"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 12 }}
          transition={{ duration: 0.2 }}
          role="status"
        >
          <Check size={15} className="text-ok" />
          <span className="text-sm">{message}</span>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
