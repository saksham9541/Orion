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
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-merge text-deep font-bold text-xs shadow-sm">
              RO
            </span>
            <div className="flex flex-col">
              <span className="text-[15px] font-bold uppercase tracking-tight leading-none text-ink">
                RailOpt
              </span>
              <span className="hidden text-[9px] font-bold uppercase tracking-widest text-faint sm:inline">
                Railway Maintenance Optimization
              </span>
            </div>
          </Link>
        </div>

        {/* Center: Stage Pill Navigation */}
        <nav className="hidden lg:flex items-center gap-1 rounded-full border border-line bg-surface/70 p-1 shadow-sm backdrop-blur-sm">
          {STAGES.map((s) => {
            const active = location.pathname.startsWith(s.to)
            return (
              <Link
                key={s.to}
                to={s.to}
                className={`rounded-full px-3.5 py-1.5 text-xs font-semibold transition-all ${
                  active
                    ? 'bg-slate-900 text-white shadow-md dark:bg-white dark:text-slate-900'
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

