import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAppState } from '@/state/AppState'
import ThemeToggle from '@/components/common/ThemeToggle'

export default function Login() {
  const navigate = useNavigate()
  const { login } = useAppState()
  const [userId, setUserId] = useState('')
  const [password, setPassword] = useState('')

  const [isLoading, setIsLoading] = useState(false)

  const handleSignIn = async (event) => {
    event.preventDefault()
    setIsLoading(true)
    const id = userId.toLowerCase().trim()
    let role = 'admin'
    if (id.includes('engineering') || id.includes('eng')) role = 'engineering'
    else if (id.includes('snt') || id.includes('s&t')) role = 'snt'
    else if (id.includes('trd')) role = 'trd'
    else if (id.includes('tech')) role = 'technician'

    await login(role)
    setIsLoading(false)
    navigate(role === 'admin' ? '/admin' : `/${role}`)
  }

  const handleQuickLogin = async (role) => {
    setIsLoading(true)
    await login(role)
    setIsLoading(false)
    navigate(role === 'admin' ? '/admin' : `/${role}`)
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-base p-4 font-sans text-ink">
      <div className="absolute right-4 top-4">
        <ThemeToggle />
      </div>
      <div className="w-full max-w-md rounded-2xl border border-line bg-surface p-8 shadow-xl">
        <div className="text-center mb-6">
          <h1 className="text-2xl tracking-tight font-bold uppercase text-ink">RAILOPT</h1>
          <p className="mt-1 text-xs uppercase tracking-wider text-muted">Railway Maintenance Management Portal</p>
        </div>

        {/* Quick Demo Sign In Buttons */}
        <div className="mb-6 rounded-xl border border-line bg-raised/50 p-3.5">
          <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-faint text-center">
            Instant Test Login (Click to open role)
          </p>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => handleQuickLogin('snt')}
              className="flex items-center justify-center gap-1.5 rounded-lg border border-line bg-surface py-2 text-xs font-bold text-ink hover:border-info hover:text-info transition-colors shadow-sm"
            >
              📡 S&T Dept
            </button>
            <button
              type="button"
              onClick={() => handleQuickLogin('engineering')}
              className="flex items-center justify-center gap-1.5 rounded-lg border border-line bg-surface py-2 text-xs font-bold text-ink hover:border-info hover:text-info transition-colors shadow-sm"
            >
              🔧 Engineering
            </button>
            <button
              type="button"
              onClick={() => handleQuickLogin('trd')}
              className="flex items-center justify-center gap-1.5 rounded-lg border border-line bg-surface py-2 text-xs font-bold text-ink hover:border-info hover:text-info transition-colors shadow-sm"
            >
              ⚡ TRD Dept
            </button>
            <button
              type="button"
              onClick={() => handleQuickLogin('admin')}
              className="flex items-center justify-center gap-1.5 rounded-lg border border-line bg-surface py-2 text-xs font-bold text-ink hover:border-info hover:text-info transition-colors shadow-sm"
            >
              🛡️ Super Admin
            </button>
          </div>
        </div>

        <div className="relative my-4 flex items-center justify-center">
          <div className="w-full border-t border-line"></div>
          <span className="absolute bg-surface px-2 text-[10px] uppercase font-bold text-faint">Or sign in with ID</span>
        </div>

        <form className="space-y-4" onSubmit={handleSignIn}>
          <div>
            <label htmlFor="login-user" className="mb-1 block text-xs font-bold uppercase tracking-wider text-faint">User ID / Email</label>
            <input
              id="login-user"
              type="text"
              placeholder="e.g. snt or eng@railopt.gov.in"
              autoComplete="username"
              className="field w-full rounded-lg border border-line bg-raised px-3 py-2 text-sm text-ink outline-none focus:border-info"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="login-password" className="mb-1 block text-xs font-bold uppercase tracking-wider text-faint">Password</label>
            <input
              id="login-password"
              type="password"
              autoComplete="current-password"
              placeholder="password123"
              className="field w-full rounded-lg border border-line bg-raised px-3 py-2 text-sm text-ink outline-none focus:border-info"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <button type="submit" disabled={isLoading} className="btn-primary mt-4 w-full py-2.5 text-xs font-bold uppercase tracking-wider disabled:opacity-50">
            {isLoading ? 'SIGNING IN...' : 'SIGN IN'}
          </button>
        </form>

        <p className="mt-6 text-center text-[10px] uppercase tracking-wider text-faint">
          Indian Railways • Authorized Personnel Only
        </p>
      </div>
    </div>
  )
}
