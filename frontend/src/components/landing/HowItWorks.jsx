import { Link } from 'react-router-dom'
import { motion, useReducedMotion } from 'framer-motion'
import { ArrowRight } from 'lucide-react'
import Button from '@/components/common/Button'

/**
 * Four stages, one sentence each. This is a real sequence, so the numbering
 * carries information. Everything the older version of this section said
 * (the worked conflict, the before/after figures) now lives in the control
 * room itself, where it can be inspected instead of read.
 */
const STAGES = [
  { n: '01', name: 'CAPTURE', line: 'Maintenance requests are collected.' },
  { n: '02', name: 'ASSESS', line: 'RailOpt evaluates priority and risk.' },
  { n: '03', name: 'OPTIMISE', line: 'RailOpt creates an efficient maintenance plan.' },
  { n: '04', name: 'ACT', line: 'Teams receive clear operational actions.' },
]

export default function HowItWorks() {
  const reduce = useReducedMotion()

  return (
    <section
      id="how"
      className="dark relative scroll-mt-16 border-t border-hair bg-[#0A121A] px-5 py-20 text-ink sm:px-8 sm:py-24"
    >
      <div className="mx-auto max-w-[1080px]">
        <h2 className="text-[clamp(1.5rem,3.4vw,2.1rem)] font-semibold leading-tight tracking-tight">
          How RailOpt works
        </h2>

        <ol className="mt-12 grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-4">
          {STAGES.map((s, i) => (
            <motion.li
              key={s.n}
              initial={reduce ? false : { opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{ delay: i * 0.08, duration: 0.5 }}
            >
              {/* A short length of track with a stop at its start. */}
              <div className="relative h-px bg-line" aria-hidden="true">
                <span className="absolute -top-[3px] left-0 h-[7px] w-[7px] rounded-full bg-merge" />
              </div>
              <p className="tnum mt-5 font-mono text-[12px] text-faint">{s.n}</p>
              <h3 className="mt-2 text-[15px] font-semibold tracking-wide">{s.name}</h3>
              <p className="mt-2 max-w-[26ch] text-[14.5px] leading-relaxed text-muted">{s.line}</p>
            </motion.li>
          ))}
        </ol>

        <div className="mt-16 flex flex-col items-start gap-4">
          <Button as={Link} to="/login" size="cta" className="group tracking-wide">
            START CONTROL ROOM
            <ArrowRight size={16} className="transition-transform group-hover:translate-x-0.5" />
          </Button>
          <p className="text-[12px] leading-relaxed text-faint">
            Prototype with demonstration data. RailOpt recommends; a railway official approves.
          </p>
        </div>
      </div>
    </section>
  )
}
