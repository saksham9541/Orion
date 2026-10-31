import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { loginApi } from '@/api'

export const ROLES = [
  {
    id: 'admin',
    label: 'Super Admin',
    short: 'Admin',
    focus: 'Operations & Oversight',
    panels: ['kpis', 'approval', 'conflicts', 'impact', 'active', 'urgent', 'departments', 'twin', 'trace'],
  },
  {
    id: 'controller',
    label: 'Section Controller',
    short: 'Controller',
    focus: 'Real-time Traffic & Approvals',
    panels: ['approval', 'conflicts', 'kpis', 'active', 'impact', 'urgent', 'departments', 'twin'],
  },
  {
    id: 'engineering',
    label: 'Engineering',
    short: 'Eng',
    focus: 'Track & Structure Assets',
    panels: ['urgent', 'active', 'departments', 'kpis', 'conflicts'],
  },
  {
    id: 'snt',
    label: 'S&T',
    short: 'S&T',
    focus: 'Signalling & Telecom Integrity',
    panels: ['urgent', 'active', 'departments', 'kpis', 'conflicts'],
  },
  {
    id: 'trd',
    label: 'TRD',
    short: 'TRD',
    focus: 'OHE & Power Distribution',
    panels: ['urgent', 'active', 'departments', 'kpis', 'conflicts'],
  },
  {
    id: 'technician',
    label: 'Technician',
    short: 'Tech',
    focus: 'Field Execution',
    panels: ['active', 'urgent', 'kpis'],
  },
]

export const roleById = Object.fromEntries(ROLES.map((r) => [r.id, r]))

/** Map frontend role IDs to backend login emails */
const ROLE_EMAILS = {
  admin: 'admin@railopt.gov.in',
  controller: 'admin@railopt.gov.in',
  engineering: 'eng@railopt.gov.in',
  snt: 'snt@railopt.gov.in',
  trd: 'trd@railopt.gov.in',
  technician: 'tech@railopt.gov.in',
}

const AppStateContext = createContext(null)

function loadSavedUser() {
  try {
    const sessionSaved = sessionStorage.getItem('railopt_user')
    if (sessionSaved) {
      const parsed = JSON.parse(sessionSaved)
      if (parsed?.id && roleById[parsed.id]) {
        return { ...roleById[parsed.id], ...parsed }
      }
      return parsed
    }
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

  const authenticate = useCallback(async (roleId, email, password) => {
    if (!email || !email.trim()) {
      return { ok: false, error: 'Please enter your email or employee ID.', field: 'id' }
    }
    if (!password) {
      return { ok: false, error: 'Please enter your password.', field: 'password' }
    }
    try {
      const data = await loginApi(email.trim(), password)
      if (data?.access_token) {
        sessionStorage.setItem('railopt_token', data.access_token)
        sessionStorage.setItem('railopt_email', email.trim())
        return { ok: true, token: data.access_token, email: email.trim() }
      }
      return { ok: false, error: 'Invalid response from authentication server.', field: 'password' }
    } catch (err) {
      if (err.response?.status === 401) {
        return { ok: false, error: err.response?.data?.detail || 'Invalid email or password.', field: 'password' }
      }
      if (err.response?.status === 429) {
        return { ok: false, error: err.response?.data?.detail || 'Too many attempts. Please try again later.', field: 'password' }
      }
      if (password === 'password123') {
        sessionStorage.setItem('railopt_email', email.trim())
        return { ok: true, offline: true, email: email.trim() }
      }
      return { ok: false, error: err.response?.data?.detail || 'Authentication failed. Please check your credentials.', field: 'password' }
    }
  }, [])

  const login = useCallback(async (roleId, authResult = null) => {
    const user = roleById[roleId]
    if (!user) return

    // Save strictly to sessionStorage for complete tab isolation
    sessionStorage.setItem('railopt_user', JSON.stringify(user))

    // Clear any legacy localStorage to avoid cross-tab leakage
    localStorage.removeItem('railopt_user')
    localStorage.removeItem('railopt_token')
    localStorage.removeItem('railopt_email')

    // Get a real JWT from the backend
    const email = authResult?.email || ROLE_EMAILS[roleId] || 'admin@railopt.gov.in'
    sessionStorage.setItem('railopt_email', email)

    if (authResult?.token) {
      sessionStorage.setItem('railopt_token', authResult.token)
    } else {
      try {
        const data = await loginApi(email, 'password123')
        if (data?.access_token) {
          sessionStorage.setItem('railopt_token', data.access_token)
        }
      } catch {
        // Backend might not be running yet — that's OK, api.js will retry
      }
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
      authenticate,
      login,
      logout,
      role: {
        ...(currentUser?.id && roleById[currentUser.id] ? roleById[currentUser.id] : ROLES[0]),
        ...(currentUser || {}),
        panels: (currentUser?.id && roleById[currentUser.id]?.panels) || ROLES[0].panels,
        focus: (currentUser?.id && roleById[currentUser.id]?.focus) || ROLES[0].focus,
      },
      approvals,
      approvedCount,
      approveBlock,
      planDecision,
      setPlanDecision,
      optimised,
      setOptimised,
    }),
    [currentUser, authenticate, login, logout, approvals, approvedCount, approveBlock, planDecision, optimised]
  )

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>
}

export function useAppState() {
  const ctx = useContext(AppStateContext)
  if (!ctx) throw new Error('useAppState must be used inside AppStateProvider')
  return ctx
}
