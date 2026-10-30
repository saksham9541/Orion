import React, { createContext, useContext, useEffect, useState, useRef, useCallback } from 'react'
import { getStoredToken, useAppState } from '@/state/AppState'
import {
  fetchDashboardCounts,
  fetchPendingAckTasks,
  acknowledgeTask as apiAcknowledge,
  declineTask as apiDecline,
  getEventsStreamUrl,
  ensureToken,
} from '@/api'

const LiveSyncContext = createContext(null)

export function formatIstClock(date = new Date()) {
  try {
    return new Intl.DateTimeFormat('en-IN', {
      timeZone: 'Asia/Kolkata',
      hour: 'numeric',
      minute: '2-digit',
      second: '2-digit',
      hour12: true,
    }).format(date) + ' IST'
  } catch (e) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true }) + ' IST'
  }
}

export function useLiveSync() {
  const context = useContext(LiveSyncContext)
  if (!context) {
    throw new Error('useLiveSync must be used within a LiveSyncProvider')
  }
  return context
}

export function LiveSyncProvider({ children }) {
  const { currentUser } = useAppState()
  const [connectionStatus, setConnectionStatus] = useState('reconnecting') // 'live' | 'reconnecting' | 'polling'
  const [lastUpdated, setLastUpdated] = useState(() => formatIstClock())
  const [counts, setCounts] = useState({
    total: 0,
    pending: 0,
    active_scheduled: 0,
    resolved: 0,
    pipeline_stages: { intake: 0, planning: 0, execution: 0, resolution: 0 },
  })
  const [pendingAckTasks, setPendingAckTasks] = useState([])
  const [recentEvents, setRecentEvents] = useState([])

  const eventSourceRef = useRef(null)
  const pollTimerRef = useRef(null)
  const isMountedRef = useRef(true)

  // Fetch counts from Part A4 source of truth endpoint
  const refreshCounts = useCallback(async (deptOverride) => {
    try {
      const dept = deptOverride || (currentUser?.department ? currentUser.department.toUpperCase() : undefined)
      const res = await fetchDashboardCounts(dept)
      if (res?.data && isMountedRef.current) {
        setCounts(res.data)
        setLastUpdated(formatIstClock())
      }
      return res?.data
    } catch (err) {
      console.warn('LiveSync: Failed to refresh dashboard counts:', err)
      return null
    }
  }, [currentUser])

  // Fetch tasks awaiting acknowledgement (Part B2)
  const refreshPendingAck = useCallback(async () => {
    try {
      const res = await fetchPendingAckTasks()
      const list = Array.isArray(res?.data) ? res.data : []
      if (isMountedRef.current) {
        setPendingAckTasks(list)
        setLastUpdated(formatIstClock())
      }
      return list
    } catch (err) {
      console.warn('LiveSync: Failed to refresh pending tasks:', err)
      return []
    }
  }, [])

  // Acknowledge a pending task (Part B2)
  const acknowledge = useCallback(async (taskId) => {
    try {
      const res = await apiAcknowledge(taskId)
      // Optimistically remove from pendingAckTasks
      setPendingAckTasks((prev) => prev.filter((t) => (t.task_id || t.id) !== taskId))
      await Promise.all([refreshCounts(), refreshPendingAck()])
      return { success: true, data: res.data }
    } catch (err) {
      const status = err.response?.status
      const detail = err.response?.data?.detail || err.message || 'Acknowledgement failed'
      if (status === 409) {
        // Someone else acknowledged it first! Refresh list immediately
        await Promise.all([refreshCounts(), refreshPendingAck()])
      }
      return { success: false, error: detail, status }
    }
  }, [refreshCounts, refreshPendingAck])

  // Decline a pending task (Part B2)
  const decline = useCallback(async (taskId, reason) => {
    try {
      const res = await apiDecline(taskId, reason)
      // Optimistically remove from pendingAckTasks
      setPendingAckTasks((prev) => prev.filter((t) => (t.task_id || t.id) !== taskId))
      await Promise.all([refreshCounts(), refreshPendingAck()])
      return { success: true, data: res.data }
    } catch (err) {
      const status = err.response?.status
      const detail = err.response?.data?.detail || err.message || 'Decline failed'
      await Promise.all([refreshCounts(), refreshPendingAck()])
      return { success: false, error: detail, status }
    }
  }, [refreshCounts, refreshPendingAck])

  // Handle incoming SSE event
  const handleIncomingEvent = useCallback((eventObj) => {
    if (!isMountedRef.current || !eventObj) return

    setRecentEvents((prev) => [eventObj, ...prev.slice(0, 19)])
    setLastUpdated(formatIstClock())

    // 1. Refetch counts from A4 endpoint on any lifecycle event
    refreshCounts()

    // 2. Refresh pending ack tasks on task-related events
    if (
      ['TASK_AWAITING_ACK', 'TASK_CREATED', 'TASK_ACKNOWLEDGED', 'TASK_DECLINED', 'NOTIFICATION_RESOLVED'].includes(
        eventObj.type || eventObj.event_type
      )
    ) {
      refreshPendingAck()
    }

    // 3. Dispatch window events for legacy listeners and multi-dashboard sync
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('railopt:live-event', { detail: eventObj }))

      const eventType = eventObj.type || eventObj.event_type
      if (eventType === 'TASK_CREATED' || eventType === 'TASK_ACKNOWLEDGED') {
        window.dispatchEvent(new CustomEvent('railopt:task-created', { detail: eventObj }))
      } else if (eventType === 'TASK_UPDATED' || eventType === 'EXECUTION_STARTED' || eventType === 'WINDOW_APPROVED') {
        window.dispatchEvent(
          new CustomEvent('railopt:task-updated', {
            detail: { task_id: eventObj.task_id, status: eventObj.status, ...eventObj },
          })
        )
      } else if (eventType === 'NOTIFICATION_RESOLVED' || eventType === 'TASK_DECLINED') {
        window.dispatchEvent(
          new CustomEvent('railopt:notification-resolved', {
            detail: { issue_id: eventObj.task_id || eventObj.issue_id },
          })
        )
      }
    }
  }, [refreshCounts, refreshPendingAck])

  // Establish SSE stream and fallback polling
  useEffect(() => {
    isMountedRef.current = true
    const token = getStoredToken()

    // Initial load
    refreshCounts()
    refreshPendingAck()

    if (!token) {
      setConnectionStatus('polling')
      return
    }

    let isClosedExplicitly = false

    const startFallbackPolling = () => {
      if (pollTimerRef.current) return
      setConnectionStatus('polling')
      pollTimerRef.current = setInterval(() => {
        refreshCounts()
        refreshPendingAck()
      }, 10000) // Fallback 10s poll
    }

    const stopFallbackPolling = () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current)
        pollTimerRef.current = null
      }
    }

    const connectSSE = async (forceRefresh = false) => {
      if (isClosedExplicitly) return

      // Use ensureToken() to validate expiration and obtain a guaranteed fresh token
      const activeToken = await ensureToken(forceRefresh)
      if (!activeToken) {
        startFallbackPolling()
        return
      }

      const streamUrl = getEventsStreamUrl(activeToken)
      let es = null
      try {
        es = new EventSource(streamUrl)
        eventSourceRef.current = es
      } catch (err) {
        console.warn('SSE: EventSource instantiation failed, starting polling:', err)
        startFallbackPolling()
        return
      }

      es.onopen = () => {
        if (!isMountedRef.current) return
        setConnectionStatus('live')
        stopFallbackPolling()
        setLastUpdated(formatIstClock())
      }

      // Generic message handler
      es.onmessage = (event) => {
        try {
          if (!event.data) return
          const parsed = JSON.parse(event.data)
          handleIncomingEvent(parsed)
        } catch (e) {
          // ignore keepalive comments
        }
      }

      // Specific named event listeners
      const knownEvents = [
        'connected',
        'TASK_CREATED',
        'TASK_UPDATED',
        'TASK_AWAITING_ACK',
        'TASK_ACKNOWLEDGED',
        'TASK_DECLINED',
        'NOTIFICATION_RESOLVED',
        'WINDOW_APPROVED',
        'EXECUTION_STARTED',
        'SYNC_COMPLETED',
      ]

      knownEvents.forEach((evtType) => {
        es.addEventListener(evtType, (event) => {
          try {
            if (!event.data) return
            const parsed = JSON.parse(event.data)
            handleIncomingEvent({ ...parsed, type: evtType })
          } catch (e) {
            console.error('Failed to parse SSE event data', e)
          }
        })
      })

      es.onerror = () => {
        if (!isMountedRef.current) return
        setConnectionStatus('reconnecting')
        startFallbackPolling()

        // If closed by browser (e.g. 401 token expiry or server restart),
        // force a fresh token fetch before reconnecting!
        if (es.readyState === EventSource.CLOSED) {
          es.close()
          eventSourceRef.current = null
          setTimeout(() => {
            if (isMountedRef.current && !isClosedExplicitly) {
              connectSSE(true) // Force fresh token!
            }
          }, 2500)
        }
      }
    }

    connectSSE()

    return () => {
      isMountedRef.current = false
      isClosedExplicitly = true
      stopFallbackPolling()
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
    }
  }, [currentUser, refreshCounts, refreshPendingAck, handleIncomingEvent])

  const value = {
    connectionStatus,
    lastUpdated,
    counts,
    pendingAckTasks,
    recentEvents,
    refreshCounts,
    refreshPendingAck,
    acknowledge,
    decline,
  }

  return <LiveSyncContext.Provider value={value}>{children}</LiveSyncContext.Provider>
}
