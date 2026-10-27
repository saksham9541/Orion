import { Fragment, useEffect, useMemo, useState } from 'react'
import {
  MapContainer,
  TileLayer,
  Polyline,
  CircleMarker,
  Tooltip,
  Popup,
  useMap,
} from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import {
  INDIAN_STATIONS,
  INDIAN_RAIL_CORRIDORS,
  ACTIVE_INDIAN_FLEET,
} from '@/data/indianRailwaysData'

// Re-export stations for backward compatibility with pages importing STATIONS
export const STATIONS = INDIAN_STATIONS

// Geographic centre of India
const INDIA_CENTER = [22.8000, 79.2000]
const INDIA_INITIAL_ZOOM = 5
const INDIA_MIN_ZOOM = 4

// Strict Indian Subcontinent bounding box: prevents drifting outside South Asia
const INDIA_BOUNDS = [
  [6.0, 67.0],   // Southwest: southern tip of India / Arabian Sea
  [37.5, 97.8],  // Northeast: Kashmir & Arunachal Pradesh
]

// Basemap layer URLs
const ESRI_SATELLITE_URL =
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
const ESRI_REFERENCE_URL =
  'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}'
const CARTO_DARK_URL =
  'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'

const ESRI_ATTRIBUTION =
  '&copy; <a href="https://www.esri.com/" target="_blank" rel="noreferrer">Esri</a>, Maxar, Earthstar Geographics'

function getColor(severity, status) {
  if (status === 'RESOLVED') return '#64748b' // slate-500
  switch (severity) {
    case 'CRITICAL':
      return '#ef4444' // red-500
    case 'HIGH':
      return '#f97316' // orange-500
    case 'MEDIUM':
      return '#facc15' // yellow-400
    default:
      return '#22c55e' // green-500
  }
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

function FlyToSelection({ station }) {
  const map = useMap()
  useEffect(() => {
    if (!station) return
    const targetZoom = Math.max(map.getZoom(), 6)
    map.flyTo([station.lat, station.lng], targetZoom, { duration: 0.6 })
  }, [station, map])
  return null
}

const SEVERITY_RADIUS = { CRITICAL: 36, HIGH: 28, MEDIUM: 20, LOW: 14 }
const SEVERITY_OPACITY = { CRITICAL: 0.35, HIGH: 0.28, MEDIUM: 0.2, LOW: 0.12 }

export default function IndiaRailwayMap({
  issues = [],
  selectedIssueId,
  onSelectIssue,
  showHeatmap = false,
  trains = [],
}) {
  const [mapMode, setMapMode] = useState('satellite') // 'satellite' | 'dark'
  const [showCorridors, setShowCorridors] = useState(true)
  const [showFleet, setShowFleet] = useState(true)

  const issuesByStation = useMemo(
    () =>
      (issues || []).reduce((acc, issue) => {
        acc[issue.locationId] = issue
        return acc
      }, {}),
    [issues]
  )

  const selectedStation = useMemo(() => {
    const issue = (issues || []).find((i) => i.id === selectedIssueId)
    if (!issue) return null
    return STATIONS.find((s) => s.id === issue.locationId) ?? null
  }, [issues, selectedIssueId])

  // Merge built-in Indian active fleet with any dynamic trains passed via props
  const allTrains = useMemo(() => {
    if (!trains || trains.length === 0) {
      return ACTIVE_INDIAN_FLEET
    }
    // If backend provided live trains, map them to station coordinates
    const mappedDynamic = trains.map((t, idx) => {
      const baseStation = STATIONS[idx % STATIONS.length]
      return {
        number: t.train_number || `IR-${1000 + idx}`,
        name: t.train_name || 'Express Special',
        lat: baseStation.lat + ((idx % 3) - 1) * 0.45,
        lng: baseStation.lng + (((idx + 1) % 3) - 1) * 0.45,
        speed: t.speed || 110,
        color: t.delay_minutes > 0 ? '#ef4444' : '#00f0ff',
        status: t.delay_minutes > 0 ? `DELAYED ${t.delay_minutes}m` : 'ON TIME',
        route: `${baseStation.name} Express`,
      }
    })
    return [...ACTIVE_INDIAN_FLEET, ...mappedDynamic]
  }, [trains])

  return (
    <div className="w-full h-full relative overflow-hidden bg-slate-950 border border-slate-800 rounded-lg isolate z-0">
      {/* Map Control HUD Overlay */}
      <div className="absolute top-3 right-3 z-[1000] flex items-center gap-1.5 bg-slate-900/90 backdrop-blur-md border border-slate-700/70 p-1.5 rounded-lg shadow-xl text-xs font-mono text-slate-200">
        <button
          type="button"
          onClick={() => setMapMode((m) => (m === 'satellite' ? 'dark' : 'satellite'))}
          className={`px-2.5 py-1 rounded transition-colors flex items-center gap-1.5 font-medium ${
            mapMode === 'satellite'
              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
              : 'hover:bg-slate-800 text-slate-400'
          }`}
          title="Toggle Satellite Terrain / Dark Tactical Basemap"
        >
          <span>{mapMode === 'satellite' ? '🛰️ Satellite' : '🗺️ Dark'}</span>
        </button>

        <button
          type="button"
          onClick={() => setShowCorridors((v) => !v)}
          className={`px-2.5 py-1 rounded transition-colors flex items-center gap-1 font-medium ${
            showCorridors
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
              : 'hover:bg-slate-800 text-slate-500'
          }`}
          title="Toggle Domestic Indian Railway Corridors"
        >
          <span>Tracks ({INDIAN_RAIL_CORRIDORS.length})</span>
        </button>

        <button
          type="button"
          onClick={() => setShowFleet((v) => !v)}
          className={`px-2.5 py-1 rounded transition-colors flex items-center gap-1 font-medium ${
            showFleet
              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
              : 'hover:bg-slate-800 text-slate-500'
          }`}
          title="Toggle Active Indian Fleet"
        >
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse inline-block" />
          <span>Fleet ({allTrains.length})</span>
        </button>
      </div>

      {/* Network Domain Indicator */}
      <div className="absolute bottom-3 left-3 z-[1000] pointer-events-none bg-slate-950/80 backdrop-blur-md border border-slate-800/80 px-2.5 py-1.5 rounded-md text-[11px] font-mono text-slate-400 flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-cyan-400 inline-block animate-ping" />
        <span className="text-slate-200 font-semibold tracking-wider">INDIAN RAILWAYS DOMESTIC NETWORK</span>
        <span className="text-slate-500">|</span>
        <span className="text-slate-400">Strict Sovereign Boundary</span>
      </div>

      <MapContainer
        center={INDIA_CENTER}
        zoom={INDIA_INITIAL_ZOOM}
        minZoom={INDIA_MIN_ZOOM}
        maxBounds={INDIA_BOUNDS}
        maxBoundsViscosity={1.0}
        scrollWheelZoom
        style={{ width: '100%', height: '100%', background: '#090d16' }}
      >
        <ResizeHandler />
        <FlyToSelection station={selectedStation} />

        {/* 1. Base Layer: Photorealistic Satellite Imagery OR Dark Tactical */}
        {mapMode === 'satellite' ? (
          <>
            <TileLayer
              attribution={ESRI_ATTRIBUTION}
              url={ESRI_SATELLITE_URL}
              maxZoom={18}
            />
            {/* Country/State Borders and Clean White Place Names (No foreign railway lines) */}
            <TileLayer
              url={ESRI_REFERENCE_URL}
              maxZoom={18}
              opacity={0.85}
            />
          </>
        ) : (
          <TileLayer
            attribution='&copy; <a href="https://carto.com/">CARTO</a>'
            url={CARTO_DARK_URL}
            maxZoom={19}
          />
        )}

        {/* 2. Domestic Indian Rail Corridors (Only strictly within India) */}
        {showCorridors &&
          INDIAN_RAIL_CORRIDORS.map((corridor) => (
            <Fragment key={corridor.id}>
              {/* Outer dark casing for high contrast against satellite terrain */}
              <Polyline
                positions={corridor.coords}
                pathOptions={{
                  color: '#020617',
                  weight: 4.5,
                  opacity: 0.9,
                  lineCap: 'round',
                  lineJoin: 'round',
                }}
              />
              {/* Vibrant inner rail track line */}
              <Polyline
                positions={corridor.coords}
                pathOptions={{
                  color: corridor.color || '#00f0ff',
                  weight: 2.2,
                  opacity: 0.95,
                  lineCap: 'round',
                  lineJoin: 'round',
                }}
              >
                <Tooltip sticky direction="top" opacity={0.95}>
                  <div className="font-sans text-xs">
                    <p className="font-bold text-slate-900">{corridor.name}</p>
                    <p className="text-[10px] text-slate-500 font-mono mt-0.5">
                      Domestic Trunk Line · {corridor.coords.length} waypoints
                    </p>
                  </div>
                </Tooltip>
              </Polyline>
            </Fragment>
          ))}

        {/* 3. Risk Heatmap: Centred strictly on Indian stations */}
        {showHeatmap &&
          STATIONS.map((s) => {
            const issue = issuesByStation[s.id]
            if (!issue || issue.status === 'RESOLVED') return null
            return (
              <CircleMarker
                key={`heat-${s.id}`}
                center={[s.lat, s.lng]}
                radius={SEVERITY_RADIUS[issue.severity] ?? SEVERITY_RADIUS.LOW}
                color="transparent"
                weight={0}
                fillColor={getColor(issue.severity, issue.status)}
                fillOpacity={SEVERITY_OPACITY[issue.severity] ?? SEVERITY_OPACITY.LOW}
                interactive={false}
              />
            )
          })}

        {/* 4. Active Indian Fleet (Vande Bharat, Rajdhani, Shatabdi, DFC) */}
        {showFleet &&
          allTrains.map((train) => {
            const isDelayed = train.status?.includes('DELAYED')
            const trainColor = train.color || (isDelayed ? '#ef4444' : '#00f0ff')

            return (
              <Fragment key={`train-${train.number}`}>
                {/* Glow ring around train dot */}
                <CircleMarker
                  center={[train.lat, train.lng]}
                  radius={7}
                  color={trainColor}
                  weight={0}
                  fillColor={trainColor}
                  fillOpacity={0.25}
                  interactive={false}
                />
                {/* Crisp train glyph dot */}
                <CircleMarker
                  center={[train.lat, train.lng]}
                  radius={4}
                  color="#ffffff"
                  weight={1.5}
                  fillColor={trainColor}
                  fillOpacity={1}
                >
                  <Tooltip direction="top" offset={[0, -6]} opacity={0.95}>
                    <div className="font-sans text-xs">
                      <div className="flex items-center gap-1.5 font-bold text-slate-900">
                        <span
                          className="w-2 h-2 rounded-full inline-block"
                          style={{ backgroundColor: trainColor }}
                        />
                        <span>{train.name} ({train.number})</span>
                      </div>
                      <div className="text-[10px] text-slate-600 mt-0.5 font-mono">
                        {train.route} · {train.speed} km/h
                      </div>
                      <div
                        className="text-[10px] font-bold mt-0.5 font-mono"
                        style={{ color: isDelayed ? '#ea580c' : '#16a34a' }}
                      >
                        {train.status}
                      </div>
                    </div>
                  </Tooltip>
                </CircleMarker>
              </Fragment>
            )
          })}

        {/* 5. Major Indian Railway Junctions & Stations */}
        {STATIONS.map((s) => {
          const issue = issuesByStation[s.id]
          const hasIssue = Boolean(issue)
          const isResolved = hasIssue && issue.status === 'RESOLVED'
          const isSelected = hasIssue && selectedIssueId === issue.id
          const color = hasIssue ? getColor(issue.severity, issue.status) : '#94a3b8'
          const radius = isSelected ? 10 : hasIssue ? 7 : 4.5

          return (
            <Fragment key={`${s.id}-${issue?.status || 'none'}`}>
              {/* Soft glow beneath station with active issue */}
              {hasIssue && !isResolved && (
                <CircleMarker
                  center={[s.lat, s.lng]}
                  radius={isSelected ? 22 : 16}
                  color={color}
                  weight={0}
                  fillColor={color}
                  fillOpacity={0.3}
                  interactive={false}
                />
              )}

              <CircleMarker
                center={[s.lat, s.lng]}
                radius={radius}
                color={hasIssue ? '#ffffff' : '#0f172a'}
                weight={hasIssue ? 2 : 1.5}
                fillColor={hasIssue ? color : '#e2e8f0'}
                fillOpacity={isResolved ? 0.6 : 1}
                eventHandlers={{
                  click: () => hasIssue && onSelectIssue?.(issue.id),
                }}
                className={hasIssue ? 'cursor-pointer' : undefined}
              >
                <Tooltip
                  permanent
                  direction="right"
                  offset={[8, 0]}
                  className="railopt-station-label"
                >
                  {s.name}
                </Tooltip>

                {hasIssue && (
                  <Popup>
                    <div className="text-[12px] p-1 font-sans">
                      <p className="font-bold text-slate-900">{issue.locationName}</p>
                      <p className="mt-0.5 uppercase tracking-wide text-[10px] font-mono font-bold" style={{ color }}>
                        {isResolved ? 'RESOLVED' : issue.severity} · {issue.department}
                      </p>
                      <p className="mt-1 text-slate-700">{issue.type}</p>
                      {!isResolved && (
                        <p className="mt-1 text-[10px] uppercase tracking-wide text-slate-500 font-mono">
                          STATUS: {issue.status}
                        </p>
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
