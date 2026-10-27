// NOTE: the palette below mirrors the :root/.dark and .light blocks in
// src/index.css. If you change a token there, change it here and re-run:
//   node tools/contrast.mjs          (prints only failing pairs)
//   node tools/contrast.mjs --all    (prints every pair)
// WCAG contrast audit for the RailOpt token palette (both themes).
const rgb = (s) => s.split(/\s+/).map(Number)
const lin = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4 }
const L = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
const cr = (a, b) => { const [x, y] = [L(a), L(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05) }
const blend = (fg, bg, a) => fg.map((c, i) => Math.round(c * a + bg[i] * (1 - a)))

export const THEMES = {
  light: {
    base: '244 246 249', deep: '255 255 255', surface: '255 255 255', raised: '238 242 247',
    line: '203 213 225', hair: '226 232 240',
    ink: '15 23 42', muted: '51 65 85', faint: '84 100 122',
    eng: '133 77 0', snt: '6 110 88', trd: '63 78 186', merge: '22 50 92',
    danger: '185 28 28', warn: '133 77 0', ok: '6 110 88', high: '170 55 8', info: '29 78 216',
    bar: '15 23 42', onbar: '255 255 255', barMuted: '148 163 184',
  },
  dark: {
    base: '14 24 33', deep: '10 18 26', surface: '21 34 48', raised: '28 44 60',
    line: '48 70 92', hair: '27 42 56',
    ink: '230 237 243', muted: '168 186 203', faint: '132 152 171',
    eng: '242 169 59', snt: '79 195 161', trd: '139 157 255', merge: '207 227 242',
    danger: '255 116 120', warn: '238 178 80', ok: '79 195 161', high: '255 149 84', info: '122 170 255',
    bar: '10 18 26', onbar: '255 255 255', barMuted: '148 163 184',
  },
}
const rows = []
for (const [name, t] of Object.entries(THEMES)) {
  const C = Object.fromEntries(Object.entries(t).map(([k, v]) => [k, rgb(v)]))
  const chk = (label, fg, bg, min = 4.5) => rows.push([name, label, cr(fg, bg).toFixed(2), cr(fg, bg) >= min ? 'ok' : 'FAIL <' + min])
  for (const bgk of ['base', 'surface', 'raised'])
    for (const fgk of ['ink', 'muted', 'faint']) chk(`${fgk} on ${bgk}`, C[fgk], C[bgk])
  chk('deep on merge (primary btn)', C.deep, C.merge)
  chk('merge on surface', C.merge, C.surface)
  chk('onbar on bar', C.onbar, C.bar)
  chk('barMuted on bar', C.barMuted, C.bar)
  for (const k of ['eng', 'snt', 'trd', 'danger', 'warn', 'ok', 'high', 'info']) {
    chk(`${k} text on surface`, C[k], C.surface)
    chk(`${k} text on ${k}/10 tint over surface`, C[k], blend(C[k], C.surface, 0.10))
    chk(`${k} text on ${k}/10 tint over raised`, C[k], blend(C[k], C.raised, 0.10))
  }
  chk('line vs surface (UI border, 3:1)', C.line, C.surface, 1.3)
}
const bad = rows.filter((r) => r[3] !== 'ok')
console.log(rows.length, 'checks;', bad.length, 'failing')
for (const r of process.argv.includes('--all') ? rows : bad) console.log(r.join(' | '))
