import { useEffect } from 'react'
import { motion } from 'framer-motion'
import { AlertTriangle, Check } from 'lucide-react'
import PageHeader from '@/components/app/PageHeader'
import DeptTag from '@/components/common/DeptTag'
import { corridors, sourceSystems } from '@/data/corridors'
import ObjectivePanel from '@/components/optimize/ObjectivePanel'
import { DataTag } from '@/components/common/StatusChip'
import { Circle } from 'lucide-react'

const cardVariants = {
  hidden: { opacity: 0, y: 20, scale: 0.97 },
  visible: (i) => ({
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      delay: 0.1 * i,
      duration: 0.5,
      ease: [0.16, 1, 0.3, 1],
    },
  }),
}

export default function Sources() {
  useEffect(() => {
    document.title = 'Data sources — RailOpt'
  }, [])

  return (
    <>
      <PageHeader
        title="Data sources"
        description="Everything downstream — scores, plan, briefing — reads from here. This prototype runs on synthetic records; nothing below is connected to a live Indian Railways system."
      >
        <DataTag kind="prototype" />
      </PageHeader>

      <div className="space-y-6 px-5 py-6 sm:px-8">
        <TrustPanel />

        <div className="grid gap-4 sm:grid-cols-2">
          {sourceSystems.map((s, idx) => (
            <motion.article
              key={s.id}
              custom={idx}
              variants={cardVariants}
              initial="hidden"
              animate="visible"
              className="panel p-5 transition-all duration-300 hover:shadow-lg"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="font-mono text-[15px] font-medium">{s.name}</h2>
                  <p className="mt-1 text-[13px] text-muted">{s.long}</p>
                </div>
                <span
                  className={`flex shrink-0 items-center gap-1.5 rounded-panel border px-2 py-1 text-[12px] ${
                    s.status === 'synced'
                      ? 'border-ok/35 bg-ok/10 text-ok'
                      : 'border-warn/35 bg-warn/10 text-warn'
                  }`}
                >
                  {s.status === 'synced' ? <Check size={12} /> : <AlertTriangle size={12} />}
                  {s.status === 'synced' ? 'Synced' : 'Partial'}
                </span>
              </div>

              <p className="mt-4 text-[13.5px] leading-relaxed text-muted">{s.feeds}</p>

              <dl className="mt-5 grid grid-cols-3 gap-4 border-t border-hair pt-4">
                <div>
                  <dt className="text-[12px] text-faint">Records</dt>
                  <dd className="mt-0.5 font-mono tnum text-[14px]">
                    {s.records.toLocaleString('en-IN')}
                  </dd>
                </div>
                <div>
                  <dt className="text-[12px] text-faint">Last sync</dt>
                  <dd className="mt-0.5 font-mono tnum text-[14px]">{s.lastSync}</dd>
                </div>
                <div>
                  <dt className="text-[12px] text-faint">Free text</dt>
                  <dd className="mt-0.5 font-mono tnum text-[14px]">
                    {Math.round(s.freeTextShare * 100)}%
                  </dd>
                </div>
              </dl>

              {s.dept && (
                <div className="mt-4">
                  <DeptTag dept={s.dept} size="sm" />
                </div>
              )}
            </motion.article>
          ))}
        </div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4, duration: 0.5 }}
          className="rounded-panel border border-warn/25 bg-warn/[0.06] px-5 py-4"
        >
          <p className="text-[13.5px] leading-relaxed text-ink/85">
            COA is marked partial because the goods forecast for weeks 40 and 41 has not been
            published yet. Those weeks are planned on a five-year seasonal average instead, and the
            monthly plan flags them as provisional.
          </p>
        </motion.div>

        <motion.section
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="overflow-hidden rounded-panel border border-line"
        >
          <div className="border-b border-line bg-surface px-5 py-3.5">
            <h2 className="text-[14px] font-semibold">Corridors in scope</h2>
          </div>
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-hair bg-surface/60">
                {['Corridor', 'Sections', 'Route km', 'Trains/day', 'Goods share'].map((h) => (
                  <th key={h} className="px-5 py-2.5 text-[12px] font-normal text-faint">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {corridors.map((c, idx) => (
                <motion.tr
                  key={c.id}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.55 + idx * 0.05, duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                  className="border-b border-hair/60 bg-surface/40 last:border-0 transition-colors hover:bg-raised/30"
                >
                  <td className="px-5 py-3.5">
                    <p className="text-[14px]">{c.name}</p>
                    <p className="mt-0.5 text-[12px] text-faint">{c.long}</p>
                  </td>
                  <td className="px-5 py-3.5 font-mono text-[12.5px] text-muted">
                    {c.sections.join('  ·  ')}
                  </td>
                  <td className="px-5 py-3.5 font-mono tnum text-[13px]">{c.routeKm}</td>
                  <td className="px-5 py-3.5 font-mono tnum text-[13px]">{c.trainsPerDay}</td>
                  <td className="px-5 py-3.5 font-mono tnum text-[13px]">
                    {Math.round(c.goodsShare * 100)}%
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </motion.section>

        <ObjectivePanel />
      </div>
    </>
  )
}

/**
 * What is real in this prototype and what is not.
 *
 * Put first, before any number, because a demonstration that lets a judge
 * believe it is reading live railway data has misled them — however good the
 * rest of it is. The right-hand column is what would replace the left in
 * service, and it is deliberately marked as not yet connected.
 */
const TRUST = [
  {
    title: 'In this prototype',
    tone: 'now',
    items: [
      ['Demo data', 'Synthetic maintenance tasks on real station codes'],
      ['Demo data', 'Corridor traffic profiles and daily train counts'],
      ['Model output', 'Urgency scores and their feature contributions'],
      ['Model output', 'The block plan, merges and reason codes'],
      ['Simulation', 'Est. train movements impacted, risk grid, scenario outcomes'],
      ['Simulation', 'The digital twin — a replay of the plan, not telemetry'],
    ],
  },
  {
    title: 'Would come from live systems',
    tone: 'later',
    items: [
      ['Not connected', 'Railway maintenance databases (TMS, SMMS, TDMS)'],
      ['Not connected', 'Working timetable and train running data'],
      ['Not connected', 'Asset management and defect history'],
      ['Not connected', 'Control Office Application block calendar'],
      ['Not connected', 'Goods traffic forecasts'],
      ['Not connected', 'Block demand and sanction workflow'],
    ],
  },
]

function TrustPanel() {
  return (
    <section className="panel overflow-hidden">
      <div className="border-b border-hair px-5 py-4 sm:px-6">
        <h2 className="text-[15px] font-semibold">What is real here</h2>
        <p className="mt-0.5 text-[12.5px] text-muted">
          RailOpt has no access to Indian Railways systems. Every figure in this product is
          generated by the prototype from the records below.
        </p>
      </div>
      <div className="grid gap-px bg-line md:grid-cols-2">
        {TRUST.map((col) => (
          <div key={col.title} className="bg-surface px-5 py-5 sm:px-6">
            <p className="font-mono text-[11px] tracking-[0.14em] text-faint">
              {col.title.toUpperCase()}
            </p>
            <ul className="mt-3.5 space-y-2.5">
              {col.items.map(([tag, text]) => (
                <li key={text} className="flex items-start gap-2.5">
                  {col.tone === 'now' ? (
                    <Check size={13} className="mt-0.5 shrink-0 text-ok" strokeWidth={2.3} />
                  ) : (
                    <Circle size={12} className="mt-0.5 shrink-0 text-faint" strokeWidth={1.8} />
                  )}
                  <span className="min-w-0">
                    <span className="block text-[13.5px] leading-snug">{text}</span>
                    <span className="mt-0.5 block font-mono text-[10.5px] tracking-[0.1em] text-faint">
                      {tag.toUpperCase()}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  )
}
