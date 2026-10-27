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

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-base p-4 font-sans text-ink">
      <div className="absolute right-4 top-4">
        <ThemeToggle />
      </div>
      <div className="w-full max-w-md rounded border border-line bg-surface p-8 shadow-sm">
        <div className="text-center mb-8">
          <h1 className="text-2xl tracking-tight font-medium uppercase">RAILOPT</h1>
          <p className="mt-1 text-sm uppercase tracking-wide text-muted">Railway Maintenance Management Portal</p>
        </div>

        <form className="space-y-4" onSubmit={handleSignIn}>
          <div>
            <label htmlFor="login-user" className="mb-1 block text-sm font-medium">User ID / Email</label>
            <input
              id="login-user"
              type="text"
              autoComplete="username"
              className="field"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="login-password" className="mb-1 block text-sm font-medium">Password</label>
            <input
              id="login-password"
              type="password"
              autoComplete="current-password"
              className="field"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <button type="submit" disabled={isLoading} className="btn-primary mt-4 w-full py-2.5 text-sm disabled:opacity-50">
            {isLoading ? 'SIGNING IN...' : 'SIGN IN'}
          </button>
        </form>

        <p className="mt-6 text-center text-xs uppercase tracking-wider text-faint">
          Authorized personnel only
        </p>
      </div>
    </div>
  )
}
