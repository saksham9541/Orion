import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'
import RailCanvasLayer from '@/lib/RailCanvasLayer'
import { TIER_COUNT, applyRisk, loadTier, tierForZoom } from '@/lib/railNetwork'
import OsmRailLoader, { LIVE_MIN_ZOOM, tilesForBounds } from '@/lib/osmRail'

/**
 * Draws the whole Indian rail network inside a react-leaflet <MapContainer>.
 *
 * Far out only the trunk lines show; each zoom step reveals the next tier of
 * real track (see lib/railNetwork.js). Tier files are fetched on demand — the
 * next tier is prefetched one zoom level ahead so lines appear without a wait.
 *
 * Props
 *  - enabled       show / hide the layer
 *  - styles        risk styles keyed LOW | MEDIUM | HIGH | CRITICAL
 *  - corridorRank  { [corridorId]: 1..4 } risk of each named corridor
 *  - sites         [{ lat, lng, rank }] open issues (rank 2..4) colouring nearby track
 *  - onState       ({ zoom, maxTier, loading, error, live }) called when that changes
 *                  live = { active, pending, failed, loaded, wanted, ways }
 *
 * From zoom LIVE_MIN_ZOOM the exact, complete track geometry for the viewport is streamed
 * from OpenStreetMap (lib/osmRail.js) and replaces the bundled, thinned lines.
 */
export default function RailNetworkLayer({
  enabled = true,
  styles,
  corridorRank,
  sites,
  onState,
}) {
  const map = useMap()
  const layerRef = useRef(null)
  const loadedRef = useRef(new Map()) // tier -> pieces
  const riskRef = useRef({ corridorRank, sites })
  const onStateRef = useRef(onState)
  const errorRef = useRef(false)
  const loaderRef = useRef(null)
  const liveStatusRef = useRef({ pending: 0, failed: 0, loaded: 0, wanted: 0, ways: 0 })
  onStateRef.current = onState
  riskRef.current = { corridorRank, sites }

  // Create / destroy the canvas layer and keep it loading tiers as the map zooms.
  useEffect(() => {
    const layer = new RailCanvasLayer({ styles })
    layerRef.current = layer
    layer.addTo(map)
    loadedRef.current = new Map()
    const pending = new Set() // tiers currently being fetched
    let alive = true

    const report = () => {
      const zoom = map.getZoom()
      const maxTier = tierForZoom(zoom)
      let loading = false
      for (let t = 1; t <= maxTier; t++) if (!loadedRef.current.has(t)) loading = true
      onStateRef.current?.({
        zoom,
        maxTier,
        loading,
        error: errorRef.current,
        live: { active: zoom >= LIVE_MIN_ZOOM, ...liveStatusRef.current },
      })
    }

    // ---- live OpenStreetMap tiles -------------------------------------------------
    const colourLive = (pieces, all) => {
      const { corridorRank: cr, sites: s } = riskRef.current
      const todo = all ? pieces : pieces.filter((p) => !p.riskSet)
      applyRisk(todo, cr, s)
      for (const p of todo) p.riskSet = true
    }
    const loader = new OsmRailLoader({
      onChange: (pieces, tiles) => {
        if (!alive) return
        colourLive(pieces, false)
        layer.setLive(pieces, tiles)
      },
      onStatus: (st) => {
        liveStatusRef.current = st
        if (alive) report()
      },
    })
    loaderRef.current = loader

    const ensureLive = () => {
      if (map.getZoom() < LIVE_MIN_ZOOM) {
        loader.want([]) // nothing in view needs live data; drop queued tiles
        return
      }
      loader.want(tilesForBounds(map.getBounds()))
    }

    const ensure = () => {
      const want = tierForZoom(map.getZoom())
      const target = Math.min(TIER_COUNT, want + 1) // prefetch one tier ahead
      for (let t = 1; t <= target; t++) {
        if (loadedRef.current.has(t) || pending.has(t)) continue
        pending.add(t)
        loadTier(t)
          .then((pieces) => {
            if (!alive) return
            const { corridorRank: cr, sites: s } = riskRef.current
            applyRisk(pieces, cr, s)
            pending.delete(t)
            loadedRef.current.set(t, pieces)
            layer.setTier(t, pieces)
            errorRef.current = false
            report()
          })
          .catch((err) => {
            console.error(`Failed to load rail network tier ${t}`, err)
            pending.delete(t)
            errorRef.current = true
            if (alive) report()
          })
      }
      report()
    }

    ensure()
    ensureLive()
    map.on('zoomend', ensure)
    map.on('moveend', ensureLive)
    return () => {
      alive = false
      map.off('zoomend', ensure)
      map.off('moveend', ensureLive)
      loader.destroy()
      loaderRef.current = null
      layer.remove()
      layerRef.current = null
    }
    // styles is a module constant in the parent; the layer is rebuilt only if the map changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map])

  // Re-colour already-loaded tiers whenever the risk picture changes.
  useEffect(() => {
    const layer = layerRef.current
    if (!layer) return
    for (const pieces of loadedRef.current.values()) applyRisk(pieces, corridorRank, sites)
    const live = loaderRef.current?.pieces
    if (live?.length) {
      applyRisk(live, corridorRank, sites)
      for (const p of live) p.riskSet = true
    }
    layer.redraw()
  }, [corridorRank, sites])

  useEffect(() => {
    layerRef.current?.setEnabled(enabled)
  }, [enabled])

  return null
}
