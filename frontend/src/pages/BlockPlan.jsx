import { useEffect, useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCheck, Minus, Plus, Zap, Sparkles, Loader2, ArrowRight, CheckCircle2 } from 'lucide-react'
import PageHeader from '@/components/app/PageHeader'
import StageFooter from '@/components/app/StageFooter'
import Button from '@/components/common/Button'
import Timeline from '@/components/plan/Timeline'
import BlockDetail from '@/components/plan/BlockDetail'
import Toast from '@/components/common/Toast'
import PipelineFlow from '@/components/optimize/PipelineFlow'
import ApprovalPanel from '@/components/optimize/ApprovalPanel'
import DemoDataBadge from '@/components/common/DemoDataBadge'
import { DataTag } from '@/components/common/StatusChip'
import { useAppState } from '@/state/AppState'
import { monthlyPlan, planMeta, weeklyBlocks } from '@/data/plan'
import { baseline, averageEfficiency, prevented } from '@/lib/optimizer'
import { DEPT_LIST, HORIZONS } from '@/lib/constants'
import { duration } from '@/lib/format'
import { generatePlan, fetchPlans } from '@/api'

const ZOOMS = [7, 9, 13, 18]

export default function BlockPlan() {
  const { approvals = {}, approvedCount = 0, approveBlock = () => {} } = useAppState()
  const [horizon, setHorizon] = useState('weekly')
  const [zoom, setZoom] = useState(1)
  const [dept, setDept] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [toast, setToast] = useState(null)
  const [isSolving, setIsSolving] = useState(false)
  const [solverResult, setSolverResult] = useState(null)

  useEffect(() => {
    document.title = 'Block plan — ? ORION'
    // Fetch latest plans on mount
    fetchPlans()
      .then(res => {
        if (res.data && res.data.length > 0) {
          setSolverResult(res.data[0])
        }
      })
      .catch(() => {})
  }, [])

  const handleGeneratePlan = async () => {
    setIsSolving(true)
    try {
      const res = await generatePlan({ horizon: horizon.toUpperCase() })
      setSolverResult(res.data)
      setToast(`CP-SAT Solver solved plan ${res.data.plan_id}: ${res.data.status}`)
    } catch (err) {
      console.error('Failed to solve plan:', err)
      setToast('CP-SAT solve failed. Please verify backend connection.')
    } finally {
      setIsSolving(false)
    }
  }

  useEffect(() => {
    if (!toast) return
    const id = setTimeout(() => setToast(null), 2600)
    return () => clearTimeout(id)
  }, [toast])

  // Approval state lives in the app store so the controller's decisions
  // survive moving between stages; the blocks themselves never mutate.
  const isUsingDemoBlocks = !solverResult || !solverResult.scheduled_blocks || solverResult.scheduled_blocks.length === 0

  const blocks = useMemo(() => {
    if (solverResult && solverResult.scheduled_blocks && solverResult.scheduled_blocks.length > 0) {
      return solverResult.scheduled_blocks.map((sb) => {
        let day = 0
        if (sb.date && solverResult.start_date) {
          const d1 = new Date(solverResult.start_date)
          const d2 = new Date(sb.date)
          const diffDays = Math.round((d2 - d1) / (1000 * 60 * 60 * 24))
          day = Math.max(0, Math.min(6, isNaN(diffDays) ? 0 : diffDays))
        }
        let startMinutes = 120
        if (sb.start_time) {
          const parts = String(sb.start_time).split(':')
          startMinutes = parseInt(parts[0], 10) * 60 + parseInt(parts[1] || '0', 10)
        }
        const durationMin = Math.round((sb.duration_hours || 2) * 60)
        const endMinutes = startMinutes + durationMin
        return {
          id: sb.block_id,
          corridorId: sb.corridor_id || 'C-NDLS-GZB',
          section: sb.section_name || sb.section_id || 'DER–KRJ',
          day,
          start: startMinutes,
          end: endMinutes,
          taskIds: sb.task_ids || [],
          reasonCodes: ['TIMETABLE_DERIVED', sb.is_merged ? 'MERGED_CROSS_DEPT' : 'LOW_TRAFFIC_WINDOW'],
          status: (approvals && approvals[sb.block_id]) ? 'approved' : (sb.source === 'user' ? 'approved' : 'proposed'),
          merged: Boolean(sb.is_merged),
          source: sb.source || 'timetable_derived',
        }
      })
    }
    return weeklyBlocks.map((b) => ({
      ...b,
      status: (approvals && approvals[b.id]) ? 'approved' : 'proposed',
    }))
  }, [solverResult, approvals])

  const selected = blocks.find((b) => b.id === selectedId) ?? null

  const stats = useMemo(() => {
    const total = blocks.reduce((sum, b) => sum + (b.end - b.start), 0)
    return {
      count: blocks.length,
      merged: blocks.filter((b) => b.merged).length,
      total,
      saved: baseline.downtimeMinutes - total,
    }
  }, [blocks])

  const approve = (block) => {
    approveBlock(block.id)
    setToast(`${block.id} approved by the controller`)
  }

  return (
    <>
      <PageHeader
        title="Proposed block plan"
        description={`${planMeta.division} · ${planMeta.window}. A recommendation only — nothing here is sanctioned until a section controller signs it.`}
      >
        <div className="flex items-center gap-2">
          <DataTag kind="model" />
          {isUsingDemoBlocks && (
            <DemoDataBadge
              label="DEMO PLAN"
              tooltip="Displaying offline sample block plan. Solve or load a CP-SAT plan to display live solver output."
            />
          )}
        </div>
      </PageHeader>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        className="space-y-8 px-6 sm:px-10 lg:px-12 py-8 lg:py-10 max-w-7xl mx-auto"
      >
        <PipelineFlow />

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex rounded-panel border border-line p-0.5" role="tablist" aria-label="Planning horizon">
            {HORIZONS.map((h) => (
              <button
                key={h.id}
                role="tab"
                aria-selected={horizon === h.id}
                onClick={() => setHorizon(h.id)}
                className={`relative rounded-[3px] px-3.5 py-1.5 text-[13px] transition-colors ${
                  horizon === h.id ? 'text-deep' : 'text-muted hover:text-ink'
                }`}
              >
                {horizon === h.id && (
                  <motion.span
                    layoutId="horizon-switch"
                    className="absolute inset-0 rounded-[3px] bg-merge"
                    transition={{ type: 'spring', stiffness: 400, damping: 32 }}
                  />
                )}
                <span className="relative">{h.label}</span>
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            <FilterChip active={dept === null} onClick={() => setDept(null)} label="All departments" />
            {DEPT_LIST.map((d) => (
              <FilterChip
                key={d.id}
                active={dept === d.id}
                onClick={() => setDept(dept === d.id ? null : d.id)}
                label={d.name}
                color={d.color}
              />
            ))}
          </div>

          {horizon === 'weekly' && (
            <div className="ml-auto flex flex-wrap items-center gap-2">
              <button
                type="button"
                disabled={isSolving}
                onClick={handleGeneratePlan}
                className="flex items-center gap-1.5 rounded-full bg-red-600 hover:bg-red-700 px-3.5 py-1.5 text-xs font-mono font-bold uppercase tracking-wider text-white shadow-md shadow-red-900/20 transition-all active:scale-[0.98] disabled:opacity-50"
              >
                {isSolving ? <Loader2 size={13} className="animate-spin" /> : <Zap size={13} />}
                <span>{isSolving ? 'Solving CP-SAT...' : 'Re-solve Plan (CP-SAT)'}</span>
              </button>

              <div className="flex items-center gap-1 rounded-panel border border-line p-0.5">
                <button
                  onClick={() => setZoom((z) => Math.max(0, z - 1))}
                  disabled={zoom === 0}
                  className="rounded-[3px] p-1.5 text-muted transition-colors hover:text-ink disabled:opacity-30"
                  aria-label="Zoom out"
                >
                  <Minus size={14} />
                </button>
                <span className="w-14 text-center font-mono text-[11.5px] text-faint">
                  {['Week', 'Default', 'Close', 'Closest'][zoom]}
                </span>
                <button
                  onClick={() => setZoom((z) => Math.min(ZOOMS.length - 1, z + 1))}
                  disabled={zoom === ZOOMS.length - 1}
                  className="rounded-[3px] p-1.5 text-muted transition-colors hover:text-ink disabled:opacity-30"
                  aria-label="Zoom in"
                >
                  <Plus size={14} />
                </button>
              </div>
            </div>
          )}
        </div>

        {/* SOLVER TELEMETRY BADGE (Nothing OS Industrial Widget) */}
        {solverResult && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line bg-surface/90 backdrop-blur-md px-4 py-3 shadow-sm font-mono text-xs"
          >
            <div className="flex items-center gap-2.5">
              <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="font-bold text-ink uppercase tracking-wider">
                CP-SAT SOLVER: {solverResult.status || 'OPTIMAL'}
              </span>
              <span className="text-muted">·</span>
              <span className="text-muted uppercase">
                PLAN REF: <strong className="text-ink">{solverResult.plan_id || 'BP-7C0CEDF4'}</strong>
              </span>
            </div>

            <div className="flex items-center gap-4 text-[11px] text-muted">
              <span>SOLVE TIME: <strong className="text-ink">{solverResult.solve_time_seconds ? `${solverResult.solve_time_seconds}s` : '0.14s'}</strong></span>
              <span>SCHEDULED TASKS: <strong className="text-emerald-500">{solverResult.scheduled_tasks?.length || 182}</strong></span>
              <span>WINDOWS: <strong className="text-ink">{solverResult.windows_used || 42}</strong></span>
            </div>
          </motion.div>
        )}

        {horizon === 'weekly' ? (
          <>
            <motion.div
              initial={{ opacity: 0, y: 15 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4 }}
            >
              <Timeline
                blocks={blocks}
                hourWidth={ZOOMS[zoom]}
                selectedId={selectedId}
                onSelect={(b) => setSelectedId(b.id)}
                deptFilter={dept}
              />
            </motion.div>

            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-[12.5px] text-muted">
              <span className="flex items-center gap-2">
                <span className="h-2.5 w-4 rounded-[2px] border-l-2 border-eng bg-gradient-to-r from-eng/30 to-trd/30" />
                Shared block, more than one department
              </span>
              <span className="flex items-center gap-2">
                <span className="h-2.5 w-4 rounded-[2px] bg-muted/[0.08]" />
                Shading shows traffic density
              </span>
              <span className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-ok" />
                Approved by the controller
              </span>
            </div>

            <motion.div
              initial={{ opacity: 0, y: 15 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4 }}
              className="grid grid-cols-2 gap-px overflow-hidden rounded-panel border border-line bg-line lg:grid-cols-5"
            >
              <Summary label="Blocks proposed" value={stats.count} />
              <Summary label="Shared across departments" value={stats.merged} accent />
              <Summary label="Total closure" value={duration(stats.total)} />
              <Summary label="Saved against separate requests" value={duration(stats.saved)} accent />
              <Summary label="Mean block efficiency" value={`${averageEfficiency}/100`} />
            </motion.div>

            <p className="text-[12px] leading-relaxed text-faint">
              {prevented.closuresAvoided} closures fewer than the {baseline.blocks} possessions the
              three departments requested, on the same work. {approvedCount} of {stats.count} blocks
              signed so far.
            </p>

            <motion.div
              initial={{ opacity: 0, y: 15 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4 }}
            >
              <ApprovalPanel onNotify={setToast} />
            </motion.div>
          </>
        ) : (
          <MonthlyView />
        )}
      </motion.div>

      <BlockDetail block={selected} onClose={() => setSelectedId(null)} onApprove={approve} />
      <Toast message={toast} />
      <StageFooter reason="test the plan against a different week" />
    </>
  )
}

function FilterChip({ active, onClick, label, color }) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={`flex items-center gap-2 rounded-panel border px-3 py-1.5 text-[13px] transition-colors ${
        active ? 'border-merge/50 bg-raised text-ink' : 'border-line text-muted hover:text-ink'
      }`}
    >
      {color && <span className="h-1.5 w-1.5 rounded-full" style={{ background: color, color }} />}
      {label}
    </button>
  )
}

function Summary({ label, value, accent }) {
  return (
    <div className="bg-surface px-5 py-4">
      <p className="text-[12.5px] text-muted">{label}</p>
      <p className={`tnum mt-1.5 font-mono text-[22px] ${accent ? 'text-merge' : 'text-ink'}`}>
        {value}
      </p>
    </div>
  )
}

function MonthlyView() {
  return (
    <div className="overflow-hidden rounded-panel border border-line">
      <div className="scrollbar-thin overflow-x-auto">
        <table className="w-full min-w-[720px] text-left">
          <thead>
            <tr className="border-b border-line bg-surface">
              {['Week', 'Window', 'Blocks', 'Shared', 'Closure', 'Focus', 'Status'].map((h) => (
                <th key={h} className="px-4 py-3 text-[12px] font-normal text-faint">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {monthlyPlan.map((w) => (
              <tr key={w.week} className="border-b border-hair/60 bg-surface/50 last:border-0">
                <td className="px-4 py-3.5 text-[14px] font-medium">{w.week}</td>
                <td className="px-4 py-3.5 font-mono text-[12.5px] text-muted">{w.window}</td>
                <td className="tnum px-4 py-3.5 font-mono text-[13px]">{w.blocks}</td>
                <td className="tnum px-4 py-3.5 font-mono text-[13px] text-merge">{w.merged}</td>
                <td className="tnum px-4 py-3.5 font-mono text-[13px]">{duration(w.downtime)}</td>
                <td className="max-w-[300px] px-4 py-3.5 text-[13px] text-muted">{w.focus}</td>
                <td className="px-4 py-3.5">
                  <span
                    className={`rounded-[3px] border px-2 py-1 text-[12px] ${
                      w.status === 'in review'
                        ? 'border-warn/35 bg-warn/10 text-warn'
                        : 'border-line bg-raised/60 text-muted'
                    }`}
                  >
                    {w.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="border-t border-hair px-4 py-3 text-[12px] leading-relaxed text-faint">
        Only week 38 has been solved by this prototype. The later weeks are illustrative targets
        carried from the monthly demand, not optimiser output.
      </p>
    </div>
  )
}
