import { useCallback, useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Activity, Radio, Train, Map, LayoutGrid } from 'lucide-react'
import PageHeader from '@/components/app/PageHeader'
import StageFooter from '@/components/app/StageFooter'
import RailwayNetwork from '@/components/network/RailwayNetwork'
import IndiaRailwayMap, { STATIONS } from '@/components/network/IndiaRailwayMap'
import TimeSlider from '@/components/network/TimeSlider'
import SectionPanel from '@/components/network/SectionPanel'
import RiskHeatmap from '@/components/network/RiskHeatmap'
import ExplainDrawer from '@/components/optimize/ExplainDrawer'
import DemoDataBadge from '@/components/common/DemoDataBadge'
import { StatusLegend, DataTag } from '@/components/common/StatusChip'
import { networkStateAt } from '@/lib/optimizer'
import { DAYS, clock } from '@/lib/format'
import { fetchCorridors, fetchPlans } from '@/api'

/**
 * The digital twin: the division as a diagram, played through the week.
 *
 * Everything on this page is a replay of the plan. Move the slider and the
 * board changes because the plan says a possession starts then — not because
 * anything is being read off a railway.
 */
export default function Network() {
  // Monday 02:15, in the middle of the first night's work.
  const [minutes, setMinutes] = useState(135)
  const [playing, setPlaying] = useState(false)
  const [selected, setSelected] = useState('DER–KRJ')
  const [explainId, setExplainId] = useState(null)
  const [viewMode, setViewMode] = useState('leaflet') // 'leaflet' (OpenRailwayMap) | 'schematic'
  const [corridors, setCorridors] = useState([])
  const [activePlan, setActivePlan] = useState(null)

  useEffect(() => {
    document.title = 'Digital twin — RailOpt'
    fetchCorridors().then(res => res.data && setCorridors(res.data)).catch(() => {})
    fetchPlans().then(res => res.data && res.data.length > 0 && setActivePlan(res.data[0])).catch(() => {})
  }, [])

  const day = Math.floor(minutes / 1440)
  const timeOfDay = Math.floor(minutes % 1440)
  const snapshot = useMemo(() => networkStateAt(day, timeOfDay), [day, timeOfDay])

  const handleTime = useCallback((next) => {
    setMinutes((m) => (typeof next === 'function' ? next(m) : next))
  }, [])

  // Geographically map simulation section states onto real station coordinates
  const simulatedIssues = useMemo(() => {
    return Object.entries(snapshot.sections).map(([secId, state], idx) => {
      const stationId = STATIONS[idx % STATIONS.length].id
      const severity = state === 'critical' || state === 'conflict' ? 'CRITICAL' : state === 'active' ? 'HIGH' : state === 'planned' ? 'MEDIUM' : 'LOW'
      return {
        id: secId,
        locationId: stationId,
        severity,
        status: state === 'active' ? 'IN PROGRESS' : state === 'planned' ? 'DEPARTMENT NOTIFIED' : 'NEW',
        type: `Block Window (${state})`,
        exactLocation: secId,
        department: 'ENGINEERING',
      }
    })
  }, [snapshot.sections])

  return (
    <>
      <PageHeader
        title="Railway digital twin"
        description="The division's sections, played through the planning week. Drag the timeline to move simulated time; select any section for the work on it."
      >
        <div className="flex items-center gap-2">
          <DemoDataBadge
            label="DEMO TWIN"
            tooltip="Digital twin replay is running on simulated schedule and calibrated section states."
          />
          <span className="flex items-center gap-2 rounded-panel border border-warn/35 bg-warn/10 px-3 py-1.5 font-mono text-[11px] tracking-[0.14em] text-warn">
            <Radio size={12} aria-hidden="true" />
            SIMULATION MODE
          </span>
        </div>
      </PageHeader>

      <div className="space-y-8 px-6 sm:px-10 lg:px-12 py-8 lg:py-10 max-w-7xl mx-auto">
        <TimeSlider
          minutes={minutes}
          onChange={handleTime}
          playing={playing}
          onTogglePlay={() => setPlaying((p) => !p)}
        />

        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-panel border border-line bg-line lg:grid-cols-4">
          <Readout
            label="Simulation time"
            value={`${DAYS[day]} ${clock(timeOfDay)}`}
            icon={Activity}
          />
          <Readout label="Blocks in force" value={snapshot.activeBlocks.length} />
          <Readout label="Est. movements impacted" value={snapshot.trainsAffected} icon={Train} />
          <Readout label="Network status" value={snapshot.status} small />
        </div>

        <div className="grid gap-5 xl:grid-cols-[1fr_380px]">
          <motion.section
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            className="panel overflow-hidden"
          >
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hair px-5 py-4 sm:px-6">
              <div>
                <h2 className="text-[15px] font-semibold text-ink">
                  {viewMode === 'leaflet' ? 'Geographic Railway Network (OpenRailwayMap)' : 'Division schematic'}
                </h2>
                <p className="text-xs text-muted font-sans mt-0.5">
                  {viewMode === 'leaflet'
                    ? 'Interactive OpenRailwayMap Leaflet tracks & live corridor heatmaps'
                    : 'Signal diagram of trunks and division sections'}
                </p>
              </div>

              <div className="flex items-center gap-2.5">
                <div className="flex items-center gap-1 rounded-full border border-line bg-raised p-1 text-xs font-mono font-bold">
                  <button
                    type="button"
                    onClick={() => setViewMode('leaflet')}
                    className={`px-3 py-1 rounded-full uppercase transition-all ${
                      viewMode === 'leaflet'
                        ? 'bg-ink text-deep shadow-sm'
                        : 'text-muted hover:text-ink'
                    }`}
                  >
                    OpenRailwayMap
                  </button>
                  <button
                    type="button"
                    onClick={() => setViewMode('schematic')}
                    className={`px-3 py-1 rounded-full uppercase transition-all ${
                      viewMode === 'schematic'
                        ? 'bg-ink text-deep shadow-sm'
                        : 'text-muted hover:text-ink'
                    }`}
                  >
                    Schematic
                  </button>
                </div>
                <DataTag kind="simulation" />
              </div>
            </div>

            {viewMode === 'leaflet' ? (
              <div className="p-3 sm:p-4">
                <div className="h-[460px] sm:h-[520px] w-full overflow-hidden rounded-xl border border-line bg-surface relative z-0 isolate">
                  <IndiaRailwayMap
                    issues={simulatedIssues}
                    selectedIssueId={selected}
                    onSelectIssue={(id) => setSelected(id)}
                    showHeatmap={true}
                  />
                </div>
              </div>
            ) : (
              <div className="px-2 py-4 sm:px-4">
                <RailwayNetwork
                  sectionStates={snapshot.sections}
                  selected={selected}
                  onSelect={setSelected}
                />
              </div>
            )}
            <div className="border-t border-hair px-5 py-3.5 sm:px-6">
              <StatusLegend />
              <p className="mt-2.5 text-[12px] leading-relaxed text-faint font-sans">
                Station codes and rail infrastructure track geometry follow real OpenRailwayMap trunk routes.
              </p>
            </div>
          </motion.section>

          <SectionPanel
            section={selected}
            day={day}
            minutes={timeOfDay}
            onClose={() => setSelected(null)}
            onExplain={setExplainId}
          />
        </div>

        <RiskHeatmap />
      </div>

      <ExplainDrawer taskId={explainId} onClose={() => setExplainId(null)} />

      <StageFooter reason="see the work waiting behind these sections" />
    </>
  )
}

function Readout({ label, value, icon: Icon, small }) {
  return (
    <div className="bg-surface px-5 py-3.5">
      <p className="flex items-center gap-1.5 text-[12px] text-muted">
        {Icon && <Icon size={12} strokeWidth={1.8} aria-hidden="true" />}
        {label}
      </p>
      <p className={`mt-1 ${small ? 'text-[13px] leading-snug' : 'tnum font-mono text-[20px]'}`}>
        {value}
      </p>
    </div>
  )
}
