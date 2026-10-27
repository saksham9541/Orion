import { motion } from 'framer-motion'
import { CalendarX2, Clock, ShieldCheck, Train } from 'lucide-react'
import { useCountUp } from '@/hooks/useCountUp'
import { DataTag } from '@/components/common/StatusChip'
import { baseline, optimised, prevented } from '@/lib/optimizer'
import { duration } from '@/lib/format'

/**
 * The counterfactual, stated plainly.
 *
 * Each figure is one subtraction between the uncoordinated baseline and the
 * coordinated plan — both computed from the same nineteen jobs. The working
 * is printed under each number so nobody has to take it on trust, and the
 * panel says outright that these are simulated outcomes on demonstration
 * data rather than measured railway performance.
 */
export default function PreventedPanel() {
  const items = [
    {
      icon: CalendarX2,
      value: prevented.closuresAvoided,
      label: 'Duplicate closures avoided',
      working: `${baseline.blocks} possessions as raised → ${optimised.blocks} in the plan`,
    },
    {
      icon: Train,
      value: prevented.trainsProtected,
      label: 'Est. train movements protected',
      working: `${baseline.trainsAffected} held uncoordinated → ${optimised.trainsAffected} in the plan`,
    },
    {
      icon: Clock,
      value: prevented.downtimeAvoided,
      label: 'Maintenance downtime avoided',
      display: duration(prevented.downtimeAvoided),
      working: `${baseline.downtimeMinutes} min → ${optimised.downtimeMinutes} min of closure`,
    },
    {
      icon: ShieldCheck,
      value: prevented.breachesPrevented,
      label: 'Deferral-limit breaches prevented',
      working: `${baseline.slaBreaches} jobs would have slipped → ${optimised.slaBreaches} left over`,
    },
  ]

  return (
    <section className="panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hair px-5 py-4 sm:px-6">
        <div>
          <h2 className="text-[15px] font-semibold">What RailOpt prevented</h2>
          <p className="mt-0.5 text-[12.5px] text-muted">
            The difference between the same work coordinated and uncoordinated.
          </p>
        </div>
        <DataTag kind="simulation" />
      </div>

      <ul className="grid gap-px bg-line sm:grid-cols-2 xl:grid-cols-4">
        {items.map((item, i) => (
          <PreventedItem key={item.label} {...item} delay={i * 0.08} />
        ))}
      </ul>

      <p className="border-t border-hair px-5 py-3.5 text-[12px] leading-relaxed text-faint sm:px-6">
        Simulation estimate on demonstration data. Every figure above is a subtraction between
        two plans this prototype generated — not an observed saving on any railway.
      </p>
    </section>
  )
}

function PreventedItem({ icon: Icon, value, label, display, working, delay }) {
  const counted = useCountUp(value, 1000)
  return (
    <motion.li
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
      className="bg-surface px-5 py-5"
    >
      <Icon size={16} className="text-merge" strokeWidth={1.7} aria-hidden="true" />
      <p className="mt-3 tnum font-mono text-[28px] font-medium leading-none">
        {display ?? counted}
      </p>
      <p className="mt-2 text-[13px] leading-snug">{label}</p>
      <p className="mt-2 font-mono text-[11px] leading-relaxed text-faint">{working}</p>
    </motion.li>
  )
}
