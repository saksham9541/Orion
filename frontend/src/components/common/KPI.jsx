import { motion } from 'framer-motion'
import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import { useCountUp } from '@/hooks/useCountUp'

/**
 * One operational number, with the comparison that makes it mean something.
 *
 * A KPI in this product is never shown alone: sixteen blocks is not a result
 * until you know it would otherwise have been nineteen. `compare` is the
 * uncoordinated figure, and the direction of travel is worked out from
 * `better` rather than assumed to be down.
 */
export default function KPI({
  label,
  value,
  unit,
  decimals = 0,
  compare = null,
  compareLabel = 'uncoordinated',
  better = 'lower',
  format = (v) => v,
  icon: Icon,
  accent = false,
  delay = 0,
}) {
  const shown = useCountUp(value, 900, decimals)
  const diff = compare == null ? null : value - compare
  const same = diff != null && Math.abs(diff) < 0.001
  const improved = diff != null && (better === 'lower' ? diff < 0 : diff > 0)
  const Arrow = same ? Minus : better === 'lower' ? ArrowDownRight : ArrowUpRight

  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      className="group relative overflow-hidden rounded-panel border border-line bg-surface transition-colors duration-300 hover:border-merge/40"
    >
      <span
        className={`absolute inset-x-0 top-0 h-[2px] ${accent ? 'accent-bar opacity-80' : 'bg-line'}`}
      />
      {Icon && (
        <span className="absolute right-3 top-3 rounded-full bg-raised/60 p-1.5 text-faint transition-colors group-hover:text-merge">
          <Icon size={14} strokeWidth={1.8} aria-hidden="true" />
        </span>
      )}
      <div className="px-5 py-4">
        <p className="pr-8 text-[12.5px] leading-snug text-muted">{label}</p>
        <p className="mt-2 flex items-baseline gap-1.5">
          <span className="tnum font-mono text-[30px] font-medium leading-none">{shown}</span>
          {unit && <span className="text-[13px] text-faint">{unit}</span>}
        </p>
        {compare != null && (
          <p
            className={`mt-2 flex items-center gap-1 text-[12px] ${
              same ? 'text-faint' : improved ? 'text-ok' : 'text-warn'
            }`}
          >
            <Arrow size={12} strokeWidth={2.2} aria-hidden="true" />
            <span className="tnum font-mono">{format(compare)}</span>
            <span className="text-faint">{compareLabel}</span>
          </p>
        )}
      </div>
    </motion.div>
  )
}
