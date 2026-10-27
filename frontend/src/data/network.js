/**
 * Geometry for the digital twin.
 *
 * A schematic, in the tradition of a signalling diagram: stations sit at even
 * intervals on straight runs, because what matters is the order of sections
 * and which ones are closed — not where they fall on a map. Coordinates are
 * in an 1200 x 320 viewBox.
 *
 * These are demonstration positions for real station codes. Nothing here is
 * a live train position or a live block status.
 */

import { corridors } from './corridors'

export const stationNames = {
  NDLS: 'New Delhi',
  SBB: 'Sahibabad',
  SHDM: 'Shahdara',
  GZB: 'Ghaziabad',
  DER: 'Dadri',
  KRJ: 'Khurja',
  ALJN: 'Aligarh',
  TDL: 'Tundla',
  ETW: 'Etawah',
  CNB: 'Kanpur Central',
  BCT: 'Mumbai Central',
  BVI: 'Borivali',
  BSR: 'Vasai Road',
  PLG: 'Palghar',
  BL: 'Valsad',
  ST: 'Surat',
}

/** The two trunk runs the division works, each a continuous chain of sections. */
const RUNS = [
  {
    id: 'northern',
    label: 'Northern trunk',
    long: 'New Delhi – Kanpur Central',
    y: 96,
    stations: ['NDLS', 'SBB', 'SHDM', 'GZB', 'DER', 'KRJ', 'ALJN', 'TDL', 'ETW', 'CNB'],
  },
  {
    id: 'western',
    label: 'Western trunk',
    long: 'Mumbai Central – Surat',
    y: 244,
    stations: ['BCT', 'BVI', 'BSR', 'PLG', 'BL', 'ST'],
  },
]

const X_START = 70
const X_END = 1130

/** Which corridor owns a given section, resolved once from corridors.js. */
const sectionOwner = {}
for (const c of corridors) for (const s of c.sections) sectionOwner[s] = c.id

export const runs = RUNS.map((run) => {
  const step = (X_END - X_START) / (run.stations.length - 1)
  const nodes = run.stations.map((code, i) => ({
    code,
    name: stationNames[code] ?? code,
    x: X_START + i * step,
    y: run.y,
    run: run.id,
  }))
  const links = nodes.slice(0, -1).map((from, i) => {
    const to = nodes[i + 1]
    const section = `${from.code}–${to.code}`
    return {
      section,
      corridorId: sectionOwner[section] ?? null,
      from,
      to,
      midX: (from.x + to.x) / 2,
      midY: from.y,
    }
  })
  return { ...run, nodes, links }
})

export const networkNodes = runs.flatMap((r) => r.nodes)
export const networkLinks = runs.flatMap((r) => r.links)

/** Sections drawn on the diagram that no corridor in scope owns. */
export const unmanagedSections = networkLinks.filter((l) => !l.corridorId).map((l) => l.section)

export const VIEWBOX = { width: 1200, height: 320 }
