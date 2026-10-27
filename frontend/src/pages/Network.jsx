import { useCallback, useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Activity, Radio, Train } from 'lucide-react'
import PageHeader from '@/components/app/PageHeader'
import StageFooter from '@/components/app/StageFooter'
import RailwayNetwork from '@/components/network/RailwayNetwork'
import TimeSlider from '@/components/network/TimeSlider'
import SectionPanel from '@/components/network/SectionPanel'
import RiskHeatmap from '@/components/network/RiskHeatmap'
import ExplainDrawer from '@/components/optimize/ExplainDrawer'
import { StatusLegend, DataTag } from '@/components/common/StatusChip'
import { networkStateAt } from '@/lib/optimizer'
import { DAYS, clock } from '@/lib/format'

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

  useEffect(() => {
    document.title = 'Digital twin — RailOpt'
  }, [])

  const day = Math.floor(minutes / 1440)
  const timeOfDay = Math.floor(minutes % 1440)
  const snapshot = useMemo(() => networkStateAt(day, timeOfDay), [day, timeOfDay])

  const handleTime = useCallback((next) => {
    setMinutes((m) => (typeof next === 'function' ? next(m) : next))
  }, [])

  return (
    <>
      <PageHeader
        title="Railway digital twin"
        description="The division's sections, played through the planning week. Drag the timeline to move simulated time; select any section for the work on it."
      >
        <span className="flex items-center gap-2 rounded-panel border border-warn/35 bg-warn/10 px-3 py-1.5 font-mono text-[11px] tracking-[0.14em] text-warn">
          <Radio size={12} aria-hidden="true" />
          SIMULATION MODE
        </span>
      </PageHeader>

      <div className="space-y-5 px-5 py-6 sm:px-8">
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
              <h2 className="text-[15px] font-semibold">Division schematic</h2>
              <DataTag kind="demo" />
            </div>
            <div className="px-2 py-4 sm:px-4">
              <RailwayNetwork
                sectionStates={snapshot.sections}
                selected={selected}
                onSelect={setSelected}
              />
            </div>
            <div className="border-t border-hair px-5 py-3.5 sm:px-6">
              <StatusLegend />
              <p className="mt-2.5 text-[12px] leading-relaxed text-faint">
                Station codes and corridor shapes follow real trunk routes. The states on them
                are this prototype&rsquo;s plan, not live block working.
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
