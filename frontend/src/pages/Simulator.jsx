import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Minus, RotateCcw, TrendingDown, TrendingUp } from 'lucide-react'
import PageHeader from '@/components/app/PageHeader'
import StageFooter from '@/components/app/StageFooter'
import Button from '@/components/common/Button'
import { DataTag } from '@/components/common/StatusChip'
import ScenarioComparison from '@/components/scenario/ScenarioComparison'
import EmergencyPanel from '@/components/scenario/EmergencyPanel'
import { SCENARIOS, currentPlanAsResult, scenarioDefaults, simulate } from '@/lib/optimizer'
import { clock, duration } from '@/lib/format'

/**
 * Scenario Lab.
 *
 * The controls are the levers a divisional office actually has: how much
 * traffic is running, how long the night window is, and how many gangs can
 * work at once. Everything else is the same plan and the same nineteen jobs,
 * re-costed. At the default settings the result is the published plan, which
 * is how you know the lab and the plan are speaking about the same week.
 */
export default function Simulator() {
  const [settings, setSettings] = useState(scenarioDefaults)
  const [presetId, setPresetId] = useState('normal')

  useEffect(() => {
    document.title = 'Scenario Lab — RailOpt'
  }, [])

  const result = useMemo(() => simulate(settings), [settings])
  const base = currentPlanAsResult

  const set = (k, v) => {
    setSettings((s) => ({ ...s, [k]: v }))
    setPresetId('custom')
  }

  const applyPreset = (s) => {
    setSettings(s.settings)
    setPresetId(s.id)
  }

  const rows = [
    { key: 'blocksCount', label: 'Blocks', format: (v) => v, better: 'lower' },
    { key: 'downtime', label: 'Planned maintenance closure', format: duration, better: 'lower' },
    { key: 'trainsAffected', label: 'Estimated train movements impacted', format: (v) => v, better: 'lower' },
    { key: 'merged', label: 'Blocks shared across departments', format: (v) => v, better: 'higher' },
    { key: 'slaBreaches', label: 'Left past deferral limit', format: (v) => v, better: 'lower' },
    {
      key: 'overrunMinutes',
      label: 'Overrun into service hours',
      format: (v) => (v ? duration(v) : 'none'),
      better: 'lower',
    },
  ]

  return (
    <>
      <PageHeader
        title="Scenario Lab"
        description="Change what the division has to work with, and see what the same week costs before anyone commits to it."
      >
        <DataTag kind="simulation" />
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            setSettings(scenarioDefaults)
            setPresetId('normal')
          }}
        >
          <RotateCcw size={14} />
          Reset
        </Button>
      </PageHeader>

      <div className="space-y-5 px-5 py-6 sm:px-8">
        <div className="flex flex-wrap gap-1.5">
          {SCENARIOS.map((s) => (
            <button
              key={s.id}
              onClick={() => applyPreset(s)}
              aria-pressed={presetId === s.id}
              title={s.note}
              className={`rounded-panel border px-3.5 py-2 text-[13px] transition-colors ${
                presetId === s.id
                  ? 'border-merge/50 bg-raised text-ink'
                  : 'border-line text-muted hover:text-ink'
              }`}
            >
              {s.name}
            </button>
          ))}
          {presetId === 'custom' && (
            <span className="rounded-panel border border-warn/35 bg-warn/10 px-3.5 py-2 text-[13px] text-warn">
              Custom
            </span>
          )}
        </div>

        <div className="grid gap-5 xl:grid-cols-[360px_1fr]">
          <motion.section
            initial={{ opacity: 0, x: -16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
            className="panel h-fit p-5 sm:p-6"
          >
            <h2 className="text-[15px] font-semibold">Constraints</h2>
            <p className="mt-1 text-[13px] text-muted">
              The levers a divisional office actually controls.
            </p>

            <div className="mt-6 space-y-6">
              <Range
                label="Traffic against the plan"
                value={settings.trafficDelta}
                min={-20}
                max={50}
                step={5}
                display={`${settings.trafficDelta > 0 ? '+' : ''}${settings.trafficDelta}%`}
                onChange={(v) => set('trafficDelta', v)}
                hint="Special trains and goods surges raise what every possession costs."
              />
              <Range
                label="Night window closes at"
                value={settings.windowEnd}
                min={180}
                max={420}
                step={30}
                display={`${clock(settings.windowStart)} – ${clock(settings.windowEnd)}`}
                onChange={(v) => set('windowEnd', v)}
                hint="Anything that will not fit overruns into service hours."
              />
              <Range
                label="Blocks running at once"
                value={settings.maxParallel}
                min={1}
                max={6}
                step={1}
                display={`${settings.maxParallel} across the division`}
                onChange={(v) => set('maxParallel', v)}
                hint="Limited by the gangs and supervisors available on a shift."
              />
              <Switch
                label="Merge work across departments"
                checked={settings.merge}
                onChange={(v) => set('merge', v)}
                hint="Off, every department gets its own closure — the situation today."
              />
              <Switch
                label="Enforce deferral limits"
                checked={settings.sla}
                onChange={(v) => set('sla', v)}
                hint="Off, safety-critical work can be pushed back on cost grounds."
              />
              <Switch
                label="Critical defect raised mid-week"
                checked={settings.emergency}
                onChange={(v) => set('emergency', v)}
                hint="Injects TDMS-1501 and re-plans the week around it."
              />
            </div>
          </motion.section>

          <motion.section
            initial={{ opacity: 0, x: 16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1, duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
            className="panel overflow-hidden"
          >
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hair px-5 py-4 sm:px-6">
              <h2 className="text-[15px] font-semibold">Simulated outcome</h2>
              <span className="font-mono text-[11.5px] text-faint">against the published plan</span>
            </div>

            <ul>
              {rows.map((r, i) => {
                const now = result[r.key]
                const before = base[r.key]
                const diff = now - before
                const same = Math.abs(diff) < 0.001
                const improved = r.better === 'lower' ? diff < 0 : diff > 0
                return (
                  <motion.li
                    key={`${r.key}-${now}-${before}`}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.04, duration: 0.3 }}
                    className="flex items-center gap-3 border-b border-hair/60 px-5 py-4 last:border-0 sm:px-6"
                  >
                    <span className="min-w-0 flex-1 text-[14px]">{r.label}</span>
                    <span className="tnum hidden font-mono text-[13px] text-faint sm:inline">
                      {r.format(before)}
                    </span>
                    <span className="hidden text-faint sm:inline">→</span>
                    <span className="tnum w-[92px] text-right font-mono text-[15px] font-medium">
                      {r.format(now)}
                    </span>
                    <span
                      className={`tnum flex w-[68px] items-center justify-end gap-1 font-mono text-[12.5px] ${
                        same ? 'text-faint' : improved ? 'text-ok' : 'text-danger'
                      }`}
                    >
                      {same ? (
                        <Minus size={12} />
                      ) : improved ? (
                        <TrendingDown size={12} />
                      ) : (
                        <TrendingUp size={12} />
                      )}
                      {same ? '—' : `${diff > 0 ? '+' : ''}${Math.round(diff)}`}
                    </span>
                  </motion.li>
                )
              })}
            </ul>

            <div className="border-t border-hair px-5 py-5 sm:px-6">
              <div className="rounded-panel border border-hair/60 bg-raised/40 px-4 py-3">
                <p className="text-[13.5px] leading-relaxed text-muted">{reading(settings, result, base)}</p>
              </div>
              {result.carried.length > 0 && (
                <p className="mt-3 text-[12.5px] text-warn">
                  {result.carried.length} job{result.carried.length === 1 ? '' : 's'} could not be
                  placed at all and would carry to the monthly horizon:{' '}
                  {result.carried.map((t) => t.id).join(', ')}.
                </p>
              )}
            </div>
          </motion.section>
        </div>

        <ScenarioComparison />
        <EmergencyPanel />
      </div>

      <StageFooter reason="ask the plan a question in plain language" />
    </>
  )
}

/** One sentence naming the binding constraint, chosen from the result. */
function reading(s, result, base) {
  if (!s.merge)
    return `Without cross-department merging the same work needs ${result.blocksCount} possessions instead of ${base.blocksCount}, and ${duration(result.downtime - base.downtime)} more track time. This is the situation the division is in today.`
  if (result.carried.length)
    return `The window and the gang limit together are too tight for this workload — ${result.carried.length} job${result.carried.length === 1 ? '' : 's'} cannot be placed anywhere in the week.`
  if (result.overrunMinutes > base.overrunMinutes)
    return `${duration(result.overrunMinutes)} of possession now runs past the end of the window and into service hours, which is where the extra exposure comes from.`
  if (result.slaBreaches > 0)
    return `${result.slaBreaches} block${result.slaBreaches === 1 ? '' : 's'} had to be placed past a deferral limit — there was no earlier day with both a free gang and a free section.`
  if (s.trafficDelta > 0)
    return `The plan itself does not change: the night window binds, not the traffic. What changes is the cost — ${result.trainsAffected} estimated movements impacted against ${base.trainsAffected}.`
  return 'These constraints reproduce the published plan. The binding limit is the number of gangs available, not the length of the window.'
}

function Range({ label, value, min, max, step, display, onChange, hint }) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <label className="text-[13.5px]">{label}</label>
        <span className="font-mono text-[12.5px] font-medium text-merge">{display}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-2.5 h-1.5 w-full cursor-pointer appearance-none rounded-full bg-line accent-merge"
        aria-label={label}
      />
      <p className="mt-2 text-[12px] leading-relaxed text-faint">{hint}</p>
    </div>
  )
}

function Switch({ label, checked, onChange, hint }) {
  return (
    <div>
      <div className="flex items-start justify-between gap-4">
        <label className="text-[13.5px]">{label}</label>
        <button
          role="switch"
          aria-checked={checked}
          aria-label={label}
          onClick={() => onChange(!checked)}
          className={`relative mt-0.5 h-[22px] w-[40px] shrink-0 rounded-full border transition-colors duration-300 ${
            checked ? 'border-merge/50 bg-merge/25' : 'border-line bg-raised'
          }`}
        >
          <motion.span
            layout
            transition={{ type: 'spring', stiffness: 500, damping: 34 }}
            className={`absolute top-[3px] h-[14px] w-[14px] rounded-full ${
              checked ? 'left-[22px] bg-merge' : 'left-[3px] bg-faint'
            }`}
          />
        </button>
      </div>
      <p className="mt-2 text-[12px] leading-relaxed text-faint">{hint}</p>
    </div>
  )
}
