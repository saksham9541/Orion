import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Wordmark from '@/components/common/Wordmark'
import Button from '@/components/common/Button'

/**
 * A minimal floating header. The landing page is one screen — the hero and
 * its call to the control room — so there is nothing to navigate to beyond
 * that, and no link list pretending otherwise.
 */
export default function Nav() {
  const [stuck, setStuck] = useState(false)

  useEffect(() => {
    const onScroll = () => setStuck(window.scrollY > 24)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <header
      // Forced dark: the landing page is one continuous hero stage, so the
      // nav stays legible over it regardless of the app-wide theme choice.
      // (Theme switching lives on the sign-in page and inside the portal,
      // where it visibly changes something.)
      className={`dark fixed inset-x-0 top-0 z-30 text-ink transition-colors duration-200 ${
        stuck ? 'bg-base/70 backdrop-blur-md' : 'bg-transparent'
      }`}
    >
      <div className="mx-auto flex max-w-[1180px] items-center justify-between px-5 py-4">
        <Link to="/" className="rounded-panel" aria-label="RailOpt home">
          <Wordmark />
        </Link>
        <div className="flex items-center gap-3">
          <Button as={Link} to="/login" size="sm" className="tracking-wide">
            START CONTROL ROOM
          </Button>
        </div>
      </div>
    </header>
  )
}
