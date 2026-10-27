import { Outlet, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import StageNav from './StageNav'
import IssueAlertModal from '@/components/common/IssueAlertModal'

/**
 * The control room is one column, driven forward stage by stage — see
 * StageNav for the sequence and StageFooter for the per-page "next" prompt.
 * Premium entry animations make the room feel alive when you step in.
 */
export default function AppShell() {
  const location = useLocation()

  return (
    <div className="relative min-h-screen">
      {/* Warm ambient wash behind the stage header */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 z-0 h-72"
        style={{
          background:
            'radial-gradient(1200px 280px at 50% -30%, rgb(var(--c-merge) / 0.10), transparent 70%)',
        }}
      />
      {/* Subtle noise texture for premium paper feel */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 z-0 opacity-[0.025]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='1'/%3E%3C/svg%3E")`,
        }}
      />
      <div className="relative z-10">
        <IssueAlertModal />
        <StageNav />
        <AnimatePresence mode="wait">
          <motion.main
            key={location.pathname}
            className="min-w-0"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          >
            <Outlet />
          </motion.main>
        </AnimatePresence>
      </div>
    </div>
  )
}
