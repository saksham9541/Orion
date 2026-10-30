import React from 'react'
import { Radio, RefreshCw } from 'lucide-react'
import { useLiveSync } from '@/state/LiveSyncStore'

export default function LiveIndicator({ className = '' }) {
  const { connectionStatus, lastUpdated, refreshCounts } = useLiveSync()

  if (connectionStatus === 'live') {
    return (
      <div
        className={`flex items-center gap-1.5 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-[11px] font-mono font-medium text-emerald-600 dark:text-emerald-400 shadow-sm ${className}`}
        title={`Live sync active · Last updated at ${lastUpdated}`}
      >
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
        </span>
        <span className="font-bold tracking-wider">LIVE</span>
        <span className="hidden sm:inline text-[10px] opacity-80">· {lastUpdated.replace(' IST', '')}</span>
      </div>
    )
  }

  if (connectionStatus === 'reconnecting') {
    return (
      <div
        className={`flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-[11px] font-mono font-medium text-amber-600 dark:text-amber-400 shadow-sm animate-pulse ${className}`}
        title="Event stream dropped. Reconnecting with automatic replay buffer..."
      >
        <RefreshCw size={11} className="animate-spin text-amber-500" />
        <span className="font-bold tracking-wider">RECONNECTING...</span>
      </div>
    )
  }

  // Polling fallback state
  return (
    <div
      onClick={() => refreshCounts()}
      className={`flex cursor-pointer items-center gap-1.5 rounded-full border border-sky-500/20 bg-sky-500/10 px-2.5 py-1 text-[11px] font-mono font-medium text-sky-600 dark:text-sky-400 shadow-sm hover:bg-sky-500/20 transition-colors ${className}`}
      title={`Fallback polling active (every 10s) · Last updated at ${lastUpdated}. Click to refresh.`}
    >
      <Radio size={12} className="text-sky-500" />
      <span className="font-bold tracking-wider">POLLING (10s)</span>
      <span className="hidden sm:inline text-[10px] opacity-80">· {lastUpdated.replace(' IST', '')}</span>
    </div>
  )
}
