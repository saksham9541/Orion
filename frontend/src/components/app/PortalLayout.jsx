import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import {
  LogOut,
  ArrowLeft,
  MessageSquare,
  User,
  AlertTriangle,
  Layers,
  Calendar,
  Sliders,
  Database,
  Plus,
  LayoutDashboard,
  ShieldAlert,
  Sparkles,
  Share2
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
  const [serverStatus, setServerStatus] = useState('idle') // 'idle' | 'loading' | 'ready' | 'error'

  const home = role === 'admin' ? '/admin' : `/${role}`

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  // Top navigation pill items inspired by the SugarCRM reference design
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

      {/* TOP HEADER WITH MODERN PILL NAVIGATION */}
      <header className="sticky top-0 z-30 border-b border-line/60 bg-base/90 backdrop-blur-md px-4 sm:px-6 py-2.5">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-4">
          
          {/* Left: Brand Logo & Back Button */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => {
                if (window.history.length > 1) {
                  navigate(-1)
                } else {
                  navigate('/dashboard')
                }
              }}
              className="flex h-9 w-9 items-center justify-center rounded-full border border-line bg-surface text-muted hover:text-ink hover:bg-raised transition-all shadow-sm"
              aria-label="Go back"
              title="Go back"
            >
              <ArrowLeft size={15} />
            </button>

            <Link to={home} className="flex items-center gap-2.5 rounded-xl px-2 py-1 hover:bg-surface/50 transition-colors" aria-label="RailOpt home">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-ink text-deep font-dot text-xs font-bold shadow-sm">
                R1
              </span>
              <div className="flex flex-col">
                <div className="flex items-center gap-1.5">
                  <span className="text-[14px] font-dot uppercase tracking-wider text-ink">
                    RAILOPT
                  </span>
                  <span className="h-1.5 w-1.5 rounded-full bg-[#d71920] inline-block animate-pulse" />
                </div>
                <span className="hidden text-[8.5px] font-mono uppercase tracking-[0.2em] text-faint sm:inline">
                  (SYSTEM / OS.02)
                </span>
              </div>
            </Link>
          </div>

          {/* Center: Nothing OS Pill Navigation Tabs */}
          <nav className="hidden lg:flex items-center gap-1 rounded-full border border-line bg-surface/80 p-1 shadow-sm backdrop-blur-md">
            {navTabs.map((tab) => {
              const active = isTabActive(tab.to)
              return (
                <Link
                  key={tab.to}
                  to={tab.to}
                  className={`rounded-full px-3.5 py-1.5 text-xs font-mono uppercase tracking-wider transition-all ${
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
          <div className="flex items-center gap-2 sm:gap-2.5">
            {currentUser?.id === 'admin' && (
              <>
                <button
                  type="button"
                  disabled={serverStatus === 'loading'}
                  onClick={async () => {
                    setServerStatus('loading')
                    try {
                      const loginRes = await fetch('http://localhost:8000/api/auth/login', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ email: 'admin@railopt.gov.in', password: 'password123' })
                      });
                      const loginData = await loginRes.json();
                      const token = loginData.access_token;
                      sessionStorage.setItem('railopt_token', token);

                      const res = await fetch('http://localhost:8000/api/demo/setup', {
                        method: 'POST',
                        headers: { 'Authorization': `Bearer ${token}` }
                      });
                      if (res.ok) {
                        setServerStatus('ready')
                        setTimeout(() => window.location.reload(), 1500)
                      } else {
                        setServerStatus('error')
                      }
                    } catch (err) {
                      console.error(err)
                      setServerStatus('error')
                    }
                  }}
                  className="hidden md:flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider text-muted hover:text-ink hover:bg-raised transition-colors shadow-sm"
                >
                  <span className={`h-1.5 w-1.5 rounded-full ${
                    serverStatus === 'ready' ? 'bg-[#d71920]' :
                    serverStatus === 'error' ? 'bg-[#d71920]' :
                    serverStatus === 'loading' ? 'bg-warn animate-ping' : 'bg-[#d71920]'
                  }`} />
                  <span>
                    {serverStatus === 'loading' ? 'Setting up...' :
                     serverStatus === 'ready' ? 'Server Ready' :
                     serverStatus === 'error' ? 'Retry Setup' :
                     'Setup Server'}
                  </span>
                </button>
                <Link
                  to="/simulate"
                  className="hidden sm:flex items-center gap-1.5 rounded-full bg-[#d71920] text-white px-3.5 py-1.5 text-[10px] font-mono font-bold uppercase tracking-widest shadow-sm hover:opacity-90 transition-opacity"
                >
                  <Sparkles size={11} />
                  <span>Generate Plan</span>
                </Link>
              </>
            )}

            {/* Quick Action: Report Defect (+) */}
            <button
              type="button"
              onClick={() => setIsComplaintModalOpen(true)}
              className="flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1.5 text-xs font-mono uppercase tracking-wider text-ink hover:border-[#d71920]/60 transition-colors shadow-sm"
              title="Report New Railway Defect"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-[#d71920] inline-block" />
              <span className="hidden sm:inline">Report Defect</span>
            </button>

            {/* Assistant Drawer Trigger */}
            <button
              type="button"
              onClick={() => setIsAssistantOpen(true)}
              className="flex h-9 w-9 items-center justify-center rounded-full border border-line bg-surface text-muted hover:text-ink hover:bg-raised transition-colors shadow-sm"
              title="RailOpt Assistant"
            >
              <MessageSquare size={15} />
            </button>

            <NotificationBell />
            <ThemeToggle />

            {/* User Profile Pill */}
            <div className="flex items-center gap-2 rounded-full border border-line bg-surface px-2.5 py-1 shadow-sm">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200 text-[10px] font-bold">
                {currentUser?.id ? currentUser.id.slice(0, 2).toUpperCase() : 'OP'}
              </span>
              <span className="hidden text-xs font-semibold text-ink sm:inline">
                {currentUser?.label || 'Officer'}
              </span>
            </div>

            {/* Logout Button */}
            <button
              type="button"
              onClick={handleLogout}
              className="flex h-9 w-9 items-center justify-center rounded-full border border-line bg-surface text-muted hover:text-danger hover:border-danger/30 hover:bg-danger/5 transition-colors shadow-sm"
              title="Log out"
            >
              <LogOut size={14} />
            </button>
          </div>

        </div>
      </header>

      {/* BODY WITH LEFT FLOATING DOCK & MAIN CLAY/BENTO CANVAS */}
      <div className="flex-1 mx-auto flex w-full max-w-[1600px] gap-4 p-4 sm:p-6 lg:p-7">
        
        {/* LEFT FLOATING VERTICAL ICON DOCK (Identical to reference screenshot) */}
        <aside className="hidden md:flex flex-col items-center gap-2.5 rounded-[26px] border border-line/80 bg-surface/90 backdrop-blur-md p-2.5 shadow-[0_4px_20px_rgba(0,0,0,0.03)] h-fit sticky top-20">
          <button
            type="button"
            onClick={() => {
              if (window.history.length > 1) {
                navigate(-1)
              } else {
                navigate('/dashboard')
              }
            }}
            className="flex h-9 w-9 items-center justify-center rounded-full text-muted hover:text-ink hover:bg-raised transition-colors"
            title="Go Back"
          >
            <ArrowLeft size={16} />
          </button>

          <div className="h-px w-5 bg-line/80" />

          <button
            type="button"
            onClick={() => navigate('/network')}
            className={`flex h-9 w-9 items-center justify-center rounded-full transition-colors ${
              location.pathname === '/network' ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900' : 'text-muted hover:text-ink hover:bg-raised'
            }`}
            title="Digital Twin Network (/network)"
          >
            <Share2 size={16} />
          </button>

          <button
            type="button"
            onClick={() => setIsComplaintModalOpen(true)}
            className="flex h-9 w-9 items-center justify-center rounded-full text-muted hover:text-ink hover:bg-raised transition-colors"
            title="Add / Report Defect"
          >
            <Plus size={16} />
          </button>

          <button
            type="button"
            onClick={() => navigate('/simulate')}
            className={`flex h-9 w-9 items-center justify-center rounded-full transition-colors ${
              location.pathname === '/simulate' ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900' : 'text-muted hover:text-ink hover:bg-raised'
            }`}
            title="Scenario Simulator (/simulate)"
          >
            <Sliders size={16} />
          </button>

          <button
            type="button"
            onClick={() => navigate('/plan')}
            className={`flex h-9 w-9 items-center justify-center rounded-full transition-colors ${
              location.pathname === '/plan' ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900' : 'text-muted hover:text-ink hover:bg-raised'
            }`}
            title="Weekly Block Plan (/plan)"
          >
            <Calendar size={16} />
          </button>

          <button
            type="button"
            onClick={() => navigate('/tasks')}
            className={`flex h-9 w-9 items-center justify-center rounded-full transition-colors ${
              location.pathname === '/tasks' ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900' : 'text-muted hover:text-ink hover:bg-raised'
            }`}
            title="Pending Work Demand (/tasks)"
          >
            <Layers size={16} />
          </button>

          <button
            type="button"
            onClick={() => navigate('/sources')}
            className={`flex h-9 w-9 items-center justify-center rounded-full transition-colors ${
              location.pathname === '/sources' ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900' : 'text-muted hover:text-ink hover:bg-raised'
            }`}
            title="Data Sources (/sources)"
          >
            <Database size={16} />
          </button>

          <button
            type="button"
            onClick={() => setIsAssistantOpen(true)}
            className="flex h-9 w-9 items-center justify-center rounded-full text-muted hover:text-ink hover:bg-raised transition-colors"
            title="RailOpt AI Assistant"
          >
            <MessageSquare size={16} />
          </button>

          <div className="h-px w-5 bg-line/80 mt-2" />

          {/* Theme Switcher at bottom of dock (Just like sun/moon in screenshot) */}
          <div className="pt-1">
            <ThemeToggle />
          </div>
        </aside>

        {/* MAIN BENTO / SQUIRCLE CANVAS */}
        <main className="flex-1 min-w-0 rounded-[32px] border border-line/70 bg-surface/85 dark:bg-surface/50 backdrop-blur-md p-5 sm:p-7 lg:p-8 shadow-[0_12px_40px_rgba(0,0,0,0.03)]">
          {children}
        </main>

      </div>

      <AssistantPanel isOpen={isAssistantOpen} onClose={() => setIsAssistantOpen(false)} />
    </div>
  )
}
