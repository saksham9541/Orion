import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ArrowRight,
  CalendarRange,
  CheckCircle2,
  UserCheck,
  Clock,
  ListOrdered,
  ShieldCheck,
  Train,
} from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import PageHeader from '@/components/app/PageHeader'
import StageFooter from '@/components/app/StageFooter'
import KPI from '@/components/common/KPI'
import Button from '@/components/common/Button'
import DeptTag from '@/components/common/DeptTag'
import ScoreMeter from '@/components/common/ScoreMeter'
import StatusChip, { DataTag, StatusLegend } from '@/components/common/StatusChip'
import RailwayNetwork from '@/components/network/RailwayNetwork'
import ConflictRadar from '@/components/optimize/ConflictRadar'
import OptimizationRun from '@/components/optimize/OptimizationRun'
import PreventedPanel from '@/components/optimize/PreventedPanel'
import ApprovalPanel from '@/components/optimize/ApprovalPanel'
import DecisionTrace from '@/components/optimize/DecisionTrace'
import Toast from '@/components/common/Toast'
import { useAppState } from '@/state/AppState'
import { weeklyBlocks, planMeta } from '@/data/plan'
import { tasks } from '@/data/tasks'
import {
  baseline,
  blockEfficiencyById,
  downtimeByDept,
  kpis,
  networkStateAt,
  optimised,
} from '@/lib/optimizer'
import { DAYS, clock, duration, hours } from '@/lib/format'

const axis = { stroke: 'rgb(var(--c-faint))', fontSize: 11, fontFamily: 'IBM Plex Mono' }

/**
 * The overview answers one question per panel, in the order the person
 * looking at it would ask them. Which order that is depends on the role: a
 * section controller wants the approval queue near the top, a planner wants
 * the clash. The panels themselves are identical either way — this reorders,
 * it does not hide.
 */
export default function Dashboard() {
  const { role, optimised: revealed } = useAppState()
  const [toast, setToast] = useState(null)

  useEffect(() => {
    document.title = 'Overview — RailOpt'
  }, [])

  useEffect(() => {
    if (!toast) return
    const id = setTimeout(() => setToast(null), 2800)
    return () => clearTimeout(id)
  }, [toast])

  const panels = {
    kpis: <KpiRow key="kpis" revealed={revealed} />,
    impact: <OptimizationRun key="impact" onComplete={() => setToast('Coordinated plan generated')} />,
    conflicts: <ConflictRadar key="conflicts" />,
    prevented: revealed ? <PreventedPanel key="prevented" /> : null,
    twin: <TwinPreview key="twin" />,
    active: <ActiveBlocks key="active" />,
    urgent: <UrgentWork key="urgent" />,
    departments: <DepartmentSplit key="departments" />,
    approval: <ApprovalPanel key="approval" onNotify={setToast} />,
    recommendation: <RecommendationBanner key="recommendation" />,
    trace: <DecisionTrace key="trace" />,
  }

  return (
    <>
      <PageHeader
        title="Week 38 at a glance"
        description={`${planMeta.window} · ${planMeta.division} · generated ${planMeta.generatedAt}. Demonstration data throughout.`}
      >
        <Button as={Link} to="/app/plan" size="sm">
          Open plan
          <ArrowRight size={14} />
        </Button>
      </PageHeader>

      <div className="space-y-6 px-5 py-6 sm:px-8">
        <p className="text-[12.5px] text-muted">
          Ordered for the <span className="text-ink">{role.label.toLowerCase()}</span> —{' '}
          {role.focus.toLowerCase()}.
        </p>
        {role.panels.map((id) => panels[id]).filter(Boolean)}
      </div>

      <Toast message={toast} />
      <StageFooter reason="see the same plan on the network" />
    </>
  )
}

function KpiRow({ revealed }) {
  const cards = [
    {
      label: 'Maintenance tasks',
      value: kpis.tasksCovered,
      unit: `of ${kpis.tasksTotal}`,
      compare: null,
      icon: ListOrdered,
    },
    {
      label: 'Optimised blocks',
      value: revealed ? optimised.blocks : baseline.blocks,
      compare: revealed ? baseline.blocks : null,
      icon: CalendarRange,
      accent: revealed,
    },
    {
      label: 'Planned closure',
      value: Number(hours(revealed ? optimised.downtimeMinutes : baseline.downtimeMinutes)),
      unit: 'hours',
      decimals: 1,
      compare: revealed ? Number(hours(baseline.downtimeMinutes)) : null,
      format: (v) => `${v} h`,
      icon: Clock,
    },
    {
      label: 'Estimated train movements impacted',
      value: revealed ? optimised.trainsAffected : baseline.trainsAffected,
      compare: revealed ? baseline.trainsAffected : null,
      icon: Train,
    },
    {
      label: 'Past deferral limit',
      value: revealed ? optimised.slaBreaches : baseline.slaBreaches,
      compare: revealed ? baseline.slaBreaches : null,
      icon: ShieldCheck,
      accent: revealed,
    },
  ]

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-5">
      {cards.map((c, i) => (
        <KPI key={c.label} {...c} delay={i * 0.06} />
      ))}
    </div>
  )
}

/** Monday 02:15 — the busiest moment of the week's night work. */
function TwinPreview() {
  const snapshot = useMemo(() => networkStateAt(0, 135), [])
  return (
    <section className="panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hair px-5 py-4 sm:px-6">
        <div>
          <h2 className="text-[15px] font-semibold">Network digital twin</h2>
          <p className="mt-0.5 text-[12.5px] text-muted">
            Monday 02:15 · {snapshot.activeBlocks.length} possessions in force ·{' '}
            {snapshot.trainsAffected} estimated movements impacted
          </p>
        </div>
        <div className="flex items-center gap-2">
          <DataTag kind="simulation" />
          <Link
            to="/app/network"
            className="flex items-center gap-1.5 rounded-panel border border-line px-2.5 py-1.5 text-[12.5px] text-muted transition-colors hover:border-merge/50 hover:text-ink"
          >
            Play the week
            <ArrowRight size={12} />
          </Link>
        </div>
      </div>
      <div className="px-2 py-3 sm:px-4">
        <RailwayNetwork sectionStates={snapshot.sections} compact />
      </div>
      <div className="border-t border-hair px-5 py-3.5 sm:px-6">
        <StatusLegend />
      </div>
    </section>
  )
}

function ActiveBlocks() {
  const rows = [...weeklyBlocks].sort((a, b) => a.day - b.day || a.start - b.start).slice(0, 6)
  return (
    <section className="panel overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b border-hair px-5 py-4 sm:px-6">
        <h2 className="text-[15px] font-semibold">Next blocks</h2>
        <Link to="/app/plan" className="text-[13px] text-muted transition-colors hover:text-ink">
          All {weeklyBlocks.length} blocks
        </Link>
      </div>
      <ul>
        {rows.map((b, i) => {
          const eff = blockEfficiencyById[b.id]
          return (
            <motion.li
              key={b.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05, duration: 0.35 }}
              className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-hair/60 px-5 py-3.5 last:border-0 sm:px-6"
            >
              <span className="w-[54px] shrink-0 font-mono text-[12px] text-faint">{b.id}</span>
              <span className="w-[86px] shrink-0 font-mono text-[13px]">{b.section}</span>
              <span className="tnum w-[130px] shrink-0 font-mono text-[12.5px] text-muted">
                {DAYS[b.day]} {clock(b.start)}–{clock(b.end)}
              </span>
              <span className="text-[12.5px] text-muted">{duration(b.end - b.start)}</span>
              {b.merged && (
                <span className="rounded-[2px] border border-merge/40 bg-merge/10 px-1.5 py-0.5 font-mono text-[10.5px] text-merge">
                  {b.taskIds.length} DEPTS
                </span>
              )}
              <span className="ml-auto flex items-center gap-3">
                <span className="text-[11.5px] text-faint">efficiency</span>
                <ScoreMeter score={eff.score} width={48} />
              </span>
            </motion.li>
          )
        })}
      </ul>
    </section>
  )
}

function UrgentWork() {
  const top = [...tasks].sort((a, b) => b.score - a.score).slice(0, 6)
  return (
    <section className="panel overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b border-hair px-5 py-4 sm:px-6">
        <h2 className="text-[15px] font-semibold">Highest urgency right now</h2>
        <Link to="/app/tasks" className="text-[13px] text-muted transition-colors hover:text-ink">
          All {tasks.length} tasks
        </Link>
      </div>
      <ul>
        {top.map((t, i) => (
          <motion.li
            key={t.id}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.05, duration: 0.35 }}
            className="flex items-center gap-4 border-b border-hair/60 px-5 py-3 last:border-0 sm:px-6"
          >
            <div className="min-w-0 flex-1">
              <p className="truncate text-[14px]">{t.defectType}</p>
              <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                <DeptTag dept={t.department} size="sm" />
                <span className="font-mono text-[11.5px] text-faint">{t.id}</span>
                <span className="font-mono text-[11.5px] text-faint">{t.section}</span>
                {t.slaDays <= 0 && (
                  <StatusChip
                    state="critical"
                    size="sm"
                    label={`${Math.abs(t.slaDays)}d over limit`}
                  />
                )}
              </div>
            </div>
            <ScoreMeter score={t.score} width={56} />
          </motion.li>
        ))}
      </ul>
    </section>
  )
}

function DepartmentSplit() {
  return (
    <section className="panel p-5 sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="text-[15px] font-semibold">Closure charged to each department</h2>
        <span className="font-mono text-[11.5px] text-faint">
          minutes · shared blocks split between the departments in them
        </span>
      </div>
      <div className="mt-5 h-[240px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={downtimeByDept} margin={{ top: 4, right: 4, left: -22, bottom: 0 }}>
            <CartesianGrid stroke="rgb(var(--c-hair))" vertical={false} />
            <XAxis dataKey="dept" tick={{ ...axis, fontSize: 10 }} tickLine={false} axisLine={false} interval={0} />
            <YAxis tick={axis} tickLine={false} axisLine={false} />
            <Tooltip
              cursor={{ fill: 'rgb(var(--c-hair) / 0.3)' }}
              contentStyle={{
                background: 'rgb(var(--c-surface))',
                border: '1px solid rgb(var(--c-line))',
                borderRadius: 10,
                fontSize: 12.5,
              }}
            />
            <Legend wrapperStyle={{ fontSize: 12, color: 'rgb(var(--c-muted))', paddingTop: 8 }} iconType="circle" />
            <Bar dataKey="baseline" name="If planned alone" fill="rgb(var(--c-line))" radius={[4, 4, 0, 0]} />
            <Bar dataKey="planned" name="In this plan" fill="rgb(var(--c-merge))" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}

/**
 * The state of the recommendation, in one strip.
 *
 * Put above everything a controller might act on, because the most important
 * fact about this plan is not any of its numbers — it is that nobody has
 * authorised it yet, and that RailOpt cannot.
 */
function RecommendationBanner() {
  const { approvedCount, planDecision } = useAppState()
  const total = weeklyBlocks.length
  const status =
    planDecision === 'approved'
      ? 'ACCEPTED BY CONTROLLER'
      : planDecision === 'revision'
        ? 'REVISION REQUESTED'
        : 'AWAITING HUMAN REVIEW'

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
      className="flex flex-wrap items-center gap-x-8 gap-y-4 rounded-panel border border-merge/30 bg-merge/[0.06] px-5 py-4 sm:px-6"
    >
      <div className="min-w-[180px]">
        <p className="font-mono text-[11px] tracking-[0.16em] text-faint">
          RAILOPT RECOMMENDATION
        </p>
        <p className="mt-1.5 text-[15px] leading-snug">
          {optimised.blocks} optimised blocks · {optimised.slaBreaches} SLA breaches
        </p>
      </div>

      <div>
        <p className="font-mono text-[11px] tracking-[0.16em] text-faint">STATUS</p>
        <p
          className={`mt-1.5 flex items-center gap-1.5 font-mono text-[13px] ${
            planDecision === 'approved' ? 'text-ok' : 'text-warn'
          }`}
        >
          {planDecision === 'approved' ? <CheckCircle2 size={13} /> : <UserCheck size={13} />}
          {status}
        </p>
      </div>

      <ol className="flex flex-wrap items-center gap-x-5 gap-y-2 text-[12.5px] text-muted">
        {['Review', 'Modify', 'Approve'].map((step, i) => (
          <li key={step} className="flex items-center gap-1.5">
            <span className="tnum font-mono text-[11px] text-faint">0{i + 1}</span>
            {step}
          </li>
        ))}
      </ol>

      <div className="ml-auto flex flex-wrap items-center gap-3">
        <span className="tnum font-mono text-[12px] text-faint">
          {approvedCount}/{total} blocks signed
        </span>
        <Button as={Link} to="/app/plan" size="sm">
          Review the plan
          <ArrowRight size={14} />
        </Button>
      </div>

      <p className="w-full text-[12px] leading-relaxed text-faint">
        RailOpt recommends. Authorised railway personnel approve. No possession is granted from
        this interface.
      </p>
    </motion.section>
  )
}
