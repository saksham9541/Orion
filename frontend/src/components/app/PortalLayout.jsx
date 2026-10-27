import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import {
  LogOut,
  ArrowLeft,
  MessageSquare,
  User,
  Plus
} from 'lucide-react'
import AssistantPanel from './AssistantPanel'
import ThemeToggle from '@/components/common/ThemeToggle'
import NotificationBell from '@/components/common/NotificationBell'
import IssueAlertModal from '@/components/common/IssueAlertModal'
import ReportComplaintModal from './ReportComplaintModal'
import { useAppState } from '@/state/AppState'

export default function PortalLayout({ children, role }) {
  const navigate = useNavigate()
  const location = useLocation()
  const { currentUser, logout } = useAppState()
  const [isAssistantOpen, setIsAssistantOpen] = useState(false)
  const [isComplaintModalOpen, setIsComplaintModalOpen] = useState(false)

  const home = role === 'admin' ? '/admin' : `/${role}`

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  // Top navigation items with generous spacing & clean Nothing OS aesthetic
  const navTabs = [
    { label: 'Overview', to: '/dashboard' },
    { label: 'Super Admin', to: '/admin' },
    { label: 'S&T Dept', to: '/snt' },
    { label: 'Engineering', to: '/engineering' },
    { label: 'TRD', to: '/trd' },
    { label: 'Technician', to: '/technician' },
    { label: 'Schedule', to: '/plan' },
  ]

  const isTabActive = (tabTo) => {
    if (tabTo === '/dashboard') return location.pathname === '/dashboard'
    return location.pathname.startsWith(tabTo)
  }

  return (
    <div className="min-h-screen bg-base font-sans text-ink transition-colors duration-300 flex flex-col">
      <IssueAlertModal />
      <ReportComplaintModal isOpen={isComplaintModalOpen} onClose={() => setIsComplaintModalOpen(false)} />

      {/* TOP HEADER WITH AIRY NOTHING OS PILL NAVIGATION */}
      <header className="sticky top-0 z-30 border-b border-line/60 bg-base/80 backdrop-blur-xl px-6 sm:px-10 py-3.5 transition-all">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-6">
          
          {/* Left: Brand Logo & Back Button */}
          <div className="flex items-center gap-4 shrink-0">
            <button
              type="button"
              onClick={() => {
                if (window.history.length > 1) {
                  navigate(-1)
                } else {
                  navigate('/dashboard')
                }
              }}
              className="flex h-10 w-10 items-center justify-center rounded-full border border-line bg-surface text-muted hover:text-ink hover:bg-raised transition-all shadow-sm active:scale-95"
              aria-label="Go back"
              title="Go back"
            >
              <ArrowLeft size={16} />
            </button>

            <Link to={home} className="flex items-center gap-3 rounded-2xl px-2 py-1 hover:bg-surface/50 transition-colors" aria-label="RailOpt home">
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-ink text-deep font-dot text-xs font-bold shadow-sm">
                R1
              </span>
              <div className="flex flex-col">
                <div className="flex items-center gap-1.5">
                  <span className="text-[15px] font-dot uppercase tracking-wider text-ink">
                    RAILOPT
                  </span>
                  <span className="h-2 w-2 rounded-full bg-[#d71920] inline-block animate-pulse" />
                </div>
                <span className="text-[9px] font-mono uppercase tracking-[0.22em] text-muted">
                  NOTHING OS · 02
                </span>
              </div>
            </Link>
          </div>

          {/* Center: Nothing OS Pill Navigation Tabs */}
          <nav className="hidden xl:flex items-center gap-1.5 rounded-full border border-line/80 bg-surface/90 p-1.5 shadow-sm backdrop-blur-md">
            {navTabs.map((tab) => {
              const active = isTabActive(tab.to)
              return (
                <Link
                  key={tab.to}
                  to={tab.to}
                  className={`rounded-full px-4 py-1.5 text-xs font-mono uppercase tracking-wider transition-all ${
                    active
                      ? 'bg-ink text-deep font-bold shadow-sm'
                      : 'text-muted hover:text-ink hover:bg-raised/70'
                  }`}
                >
                  {tab.label}
                </Link>
              )
            })}
          </nav>

          {/* Right: Actions, Utilities & Profile */}
          <div className="flex items-center gap-3 shrink-0">
            {/* Quick Action: Report Defect (+) */}
            <button
              type="button"
              onClick={() => setIsComplaintModalOpen(true)}
              className="flex items-center gap-2 rounded-full border border-red-500/30 bg-red-500/10 hover:bg-red-500/20 px-4 py-2 text-xs font-mono font-bold uppercase tracking-wider text-red-500 transition-all shadow-sm active:scale-95"
              title="Report New Railway Defect"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-[#d71920] inline-block animate-ping" />
              <span>Report Defect</span>
            </button>

            {/* Assistant Drawer Trigger */}
            <button
              type="button"
              onClick={() => setIsAssistantOpen(true)}
              className="flex h-10 w-10 items-center justify-center rounded-full border border-line bg-surface text-muted hover:text-ink hover:bg-raised transition-colors shadow-sm"
              title="RailOpt AI Assistant"
            >
              <MessageSquare size={16} />
            </button>

            <NotificationBell />
            <ThemeToggle />

            {/* User Profile Pill */}
            <div className="flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1.5 shadow-sm">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200 text-[10px] font-bold">
                {currentUser?.id ? currentUser.id.slice(0, 2).toUpperCase() : 'OP'}
              </span>
              <span className="hidden sm:inline text-xs font-semibold text-ink font-mono uppercase">
                {currentUser?.label || 'Officer'}
              </span>
            </div>

            {/* Logout Button */}
            <button
              type="button"
              onClick={handleLogout}
              className="flex h-10 w-10 items-center justify-center rounded-full border border-line bg-surface text-muted hover:text-danger hover:border-danger/30 hover:bg-danger/5 transition-colors shadow-sm"
              title="Log out"
            >
              <LogOut size={15} />
            </button>
          </div>

        </div>
      </header>

      {/* EXPANSIVE, BREATHING MAIN CANVAS (NO REDUNDANT DOCK, NO DOUBLE BOXING) */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-6 sm:px-10 lg:px-12 py-8 lg:py-12">
        {children}
      </main>

      <AssistantPanel isOpen={isAssistantOpen} onClose={() => setIsAssistantOpen(false)} />
    </div>
  )
}
