import { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react'
import { getStoredToken, getStoredEmail, useAppState } from '@/state/AppState'
import { API_BASE, getWsNotificationsUrl } from '@/api'

const NotificationContext = createContext(null)

const getBackendBase = () => `${API_BASE}/api`

const getWsUrl = (token) => getWsNotificationsUrl(token)

export function useNotifications() {
  const ctx = useContext(NotificationContext)
  if (!ctx) {
    throw new Error('useNotifications must be used within a NotificationProvider')
  }
  return ctx
}

export function NotificationProvider({ children }) {
  const { currentUser } = useAppState()
  const [notifications, setNotifications] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [activePopup, setActivePopup] = useState(null)
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const backoffRef = useRef(1000)

  const fetchUnreadCount = useCallback(async () => {
    const token = getStoredToken()
    if (!token) return
    try {
      const res = await fetch(`${getBackendBase()}/notifications/unread-count`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        const data = await res.json()
        setUnreadCount(data.unread_count)
      }
    } catch (e) {
      // Backend might be offline
    }
  }, [])

  const fetchNotifications = useCallback(async () => {
    const token = getStoredToken()
    if (!token) return
    try {
      const res = await fetch(`${getBackendBase()}/notifications?limit=30`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        const data = await res.json()
        setNotifications(data)
      }
    } catch (e) {
      // Backend might be offline
    }
  }, [])

  const markAsRead = useCallback(async (id) => {
    const token = getStoredToken()
    if (!token) return
    try {
      const res = await fetch(`${getBackendBase()}/notifications/${id}/read`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        const updated = await res.json()
        setNotifications((prev) =>
          prev.map((n) => (n.id === id ? { ...n, read_at: updated.read_at } : n))
        )
        setUnreadCount((prev) => Math.max(0, prev - 1))
      }
    } catch (e) {
      console.error('Failed to mark notification as read:', e)
    }
  }, [])

  const acknowledge = useCallback(async (id) => {
    const token = getStoredToken()
    if (!token) return
    try {
      const res = await fetch(`${getBackendBase()}/notifications/${id}/acknowledge`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        const updated = await res.json()
        setNotifications((prev) =>
          prev.map((n) => (n.id === id ? { ...n, acknowledged_at: updated.acknowledged_at, read_at: updated.read_at } : n))
        )
        setUnreadCount((prev) => Math.max(0, prev - 1))
        if (activePopup?.id === id) {
          setActivePopup(null)
        }
      }
    } catch (e) {
      console.error('Failed to acknowledge notification:', e)
    }
  }, [activePopup])

  const dismissPopup = useCallback(() => {
    setActivePopup(null)
  }, [])

  // Establish and manage WebSocket connection with auto-reconnect
  useEffect(() => {
    const token = getStoredToken()
    if (!token || !currentUser) {
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      setIsConnected(false)
      return
    }

    let isUnmounted = false

    function connect() {
      if (isUnmounted) return
      const currentToken = getStoredToken()
      if (!currentToken) return

      const wsUrl = getWsUrl(currentToken)
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        if (isUnmounted) return
        setIsConnected(true)
        backoffRef.current = 1000 // Reset backoff on successful connect
        // Fetch fresh state upon connecting
        fetchUnreadCount()
        fetchNotifications()
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'ISSUE_RAISED' && data.notification) {
            const notif = data.notification
            setNotifications((prev) => [notif, ...prev])
            setUnreadCount((prev) => prev + 1)

            // Only display popup notification to other authorized users, never to the reporter who raised it
            const currentEmail = (getStoredEmail() || currentUser?.email || '').trim().toLowerCase()
            const creatorEmail = (notif.created_by || '').trim().toLowerCase()
            const isReporter = creatorEmail && currentEmail && creatorEmail === currentEmail

            if (!isReporter) {
              setActivePopup(notif)
            }

            if (typeof window !== 'undefined') {
              window.dispatchEvent(new CustomEvent('railopt:task-created', { detail: notif }))
            }
          } else if (data.type === 'TASK_UPDATED') {
            if (typeof window !== 'undefined') {
              window.dispatchEvent(new CustomEvent('railopt:task-updated', { detail: data }))
            }
          }
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err)
        }
      }

      ws.onclose = () => {
        if (isUnmounted) return
        setIsConnected(false)
        wsRef.current = null
        // Exponential backoff reconnect
        const nextDelay = Math.min(backoffRef.current * 2, 16000)
        backoffRef.current = nextDelay
        reconnectTimeoutRef.current = setTimeout(connect, nextDelay)
      }

      ws.onerror = () => {
        ws.close()
      }
    }

    connect()
    fetchUnreadCount()
    fetchNotifications()

    return () => {
      isUnmounted = true
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [currentUser, fetchUnreadCount, fetchNotifications])

  // Listen for live SSE resolution events to clear notifications in real-time
  useEffect(() => {
    const handleResolved = (e) => {
      const issueId = e.detail?.issue_id || e.detail?.task_id
      if (issueId) {
        setNotifications((prev) => prev.filter((n) => n.issue_id !== issueId && n.id !== issueId))
        fetchUnreadCount()
      }
    }

    const handleLiveEvent = (e) => {
      const evt = e.detail
      if (!evt) return
      const evtType = evt.type || evt.event_type
      if (['NOTIFICATION_RESOLVED', 'TASK_ACKNOWLEDGED', 'TASK_DECLINED'].includes(evtType)) {
        const targetId = evt.task_id || evt.payload?.task_id || evt.issue_id
        if (targetId) {
          setNotifications((prev) => prev.filter((n) => n.issue_id !== targetId && n.id !== targetId))
          fetchUnreadCount()
        }
      } else if (evtType === 'TASK_AWAITING_ACK' || evtType === 'TASK_CREATED') {
        fetchNotifications()
        fetchUnreadCount()
      }
    }

    window.addEventListener('railopt:notification-resolved', handleResolved)
    window.addEventListener('railopt:live-event', handleLiveEvent)
    return () => {
      window.removeEventListener('railopt:notification-resolved', handleResolved)
      window.removeEventListener('railopt:live-event', handleLiveEvent)
    }
  }, [fetchNotifications, fetchUnreadCount])

  return (
    <NotificationContext.Provider
      value={{
        notifications,
        unreadCount,
        activePopup,
        isConnected,
        markAsRead,
        acknowledge,
        dismissPopup,
        fetchNotifications,
        fetchUnreadCount,
      }}
    >
      {children}
    </NotificationContext.Provider>
  )
}
