/**
 * Colour behind the globe. On its own the hero was a flat dark field with a
 * particle scene on top — technically correct, visually a little inert. This
 * sits between the body's grid and the WebGL canvas: three large, heavily
 * blurred fields in the same four hues as the department clusters
 * (amber / teal / indigo / cyan), each drifting on its own slow, looping
 * path so the field never quite repeats. Screen-blended and kept dim, so it
 * reads as depth and atmosphere rather than a coloured spotlight — the globe
 * stays the brightest thing in the frame.
 */
export default function AuroraBackground() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      <div
        className="aurora-blob animate-auroraA left-[8%] top-[-10%] h-[520px] w-[520px] opacity-[0.22] sm:h-[620px] sm:w-[620px]"
        style={{ background: 'radial-gradient(circle, #F2A93B 0%, transparent 68%)' }}
      />
      <div
        className="aurora-blob animate-auroraB right-[4%] top-[-6%] h-[560px] w-[560px] opacity-[0.18] sm:h-[680px] sm:w-[680px]"
        style={{ background: 'radial-gradient(circle, #5FD6E8 0%, transparent 68%)' }}
      />
      <div
        className="aurora-blob animate-auroraC bottom-[-16%] left-[18%] h-[600px] w-[600px] opacity-[0.16] sm:h-[720px] sm:w-[720px]"
        style={{ background: 'radial-gradient(circle, #8B9DFF 0%, transparent 68%)' }}
      />
      <div
        className="aurora-blob animate-auroraA right-[14%] bottom-[-14%] h-[420px] w-[420px] opacity-[0.16] [animation-duration:24s] sm:h-[520px] sm:w-[520px]"
        style={{ background: 'radial-gradient(circle, #4FC3A1 0%, transparent 68%)' }}
      />
    </div>
  )
}
