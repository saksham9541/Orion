/**
 * Live, ground-truth railway geometry straight from OpenStreetMap.
 *
 * Why this exists
 * ---------------
 * The bundled network (src/data/railNetwork) is derived from a thinned, ~30k
 * segment extract: vertices are ~70 m apart on average (up to ~800 m on some
 * curves) and ~14 % of India's real track is missing. Drawn over satellite
 * imagery those long chords cut across roads and buildings.
 *
 * OpenStreetMap itself has every railway way, traced against imagery, with a
 * vertex every few metres. So once the map is zoomed in far enough to see
 * individual tracks (>= LIVE_MIN_ZOOM) we ask the Overpass API for every
 * railway way in the viewport and draw those instead. Bundled geometry is only
 * used (a) when zoomed out, where its error is far below a pixel, and (b) as a
 * fallback while a tile loads or if Overpass is unreachable.
 *
 * Data flow
 *   viewport -> z10 tiles -> IndexedDB cache | Overpass (3 mirrors, retries)
 *            -> pieces shaped exactly like the bundled ones (see railNetwork.js)
 *
 * Track data (c) OpenStreetMap contributors, ODbL.
 */
import { CORRIDOR_IDS, METRO_NAME_RE } from '@/lib/railNetwork'
import RAIL_TRACKS from '@/data/railTracks.json'

/** Live data takes over from the bundled network from this zoom upwards. */
export const LIVE_MIN_ZOOM = 10
/** Fetch granularity: standard XYZ tiles at this zoom (~39 km wide). */
export const LIVE_TILE_ZOOM = 10
/** Service tracks (yards, sidings, spurs, crossovers) only draw from this zoom. */
export const SERVICE_MIN_ZOOM = 12

const MIRRORS = [
  'https://overpass-api.de/api/interpreter',
  'https://overpass.private.coffee/api/interpreter',
  'https://overpass.kumi.systems/api/interpreter',
]
const MAX_PARALLEL = 3
const MAX_ATTEMPTS = 5
const REQUEST_TIMEOUT_MS = 55_000
const TILE_PAD_DEG = 0.0015 // ~170 m, so ways on a tile edge are never clipped
const MAX_TILES_IN_MEMORY = 120
const CACHE_TTL_MS = 7 * 24 * 3600 * 1000
const DB_NAME = 'railopt-osm-rail'
const DB_VERSION = 1

// Mainline railway only. Disused / abandoned / planned lines and all urban metro,
// light-rail, monorail and subway are deliberately excluded.
const RAILWAY_RE = '^(rail|narrow_gauge)$'

const RAD = Math.PI / 180

// ----------------------------------------------------------------- tiles ---

export const tileKey = (x, y) => `${x}/${y}`

/** Tile x/y (at LIVE_TILE_ZOOM) holding a normalised web-mercator point. */
export function tileOfMerc(mx, my) {
  const n = 1 << LIVE_TILE_ZOOM
  return [Math.floor(mx * n), Math.floor(my * n)]
}

function tileBounds(x, y) {
  const n = 1 << LIVE_TILE_ZOOM
  const lng = (t) => (t / n) * 360 - 180
  const lat = (t) => (Math.atan(Math.sinh(Math.PI * (1 - (2 * t) / n))) * 180) / Math.PI
  return { w: lng(x), e: lng(x + 1), n: lat(y), s: lat(y + 1) }
}

/** All tiles intersecting a lat/lng box, nearest-to-centre first. */
export function tilesForBounds(bounds) {
  const n = 1 << LIVE_TILE_ZOOM
  const toX = (lng) => ((lng + 180) / 360) * n
  const toY = (lat) => {
    const s = Math.sin(lat * RAD)
    return (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * n
  }
  const x0 = Math.max(0, Math.floor(toX(bounds.getWest())))
  const x1 = Math.min(n - 1, Math.floor(toX(bounds.getEast())))
  const y0 = Math.max(0, Math.floor(toY(bounds.getNorth())))
  const y1 = Math.min(n - 1, Math.floor(toY(bounds.getSouth())))
  const cx = (x0 + x1 + 1) / 2
  const cy = (y0 + y1 + 1) / 2
  const out = []
  for (let x = x0; x <= x1; x++) for (let y = y0; y <= y1; y++) out.push([x, y])
  out.sort((a, b) => (a[0] + 0.5 - cx) ** 2 + (a[1] + 0.5 - cy) ** 2 - ((b[0] + 0.5 - cx) ** 2 + (b[1] + 0.5 - cy) ** 2))
  return out
}

// ------------------------------------------------------ corridor tagging ---
// Live ways carry no notion of the app's 15 named corridors, so a way is tagged
// with a corridor when most of it lies within a few hundred metres of that
// corridor's (bundled) alignment. Keeps corridor-based risk colouring working.

const CELL = 0.0025 // ~280 m
let corridorCells = null // Map<cellKey, bitmask over CORRIDOR_IDS>

const cellKey = (ix, iy) => ix * 200003 + iy

function buildCorridorCells() {
  const cells = new Map()
  CORRIDOR_IDS.forEach((id, bit) => {
    const line = RAIL_TRACKS[id]
    if (!line) return
    const flag = 1 << bit
    for (let i = 0; i < line.length; i++) {
      const [la0, lo0] = line[i]
      const [la1, lo1] = line[Math.min(i + 1, line.length - 1)]
      const steps = Math.max(1, Math.ceil(Math.max(Math.abs(la1 - la0), Math.abs(lo1 - lo0)) / 0.001))
      for (let s = 0; s <= steps; s++) {
        const la = la0 + ((la1 - la0) * s) / steps
        const lo = lo0 + ((lo1 - lo0) * s) / steps
        const k = cellKey(Math.floor(lo / CELL), Math.floor(la / CELL))
        cells.set(k, (cells.get(k) || 0) | flag)
      }
    }
  })
  return cells
}

function corridorsFor(lat, lng, n) {
  if (!corridorCells) corridorCells = buildCorridorCells()
  const SAMPLES = Math.min(n, 8)
  const counts = new Uint8Array(CORRIDOR_IDS.length)
  for (let s = 0; s < SAMPLES; s++) {
    const i = SAMPLES === 1 ? 0 : Math.round((s * (n - 1)) / (SAMPLES - 1))
    const cx = Math.floor(lng[i] / CELL)
    const cy = Math.floor(lat[i] / CELL)
    let m = 0
    for (let dx = -1; dx <= 1; dx++)
      for (let dy = -1; dy <= 1; dy++) m |= corridorCells.get(cellKey(cx + dx, cy + dy)) || 0
    if (!m) continue
    for (let b = 0; b < counts.length; b++) if (m & (1 << b)) counts[b]++
  }
  const need = Math.ceil(SAMPLES * 0.6)
  const out = []
  for (let b = 0; b < counts.length; b++) if (counts[b] >= need) out.push(b)
  return out
}

// -------------------------------------------------------------- decoding ---

/** OSM `gauge` is in mm. India: 1676 broad, 1000 metre, 762 / 610 narrow. */
function gaugeName(tags) {
  const g = parseInt(String(tags.gauge || '').split(';')[0], 10)
  if (g >= 1600) return 'Broad gauge'
  if (g >= 950) return 'Metre gauge'
  if (g > 0) return 'Narrow gauge'
  if (tags.railway === 'narrow_gauge') return 'Narrow gauge'
  return 'Broad gauge'
}

/** Which of the five importance tiers a way belongs to (drives line weight). */
function tierOf(tags, onCorridor) {
  if (tags.service) return 5
  if (tags.railway !== 'rail') return 4
  if (onCorridor) return 1
  if (tags.usage === 'main') return 2
  if (tags.usage === 'branch') return 3
  if (tags.usage === 'industrial' || tags.usage === 'military' || tags.usage === 'tourism') return 5
  return 3
}

function geomFromLatLng(lat, lng) {
  const n = lat.length
  const mx = new Float64Array(n)
  const my = new Float64Array(n)
  let km = 0
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity
  for (let i = 0; i < n; i++) {
    const x = (lng[i] + 180) / 360
    const s = Math.sin(lat[i] * RAD)
    const y = 0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)
    mx[i] = x
    my[i] = y
    if (x < x0) x0 = x
    if (x > x1) x1 = x
    if (y < y0) y0 = y
    if (y > y1) y1 = y
    if (i > 0) {
      km += Math.hypot((lng[i] - lng[i - 1]) * 111.32 * Math.cos(lat[i] * RAD), (lat[i] - lat[i - 1]) * 110.57)
    }
  }
  return { n, mx, my, lat, lng, km, x0, y0, x1, y1 }
}

/**
 * Compact cacheable form of one way: { id, t: tags subset, c: [lat0,lng0,lat1,lng1,...] }
 * (full double precision; OSM stores 1e-7 deg, so there is no rounding to hide).
 */
function compactWays(elements) {
  const out = []
  for (const el of elements) {
    if (el.type !== 'way' || !el.geometry || el.geometry.length < 2) continue
    const tg = el.tags || {}
    if (tg.railway !== 'rail' && tg.railway !== 'narrow_gauge') continue // no metro / light rail / monorail
    if (METRO_NAME_RE.test(tg.name || '') || METRO_NAME_RE.test(tg.network || '')) continue
    const c = new Array(el.geometry.length * 2)
    for (let i = 0; i < el.geometry.length; i++) {
      c[2 * i] = el.geometry[i].lat
      c[2 * i + 1] = el.geometry[i].lon
    }
    const t = { r: tg.railway }
    if (tg.service) t.s = tg.service
    if (tg.usage) t.u = tg.usage
    if (tg.gauge) t.g = tg.gauge
    if (tg.name) t.n = tg.name
    else if (tg.ref) t.n = tg.ref
    out.push({ id: el.id, t, c })
  }
  return out
}

function ways2piece(w) {
  const n = w.c.length >> 1
  const lat = new Float32Array(n)
  const lng = new Float32Array(n)
  // Float32 keeps ~1 m at India's longitudes — plenty for drawing, and halves memory.
  // Draw geometry (mx/my) is computed from the full-precision values below.
  const latD = new Float64Array(n)
  const lngD = new Float64Array(n)
  for (let i = 0; i < n; i++) {
    latD[i] = w.c[2 * i]
    lngD[i] = w.c[2 * i + 1]
    lat[i] = latD[i]
    lng[i] = lngD[i]
  }
  const cors = w.t.r === 'rail' || w.t.r === 'narrow_gauge' ? corridorsFor(latD, lngD, n) : []
  const tags = {
    railway: w.t.r, service: w.t.s, usage: w.t.u, gauge: w.t.g,
  }
  const g = geomFromLatLng(latD, lngD)
  g.lat = lat
  g.lng = lng
  return {
    tier: tierOf(tags, cors.length > 0),
    state: '',
    gauge: gaugeName(tags),
    name: w.t.n || '',
    cors,
    fine: g,
    coarse: null,
    risk: 1,
    live: true,
    service: Boolean(w.t.s),
    osmId: w.id,
  }
}

// ----------------------------------------------------------- IndexedDB ------

let dbPromise = null
function openDb() {
  if (dbPromise) return dbPromise
  dbPromise = new Promise((resolve) => {
    try {
      if (typeof indexedDB === 'undefined') return resolve(null)
      const req = indexedDB.open(DB_NAME, DB_VERSION)
      req.onupgradeneeded = () => req.result.createObjectStore('tiles')
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => resolve(null)
      req.onblocked = () => resolve(null)
    } catch {
      resolve(null)
    }
  })
  return dbPromise
}

async function cacheGet(key) {
  const db = await openDb()
  if (!db) return null
  return new Promise((resolve) => {
    try {
      const req = db.transaction('tiles').objectStore('tiles').get(key)
      req.onsuccess = () => {
        const v = req.result
        resolve(v && Date.now() - v.at < CACHE_TTL_MS ? v.ways : null)
      }
      req.onerror = () => resolve(null)
    } catch {
      resolve(null)
    }
  })
}

async function cachePut(key, ways) {
  const db = await openDb()
  if (!db) return
  try {
    db.transaction('tiles', 'readwrite').objectStore('tiles').put({ at: Date.now(), ways }, key)
  } catch {
    /* quota / private mode: the cache is only an optimisation */
  }
}

// -------------------------------------------------------------- network ----

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function fetchOverpass(x, y, attempt0 = 0, signalOuter) {
  const b = tileBounds(x, y)
  const q =
    `[out:json][timeout:50];` +
    `way["railway"~"${RAILWAY_RE}"]["name"!~"[Mm]etro|[Mm]onorail|MRTS"]["network"!~"[Mm]etro"](${(b.s - TILE_PAD_DEG).toFixed(5)},${(b.w - TILE_PAD_DEG).toFixed(5)},` +
    `${(b.n + TILE_PAD_DEG).toFixed(5)},${(b.e + TILE_PAD_DEG).toFixed(5)});` +
    `out tags geom qt;`
  let lastErr
  for (let attempt = attempt0; attempt < MAX_ATTEMPTS; attempt++) {
    if (signalOuter?.aborted) throw new Error('aborted')
    const url = MIRRORS[(x + y + attempt) % MIRRORS.length]
    const ctl = new AbortController()
    const timer = setTimeout(() => ctl.abort(), REQUEST_TIMEOUT_MS)
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `data=${encodeURIComponent(q)}`,
        signal: ctl.signal,
      })
      if (!res.ok) throw new Error(`Overpass ${res.status}`)
      const json = await res.json()
      // A busy server can answer 200 with a `remark` and no elements — treat as failure.
      if (json.remark && /runtime error|timed out|out of memory/i.test(json.remark) && !json.elements?.length) {
        throw new Error(`Overpass remark: ${json.remark}`)
      }
      return json.elements || []
    } catch (err) {
      lastErr = err
      await sleep(Math.min(8000, 600 * 2 ** attempt) + Math.random() * 300)
    } finally {
      clearTimeout(timer)
    }
  }
  throw lastErr || new Error('Overpass unreachable')
}

// ---------------------------------------------------------------- loader ---

/**
 * Keeps the set of live tiles the map needs, loads them (cache first, then
 * network), dedupes ways that straddle tiles, and evicts the least recently
 * used tiles. Emits `onChange` whenever the drawable set changes.
 *
 *   const loader = new OsmRailLoader({ onChange, onStatus })
 *   loader.want(tilesForBounds(map.getBounds()))   // on every moveend, zoom >= LIVE_MIN_ZOOM
 *   loader.pieces        // Piece[] to draw (shape-compatible with the bundled pieces)
 *   loader.loadedTiles   // Set<"x/y"> — bundled geometry inside these is hidden
 */
export default class OsmRailLoader {
  constructor({ onChange, onStatus }) {
    this.onChange = onChange
    this.onStatus = onStatus
    this.tiles = new Map() // key -> { ids:number[], used:number }
    this.ways = new Map() // osm id -> { piece, refs }
    this.loadedTiles = new Set()
    this.pieces = []
    this._piecesDirty = false
    this._queue = []
    this._inflight = new Map() // key -> AbortController
    this._failed = new Map() // key -> timestamp of last failure
    this._wanted = new Set()
    this._pump = this._pump.bind(this)
    this._dead = false
    this._tick = 0
  }

  destroy() {
    this._dead = true
    for (const c of this._inflight.values()) c.abort()
    this._inflight.clear()
  }

  /** Declare the tiles currently in view; anything queued but no longer wanted is dropped. */
  want(tileList) {
    if (this._dead) return
    this._wanted = new Set(tileList.map(([x, y]) => tileKey(x, y)))
    this._tick++
    for (const key of this._wanted) {
      const t = this.tiles.get(key)
      if (t) t.used = this._tick
    }
    const now = Date.now()
    this._queue = tileList.filter(([x, y]) => {
      const k = tileKey(x, y)
      if (this.tiles.has(k) || this._inflight.has(k)) return false
      const f = this._failed.get(k)
      return !f || now - f > 20_000 // do not hammer a tile that just failed
    })
    this._status()
    this._pump()
  }

  /** Re-try tiles that failed earlier (e.g. after the network came back). */
  retryFailed() {
    this._failed.clear()
  }

  get pending() {
    let n = this._queue.length
    for (const k of this._inflight.keys()) if (this._wanted.has(k)) n++
    return n
  }

  _status() {
    const failed = [...this._wanted].filter((k) => this._failed.has(k) && !this.tiles.has(k)).length
    let loaded = 0
    for (const k of this._wanted) if (this.tiles.has(k)) loaded++
    this.onStatus?.({
      pending: this.pending,
      failed,
      loaded,
      wanted: this._wanted.size,
      ways: this.ways.size,
    })
  }

  _pump() {
    if (this._dead) return
    while (this._inflight.size < MAX_PARALLEL && this._queue.length) {
      const [x, y] = this._queue.shift()
      const key = tileKey(x, y)
      if (this.tiles.has(key) || this._inflight.has(key)) continue
      const ctl = new AbortController()
      this._inflight.set(key, ctl)
      this._load(x, y, key, ctl).finally(() => {
        this._inflight.delete(key)
        this._status()
        this._pump()
      })
    }
  }

  async _load(x, y, key, ctl) {
    try {
      let ways = await cacheGet(key)
      if (!ways) {
        const elements = await fetchOverpass(x, y, 0, ctl.signal)
        ways = compactWays(elements)
        cachePut(key, ways)
      }
      if (this._dead) return
      this._addTile(key, ways)
      this._failed.delete(key)
    } catch (err) {
      if (!this._dead && !ctl.signal.aborted) {
        console.warn(`Live OSM rail tile ${key} failed:`, err?.message || err)
        this._failed.set(key, Date.now())
      }
    }
  }

  _addTile(key, ways) {
    const ids = []
    for (const w of ways) {
      if ((w.t.r !== 'rail' && w.t.r !== 'narrow_gauge') || METRO_NAME_RE.test(w.t.n || '')) continue
      let rec = this.ways.get(w.id)
      if (!rec) {
        rec = { piece: ways2piece(w), refs: 0 }
        this.ways.set(w.id, rec)
        this._piecesDirty = true
      }
      rec.refs++
      ids.push(w.id)
    }
    this.tiles.set(key, { ids, used: this._tick })
    this.loadedTiles.add(key)
    this._piecesDirty = true
    this._evict()
    this._publish()
  }

  _evict() {
    if (this.tiles.size <= MAX_TILES_IN_MEMORY) return
    const victims = [...this.tiles.entries()]
      .filter(([k]) => !this._wanted.has(k))
      .sort((a, b) => a[1].used - b[1].used)
    for (const [k, t] of victims) {
      if (this.tiles.size <= MAX_TILES_IN_MEMORY) break
      for (const id of t.ids) {
        const rec = this.ways.get(id)
        if (rec && --rec.refs <= 0) this.ways.delete(id)
      }
      this.tiles.delete(k)
      this.loadedTiles.delete(k)
      this._piecesDirty = true
    }
  }

  _publish() {
    if (this._piecesDirty) {
      this.pieces = [...this.ways.values()].map((r) => r.piece)
      this._piecesDirty = false
    }
    this.onChange?.(this.pieces, this.loadedTiles)
  }
}
