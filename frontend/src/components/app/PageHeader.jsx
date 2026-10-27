import { motion } from 'framer-motion'

export default function PageHeader({ title, description, children }) {
  return (
    <header className="flex flex-col gap-4 border-b border-hair px-5 py-6 sm:px-8 sm:py-7 lg:flex-row lg:items-end lg:justify-between">
      <div className="max-w-[620px]">
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
