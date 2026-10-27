import { useEffect, useRef, useState } from 'react'

/**
 * Counts a number up on mount. Used only on first-view KPIs — repeating this
 * on every render would make the dashboard feel unstable.
 */
export function useCountUp(target, ms = 900, decimals = 0) {
  const [value, setValue] = useState(0)
  const frame = useRef()

  useEffect(() => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce) {
      setValue(target)
      return
    }
    const start = performance.now()
    const step = (now) => {
      const t = Math.min(1, (now - start) / ms)
      const eased = 1 - Math.pow(1 - t, 3)
      setValue(target * eased)
      if (t < 1) frame.current = requestAnimationFrame(step)
    }
    frame.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame.current)
  }, [target, ms])

  return decimals > 0
    ? value.toFixed(decimals)
    : Math.round(value).toLocaleString('en-IN')
}
