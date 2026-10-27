import { useState, useEffect, useMemo } from 'react'
import { Navigate } from 'react-router-dom'
import PortalLayout from '@/components/app/PortalLayout'
import { useAppState } from '@/state/AppState'
import IndiaRailwayMap from '@/components/network/IndiaRailwayMap'
import { fetchLiveTrains } from '@/api'
import { DEMO_ISSUES } from '@/data/issues'

import { updateTaskStatus } from '@/api'

const uiToBackendStatus = {
  'Acknowledged': 'ESCALATED',
  'Action Started': 'SCHEDULED',
  'In Progress': 'IN_PROGRESS',
  'Resolved': 'COMPLETED'
}

export default function DepartmentDashboard({ deptId, title, taskName, issueData }) {
  const { currentUser } = useAppState()
  const [issueStatus, setIssueStatus] = useState(issueData?.status || 'New')
  const [liveTrains, setLiveTrains] = useState([])

  useEffect(() => {
    fetchLiveTrains().then(res => setLiveTrains(res.data)).catch(console.error)
  }, [])
  
  const handleStatusChange = async (newStatus) => {
    setIssueStatus(newStatus)
    try {
      const backendStatus = uiToBackendStatus[newStatus]
      if (backendStatus && issueData.id) {
        await updateTaskStatus(issueData.id, { status: backendStatus })
      }
    } catch (e) {
      console.error(e)
    }
  }

  const deptIssues = useMemo(() => {
    const d = deptId === 'snt' ? 'S&T' : deptId.toUpperCase()
    return DEMO_ISSUES.filter(i => i.department === d)
  }, [deptId])
  
  if (currentUser?.id !== deptId && currentUser?.id !== 'admin') {
    return <Navigate to="/restricted" replace />
  }

  const getSeriousnessColor = (level) => {
    if (!level) return 'tag-neutral'
    switch(level.toLowerCase()) {
      case 'critical': return 'sev-critical'
      case 'high': return 'sev-high'
      case 'medium': return 'sev-medium'
      case 'low': return 'sev-low'
      default: return 'tag-neutral'
    }
  }

  const getCauseColor = (level) => {
    switch(level) {
      case 'CONFIRMED': return 'bg-danger/10 text-danger border-danger/30'
      case 'LIKELY': return 'bg-high/10 text-high border-high/30'
      case 'POSSIBLE': return 'bg-warn/10 text-warn border-warn/30'
      default: return 'bg-raised text-muted border-line'
    }
  }

  return (
    <PortalLayout role={deptId}>
      <div className="mb-6 flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink uppercase flex items-center gap-2">
            <span className="w-2.5 h-2.5 bg-info rounded-full inline-block"></span>
            {title}
          </h1>
          <p className="text-[11px] text-muted uppercase tracking-widest mt-1">Department Intelligence Portal</p>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-surface p-4 border border-line rounded shadow-sm">
          <p className="text-[10px] font-bold text-faint uppercase tracking-wider mb-2">My Tasks</p>
          <p className="text-2xl font-light tracking-tight text-ink">24</p>
        </div>
        <div className="bg-surface p-4 border border-line rounded shadow-sm">
          <p className="text-[10px] font-bold text-faint uppercase tracking-wider mb-2">Active Alerts</p>
          <p className="text-2xl font-light tracking-tight text-high">3</p>
        </div>
        <div className="bg-surface p-4 border border-line rounded shadow-sm">
          <p className="text-[10px] font-bold text-faint uppercase tracking-wider mb-2">High Priority Issues</p>
          <p className="text-2xl font-light tracking-tight text-danger">1</p>
        </div>
        <div className="bg-surface p-4 border border-line rounded shadow-sm">
          <p className="text-[10px] font-bold text-faint uppercase tracking-wider mb-2">Maintenance Blocks</p>
          <p className="text-2xl font-light tracking-tight text-info">2</p>
        </div>
      </div>

      <div className="mb-6 h-96 w-full overflow-hidden rounded border border-line bg-surface shadow-sm relative z-0">
        <IndiaRailwayMap
          issues={deptIssues}
          selectedIssueId={null}
          onSelectIssue={() => {}}
          showHeatmap={true}
          trains={liveTrains}
        />
      </div>

      {/* DEPARTMENT ISSUE INTELLIGENCE SECTION */}
      <div className="bg-surface border border-line rounded shadow-sm overflow-hidden mb-6 flex flex-col">
        <div className="bg-bar text-onbar px-5 py-4 flex justify-between items-center">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wider flex items-center gap-2">
              <span className="w-1.5 h-1.5 bg-barmuted rounded-full inline-block"></span>
              Active Issue Intelligence Analysis
            </h2>
            <span className="text-[10px] text-barmuted uppercase tracking-widest mt-1 block">Demonstration Data</span>
          </div>
          <span className="px-3 py-1.5 bg-onbar/10 rounded border border-onbar/20 text-[10px] font-bold uppercase tracking-wider">Status: {issueStatus}</span>
        </div>
        
        <div className="p-6">
          <div className="grid grid-cols-3 gap-x-8 gap-y-10">
            
            {/* 1. WHAT HAPPENED? */}
            <div className="col-span-2">
              <h3 className="text-xs font-bold text-muted uppercase tracking-wider mb-2">1. WHAT HAPPENED?</h3>
              <p className="text-base font-medium">{issueData.what}</p>
            </div>

            {/* 4. HOW SERIOUS IS IT? */}
            <div className="col-span-1">
              <h3 className="text-xs font-bold text-muted uppercase tracking-wider mb-2">4. HOW SERIOUS IS IT?</h3>
              <span className={`inline-block rounded-full px-4 py-1.5 text-sm font-bold uppercase tracking-wide ${getSeriousnessColor(issueData.seriousness)}`}>
                {issueData.seriousness}
              </span>
            </div>

            {/* 2. WHY DID IT HAPPEN? (ROOT CAUSE) */}
            <div className="col-span-2">
              <h3 className="text-xs font-bold text-muted uppercase tracking-wider mb-3">2. WHY DID IT HAPPEN? (Possible Causes)</h3>
              <div className="space-y-2">
                {(issueData.causes || []).map((cause, i) => (
                  <div key={i} className={`p-3 rounded border text-sm flex gap-3 ${getCauseColor(cause.level)}`}>
                    <span className="font-bold uppercase tracking-wider text-xs w-24 shrink-0">{cause.level}</span>
                    <span>{cause.text}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* EXPLAINABILITY */}
            <div className="col-span-1">
              <h3 className="text-xs font-bold text-muted uppercase tracking-wider mb-3">WHY IS THIS HIGH PRIORITY?</h3>
              <ul className="space-y-1">
                {(issueData.priorityReasons || []).map((reason, i) => (
                  <li key={i} className="text-sm flex items-start gap-2">
                    <span className="text-danger font-bold">•</span>
                    {reason}
                  </li>
                ))}
              </ul>
            </div>

            {/* 3. HOW DID IT DEVELOP? (TIMELINE) */}
            <div className="col-span-3 border-t border-hair pt-6">
              <h3 className="text-[10px] font-bold text-muted uppercase tracking-wider mb-6">3. HOW DID IT DEVELOP?</h3>
              <div className="flex justify-between items-start relative px-4">
                <div className="absolute top-2.5 left-8 right-8 h-[1px] bg-line -z-10"></div>
                {['Reported', 'Detected', 'Analysed', 'Alert raised', 'Action req.', 'Resolved'].map((stage, i) => {
                  const isPast = i < 4;
                  const isCurrent = i === 4;
                  return (
                  <div key={stage} className="flex flex-col items-center flex-1 text-center group">
                    <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center mb-2 shadow-sm text-[10px] font-bold transition-colors ${
                      isPast ? 'bg-info border-info text-deep' : 
                      isCurrent ? 'bg-surface border-info text-info ring-4 ring-info/15' : 
                      'bg-raised border-line text-faint'
                    }`}>
                      {isPast ? '✓' : i + 1}
                    </div>
                    <span className={`text-[10px] font-bold uppercase tracking-wider mb-1 ${isCurrent ? 'text-info' : 'text-muted'}`}>{stage}</span>
                    <span className="text-[10px] text-muted max-w-[100px] leading-tight hidden group-hover:block absolute mt-12 bg-surface border border-line p-2 rounded shadow-lg z-20">
                      {issueData.timeline[i]?.desc || 'Pending completion'}
                    </span>
                  </div>
                )})}
              </div>
            </div>

            {/* 5. WHAT IS THE IMPACT? */}
            <div className="col-span-2 grid grid-cols-2 gap-3 border-t border-hair pt-6">
              <h3 className="col-span-2 text-[10px] font-bold text-muted uppercase tracking-wider">5. WHAT IS THE IMPACT?</h3>
              <div className="bg-raised p-3 rounded border border-line">
                <span className="text-[10px] uppercase tracking-wider text-muted block mb-1">Safety</span>
                <span className="text-xs font-semibold text-ink">{issueData.impact?.safety}</span>
              </div>
              <div className="bg-raised p-3 rounded border border-line">
                <span className="text-[10px] uppercase tracking-wider text-muted block mb-1">Operations</span>
                <span className="text-xs font-semibold text-ink">{issueData.impact?.operations}</span>
              </div>
              <div className="bg-raised p-3 rounded border border-line">
                <span className="text-[10px] uppercase tracking-wider text-muted block mb-1">Maintenance</span>
                <span className="text-xs font-semibold text-ink">{issueData.impact?.maintenance}</span>
              </div>
              <div className="bg-raised p-3 rounded border border-line">
                <span className="text-[10px] uppercase tracking-wider text-muted block mb-1">Affected Location</span>
                <span className="text-xs font-semibold text-ink">{issueData.impact?.location}</span>
                {issueData.exactLocation && (
                  <span className="text-[11px] text-muted block mt-1">{issueData.exactLocation}</span>
                )}
              </div>
            </div>

            {/* 6. WHAT SHOULD WE DO? */}
            <div className="col-span-1">
              <h3 className="text-xs font-bold text-muted uppercase tracking-wider mb-3">6. WHAT SHOULD WE DO?</h3>
              <div className="flex flex-wrap gap-2">
                {(issueData.actions || []).map((action, i) => (
                  <span key={i} className="bg-info/10 text-info border border-info/30 px-3 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wide">
                    {action}
                  </span>
                ))}
              </div>
            </div>

            {/* 7. RAILOPT RECOMMENDATION */}
            <div className="col-span-2">
              <div className="border border-merge/30 rounded-lg overflow-hidden bg-info/10">
                <div className="bg-merge text-deep px-4 py-2 flex items-center gap-2">
                  <span className="text-[11px] font-bold uppercase tracking-wider">7. RAILOPT RECOMMENDATION</span>
                </div>
                <div className="p-4 text-sm font-medium text-ink">
                  {issueData.recommendation}
                </div>
              </div>
            </div>

            {/* 8. SUPPORTING INFORMATION */}
            <div className="col-span-1">
              <h3 className="text-xs font-bold text-muted uppercase tracking-wider mb-2">8. SUPPORTING INFORMATION</h3>
              <div className="space-y-3">
                {(issueData.supporting || []).map((item, i) => (
                  <div key={i}>
                    <span className="text-[10px] uppercase tracking-wider text-muted block">{item.label}</span>
                    <span className="text-xs">{item.value}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* EXTERNAL INFORMATION */}
            <div className="col-span-3 border-t border-line pt-6 mt-2">
              <div className="flex items-center gap-3 mb-4">
                <h3 className="text-xs font-bold text-muted uppercase tracking-wider">EXTERNAL INFORMATION</h3>
                <span className="px-2 py-0.5 bg-base border border-line text-[10px] uppercase tracking-wider text-muted rounded">Demo External Information</span>
              </div>
              
              <div className="grid grid-cols-2 gap-6">
                <div className="bg-surface border border-line rounded p-4">
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-info">IMD Weather Advisory</span>
                    <span className="text-[10px] text-muted">Today, 06:00</span>
                  </div>
                  <h4 className="text-sm font-semibold mb-2">Heavy Rainfall Warning for Sector 7</h4>
                  <p className="text-xs text-muted mb-3">Expected continuous heavy rainfall (60-80mm) in the region over the next 24 hours, increasing risk of localized flooding and soil saturation.</p>
                </div>

                <div className="bg-surface border border-line rounded p-4 flex flex-col justify-center">
                  <h4 className="text-[11px] font-bold text-muted uppercase tracking-wider mb-2">WHY THIS INFORMATION MATTERS</h4>
                  <p className="text-sm">
                    Weather conditions may severely affect maintenance planning. Saturated soil increases subsidence risk for Track operations, and heavy rain may delay OHE repair works.
                  </p>
                </div>
              </div>
            </div>

          </div>
        </div>

        {/* DEPARTMENT ACTIONS */}
        <div className="bg-base border-t border-line px-6 py-4 flex gap-3">
          <button 
            onClick={() => handleStatusChange('Acknowledged')}
            className="px-4 py-2 bg-surface border border-line rounded text-xs font-semibold uppercase tracking-wider hover:bg-raised transition-colors"
          >
            ACKNOWLEDGE
          </button>
          <button 
            onClick={() => handleStatusChange('Action Started')}
            className="px-4 py-2 bg-merge text-deep rounded text-xs font-semibold uppercase tracking-wider hover:bg-merge/90 transition-colors"
          >
            START ACTION
          </button>
          <button 
            onClick={() => handleStatusChange('In Progress')}
            className="px-4 py-2 bg-surface border border-line text-info rounded text-xs font-semibold uppercase tracking-wider hover:bg-info/10 transition-colors"
          >
            MARK IN PROGRESS
          </button>
          <button 
            onClick={() => handleStatusChange('Resolved')}
            className="px-4 py-2 bg-surface border border-line text-ok rounded text-xs font-semibold uppercase tracking-wider hover:bg-ok/10 transition-colors"
          >
            MARK RESOLVED
          </button>
        </div>
      </div>

    </PortalLayout>
  )
}
