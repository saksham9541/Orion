import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { AlertTriangle, Check, Database, Clock, MapPin, Train, FileText, ChevronDown, ChevronUp } from 'lucide-react'
import PageHeader from '@/components/app/PageHeader'
import StageFooter from '@/components/app/StageFooter'
import DeptTag from '@/components/common/DeptTag'
import DemoDataBadge from '@/components/common/DemoDataBadge'
import { corridors as fallbackCorridors, sourceSystems } from '@/data/corridors'
import ObjectivePanel from '@/components/optimize/ObjectivePanel'
import { DataTag } from '@/components/common/StatusChip'
import { Circle } from 'lucide-react'
import { fetchCorridors, fetchSourcesSnapshots } from '@/api'

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
  const [corridors, setCorridors] = useState(fallbackCorridors)
  const [snapshotReport, setSnapshotReport] = useState(null)
  const [isUsingDemoData, setIsUsingDemoData] = useState(false)
  const [showItemizedDetails, setShowItemizedDetails] = useState(false)

  useEffect(() => {
    document.title = 'Data sources — ? ORION'

    // Fetch live backend corridors and snapshots provenance
    fetchCorridors()
      .then((res) => {
        if (res.data && Array.isArray(res.data) && res.data.length > 0) {
          // Format corridor data to match UI needs
          const formatted = res.data.map((c) => ({
            id: c.corridor_id || c.id,
            name: c.name,
            long: c.division ? `${c.zone} / ${c.division}` : c.name,
            sections: (c.sections || []).map((s) => s.name || s),
            routeKm: c.sections?.reduce((acc, s) => acc + (s.length_km || 0), 0) || 160,
            trainsPerDay: c.sections?.[0]?.daily_train_count || 60,
            goodsShare: 0.32,
          }))
          setCorridors(formatted)
          setIsUsingDemoData(false)
        } else {
          setIsUsingDemoData(true)
        }
      })
      .catch(() => {
        setIsUsingDemoData(true)
      })

    fetchSourcesSnapshots()
      .then((res) => {
        setSnapshotReport(res.data)
      })
      .catch(() => {
        // Fallback static report if backend is offline
        setSnapshotReport({
          total_snapshots: 20,
          provenance_breakdown: { live: 0, hand_written: 20 },
          overall_provenance: 'hand_written',
          has_hand_written: true,
          ui_label: 'illustrative, not fetched',
          average_age_days: 0.0,
          oldest_timestamp: '2026-10-30T10:50:00Z',
          hand_written_details: {
            coordinates: [
              { code: 'NDLS', name: 'New Delhi', lat: 28.6424, lon: 77.2205, distance_km: 0.0, corridor: 'Delhi–Howrah Main' },
              { code: 'GZB', name: 'Ghaziabad', lat: 28.6675, lon: 77.4338, distance_km: 19.0, corridor: 'Delhi–Howrah Main' },
              { code: 'MTJ', name: 'Mathura Jn', lat: 27.4924, lon: 77.6737, distance_km: 141.0, corridor: 'Delhi–Mumbai Rajdhani Route' },
            ],
            timetables: [
              { number: '12004', name: 'Lucknow Shatabdi', type: 'SHATABDI' },
              { number: '12302', name: 'Howrah Rajdhani', type: 'RAJDHANI' },
              { number: '12952', name: 'Mumbai Rajdhani', type: 'RAJDHANI' },
            ],
            station_pairs: ['NDLS–GZB', 'NDLS–MTJ'],
          },
        })
      })
  }, [])

  const hasHandWritten = snapshotReport?.has_hand_written ?? true

  return (
    <>
      <PageHeader
        title="Data sources"
        description="Everything downstream — scores, plan, briefing — reads from here. Review data provenance, snapshot freshness, and live integration boundaries."
      >
        <div className="flex items-center gap-2">
          {isUsingDemoData && <DemoDataBadge label="FALLBACK DEMO DATA" />}
          <DataTag kind="prototype" />
        </div>
      </PageHeader>

      <div className="space-y-8 px-6 sm:px-10 lg:px-12 py-8 lg:py-10 max-w-7xl mx-auto">
        <TrustPanel />

        {/* ── Pilot Snapshots Provenance Panel ─────────────────────────────────── */}
        <motion.section
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="rounded-panel border border-line bg-surface overflow-hidden shadow-sm"
        >
          <div className="p-5 sm:p-6 border-b border-line flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2.5">
                <Database size={18} className="text-accent" />
                <h2 className="text-base font-semibold">RailRadar Offline Snapshot Provenance</h2>
                {hasHandWritten ? (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-amber-500/10 text-amber-500 border border-amber-500/30">
                    illustrative, not fetched
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-emerald-500/10 text-emerald-500 border border-emerald-500/30">
                    live snapshot
                  </span>
                )}
              </div>
              <p className="mt-1 text-xs text-muted">
                Zero live network calls occur on user request paths. Pilot corridor passages and track chainage read directly from local snapshots in <code className="font-mono text-[11px] bg-raised px-1 py-0.5 rounded">data/railradar_snapshots/</code>.
              </p>
            </div>

            <div className="flex items-center gap-6 text-xs text-muted border-t md:border-t-0 pt-3 md:pt-0">
              <div className="flex items-center gap-1.5">
                <FileText size={14} className="text-faint" />
                <span>Snapshots: <strong className="font-mono text-ink">{snapshotReport?.total_snapshots ?? 20} files</strong></span>
              </div>
              <div className="flex items-center gap-1.5">
                <Clock size={14} className="text-faint" />
                <span>Average age: <strong className="font-mono text-ink">{snapshotReport?.average_age_days ?? 0.1} days</strong></span>
              </div>
            </div>
          </div>

          {/* Highlight note about illustrative values */}
          {hasHandWritten && (
            <div className="px-5 sm:px-6 py-3.5 bg-amber-500/[0.06] border-b border-amber-500/20 text-xs text-amber-600 dark:text-amber-400 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="flex items-start sm:items-center gap-2">
                <AlertTriangle size={15} className="shrink-0 mt-0.5 sm:mt-0" />
                <span>
                  <strong>Data Provenance Notice:</strong> Pilot timetables and station coordinates were calibrated from published public timetables and written by hand as offline seed fixtures to respect API rate limits. They are <strong>illustrative, not fetched</strong>.
                </span>
              </div>
              <button
                onClick={() => setShowItemizedDetails(!showItemizedDetails)}
                className="inline-flex items-center gap-1 font-mono text-[11px] underline underline-offset-2 hover:text-amber-500 shrink-0 self-start sm:self-auto"
              >
                {showItemizedDetails ? 'Hide exact values' : 'Inspect exact values'}
                {showItemizedDetails ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              </button>
            </div>
          )}

          {/* Itemized list of hand-written values when expanded */}
          {showItemizedDetails && snapshotReport?.hand_written_details && (
            <div className="p-5 sm:p-6 bg-surface/50 border-b border-line space-y-4 text-xs font-mono">
              <div>
                <h3 className="font-sans font-semibold text-ink text-xs uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <MapPin size={13} className="text-accent" /> Hand-Written Station Coordinates ({snapshotReport.hand_written_details.coordinates?.length || 0} stations)
                </h3>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2 text-[11px]">
                  {snapshotReport.hand_written_details.coordinates?.map((c, i) => (
                    <div key={i} className="p-2 rounded bg-raised/40 border border-line/60">
                      <div className="font-bold text-ink">{c.code} — {c.name}</div>
                      <div className="text-muted mt-0.5">{c.lat.toFixed(4)}, {c.lon.toFixed(4)}</div>
                      <div className="text-[10px] text-faint">{c.corridor} ({c.distance_km}km)</div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="pt-2 border-t border-hair">
                <h3 className="font-sans font-semibold text-ink text-xs uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <Train size={13} className="text-accent" /> Hand-Written Pilot Train Timetables ({snapshotReport.hand_written_details.timetables?.length || 0} trains)
                </h3>
                <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-2 text-[11px]">
                  {snapshotReport.hand_written_details.timetables?.map((t, i) => (
                    <div key={i} className="p-2 rounded bg-raised/40 border border-line/60">
                      <div className="font-bold text-ink">{t.number}</div>
                      <div className="text-muted text-[10px] truncate">{t.name}</div>
                      <div className="text-accent text-[9.5px] uppercase">{t.type}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </motion.section>

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
          <div className="border-b border-line bg-surface px-5 py-3.5 flex items-center justify-between">
            <h2 className="text-[14px] font-semibold">Corridors in scope</h2>
            {isUsingDemoData && <DemoDataBadge label="DEMO CORRIDORS" />}
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
                    {Array.isArray(c.sections) ? c.sections.join('  ·  ') : c.sections}
                  </td>
                  <td className="px-5 py-3.5 font-mono tnum text-[13px]">{c.routeKm}</td>
                  <td className="px-5 py-3.5 font-mono tnum text-[13px]">{c.trainsPerDay}</td>
                  <td className="px-5 py-3.5 font-mono tnum text-[13px]">
                    {Math.round((c.goodsShare || 0.3) * 100)}%
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </motion.section>

        <ObjectivePanel />
      </div>

      <StageFooter reason="return to block plan" />
    </>
  )
}

const TRUST = [
  {
    title: 'In this prototype',
    tone: 'now',
    items: [
      ['Real Timetables', 'RailRadar snapshots on pilot sections (NDLS–GZB, NDLS–MTJ)'],
      ['Real Coordinates', 'Anchor station lat/lon extracted from train route geometry'],
      ['Demo data', 'Synthetic maintenance tasks on real station chainage'],
      ['Model output', 'Urgency scores and their feature contributions'],
      ['Model output', 'The block plan, merges and reason codes'],
      ['Simulation', 'Est. train movements impacted, risk grid, scenario outcomes'],
    ],
  },
  {
    title: 'Would come from live systems',
    tone: 'later',
    items: [
      ['Not connected', 'Railway maintenance databases (TMS, SMMS, TDMS)'],
      ['Live API', 'RailRadar production API key subscription (budgeted offline in prototype)'],
      ['Not connected', 'Asset management and defect history'],
      ['Not connected', 'Control Office Application (COA) live block calendar'],
      ['Not connected', 'Goods traffic forecasts (FOIS)'],
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
          Orion combines real timetables and coordinates from offline RailRadar snapshots with mathematical optimization.
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
