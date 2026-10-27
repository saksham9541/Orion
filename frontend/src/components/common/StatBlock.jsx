import { useCountUp } from '@/hooks/useCountUp'

/**
 * One number with its own comparison. Every KPI in this product is only
 * meaningful against the uncoordinated baseline, so the delta is not optional.
 */
export default function StatBlock({ label, value, unit, delta, deltaLabel, tone = 'ok', decimals = 0 }) {
  const shown = useCountUp(value, 900, decimals)
  const toneClass = tone === 'ok' ? 'text-ok' : tone === 'danger' ? 'text-danger' : 'text-muted'

  return (
    <div className="px-5 py-4">
      <p className="text-[13px] text-muted">{label}</p>
      <p className="mt-2 flex items-baseline gap-1.5">
        <span className="font-mono tnum text-[30px] leading-none font-medium">{shown}</span>
        {unit && <span className="text-[13px] text-faint">{unit}</span>}
      </p>
      {delta != null && (
        <p className={`mt-2 text-[12.5px] ${toneClass}`}>
          {delta} <span className="text-faint">{deltaLabel}</span>
        </p>
      )}
    </div>
  )
}
