/**
 * Canvas renderer for the zoom-tiered railway network.
 *
 * Why not <Polyline>? The full network is ~16k line pieces. As SVG elements
 * that is far too heavy; here we draw straight onto one canvas, per frame:
 *   - only tiers allowed at the current zoom (tierForZoom)
 *   - only pieces whose bounding box intersects the viewport
 *   - the simplified geometry when zoomed far out, full detail when close
 *   - one batched Path2D per (risk, tier) so a frame is a few dozen strokes
 *
 * Higher risk is always painted last, so critical routes sit on top.
 */
import L from 'leaflet'
import {
  tierForZoom,
  COARSE_MAX_ZOOM,
  RISK_KEYS,
  TIERS,
  CORRIDOR_NAMES,
} from '@/lib/railNetwork'
import { LIVE_MIN_ZOOM, SERVICE_MIN_ZOOM, tileOfMerc, tileKey } from '@/lib/osmRail'

// Line weight / opacity relative to the risk style, by tier (main lines read heavier).
const TIER_LOOK = {
  1: { w: 1.0, a: 1.0 },
  2: { w: 0.86, a: 1.0 },
  3: { w: 0.74, a: 0.95 },
  4: { w: 0.62, a: 0.9 },
  5: { w: 0.52, a: 0.85 },
}

const PANE = 'railNetworkPane'
const PICK_PX = 6

// Line weight grows with zoom up to ~z11, then eases back so that, over satellite imagery,
// the stroke stays narrower than the railway bed and never hides the track it marks.
const zoomFactor = (z) => {
  const base = Math.min(1.7, Math.max(0.5, 0.5 + (z - 4) * 0.17))
  if (z >= 16) return base * 0.5
  if (z >= 14) return base * 0.62
  if (z >= 12) return base * 0.78
  return base
}

export default class RailCanvasLayer {
  /**
   * @param {object} opts
   * @param {object} opts.styles  risk styles keyed LOW|MEDIUM|HIGH|CRITICAL
   *   ({ label, glowColor, glowWeight, glowOpacity, casingColor, casingWeight,
   *      coreColor, coreWeight, coreOpacity })
   */
  constructor({ styles }) {
    this._styles = styles
    this._tiers = new Map() // tier -> piece[]
    this._live = [] // live OpenStreetMap pieces (see lib/osmRail.js)
    this._liveTiles = new Set() // "x/y" tiles whose live data is loaded
    this._enabled = true
    this._map = null
    this._view = null
    this._hover = null
    this._pickQueued = false
    this._lastMouse = null
  }

  // ------------------------------------------------------------ lifecycle ---

  addTo(map) {
    this._map = map
    if (!map.getPane(PANE)) {
      const pane = map.createPane(PANE)
      pane.style.zIndex = 390 // above tiles, below the vector overlay (stations, heat)
      pane.style.pointerEvents = 'none'
    }
    const canvas = L.DomUtil.create('canvas', 'railopt-rail-canvas leaflet-zoom-animated')
    canvas.style.pointerEvents = 'none'
    map.getPane(PANE).appendChild(canvas)
    this._canvas = canvas
    this._ctx = canvas.getContext('2d')

    const tip = L.DomUtil.create('div', 'railopt-track-tip')
    tip.style.display = 'none'
    map.getContainer().appendChild(tip)
    this._tip = tip

    this._onMove = () => this.redraw()
    this._onMouse = (e) => this._handleMouse(e)
    this._onHide = () => this._setHover(null)
    this._onZoomAnim = (e) => this._animateZoom(e)
    map.on('move moveend zoomend resize viewreset', this._onMove)
    map.on('zoomanim', this._onZoomAnim)
    map.on('mousemove', this._onMouse)
    map.on('mouseout movestart zoomstart', this._onHide)
    this.redraw()
    return this
  }

  remove() {
    const map = this._map
    if (!map) return
    map.off('move moveend zoomend resize viewreset', this._onMove)
    map.off('zoomanim', this._onZoomAnim)
    map.off('mousemove', this._onMouse)
    map.off('mouseout movestart zoomstart', this._onHide)
    L.DomUtil.remove(this._canvas)
    L.DomUtil.remove(this._tip)
    this._map = null
    this._view = null
  }

  // ----------------------------------------------------------------- data ---

  setTier(tier, pieces) {
    this._tiers.set(tier, pieces)
    this.redraw()
  }

  /** Live OSM geometry + the set of tiles it fully covers (bundled lines inside them are hidden). */
  setLive(pieces, loadedTiles) {
    this._live = pieces || []
    this._liveTiles = loadedTiles || new Set()
    this.redraw()
  }

  setEnabled(on) {
    this._enabled = on
    if (!on) this._setHover(null)
    this.redraw()
  }

  // -------------------------------------------------------------- drawing ---

  _animateZoom(e) {
    const map = this._map
    const scale = map.getZoomScale(e.zoom)
    const offset = map._latLngToNewLayerPoint(map.getBounds().getNorthWest(), e.zoom, e.center)
    L.DomUtil.setTransform(this._canvas, offset, scale)
  }

  redraw() {
    const map = this._map
    if (!map) return
    const size = map.getSize()
    const dpr = window.devicePixelRatio || 1
    const cv = this._canvas
    const w = Math.round(size.x * dpr)
    const h = Math.round(size.y * dpr)
    if (cv.width !== w || cv.height !== h) {
      cv.width = w
      cv.height = h
      cv.style.width = `${size.x}px`
      cv.style.height = `${size.y}px`
    }
    // Pin the canvas to the viewport (drops any leftover zoom-animation transform).
    L.DomUtil.setPosition(cv, map.containerPointToLayerPoint([0, 0]))

    const ctx = this._ctx
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, size.x, size.y)
    if (!this._enabled) {
      this._view = null
      return
    }

    const z = map.getZoom()
    const maxTier = tierForZoom(z)
    const W = map.options.crs.scale(z)
    const tl = map.getPixelBounds().min
    const pad = 24
    const vx0 = (tl.x - pad) / W
    const vx1 = (tl.x + size.x + pad) / W
    const vy0 = (tl.y - pad) / W
    const vy1 = (tl.y + size.y + pad) / W
    const useCoarse = z <= COARSE_MAX_ZOOM

    const paths = new Map() // rank*8 + tier -> Path2D
    const visible = []

    const addPiece = (p, g, t) => {
      const key = p.risk * 8 + t
      let path = paths.get(key)
      if (!path) paths.set(key, (path = new Path2D()))

      const { mx, my, n } = g
      let lx = mx[0] * W - tl.x
      let ly = my[0] * W - tl.y
      path.moveTo(lx, ly)
      for (let i = 1; i < n; i++) {
        const x = mx[i] * W - tl.x
        const y = my[i] * W - tl.y
        // drop vertices closer than ~0.8 px to the last one (keep the end)
        if (i < n - 1 && (x - lx) * (x - lx) + (y - ly) * (y - ly) < 0.64) continue
        path.lineTo(x, y)
        lx = x
        ly = y
      }
      visible.push({ p, g })
    }

    // Live OpenStreetMap geometry is exact; where a tile of it is loaded it replaces the
    // bundled (thinned) lines there. Everywhere else the bundled network still draws.
    const liveOn = z >= LIVE_MIN_ZOOM && this._liveTiles.size > 0

    for (let t = 1; t <= maxTier; t++) {
      const list = this._tiers.get(t)
      if (!list) continue
      for (let k = 0; k < list.length; k++) {
        const p = list[k]
        const g = useCoarse && p.coarse ? p.coarse : p.fine
        if (g.x1 < vx0 || g.x0 > vx1 || g.y1 < vy0 || g.y0 > vy1) continue
        if (liveOn) {
          const [tx, ty] = tileOfMerc((g.x0 + g.x1) / 2, (g.y0 + g.y1) / 2)
          if (this._liveTiles.has(tileKey(tx, ty))) continue
        }
        addPiece(p, g, t)
      }
    }

    if (z >= LIVE_MIN_ZOOM) {
      const showService = z >= SERVICE_MIN_ZOOM
      const live = this._live
      for (let k = 0; k < live.length; k++) {
        const p = live[k]
        if (p.service && !showService) continue
        const g = p.fine
        if (g.x1 < vx0 || g.x0 > vx1 || g.y1 < vy0 || g.y0 > vy1) continue
        addPiece(p, g, p.tier)
      }
    }

    const zf = zoomFactor(z)
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    for (let rank = 1; rank <= 4; rank++) {
      const st = this._styles[RISK_KEYS[rank]]
      // glow → casing → core, thin tiers first so trunk lines stay crisp on top
      for (let pass = 0; pass < 3; pass++) {
        for (let t = maxTier; t >= 1; t--) {
          const path = paths.get(rank * 8 + t)
          if (!path) continue
          const look = TIER_LOOK[t]
          if (pass === 0) {
            if (rank === 1 && (t > 2 || z < 8)) continue // no glow on calm minor lines
            ctx.strokeStyle = st.glowColor
            ctx.globalAlpha = st.glowOpacity * look.a
            ctx.lineWidth = st.glowWeight * zf * look.w
          } else if (pass === 1) {
            ctx.strokeStyle = st.casingColor
            ctx.globalAlpha = 0.85 * look.a
            ctx.lineWidth = Math.max(1.1, st.casingWeight * zf * look.w)
          } else {
            ctx.strokeStyle = st.coreColor
            ctx.globalAlpha = st.coreOpacity * look.a
            ctx.lineWidth = Math.max(0.7, st.coreWeight * zf * look.w)
          }
          ctx.stroke(path)
        }
      }
    }
    ctx.globalAlpha = 1

    this._view = { W, tl, visible, zf, z }
    if (this._hover) this._drawHover(ctx)
  }

  _drawHover(ctx) {
    const v = this._view
    if (!v) return
    const { p } = this._hover
    const g = v.z <= COARSE_MAX_ZOOM && p.coarse ? p.coarse : p.fine
    ctx.beginPath()
    for (let i = 0; i < g.n; i++) {
      const x = g.mx[i] * v.W - v.tl.x
      const y = g.my[i] * v.W - v.tl.y
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    }
    ctx.strokeStyle = '#22d3ee'
    ctx.globalAlpha = 0.85
    ctx.lineWidth = Math.max(1.2, 1.4 * v.zf * TIER_LOOK[p.tier].w)
    ctx.stroke()
    ctx.globalAlpha = 1
  }

  // -------------------------------------------------------------- hovering ---

  _handleMouse(e) {
    const oe = e.originalEvent
    // Let station markers / popups own the pointer.
    if (oe && oe.target && oe.target.closest && oe.target.closest('.leaflet-interactive')) {
      this._setHover(null)
      return
    }
    this._lastMouse = e.containerPoint
    if (this._pickQueued) return
    this._pickQueued = true
    requestAnimationFrame(() => {
      this._pickQueued = false
      if (!this._map || !this._lastMouse) return
      this._setHover(this._pick(this._lastMouse), this._lastMouse)
    })
  }

  _pick(pt) {
    const v = this._view
    if (!v) return null
    const { W, tl, visible, z } = v
    const px = pt.x + tl.x
    const py = pt.y + tl.y
    const tol = PICK_PX
    let best = null
    let bestScore = Infinity
    for (let k = 0; k < visible.length; k++) {
      const { p, g } = visible[k]
      if (
        px < g.x0 * W - tol || px > g.x1 * W + tol ||
        py < g.y0 * W - tol || py > g.y1 * W + tol
      ) continue
      let d2min = Infinity
      for (let i = 1; i < g.n; i++) {
        const ax = g.mx[i - 1] * W
        const ay = g.my[i - 1] * W
        const bx = g.mx[i] * W
        const by = g.my[i] * W
        const dx = bx - ax
        const dy = by - ay
        const len2 = dx * dx + dy * dy
        let t = len2 ? ((px - ax) * dx + (py - ay) * dy) / len2 : 0
        t = t < 0 ? 0 : t > 1 ? 1 : t
        const ex = ax + t * dx - px
        const ey = ay + t * dy - py
        const d2 = ex * ex + ey * ey
        if (d2 < d2min) d2min = d2
      }
      if (d2min > tol * tol) continue
      // prefer the more important line when several overlap
      const score = Math.sqrt(d2min) + (p.tier - 1) * 0.4
      if (score < bestScore) {
        bestScore = score
        best = { p, g, z }
      }
    }
    return best
  }

  _setHover(hit, pt) {
    const prev = this._hover?.p
    const next = hit?.p
    if (prev !== next) {
      this._hover = hit
      this.redraw()
    }
    const tip = this._tip
    if (!tip) return
    if (!hit || !pt) {
      tip.style.display = 'none'
      return
    }
    if (prev !== next) this._fillTip(hit.p)
    tip.style.display = 'block'
    const box = this._map.getSize()
    const w = tip.offsetWidth
    const h = tip.offsetHeight
    let x = pt.x + 14
    let y = pt.y - h - 10
    if (x + w > box.x - 4) x = pt.x - w - 14
    if (y < 4) y = pt.y + 18
    tip.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px)`
  }

  _fillTip(p) {
    const st = this._styles[RISK_KEYS[p.risk]]
    const tier = TIERS[p.tier - 1]
    const tip = this._tip
    tip.textContent = ''

    const title = document.createElement('div')
    title.className = 'railopt-track-tip__title'
    const dot = document.createElement('span')
    dot.className = 'railopt-track-tip__dot'
    dot.style.backgroundColor = st.coreColor
    const label = document.createElement('span')
    label.textContent = p.cors.length
      ? CORRIDOR_NAMES[p.cors[0]]
      : p.name || `${tier.name} railway line`
    title.append(dot, label)

    const meta = document.createElement('div')
    meta.className = 'railopt-track-tip__meta'
    const badge = document.createElement('span')
    badge.className = 'railopt-track-tip__badge'
    badge.textContent = st.label
    badge.style.color = st.coreColor
    badge.style.borderColor = st.coreColor
    const tierEl = document.createElement('span')
    tierEl.textContent = `${tier.name} line`
    meta.append(badge, tierEl)

    const sub = document.createElement('div')
    sub.className = 'railopt-track-tip__sub'
    sub.textContent = [p.state, p.gauge, p.service ? 'service track' : '', p.live ? 'live OpenStreetMap' : '']
      .filter(Boolean)
      .join(' · ')

    tip.append(title, meta, sub)
  }
}
