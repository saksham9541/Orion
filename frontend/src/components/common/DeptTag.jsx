import { DEPARTMENTS } from '@/lib/constants'

/** Department identity, shown the same way everywhere: lamp + short name. */
export default function DeptTag({ dept, showName = true, size = 'md' }) {
  const d = DEPARTMENTS[dept]
  if (!d) return null
  const dot = size === 'sm' ? 6 : 8
  return (
    <span className="inline-flex items-center gap-2 whitespace-nowrap">
      <span
        className="lamp rounded-full shrink-0"
        style={{ width: dot, height: dot, background: d.color, color: d.color }}
      />
      {showName && (
        <span className={size === 'sm' ? 'text-[12px] text-muted' : 'text-[13px] text-muted'}>
          {d.name}
        </span>
      )}
    </span>
  )
}
