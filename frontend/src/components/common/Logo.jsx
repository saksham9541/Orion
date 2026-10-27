import { motion } from 'framer-motion'

/**
 * The mark is the argument: three department lines arriving from different
 * places and leaving as one. Animated on the landing hero, static everywhere
 * else so it doesn't nag.
 */
export default function Logo({ size = 28, animated = false, className = '' }) {
  const draw = {
    hidden: { pathLength: 0, opacity: 0 },
    show: (i) => ({
      pathLength: 1,
      opacity: 1,
      transition: { delay: 0.15 * i, duration: 0.7, ease: 'easeInOut' },
    }),
  }
  const Path = animated ? motion.path : 'path'
  const props = (i) =>
    animated ? { variants: draw, custom: i, initial: 'hidden', animate: 'show' } : {}

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <Path
        d="M2 6 H12 C17 6 17 16 22 16 H30"
        stroke="#F2A93B"
        strokeWidth="2.2"
        strokeLinecap="round"
        {...props(0)}
      />
      <Path d="M2 16 H30" stroke="#4FC3A1" strokeWidth="2.2" strokeLinecap="round" {...props(1)} />
      <Path
        d="M2 26 H12 C17 26 17 16 22 16 H30"
        stroke="#8B9DFF"
        strokeWidth="2.2"
        strokeLinecap="round"
        {...props(2)}
      />
      <circle cx="22" cy="16" r="2.6" fill="#0E1821" stroke="#CFE3F2" strokeWidth="1.6" />
    </svg>
  )
}
