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
import LiveIndicator from '@/components/common/LiveIndicator'
import IssueAlertModal from '@/components/common/IssueAlertModal'
import ReportComplaintModal from './ReportComplaintModal'
import { useAppState } from '@/state/AppState'
import { getPermittedNavTabs, isTabActive } from './navConfig'

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

  // Role-permitted navigation tabs
  const navTabs = getPermittedNavTabs(currentUser, role)

  return (
    <div className="min-h-screen bg-base font-sans text-ink transition-colors duration-300 flex flex-col">
      <IssueAlertModal />
      <ReportComplaintModal isOpen={isComplaintModalOpen} onClose={() => setIsComplaintModalOpen(false)} />

      {/* TOP HEADER WITH INDUSTRIAL GRAPHITE NAVIGATION */}
      <header className="sticky top-0 z-30 border-b border-line bg-base/90 backdrop-blur-xl px-6 sm:px-10 py-3 transition-all">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-6">
          
          {/* Left: Brand Logo & Back Button */}
          <div className="flex items-center gap-3.5 shrink-0">
            <button
              type="button"
              onClick={() => {
                if (window.history.length > 1) {
                  navigate(-1)
                } else {
                  navigate('/dashboard')
                }
              }}
              className="flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-surface text-muted hover:text-ink hover:bg-base transition-all shadow-sm active:scale-95"
              aria-label="Go back"
              title="Go back"
            >
              <ArrowLeft size={15} />
            </button>

            <Link to={home} className="flex items-center gap-3 rounded-xl px-2 py-1 hover:bg-surface/50 transition-colors" aria-label="RailOpt home">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#282D2A] text-[#D99A2B] border border-[#3A403B] font-mono font-bold text-xs shadow-sm">
                R1
              </span>
              <div className="flex flex-col">
                <div className="flex items-center gap-1.5">
                  <span className="text-[17px] font-bold tracking-tight text-ink font-sans">
                    RailOpt
                  </span>
                  <span className="h-2 w-2 rounded-full bg-[#D99A2B] inline-block" />
                </div>
                <span className="text-[9.5px] font-mono uppercase tracking-wider text-muted">
                  System OS · 02
                </span>
              </div>
            </Link>
          </div>

          {/* Center: Industrial Navigation Tabs */}
          <nav className="hidden md:flex items-center gap-1 rounded-xl border border-line bg-surface p-1 shadow-sm">
            {navTabs.map((tab) => {
              const active = isTabActive(tab.to, location.pathname)
              return (
                <Link
                  key={tab.to}
                  to={tab.to}
                  className={`rounded-lg px-3.5 py-1.5 text-xs font-mono font-semibold uppercase tracking-wider transition-all ${
                    active
                      ? 'bg-[#282D2A] text-white shadow-sm'
                      : 'text-muted hover:text-ink hover:bg-base'
                  }`}
                >
                  {tab.label}
                </Link>
              )
            })}
          </nav>

          {/* Right: Actions, Utilities & Profile */}
          <div className="flex items-center gap-2.5 shrink-0">
            {/* Quick Action: Report Defect (+) */}
            <button
              type="button"
              onClick={() => setIsComplaintModalOpen(true)}
              className="flex items-center gap-1.5 rounded-lg bg-[#DC3030] hover:bg-[#b92525] text-white px-3.5 py-2 text-xs font-sans font-semibold tracking-wide shadow-sm transition-all active:scale-95"
              title="Report New Railway Defect"
            >
              <Plus size={14} />
              <span>Report Defect</span>
            </button>

            {/* Assistant Drawer Trigger */}
            <button
              type="button"
              onClick={() => setIsAssistantOpen(true)}
              className="flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-surface text-muted hover:text-ink hover:bg-base transition-colors shadow-sm"
              title="RailOpt AI Assistant"
            >
              <MessageSquare size={15} />
            </button>

            <LiveIndicator />
            <NotificationBell />
            <ThemeToggle />

            {/* User Profile Pill */}
            <div className="flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-1.5 shadow-sm">
              <span className="flex h-5 w-5 items-center justify-center rounded-md bg-[#282D2A] text-[#D99A2B] text-[10px] font-mono font-bold">
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
              className="flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-surface text-muted hover:text-[#DC3030] hover:border-[#DC3030]/30 hover:bg-[#FCE8E8] transition-colors shadow-sm"
              title="Log out"
            >
              <LogOut size={14} />
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
