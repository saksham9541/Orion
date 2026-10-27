import { Suspense } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import HeroScene from './HeroScene'
import AuroraBackground from './AuroraBackground'
import HeroSidePanels from './HeroSidePanels'
import AssembledTitle from './AssembledTitle'
import Button from '@/components/common/Button'

// Everything below is timed against HeroScene's own animation clock: the
// swarm separates into four department clusters by ~1.05s, then sweeps onto
// the globe and the globe fades in between 1.65s and 2.55s. The title lands
// just as the globe resolves, so the two payoffs read as one moment, and
// the tagline and buttons follow once there's something to read them next to.
const T = {
  title: 1.5,
  subhead: 1.95,
  cta: 2.2,
  side: 1.85,
}

/**
 * The first screen says three things and nothing else: the name, the one-line
 * idea, and the two ways forward. The globe and the side panels carry the
 * rest visually.
 */
export default function Hero() {
  const reduce = useReducedMotion()

  const reveal = (delay) =>
    reduce
      ? { initial: { opacity: 1 }, animate: { opacity: 1 } }
      : {
          initial: { opacity: 0, y: 18 },
          animate: { opacity: 1, y: 0 },
          transition: { delay, duration: 0.7, ease: [0.16, 1, 0.3, 1] },
        }

  // Scroll to the How It Works section. If the section is ever missing we
  // return without preventing the default, so the plain #how link still acts.
  const scrollToHow = (event) => {
    const target = document.getElementById('how')
    if (!target) return
    event.preventDefault()
    target.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' })
  }

  return (
    <section id="top"
      className="dark relative h-[100svh] min-h-[600px] w-full overflow-hidden bg-[#0A121A] text-ink">
      {/* `dark` is forced here (see index.css) so text-ink/muted/faint etc.
          stay legible against this section's pinned-dark stage even when
          the rest of the app is switched to light theme. */}
      {/* The hero is a fixed dark stage regardless of the site theme — like
          a lit control room at night — so the globe and its colour field
          always read at full contrast even when the rest of the app is
          switched to light mode. */}
      <AuroraBackground />

      <Suspense fallback={null}>
        <HeroScene reduce={reduce} />
      </Suspense>

      {/* Vignette so the scene reads as depth behind the text, not noise under it. */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse 70% 62% at 50% 46%, transparent 0%, rgba(10,18,26,0.45) 62%, rgba(10,18,26,0.92) 100%)',
        }}
      />

      <HeroSidePanels reduce={reduce} delay={reduce ? 0 : T.side} />

      {/* Title just above the middle, message and buttons below it, so the
          middle of the globe stays clear. */}
      <div className="relative z-10 flex h-full flex-col items-center px-5 text-center">
        {/* Anchored by its bottom edge, so it always ends just above the
            middle of the globe whatever size the title is on this screen. */}
        <div className="absolute inset-x-0 bottom-[55%] flex justify-center px-5">
          <AssembledTitle delay={reduce ? 0 : T.title} reduce={reduce} />
        </div>

        <div className="mt-auto flex flex-col items-center pb-[clamp(3rem,18vh,11rem)]">
          <motion.h2
            {...reveal(reduce ? 0.2 : T.subhead)}
            className="text-[clamp(1rem,2.2vw,1.4rem)] font-medium leading-snug tracking-tight text-ink/85"
          >
            One railway. Many maintenance requests.
            <br className="sm:hidden" /> One optimised plan.
          </motion.h2>

          <motion.div
            {...reveal(reduce ? 0.3 : T.cta)}
            className="mt-6 flex flex-wrap items-center justify-center gap-3"
          >
            <Button as={Link} to="/login" size="cta" className="group tracking-wide">
              START CONTROL ROOM
              <ArrowRight size={16} className="transition-transform group-hover:translate-x-0.5" />
            </Button>
            <Button
              as="a"
              href="#how"
              onClick={scrollToHow}
              variant="ghost"
              size="cta"
              className="tracking-wide"
            >
              SEE HOW RAILOPT WORKS
            </Button>
          </motion.div>
        </div>
      </div>
    </section>
  )
}
