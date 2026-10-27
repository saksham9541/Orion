import { useNavigate } from 'react-router-dom'
import { ArrowLeft, LogOut, User } from 'lucide-react'
import { useAppState } from '@/state/AppState'
import NotificationBell from '@/components/common/NotificationBell'

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
    <header className="sticky top-0 z-30 border-b border-line bg-white text-ink">
      <div className="flex items-center justify-between px-6 py-3">
        <div className="flex items-center gap-3">
          <button
            onClick={handleBack}
            className="flex items-center gap-1.5 px-2.5 h-8 rounded border border-line bg-base text-muted hover:text-ink hover:bg-[#f8fafc] transition-colors text-xs font-semibold shadow-sm"
            aria-label="Go back"
            title="Go back"
          >
            <ArrowLeft size={15} />
            <span className="hidden sm:inline">Back</span>
          </button>
          <div>
            <h1 className="text-xl tracking-tight font-medium uppercase leading-tight">RAILOPT</h1>
            <p className="text-[11px] text-muted uppercase tracking-wide">Railway Maintenance Management Portal</p>
          </div>
        </div>

        <div className="flex items-center gap-6">
          <NotificationBell />

          <div className="h-8 w-[1px] bg-line"></div>

          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded bg-base flex items-center justify-center border border-line text-muted">
              <User size={16} />
            </div>
            <div className="hidden sm:block">
              <div className="text-sm font-medium leading-tight">
                {currentUser?.label || 'Guest'}
              </div>
              <div className="text-[11px] text-muted uppercase tracking-wider">
                {currentUser?.id === 'admin' ? 'System Administrator' : 'Department User'}
              </div>
            </div>
          </div>

          <button 
            onClick={handleLogout}
            className="flex items-center gap-2 text-sm text-muted hover:text-ink border border-line px-3 py-1.5 rounded bg-base hover:bg-[#f8fafc] transition-colors"
          >
            <LogOut size={14} />
            <span className="hidden sm:inline">Logout</span>
          </button>
        </div>
      </div>
    </header>
  )
}

