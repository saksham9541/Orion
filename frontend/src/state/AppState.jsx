import { createContext, useCallback, useContext, useMemo, useState } from 'react'

export const ROLES = [
  { id: 'admin', label: 'Super Admin', short: 'Admin' },
  { id: 'engineering', label: 'Engineering', short: 'Eng' },
  { id: 'snt', label: 'S&T', short: 'S&T' },
  { id: 'trd', label: 'TRD', short: 'TRD' },
  { id: 'technician', label: 'Technician', short: 'Tech' },
]

export const roleById = Object.fromEntries(ROLES.map((r) => [r.id, r]))

/** Map frontend role IDs to backend login emails */
const ROLE_EMAILS = {
  admin: 'admin@railopt.gov.in',
  engineering: 'eng@railopt.gov.in',
  snt: 'snt@railopt.gov.in',
  trd: 'trd@railopt.gov.in',
  technician: 'tech@railopt.gov.in',
}

const AppStateContext = createContext(null)

function loadSavedUser() {
  try {
    const sessionSaved = sessionStorage.getItem('railopt_user')
    if (sessionSaved) return JSON.parse(sessionSaved)
    return null
  } catch {
    return null
  }
}

export function getStoredToken() {
  return sessionStorage.getItem('railopt_token') || null
}

export function setStoredToken(token) {
  if (token) {
    sessionStorage.setItem('railopt_token', token)
  } else {
    sessionStorage.removeItem('railopt_token')
  }
  // Clear localStorage to prevent cross-tab contamination
  localStorage.removeItem('railopt_token')
}

export function getStoredEmail() {
  return sessionStorage.getItem('railopt_email') || null
}

export function AppStateProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(loadSavedUser)
  const [approvals, setApprovals] = useState({})
  const [planDecision, setPlanDecision] = useState(null)
  const [optimised, setOptimised] = useState(true)

  const approveBlock = useCallback((blockId) => {
    setApprovals((prev) => ({ ...prev, [blockId]: true }))
  }, [])

  const approvedCount = useMemo(() => Object.keys(approvals).length, [approvals])

  const login = useCallback(async (roleId) => {
    const user = roleById[roleId]
    if (!user) return

    // Save strictly to sessionStorage for complete tab isolation
    sessionStorage.setItem('railopt_user', JSON.stringify(user))

    // Clear any legacy localStorage to avoid cross-tab leakage
    localStorage.removeItem('railopt_user')
    localStorage.removeItem('railopt_token')
    localStorage.removeItem('railopt_email')

    // Get a real JWT from the backend
    const email = ROLE_EMAILS[roleId] || 'admin@railopt.gov.in'
    sessionStorage.setItem('railopt_email', email)

    try {
      const res = await fetch('http://localhost:8000/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password: 'password123' }),
      })
      if (res.ok) {
        const data = await res.json()
        sessionStorage.setItem('railopt_token', data.access_token)
      }
    } catch {
      // Backend might not be running yet — that's OK, api.js will retry
    }

    setCurrentUser(user)
  }, [])

  const logout = useCallback(() => {
    sessionStorage.removeItem('railopt_user')
    sessionStorage.removeItem('railopt_token')
    sessionStorage.removeItem('railopt_email')
    localStorage.removeItem('railopt_user')
    localStorage.removeItem('railopt_token')
    localStorage.removeItem('railopt_email')
    setCurrentUser(null)
  }, [])

  const value = useMemo(
    () => ({
      currentUser,
      login,
      logout,
      role: currentUser || { id: 'admin', label: 'Super Admin', focus: 'Operations', panels: ['kpis', 'conflicts', 'twin'] },
      approvals,
      approvedCount,
      approveBlock,
      planDecision,
      setPlanDecision,
      optimised,
      setOptimised,
    }),
    [currentUser, login, logout, approvals, approvedCount, approveBlock, planDecision, optimised]
  )

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>
}

export function useAppState() {
  const ctx = useContext(AppStateContext)
  if (!ctx) throw new Error('useAppState must be used inside AppStateProvider')
  return ctx
}
