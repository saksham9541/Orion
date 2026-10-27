import { AnimatePresence, motion } from 'framer-motion'
import { Moon, Sun } from 'lucide-react'
import { useTheme } from '@/hooks/useTheme'

/**
 * Day / control-room toggle. Small and quiet — it changes the palette, not
 * the product — but the icon swap gets a real transition, since it's the
 * one interaction people will reach for constantly.
 */
export default function ThemeToggle({ className = '' }) {
  const { theme, toggle, isDark } = useTheme()

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
      aria-pressed={!isDark}
      title={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
      className={`group relative inline-flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded-panel border border-line bg-raised/50 text-muted transition-colors duration-200 hover:border-merge/50 hover:text-ink ${className}`}
    >
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 scale-0 rounded-full bg-merge/15 transition-transform duration-300 group-hover:scale-150"
      />
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={theme}
          initial={{ opacity: 0, rotate: -80, scale: 0.4 }}
          animate={{ opacity: 1, rotate: 0, scale: 1 }}
          exit={{ opacity: 0, rotate: 80, scale: 0.4 }}
          transition={{ duration: 0.26, ease: [0.16, 1, 0.3, 1] }}
          className="relative flex"
        >
          {isDark ? <Moon size={15} strokeWidth={1.8} /> : <Sun size={15} strokeWidth={1.8} />}
        </motion.span>
      </AnimatePresence>
    </button>
  )
}
