import { useEffect } from 'react'
import Nav from '@/components/landing/Nav'
import Hero from '@/components/landing/Hero'
import HowItWorks from '@/components/landing/HowItWorks'

/**
 * Two screens: the hero, and the one argument a judge needs before walking
 * into the control room. Nothing else — no pricing, no testimonials, no
 * feature grid. The product is the pitch.
 */
export default function Landing() {
  useEffect(() => {
    document.title = 'RailOpt — one block plan for three departments'
  }, [])

  return (
    <div className="min-h-screen overflow-x-hidden">
      <Nav />
      <Hero />
      <HowItWorks />
    </div>
  )
}
