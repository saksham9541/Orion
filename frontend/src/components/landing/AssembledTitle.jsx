import { motion } from 'framer-motion'

/**
 * "RAILOPT comes from different parts, then combines" — as the actual word.
 * Each letter starts thrown out to its own corner of the frame, blurred and
 * rotated, and springs into the reading position. Timed to land just as the
 * globe behind it finishes forming, so the two payoffs read as one moment.
 */
const LETTERS = ['R', 'A', 'I', 'L', 'O', 'P', 'T']

// One flung-out origin per letter, deliberately from different directions
// rather than a uniform fan, so it reads as fragments arriving rather than a
// single mechanical wipe.
const ORIGINS = [
  { x: -340, y: -90, rotate: -50 },
  { x: 280, y: -160, rotate: 40 },
  { x: -260, y: 160, rotate: 30 },
  { x: 320, y: 130, rotate: -35 },
  { x: -160, y: -220, rotate: 20 },
  { x: 200, y: 210, rotate: -25 },
  { x: 0, y: -260, rotate: 55 },
]

export default function AssembledTitle({ delay = 0, reduce = false }) {
  return (
    <h1
      className="flex justify-center text-[clamp(2.6rem,9vw,6.2rem)] font-bold leading-[0.94] tracking-[-0.03em]"
      aria-label="RailOpt"
    >
      {LETTERS.map((letter, i) => (
        <motion.span
          key={i}
          className="inline-block"
          initial={
            reduce
              ? { opacity: 1, x: 0, y: 0, rotate: 0, filter: 'blur(0px)' }
              : {
                  opacity: 0,
                  x: ORIGINS[i].x,
                  y: ORIGINS[i].y,
                  rotate: ORIGINS[i].rotate,
                  filter: 'blur(7px)',
                }
          }
          animate={{ opacity: 1, x: 0, y: 0, rotate: 0, filter: 'blur(0px)' }}
          transition={
            reduce
              ? { duration: 0 }
              : {
                  delay: delay + i * 0.075,
                  type: 'spring',
                  stiffness: 130,
                  damping: 15,
                  mass: 0.9,
                }
          }
          aria-hidden="true"
        >
          {letter}
        </motion.span>
      ))}
    </h1>
  )
}
