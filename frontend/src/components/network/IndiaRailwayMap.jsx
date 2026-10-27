import { Fragment, useEffect, useMemo } from 'react'
import { MapContainer, TileLayer, CircleMarker, Tooltip, Popup, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

/**
 * A real, interactive map of India — OpenStreetMap for the geographic
 * basemap, OpenRailwayMap for the railway infrastructure overlay, RailOpt's
 * issue markers on top. No hand-drawn India outline, no invented x/y station
 * grid, no straight-line "corridors": the track geometry on screen is
 * OpenRailwayMap's own data, not anything this component draws.
 *
 * Station positions are the real coordinates of the named stations, so
 * panning and zooming land where the actual railway does.
 */

// Approximate real-world coordinates for each station's main terminus.
// Close enough for a control-room map at country/region zoom; swap for exact
// survey coordinates if this ever needs platform-level precision.
export const STATIONS = [
  { id: 'NDLS', name: 'Delhi', lat: 28.6435, lng: 77.2197 },
  { id: 'LDH', name: 'Ludhiana', lat: 30.9010, lng: 75.8573 },
  { id: 'ASR', name: 'Amritsar', lat: 31.6336, lng: 74.8737 },
  { id: 'JP', name: 'Jaipur', lat: 26.9196, lng: 75.7878 },
  { id: 'LKO', name: 'Lucknow', lat: 26.8302, lng: 80.9151 },
  { id: 'BCT', name: 'Mumbai', lat: 18.9696, lng: 72.8205 },
  { id: 'HWH', name: 'Kolkata', lat: 22.5831, lng: 88.3426 },
  { id: 'MAS', name: 'Chennai', lat: 13.0827, lng: 80.2707 },
  { id: 'SBC', name: 'Bengaluru', lat: 12.9779, lng: 77.5713 },
  { id: 'SC', name: 'Hyderabad', lat: 17.4399, lng: 78.5011 },
]

// Roughly the geographic centre of India; zoom 5 keeps the whole country in
// frame on first load without the operator having to zoom out.
const INDIA_CENTER = [22.9734, 78.6569]
const INDIA_INITIAL_ZOOM = 5
const INDIA_MIN_ZOOM = 4

const OSM_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors'
const ORM_ATTRIBUTION =
  'Rail infrastructure: <a href="https://www.openrailwaymap.org/" target="_blank" rel="noreferrer">OpenRailwayMap</a>'

function getColor(severity, status) {
  if (status === 'RESOLVED') return '#64748b' // slate-500 — handled, no longer an active concern
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

/**
 * Leaflet sizes its tiles from the container's measured dimensions at mount
 * time. This page toggles the map's container between full-width and
 * half-width when an issue is selected, and Leaflet has no way to know that
 * happened on its own — without this, the map shows blank/offset tiles until
 * the user manually drags it. A ResizeObserver on the container tells it.
 */
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

/**
 * When an issue is selected — from the map, the heatmap, or the alert
 * centre — the map itself should acknowledge it: pan to the station and
 * ease in slightly, so a click anywhere in the workflow visibly lands on
 * the same place on the map, not just opens a panel elsewhere on the page.
 */
function FlyToSelection({ station }) {
  const map = useMap()
  useEffect(() => {
    if (!station) return
    const targetZoom = Math.max(map.getZoom(), 6)
    map.flyTo([station.lat, station.lng], targetZoom, { duration: 0.6 })
  }, [station, map])
  return null
}

const SEVERITY_RADIUS = { CRITICAL: 34, HIGH: 26, MEDIUM: 19, LOW: 13 }
const SEVERITY_OPACITY = { CRITICAL: 0.32, HIGH: 0.24, MEDIUM: 0.17, LOW: 0.1 }

export default function IndiaRailwayMap({ issues, selectedIssueId, onSelectIssue, showHeatmap = false, trains = [] }) {
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

  return (
    <div className="w-full h-full relative overflow-hidden bg-[#f8fafc] border border-slate-200 rounded-lg">
      <MapContainer
        center={INDIA_CENTER}
        zoom={INDIA_INITIAL_ZOOM}
        minZoom={INDIA_MIN_ZOOM}
        scrollWheelZoom
        style={{ width: '100%', height: '100%' }}
      >
        <ResizeHandler />
        <FlyToSelection station={selectedStation} />

        {/* Base layer: real geography from OpenStreetMap. */}
        <TileLayer
          attribution={OSM_ATTRIBUTION}
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {/* Overlay: actual railway infrastructure from OpenRailwayMap. This
            is the only source of track geometry on this map — nothing here
            draws its own lines between stations. */}
        <TileLayer
          attribution={ORM_ATTRIBUTION}
          url="https://tiles.openrailwaymap.org/standard/{z}/{x}/{y}.png"
          opacity={0.85}
          maxZoom={19}
        />

        {/* Risk heatmap: large, low-opacity, colour-by-severity circles
            centred on the SAME station coordinates the markers use below —
            geographically tied to the map, not screen-space decoration.
            Rendered before the markers so the crisp marker dots sit on top
            of the soft heat wash rather than under it. Resolved issues carry
            no heat: the heatmap answers "where are the current problems",
            not "where has anything ever happened". */}
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

        {/* RailOpt issue markers, on top of both. */}
        {STATIONS.map((s) => {
          const issue = issuesByStation[s.id]
          const hasIssue = Boolean(issue)
          const isResolved = hasIssue && issue.status === 'RESOLVED'
          const isSelected = hasIssue && selectedIssueId === issue.id
          const color = hasIssue ? getColor(issue.severity, issue.status) : '#64748b'
          const radius = isSelected ? 11 : hasIssue ? 8 : 5

          return (
            <Fragment key={`${s.id}-${issue?.status || 'none'}`}>
              {/* A soft glow beneath any station currently carrying an
                  active issue. Resolved issues lose the glow — the point of
                  the glow is to draw the eye to something that still needs
                  attention. */}
              {hasIssue && !isResolved && (
                <CircleMarker
                  center={[s.lat, s.lng]}
                  radius={isSelected ? 22 : 16}
                  color={color}
                  weight={0}
                  fillColor={color}
                  fillOpacity={0.22}
                  interactive={false}
                />
              )}

              <CircleMarker
                center={[s.lat, s.lng]}
                radius={radius}
                color={hasIssue ? '#ffffff' : '#64748b'}
                weight={2}
                fillColor={hasIssue ? color : '#f8fafc'}
                fillOpacity={isResolved ? 0.6 : 1}
                eventHandlers={{
                  click: () => hasIssue && onSelectIssue?.(issue.id),
                }}
                className={hasIssue ? 'cursor-pointer' : undefined}
              >
                <Tooltip permanent direction="right" offset={[10, 0]} className="railopt-station-label">
                  {s.name}
                </Tooltip>

                {hasIssue && (
                  <Popup>
                    <div className="text-[12px]">
                      <p className="font-semibold text-slate-800">{issue.locationName}</p>
                      <p className="mt-0.5 uppercase tracking-wide text-[10px]" style={{ color }}>
                        {isResolved ? 'RESOLVED' : issue.severity} · {issue.department}
                      </p>
                      <p className="mt-1 text-slate-600">{issue.type}</p>
                      {!isResolved && (
                        <p className="mt-1 text-[10px] uppercase tracking-wide text-slate-400">
                          {issue.status}
                        </p>
                      )}
                    </div>
                  </Popup>
                )}
              </CircleMarker>
            </Fragment>
          )
        })}

          {/* Render live trains */}
          {trains.map((train, i) => {
            // Pseudo-random position near the center or mapped to stations
            // We use the index to pick a station and offset it slightly to simulate movement
            const baseStation = STATIONS[i % STATIONS.length]
            const latOffset = (Math.random() - 0.5) * 2.0
            const lngOffset = (Math.random() - 0.5) * 2.0
            const lat = baseStation.lat + latOffset
            const lng = baseStation.lng + lngOffset
            const isDelayed = train.delay_minutes > 0
            const color = isDelayed ? '#ef4444' : '#3b82f6'

            return (
              <CircleMarker
                key={`train-${train.train_number}-${i}`}
                center={[lat, lng]}
                radius={6}
                color="#ffffff"
                weight={2}
                fillColor={color}
                fillOpacity={1}
              >
                <Tooltip direction="top" offset={[0, -10]} opacity={1} permanent={false}>
                  <div className="font-sans">
                    <p className="font-bold text-slate-800 text-xs">
                      🚆 {train.train_name} ({train.train_number})
                    </p>
                    <p className="text-[10px] uppercase font-bold mt-1" style={{ color }}>
                      {isDelayed ? `DELAYED: ${train.delay_minutes} min` : 'ON TIME'}
                    </p>
                  </div>
                </Tooltip>
              </CircleMarker>
            )
          })}
      </MapContainer>
    </div>
  )
}
