import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import {
  MapContainer,
  TileLayer,
  Polyline,
  CircleMarker,
  Tooltip,
  Popup,
  useMap,
  useMapEvents,
} from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import {
  INDIAN_STATIONS,
  INDIAN_RAIL_CORRIDORS,
} from '@/data/indianRailwaysData'
import RailNetworkLayer from '@/components/network/RailNetworkLayer'
import { TIERS, TIER_COUNT, totalKm } from '@/lib/railNetwork'
import { LIVE_MIN_ZOOM } from '@/lib/osmRail'

// Re-export stations for backward compatibility with external page imports
export const STATIONS = INDIAN_STATIONS

// Geographic centre and boundaries strictly for the Indian subcontinent
const INDIA_CENTER = [22.8000, 79.2000]
const INDIA_INITIAL_ZOOM = 5
const INDIA_MIN_ZOOM = 4
const INDIA_BOUNDS = [
  [6.0, 67.0],   // Southwest: Indian Ocean / Arabian Sea
  [37.5, 97.8],  // Northeast: Kashmir & Arunachal Pradesh
]

// Basemap layer endpoints
const CARTO_DARK_URL =
  'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
const ESRI_SATELLITE_URL =
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
const ESRI_REFERENCE_URL =
  'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}'

const CARTO_ATTRIBUTION =
  '&copy; <a href="https://carto.com/" target="_blank" rel="noreferrer">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a>'
const ESRI_ATTRIBUTION =
  '&copy; <a href="https://www.esri.com/" target="_blank" rel="noreferrer">Esri</a>, Maxar, Earthstar'

// Major Indian Railway Zonal Termini (Prominent Tactical Hubs)
const MAJOR_HUBS = ['NDLS', 'BCT', 'HWH', 'MAS', 'SBC', 'SC']

// Connected station mapping to compute corridor risk levels
const CORRIDOR_STATION_MAP = {
  'COR-NDLS-ASR-JAT': ['NDLS', 'LDH', 'ASR'],
  'COR-NDLS-JP-ADI': ['NDLS', 'JP'],
  'COR-NDLS-KOTA-BCT': ['NDLS', 'BCT'],
  'COR-ADI-BRC-ST': ['JP', 'BCT'],
  'COR-NDLS-CNB-HWH': ['NDLS', 'HWH', 'LKO'],
  'COR-NDLS-LKO-BSB': ['NDLS', 'LKO'],
  'COR-NDLS-BPL-NGP': ['NDLS', 'SC'],
  'COR-NGP-BZA-MAS': ['SC', 'MAS'],
  'COR-CSMT-NGP-HWH': ['BCT', 'HWH'],
  'COR-HWH-BBS-MAS': ['HWH', 'MAS'],
  'COR-BCT-PUNE-MAS': ['BCT', 'MAS'],
  'COR-GTL-SBC': ['SBC', 'SC'],
  'COR-MAS-SBC-ERS-TVC': ['MAS', 'SBC'],
  'COR-KONKAN': ['BCT', 'SBC'],
  'COR-HWH-GHY-DBRG': ['HWH'],
}

// Professional Risk Color Hierarchy & Subtle Glowing Track Specs
const RISK_STYLES = {
  CRITICAL: {
    label: 'Critical Risk',
    glowColor: '#ef4444',
    glowWeight: 6.0,
    glowOpacity: 0.32,
    casingColor: '#030712',
    casingWeight: 3.6,
    coreColor: '#f87171',
    coreWeight: 2.2,
    coreOpacity: 1.0,
    dotColor: '#ef4444',
    badgeClass: 'bg-red-500/20 text-red-300 border-red-500/40',
  },
  HIGH: {
    label: 'High Risk',
    glowColor: '#f97316',
    glowWeight: 5.0,
    glowOpacity: 0.25,
    casingColor: '#030712',
    casingWeight: 3.2,
    coreColor: '#fb923c',
    coreWeight: 2.0,
    coreOpacity: 0.95,
    dotColor: '#f97316',
    badgeClass: 'bg-orange-500/20 text-orange-300 border-orange-500/40',
  },
  MEDIUM: {
    label: 'Moderate Risk',
    glowColor: '#eab308',
    glowWeight: 4.2,
    glowOpacity: 0.18,
    casingColor: '#030712',
    casingWeight: 2.8,
    coreColor: '#facc15',
    coreWeight: 1.8,
    coreOpacity: 0.9,
    dotColor: '#eab308',
    badgeClass: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40',
  },
  LOW: {
    label: 'Normal Flow',
    glowColor: '#10b981',
    glowWeight: 3.0,
    glowOpacity: 0.12,
    casingColor: '#030712',
    casingWeight: 2.4,
    coreColor: '#34d399',
    coreWeight: 1.6,
    coreOpacity: 0.85,
    dotColor: '#10b981',
    badgeClass: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
  },
}

const SEVERITY_RANK = {
  CRITICAL: 4,
  HIGH: 3,
  MEDIUM: 2,
  LOW: 1,
}

// Returns the previous reference while the value is deeply unchanged, so
// effects that depend on it don't re-run (and re-colour 16k track pieces)
// every time the parent re-renders with an equal-but-new array/object.
function useStableValue(value) {
  const ref = useRef(value)
  if (JSON.stringify(ref.current) !== JSON.stringify(value)) ref.current = value
  return ref.current
}

const formatKm = (km) => (km >= 1000 ? `${(km / 1000).toFixed(km >= 10000 ? 0 : 1)}k` : `${km}`)

// Compute corridor risk based on active (unresolved) issues
function getCorridorRisk(corridor, issues = []) {
  if (!issues || issues.length === 0) return 'LOW'

  const connectedStations = CORRIDOR_STATION_MAP[corridor.id] || []
  let highestSeverity = 'LOW'

  for (const issue of issues) {
    if (issue.status === 'RESOLVED') continue

    const isAtStation = connectedStations.includes(issue.locationId)
    const cName = (corridor.name || '').toLowerCase()
    const locName = (issue.locationName || '').toLowerCase()
    const exactLoc = (issue.exactLocation || '').toLowerCase()
    const isNamed =
      locName.includes(corridor.id.toLowerCase()) ||
      (locName.length > 3 && cName.includes(locName)) ||
      (exactLoc.length > 3 && cName.includes(exactLoc))

    if (isAtStation || isNamed) {
      const sev = (issue.severity || 'LOW').toUpperCase()
      if ((SEVERITY_RANK[sev] || 1) > (SEVERITY_RANK[highestSeverity] || 1)) {
        highestSeverity = sev
      }
    }
  }

  return highestSeverity
}

function ResizeHandler() {
  const map = useMap()
  useEffect(() => {
    const container = map.getContainer()
    const observer = new ResizeObserver(() => map.invalidateSize())
    observer.observe(container)
    return () => observer.disconnect()
  }, [map])
  return null
}

// Scroll-wheel zoom is only active while the map is expanded, so scrolling
// over a collapsed map scrolls the page instead of zooming the map.
function WheelZoomToggle({ enabled }) {
  const map = useMap()
  useEffect(() => {
    if (enabled) map.scrollWheelZoom.enable()
    else map.scrollWheelZoom.disable()
  }, [map, enabled])
  return null
}

// Clicking empty map (not a station / track line) expands the map.
function ExpandOnClick({ onExpand }) {
  useMapEvents({
    click(e) {
      const target = e.originalEvent?.target
      if (target && target.closest && target.closest('.leaflet-interactive')) return
      onExpand()
    },
  })
  return null
}

function FlyToSelection({ station }) {
  const map = useMap()
  useEffect(() => {
    if (!station) return
    const targetZoom = Math.max(map.getZoom(), 6)
    map.flyTo([station.lat, station.lng], targetZoom, { duration: 0.6 })
  }, [station, map])
  return null
}

// Custom Dark Translucent Zoom & Navigation Controls
function CustomMapControls({ center, initialZoom }) {
  const map = useMap()
  return (
    <div className="absolute top-3 left-3 z-[1000] flex flex-col rounded-lg bg-slate-950/85 backdrop-blur-md border border-slate-700/70 shadow-2xl overflow-hidden divide-y divide-slate-800">
      <button
        type="button"
        onClick={() => map.zoomIn()}
        aria-label="Zoom In"
        className="w-8 h-8 flex items-center justify-center text-slate-300 hover:text-white hover:bg-slate-800/80 active:bg-slate-700 transition-colors text-base font-semibold"
        title="Zoom In"
      >
        +
      </button>
      <button
        type="button"
        onClick={() => map.zoomOut()}
        aria-label="Zoom Out"
        className="w-8 h-8 flex items-center justify-center text-slate-300 hover:text-white hover:bg-slate-800/80 active:bg-slate-700 transition-colors text-base font-semibold"
        title="Zoom Out"
      >
        −
      </button>
      <button
        type="button"
        onClick={() => map.flyTo(center, initialZoom, { duration: 0.6 })}
        aria-label="Reset Map View"
        className="w-8 h-8 flex items-center justify-center text-slate-400 hover:text-cyan-400 hover:bg-slate-800/80 transition-colors text-xs"
        title="Reset to Central India view"
      >
        ⛶
      </button>
    </div>
  )
}

export default function IndiaRailwayMap({
  issues = [],
  selectedIssueId,
  onSelectIssue,
  showHeatmap = false,
  trains = [],
}) {
  // Photorealistic satellite imagery as default basemap
  const mapMode = 'satellite'
  const [expanded, setExpanded] = useState(false)

  // Esc closes the expanded map; page scroll is locked while it is open.
  useEffect(() => {
    if (!expanded) return undefined
    const onKey = (e) => e.key === 'Escape' && setExpanded(false)
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = prevOverflow
    }
  }, [expanded])
  const [showCorridors, setShowCorridors] = useState(true)
  // Reported by <RailNetworkLayer>: current zoom, tiers unlocked, loading / error
  const [track, setTrack] = useState({
    zoom: INDIA_INITIAL_ZOOM,
    maxTier: 1,
    loading: true,
    error: false,
    live: { active: false, pending: 0, failed: 0, loaded: 0, wanted: 0, ways: 0 },
  })
  const handleTrackState = (next) =>
    setTrack((prev) => {
      const a = prev.live
      const b = next.live
      return prev.zoom === next.zoom &&
        prev.maxTier === next.maxTier &&
        prev.loading === next.loading &&
        prev.error === next.error &&
        a.active === b.active &&
        a.pending === b.pending &&
        a.failed === b.failed &&
        a.loaded === b.loaded &&
        a.wanted === b.wanted
        ? prev
        : next
    })

  // Risk of each named corridor (existing station → corridor model) ...
  const corridorRank = useStableValue(
    useMemo(() => {
      const out = {}
      for (const c of INDIAN_RAIL_CORRIDORS) {
        out[c.id] = SEVERITY_RANK[getCorridorRisk(c, issues)] || 1
      }
      return out
    }, [issues])
  )

  // ... plus every open issue, so track near it (not only on the 15 corridors) is coloured too.
  const sites = useStableValue(
    useMemo(
      () =>
        (issues || [])
          .filter((i) => i.status !== 'RESOLVED')
          .map((i) => {
            const st = STATIONS.find((x) => x.id === i.locationId)
            const rank = SEVERITY_RANK[(i.severity || 'LOW').toUpperCase()] || 1
            return st ? { lat: st.lat, lng: st.lng, rank } : null
          })
          .filter(Boolean),
      [issues]
    )
  )

  const issuesByStation = useMemo(
    () =>
      (issues || []).reduce((acc, issue) => {
        acc[issue.locationId] = issue
        return acc
      }, {}),
    [issues]
  )

  const activeIssuesCount = useMemo(
    () => (issues || []).filter((i) => i.status !== 'RESOLVED').length,
    [issues]
  )

  const selectedStation = useMemo(() => {
    const issue = (issues || []).find((i) => i.id === selectedIssueId)
    if (!issue) return null
    return STATIONS.find((s) => s.id === issue.locationId) ?? null
  }, [issues, selectedIssueId])

  return (
    <div
      className={`railopt-map-container relative overflow-hidden bg-[#070b14] border border-slate-800 isolate ${
        expanded ? 'fixed inset-0 z-[2000] w-screen h-screen rounded-none' : 'w-full h-full rounded-lg z-0'
      }`}
    >
      {expanded && (
        <button
          type="button"
          onClick={() => setExpanded(false)}
          aria-label="Back"
          title="Back (Esc)"
          className="absolute top-3 left-14 z-[1001] rounded-lg bg-slate-950/85 backdrop-blur-md border border-slate-700/70 px-3 h-8 text-[12px] font-semibold text-slate-200 hover:text-white hover:bg-slate-800/80 shadow-2xl"
        >
          ← Back
        </button>
      )}
      {/* Top-Right Refined Command Bar */}
      <div className="absolute top-3 right-3 z-[1000] flex items-center gap-1.5 bg-slate-950/85 backdrop-blur-md px-2.5 py-1.5 rounded-lg border border-slate-700/70 shadow-2xl text-[11px] font-mono text-slate-300">
        {/* Satellite Mode Badge */}
        <div
          className="flex items-center gap-1 px-2.5 py-1 rounded bg-slate-900/90 border border-amber-500/30 text-amber-300 font-medium shadow-sm"
          title="Esri Photorealistic Satellite View"
        >
          <span>🛰️ Satellite</span>
        </div>

        <div className="w-[1px] h-4 bg-slate-800 mx-0.5" />

        {/* Corridor Tracks Toggle */}
        <button
          type="button"
          onClick={() => setShowCorridors((v) => !v)}
          className={`px-2.5 py-1 rounded transition-all border font-medium ${
            showCorridors
              ? 'bg-slate-900 text-slate-200 border-slate-700'
              : 'text-slate-500 border-transparent hover:text-slate-300'
          }`}
          title={`Toggle railway tracks — showing ${TIERS[track.maxTier - 1].name.toLowerCase()} lines and above (zoom in for more)`}
        >
          {track.live.active ? 'Tracks · live OSM' : `Tracks · ${formatKm(totalKm(track.maxTier))} km`}
          {track.loading && showCorridors && <span className="ml-1 text-slate-500">…</span>}
        </button>

        {/* Live Active Risks Counter Badge */}
        <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-slate-900/80 border border-slate-800 text-[10px]">
          <span
            className={`w-2 h-2 rounded-full inline-block ${
              activeIssuesCount > 0 ? 'bg-red-400 animate-pulse' : 'bg-emerald-400'
            }`}
          />
          <span className="text-slate-400">
            {activeIssuesCount} {activeIssuesCount === 1 ? 'Risk' : 'Risks'}
          </span>
        </div>
      </div>

      {/* Bottom-Left Network Detail Indicator: which track tiers the current zoom reveals */}
      {showCorridors && (
        <div className="absolute bottom-[50px] left-3 z-[1000] pointer-events-none bg-slate-950/85 backdrop-blur-md border border-slate-700/70 px-2.5 py-1 rounded-lg shadow-2xl text-[10px] font-mono flex items-center gap-2">
          <span className="text-slate-400 font-semibold tracking-wider uppercase border-r border-slate-800 pr-2">
            Detail
          </span>
          {TIERS.map((t) => {
            const on = t.id <= track.maxTier
            return (
              <span
                key={t.id}
                className={`flex items-center gap-1 ${on ? 'text-slate-200' : 'text-slate-600'}`}
              >
                <span
                  className="inline-block rounded-full bg-current"
                  style={{ width: 14, height: Math.max(1, 3.4 - t.id * 0.5), opacity: on ? 1 : 0.5 }}
                />
                {t.name}
              </span>
            )
          })}
          {!track.live.active && (
            <span className="text-cyan-400/80 border-l border-slate-800 pl-2">
              zoom to {LIVE_MIN_ZOOM}+ for every real track
            </span>
          )}
          {track.live.active && (
            <span
              className={`border-l border-slate-800 pl-2 ${
                track.live.failed > 0 && track.live.pending === 0
                  ? 'text-amber-400'
                  : track.live.pending > 0
                  ? 'text-cyan-400/80'
                  : 'text-emerald-400/90'
              }`}
            >
              {track.live.pending > 0
                ? `loading exact tracks · ${track.live.loaded}/${track.live.wanted} tiles`
                : track.live.failed > 0
                ? `OpenStreetMap unreachable for ${track.live.failed} tile${track.live.failed > 1 ? 's' : ''} · showing built-in lines there`
                : 'every track · live OpenStreetMap'}
            </span>
          )}
        </div>
      )}

      {/* Bottom-Left Unified Risk Status Legend */}
      <div className="absolute bottom-3 left-3 z-[1000] pointer-events-auto bg-slate-950/90 backdrop-blur-md border border-slate-700/70 px-3 py-1.5 rounded-lg shadow-2xl text-[10px] font-mono flex items-center gap-3">
        <span className="text-slate-400 font-semibold tracking-wider uppercase border-r border-slate-800 pr-2">
          Route Risk
        </span>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-1 rounded-full bg-red-400 shadow-[0_0_6px_rgba(239,68,68,0.7)]" />
          <span className="text-slate-300">Critical</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-1 rounded-full bg-orange-400 shadow-[0_0_6px_rgba(249,115,22,0.6)]" />
          <span className="text-slate-300">High</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-1 rounded-full bg-yellow-400 shadow-[0_0_6px_rgba(234,179,8,0.5)]" />
          <span className="text-slate-300">Medium</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-1 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(16,185,129,0.5)]" />
          <span className="text-slate-300">Low</span>
        </div>

        <div className="w-[1px] h-3.5 bg-slate-800 mx-0.5" />

        <div className="flex items-center gap-1.5 text-slate-400">
          <span className="w-2 h-2 rounded-full border border-cyan-400/80 bg-slate-900 inline-block" />
          <span>Major Hubs</span>
        </div>
      </div>

      {/* Bottom-Right Subdued Watermark */}
      <div className="absolute bottom-3 right-3 z-[1000] pointer-events-none bg-slate-950/70 backdrop-blur-md border border-slate-800/80 px-2 py-0.5 rounded text-[9.5px] font-mono text-slate-500 uppercase tracking-widest">
        IR Domestic Network · {mapMode === 'dark' ? 'CARTO Dark Matter' : 'Esri Imagery'} · Track © OpenStreetMap contributors
      </div>

      <MapContainer
        center={INDIA_CENTER}
        zoom={INDIA_INITIAL_ZOOM}
        minZoom={INDIA_MIN_ZOOM}
        maxBounds={INDIA_BOUNDS}
        maxBoundsViscosity={1.0}
        zoomControl={false}
        scrollWheelZoom={false}
        style={{ width: '100%', height: '100%', background: '#070b14' }}
      >
        <ResizeHandler />
        <WheelZoomToggle enabled={expanded} />
        <ExpandOnClick onExpand={() => setExpanded(true)} />
        <FlyToSelection station={selectedStation} />
        <CustomMapControls center={INDIA_CENTER} initialZoom={INDIA_INITIAL_ZOOM} />

        {/* 1. Basemap Layers: CARTO Dark Matter (Default) OR Esri Satellite */}
        {mapMode === 'dark' ? (
          <TileLayer
            attribution={CARTO_ATTRIBUTION}
            url={CARTO_DARK_URL}
            subdomains="abcd"
            maxZoom={20}
          />
        ) : (
          <>
            <TileLayer
              attribution={ESRI_ATTRIBUTION}
              url={ESRI_SATELLITE_URL}
              maxZoom={18}
              keepBuffer={8}
              updateWhenZooming={false}
            />
            {/* Esri "Reference" overlay (white boundary lines + labels) removed on purpose:
                its white state/district borders read as stray white lines over the tracks. */}
          </>
        )}

        {/* 2. Whole-India rail network — real OSM track geometry, revealed tier by tier as you
               zoom in (trunk lines first, then main, regional, branch, local), each piece coloured
               by risk priority. See lib/railNetwork.js and tools/railtracks/build_network.py */}
        <RailNetworkLayer
          enabled={showCorridors}
          styles={RISK_STYLES}
          corridorRank={corridorRank}
          sites={sites}
          onState={handleTrackState}
        />

        {/* Fallback if the track data fails to load: the 15 named corridors, risk coloured */}
        {showCorridors &&
          track.error &&
          INDIAN_RAIL_CORRIDORS.map((corridor) => {
            const style = RISK_STYLES[getCorridorRisk(corridor, issues)] || RISK_STYLES.LOW
            return (
              <Polyline
                key={`fallback-${corridor.id}`}
                positions={corridor.coords}
                pathOptions={{
                  color: style.coreColor,
                  weight: style.coreWeight,
                  opacity: style.coreOpacity,
                  lineCap: 'round',
                  lineJoin: 'round',
                }}
              >
                <Tooltip sticky direction="top" opacity={0.95}>
                  <span className="font-sans text-xs">{corridor.name}</span>
                </Tooltip>
              </Polyline>
            )
          })}

        {/* 3. Risk Heatmap: Soft subtle circular wash on active issue stations */}
        {showHeatmap &&
          STATIONS.map((s) => {
            const issue = issuesByStation[s.id]
            if (!issue || issue.status === 'RESOLVED') return null
            const style = RISK_STYLES[issue.severity] || RISK_STYLES.LOW
            const radius = issue.severity === 'CRITICAL' ? 32 : issue.severity === 'HIGH' ? 24 : 18

            return (
              <CircleMarker
                key={`heat-${s.id}`}
                center={[s.lat, s.lng]}
                radius={radius}
                color="transparent"
                weight={0}
                fillColor={style.dotColor}
                fillOpacity={issue.severity === 'CRITICAL' ? 0.24 : 0.16}
                interactive={false}
              />
            )
          })}

        {/* 4. Live Trains (Real trains from backend prop if provided) */}
        {trains &&
          trains.length > 0 &&
          trains.map((train, idx) => {
            const isDelayed = train.delay_minutes > 0
            const lat = train.lat || STATIONS[idx % STATIONS.length].lat + 0.15
            const lng = train.lng || STATIONS[idx % STATIONS.length].lng + 0.15

            return (
              <CircleMarker
                key={`live-train-${train.train_number || idx}`}
                center={[lat, lng]}
                radius={3.8}
                color="#030712"
                weight={1.8}
                fillColor={isDelayed ? '#ef4444' : '#f8fafc'}
                fillOpacity={1}
              >
                <Tooltip direction="top" offset={[0, -6]} opacity={0.95}>
                  <div className="font-sans text-xs">
                    <p className="font-bold text-slate-100">
                      🚆 {train.train_name} ({train.train_number})
                    </p>
                    <p className="text-[10px] font-mono mt-0.5" style={{ color: isDelayed ? '#ef4444' : '#10b981' }}>
                      {isDelayed ? `DELAYED: ${train.delay_minutes}m` : 'ON TIME'}
                    </p>
                  </div>
                </Tooltip>
              </CircleMarker>
            )
          })}

        {/* 5. Railway Station Nodes & Refined Labels */}
        {STATIONS.map((s) => {
          const isMajor = MAJOR_HUBS.includes(s.id)
          const issue = issuesByStation[s.id]
          const hasIssue = Boolean(issue)
          const isResolved = hasIssue && issue.status === 'RESOLVED'
          const isSelected = hasIssue && selectedIssueId === issue.id

          // Risk styling
          const style = hasIssue && !isResolved ? RISK_STYLES[issue.severity] : null
          const nodeColor = style ? style.dotColor : '#090d16'
          const outerBorder = isSelected
            ? '#ffffff'
            : style
            ? '#ffffff'
            : isMajor
            ? '#38bdf8'
            : '#64748b'

          const baseRadius = isMajor ? 6.5 : 4.5
          const nodeRadius = isSelected ? 8.5 : hasIssue && !isResolved ? baseRadius + 1 : baseRadius
          // Station names are always visible (previously only selected / issue stations)
          const showPermanentLabel = true

          return (
            <Fragment key={`${s.id}-${issue?.status || 'none'}`}>
              {/* Selected station target reticle */}
              {isSelected && (
                <CircleMarker
                  center={[s.lat, s.lng]}
                  radius={14}
                  color="#ffffff"
                  weight={1.8}
                  dashArray="3 3"
                  opacity={0.8}
                  fillColor="transparent"
                  interactive={false}
                />
              )}

              {/* Active issue subtle glowing pulse ring */}
              {hasIssue && !isResolved && (
                <CircleMarker
                  center={[s.lat, s.lng]}
                  radius={nodeRadius + 4}
                  color={nodeColor}
                  weight={1.2}
                  opacity={0.35}
                  fillColor="transparent"
                  interactive={false}
                />
              )}

              {/* Major Hub outer indicator halo */}
              {isMajor && !hasIssue && (
                <CircleMarker
                  center={[s.lat, s.lng]}
                  radius={nodeRadius + 3.5}
                  color="#38bdf8"
                  weight={1}
                  opacity={0.35}
                  fillColor="transparent"
                  interactive={false}
                />
              )}

              {/* Station Node Marker */}
              <CircleMarker
                center={[s.lat, s.lng]}
                radius={nodeRadius}
                color={outerBorder}
                weight={isMajor || hasIssue ? 2 : 1.5}
                fillColor={nodeColor}
                fillOpacity={1}
                eventHandlers={{
                  click: () => hasIssue && onSelectIssue?.(issue.id),
                }}
                className={hasIssue ? 'cursor-pointer' : undefined}
              >
                {/* Station Label Tooltip */}
                <Tooltip
                  permanent={showPermanentLabel}
                  direction="right"
                  offset={[10, 0]}
                  className="railopt-station-label"
                >
                  <div className="flex items-center gap-1.5 font-mono">
                    <span className="font-bold text-white tracking-wide">{s.id}</span>
                    <span className="text-slate-400 font-normal">· {s.name}</span>
                    {hasIssue && !isResolved && (
                      <span
                        className="w-1.5 h-1.5 rounded-full inline-block animate-pulse ml-0.5"
                        style={{ backgroundColor: style.dotColor }}
                        title={`${issue.severity} Risk`}
                      />
                    )}
                  </div>
                </Tooltip>

                {/* Issue Popup Card */}
                {hasIssue && (
                  <Popup>
                    <div className="text-xs font-sans text-slate-100 min-w-[200px]">
                      <div className="flex items-center justify-between gap-2 border-b border-slate-800 pb-1.5">
                        <span className="font-bold text-white font-mono">{s.name} ({s.id})</span>
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono uppercase font-bold border ${style ? style.badgeClass : 'bg-slate-800 text-slate-300'}`}>
                          {isResolved ? 'RESOLVED' : issue.severity}
                        </span>
                      </div>
                      <div className="mt-2 space-y-1">
                        <p className="text-[11px] text-slate-400 uppercase font-mono">
                          {issue.department} · {issue.type}
                        </p>
                        <p className="text-[11.5px] text-slate-200 leading-snug">
                          {issue.details?.what || issue.type}
                        </p>
                      </div>
                      {!isResolved && (
                        <div className="mt-2 pt-1.5 border-t border-slate-800/80 flex items-center justify-between text-[10px] font-mono text-slate-400">
                          <span>STATUS: {issue.status}</span>
                          <span className="text-cyan-400">Click to Inspect →</span>
                        </div>
                      )}
                    </div>
                  </Popup>
                )}
              </CircleMarker>
            </Fragment>
          )
        })}
      </MapContainer>
    </div>
  )
}
