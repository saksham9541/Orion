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
} from '@/data/indianRailwaysData'

// Re-export stations for backward compatibility with pages importing STATIONS
export const STATIONS = INDIAN_STATIONS

// Geographic centre of India
const INDIA_CENTER = [22.8000, 79.2000]
const INDIA_INITIAL_ZOOM = 5
const INDIA_MIN_ZOOM = 4

// Strict Indian Subcontinent bounding box: locks view strictly to India
const INDIA_BOUNDS = [
  [6.0, 67.0],   // Southwest: Indian Ocean / Arabian Sea
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
  '&copy; <a href="https://www.esri.com/" target="_blank" rel="noreferrer">Esri</a>, Maxar, Earthstar'

// Deep, darkened technical severity palette — grounded tones, no bright neon glows
function getColor(severity, status) {
  if (status === 'RESOLVED') return '#334155' // dark slate
  switch (severity) {
    case 'CRITICAL':
      return '#991b1b' // deep dark crimson / maroon
    case 'HIGH':
      return '#9a3412' // deep dark burnt rust
    case 'MEDIUM':
      return '#854d0e' // deep dark amber / bronze
    default:
      return '#1e293b' // deep dark charcoal
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

const SEVERITY_RADIUS = { CRITICAL: 28, HIGH: 22, MEDIUM: 16, LOW: 10 }
const SEVERITY_OPACITY = { CRITICAL: 0.22, HIGH: 0.16, MEDIUM: 0.12, LOW: 0.06 }

const ROUTE_PALETTE = {
  amber: { label: 'Amber', color: '#ea580c' }, // Classic railway orange (OpenRailwayMap standard)
  crimson: { label: 'Crimson', color: '#b91c1c' }, // Deep Nothing Red
  cyan: { label: 'Cyan', color: '#0284c7' }, // Deep tactical cyan
  slate: { label: 'Slate', color: '#64748b' }, // Dark technical slate
}

export default function IndiaRailwayMap({
  issues = [],
  selectedIssueId,
  onSelectIssue,
  showHeatmap = false,
  trains = [],
}) {
  const [mapMode, setMapMode] = useState('satellite') // 'satellite' | 'dark'
  const [routeTheme, setRouteTheme] = useState('amber') // default to classic Railway Amber/Orange

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

  const activeRouteColor = ROUTE_PALETTE[routeTheme]?.color || '#ea580c'

  return (
    <div className="w-full h-full relative overflow-hidden bg-slate-950 border border-line rounded-lg isolate z-0">
      {/* Sleek Minimalist HUD Controls */}
      <div className="absolute top-3 right-3 z-[1000] flex items-center gap-1.5 bg-black/85 backdrop-blur-md px-2 py-1 rounded-md border border-white/15 shadow-lg">
        <button
          type="button"
          onClick={() => setMapMode((m) => (m === 'satellite' ? 'dark' : 'satellite'))}
          className="px-2 py-0.5 rounded text-[10px] font-mono tracking-wider uppercase text-white/80 hover:text-white transition-colors"
          title="Toggle Satellite Terrain / Dark Tactical Basemap"
        >
          {mapMode === 'satellite' ? '🛰️ Satellite' : '🗺️ Dark'}
        </button>

        <div className="w-[1px] h-3.5 bg-white/20 mx-0.5" />

        <div className="flex items-center gap-1.5">
          <span className="text-[9px] font-mono text-white/50 uppercase tracking-widest">Route:</span>
          {Object.entries(ROUTE_PALETTE).map(([key, item]) => (
            <button
              key={key}
              type="button"
              onClick={() => setRouteTheme(key)}
              className={`w-3.5 h-3.5 rounded-full border transition-transform ${
                routeTheme === key
                  ? 'border-white scale-110 shadow-sm'
                  : 'border-transparent opacity-50 hover:opacity-100 hover:scale-105'
              }`}
              style={{ backgroundColor: item.color }}
              title={`Switch route color to ${item.label}`}
            />
          ))}
        </div>
      </div>

      {/* Clean Subtle Network Watermark */}
      <div className="absolute bottom-2 left-2 z-[1000] pointer-events-none bg-black/60 backdrop-blur-md border border-white/10 px-2 py-0.5 rounded text-[10px] font-mono text-white/50 tracking-widest uppercase">
        IR Domestic Network
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
            {/* Clean White Sovereign Boundaries & Labels (NO foreign railway tracks) */}
            <TileLayer
              url={ESRI_REFERENCE_URL}
              maxZoom={18}
              opacity={0.8}
            />
          </>
        ) : (
          <TileLayer
            attribution='&copy; <a href="https://carto.com/">CARTO</a>'
            url={CARTO_DARK_URL}
            maxZoom={19}
          />
        )}

        {/* 2. Domestic Indian Rail Corridors — Dark-cased Railway Tracks with Distinct Route Color */}
        {INDIAN_RAIL_CORRIDORS.map((corridor) => (
          <Fragment key={corridor.id}>
            {/* Dark track casing for high ground contrast */}
            <Polyline
              positions={corridor.coords}
              pathOptions={{
                color: '#000000',
                weight: 3.4,
                opacity: 0.85,
                lineCap: 'round',
                lineJoin: 'round',
              }}
            />
            {/* Vibrant, clean railway route line */}
            <Polyline
              positions={corridor.coords}
              pathOptions={{
                color: activeRouteColor,
                weight: 1.8,
                opacity: 0.9,
                lineCap: 'round',
                lineJoin: 'round',
              }}
            >
              <Tooltip sticky direction="top" opacity={0.9}>
                <div className="font-sans text-xs">
                  <p className="font-bold text-slate-900">{corridor.name}</p>
                  <p className="text-[10px] text-slate-500 font-mono mt-0.5">
                    Domestic Railway Corridor
                  </p>
                </div>
              </Tooltip>
            </Polyline>
          </Fragment>
        ))}

        {/* 3. Risk Heatmap: Soft, subtle wash ONLY on stations with active unresolved issues */}
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

        {/* 4. Live Trains (ONLY real trains from backend prop — Darkened, sleek markers) */}
        {trains &&
          trains.length > 0 &&
          trains.map((train, idx) => {
            const isDelayed = train.delay_minutes > 0
            const lat = train.lat || (STATIONS[idx % STATIONS.length].lat + 0.2)
            const lng = train.lng || (STATIONS[idx % STATIONS.length].lng + 0.2)
            const color = isDelayed ? '#991b1b' : '#0f172a'

            return (
              <CircleMarker
                key={`live-train-${train.train_number || idx}`}
                center={[lat, lng]}
                radius={3.5}
                color="#000000"
                weight={1.5}
                fillColor={color}
                fillOpacity={1}
              >
                <Tooltip direction="top" offset={[0, -6]} opacity={0.95}>
                  <div className="font-sans text-xs">
                    <p className="font-bold text-slate-900">
                      🚆 {train.train_name} ({train.train_number})
                    </p>
                    <p className="text-[10px] font-mono mt-0.5" style={{ color: isDelayed ? '#ea580c' : '#16a34a' }}>
                      {isDelayed ? `DELAYED: ${train.delay_minutes}m` : 'ON TIME'}
                    </p>
                  </div>
                </Tooltip>
              </CircleMarker>
            )
          })}

        {/* 5. Indian Railway Stations — Darkened, deep technical dots */}
        {STATIONS.map((s) => {
          const issue = issuesByStation[s.id]
          const hasIssue = Boolean(issue)
          const isResolved = hasIssue && issue.status === 'RESOLVED'
          const isSelected = hasIssue && selectedIssueId === issue.id
          const dotColor = hasIssue ? getColor(issue.severity, issue.status) : '#090d16'
          const borderColor = hasIssue ? '#000000' : '#1e293b'
          const radius = isSelected ? 7 : hasIssue && !isResolved ? 5.5 : 3.5

          // Only keep label permanently visible if it's the selected station or has an active issue
          const showPermanentLabel = isSelected || (hasIssue && !isResolved)

          return (
            <Fragment key={`${s.id}-${issue?.status || 'none'}`}>
              {/* Subtle darkened accent ring around stations with active issues */}
              {hasIssue && !isResolved && (
                <CircleMarker
                  center={[s.lat, s.lng]}
                  radius={radius + 3.5}
                  color={dotColor}
                  weight={1.2}
                  opacity={0.4}
                  fillColor="transparent"
                  interactive={false}
                />
              )}

              {/* Darkened station marker dot */}
              <CircleMarker
                center={[s.lat, s.lng]}
                radius={radius}
                color={borderColor}
                weight={2}
                fillColor={dotColor}
                fillOpacity={1}
                eventHandlers={{
                  click: () => hasIssue && onSelectIssue?.(issue.id),
                }}
                className={hasIssue ? 'cursor-pointer' : undefined}
              >
                <Tooltip
                  permanent={showPermanentLabel}
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
                      <p className="mt-0.5 uppercase tracking-wide text-[10px] font-mono font-bold" style={{ color: dotColor }}>
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
