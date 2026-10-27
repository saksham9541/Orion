import { urgencyClass } from '@/lib/constants'

/** Urgency score, 0-100, on the one scale shared by all three departments. */
export default function ScoreMeter({ score, width = 74, showValue = true }) {
  const u = urgencyClass(score)
  return (
    <span className="inline-flex items-center gap-2.5">
      {showValue && (
        <span className="font-mono text-[13px] tnum w-7 text-right" style={{ color: u.color }}>
          {score}
        </span>
      )}
      <span
        className="h-[5px] rounded-full bg-line/70 overflow-hidden shrink-0"
        style={{ width }}
        role="img"
        aria-label={`Urgency ${score} of 100, ${u.label}`}
      >
        <span
          className="block h-full rounded-full transition-[width] duration-500"
          style={{ width: `${score}%`, background: u.color }}
        />
      </span>
    </span>
  )
}
