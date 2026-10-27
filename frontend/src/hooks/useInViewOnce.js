import { useEffect, useRef, useState } from 'react'

/** Fires once when an element first enters the viewport. */
export function useInViewOnce(threshold = 0.3) {
  const ref = useRef(null)
  const [seen, setSeen] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el || seen) return
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setSeen(true)
          io.disconnect()
        }
      },
      { threshold }
    )
    io.observe(el)
    return () => io.disconnect()
  }, [seen, threshold])

  return [ref, seen]
}
