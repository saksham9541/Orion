import React from 'react'
import { AlertCircle } from 'lucide-react'

export default function DemoDataBadge({ label = "DEMO DATA", tooltip = "Displaying local prototype data. Connect to backend to load live operational database." }) {
  return (
    <span
      title={tooltip}
      className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-medium bg-amber-500/10 text-amber-500 border border-amber-500/30 uppercase tracking-wider select-none shadow-sm"
    >
      <AlertCircle size={12} className="stroke-[2.5]" />
      <span>{label}</span>
    </span>
  )
}
