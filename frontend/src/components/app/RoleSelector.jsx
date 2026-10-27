import { motion } from 'framer-motion'
import { useAppState, ROLES } from '@/state/AppState'

/**
 * Who is looking at the board.
 *
 * The plan does not change with the role — the same sixteen blocks are the
 * same sixteen blocks for everyone. What changes is the order the overview
 * puts things in, because a section controller opens the screen to approve
 * and a planner opens it to find the clash.
 */
export default function RoleSelector({ className = '' }) {
  const { roleId, setRoleId, role } = useAppState()

  return (
    <div className={className}>
      <div
        className="flex rounded-panel border border-line p-0.5"
        role="radiogroup"
        aria-label="Control room role"
      >
        {ROLES.map((r) => {
          const active = r.id === roleId
          return (
            <button
              key={r.id}
              role="radio"
              aria-checked={active}
              onClick={() => setRoleId(r.id)}
              title={r.focus}
              className={`relative shrink-0 rounded-[3px] px-2.5 py-1.5 text-[12.5px] transition-colors ${
                active ? 'text-deep' : 'text-muted hover:text-ink'
              }`}
            >
              {active && (
                <motion.span
                  layoutId="role-pill"
                  className="absolute inset-0 rounded-[3px] bg-merge"
                  transition={{ type: 'spring', stiffness: 380, damping: 32 }}
                />
              )}
              <span className="relative">{r.short}</span>
            </button>
          )
        })}
      </div>
      <p className="mt-1.5 hidden text-right text-[11.5px] text-faint lg:block">{role.focus}</p>
    </div>
  )
}
