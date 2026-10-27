import { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react'
import { getStoredToken, useAppState } from '@/state/AppState'

const NotificationContext = createContext(null)

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
      const res = await fetch('http://localhost:8000/api/notifications/unread-count', {
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
      const res = await fetch('http://localhost:8000/api/notifications?limit=30', {
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
      const res = await fetch(`http://localhost:8000/api/notifications/${id}/read`, {
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
      const res = await fetch(`http://localhost:8000/api/notifications/${id}/acknowledge`, {
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

      const wsUrl = `ws://localhost:8000/ws/notifications?token=${currentToken}`
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
            // Immediately interrupt screen with Real-time Alert Popup!
            setActivePopup(notif)
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
