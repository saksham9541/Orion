import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ArrowLeft, LogOut, User } from 'lucide-react'
import { useAppState } from '@/state/AppState'
import NotificationBell from '@/components/common/NotificationBell'
import ThemeToggle from '@/components/common/ThemeToggle'

export const STAGES = [
  { to: '/dashboard', name: 'OVERVIEW' },
  { to: '/tasks', name: 'DEMAND' },
  { to: '/network', name: 'NETWORK' },
  { to: '/simulate', name: 'OPTIMIZATION' },
  { to: '/plan', name: 'SCHEDULE' },
  { to: '/assistant', name: 'BRIEFING' }
]

export default function StageNav() {
  const { currentUser, logout } = useAppState()
  const navigate = useNavigate()
  const location = useLocation()

  const handleBack = () => {
    const roleId = currentUser?.id
    if (roleId && roleId !== 'admin') {
      navigate(`/${roleId}`)
    } else if (roleId === 'admin') {
      navigate('/admin')
    } else {
      navigate(-1)
    }
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <header className="sticky top-0 z-30 border-b border-line/60 bg-base/90 backdrop-blur-md text-ink px-4 sm:px-6 py-2.5">
      <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-4">
        {/* Left: Brand & Back */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleBack}
            className="flex h-9 w-9 items-center justify-center rounded-full border border-line bg-surface text-muted hover:text-ink hover:bg-raised transition-all shadow-sm"
            aria-label="Go back"
            title="Go back"
          >
            <ArrowLeft size={15} />
          </button>
          
          <Link to="/dashboard" className="flex items-center gap-2.5 rounded-xl px-2 py-1 hover:bg-surface/50 transition-colors">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#282D2A] text-[#D99A2B] border border-[#3A403B] font-mono font-bold text-xs shadow-sm">
              R1
            </span>
            <div className="flex flex-col">
              <div className="flex items-center gap-1.5">
                <span className="text-[16px] font-bold tracking-tight text-ink font-sans">
                  RailOpt
                </span>
                <span className="h-1.5 w-1.5 rounded-full bg-[#D99A2B] inline-block" />
              </div>
              <span className="hidden text-[8.5px] font-mono uppercase tracking-[0.2em] text-faint sm:inline">
                (SCHEDULE / OS.02)
              </span>
            </div>
          </Link>
        </div>

        {/* Center: Stage Pill Navigation */}
        <nav className="hidden lg:flex items-center gap-1 rounded-full border border-line bg-surface/80 p-1 shadow-sm backdrop-blur-md">
          {STAGES.map((s) => {
            const active = location.pathname.startsWith(s.to)
            return (
              <Link
                key={s.to}
                to={s.to}
                className={`rounded-full px-3.5 py-1.5 text-xs font-mono uppercase tracking-wider transition-all ${
                  active
                    ? 'bg-ink text-deep font-bold shadow-sm'
                    : 'text-muted hover:text-ink hover:bg-raised/70'
                }`}
              >
                {s.name}
              </Link>
            )
          })}
        </nav>

        {/* Right: Notification, Theme, Profile, Logout */}
        <div className="flex items-center gap-2 sm:gap-2.5">
          <NotificationBell />
          <ThemeToggle />

          {/* User Profile Pill */}
          <div className="flex items-center gap-2 rounded-full border border-line bg-surface px-2.5 py-1 shadow-sm">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200 text-[10px] font-bold">
              <User size={13} />
            </span>
            <span className="hidden text-xs font-semibold text-ink sm:inline">
              {currentUser?.label || 'Operator'}
            </span>
          </div>

          <button 
            onClick={handleLogout}
            className="flex h-9 w-9 items-center justify-center rounded-full border border-line bg-surface text-muted hover:text-danger hover:border-danger/30 hover:bg-danger/5 transition-colors shadow-sm"
            title="Logout"
          >
            <LogOut size={14} />
          </button>
        </div>
      </div>
    </header>
  )
}

