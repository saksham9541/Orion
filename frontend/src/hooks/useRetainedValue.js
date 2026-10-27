import { useEffect, useState } from 'react'

/**
 * Holds on to the last non-null value.
 *
 * Detail panels are driven by a selection that becomes null on close. Without
 * this the panel would unmount instantly and skip its slide-out, so the user
 * never sees where it went.
 */
export function useRetainedValue(value) {
  const [retained, setRetained] = useState(value)

  useEffect(() => {
    if (value) setRetained(value)
  }, [value])

  return value ?? retained
}
