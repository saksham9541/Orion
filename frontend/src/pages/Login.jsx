import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AnimatePresence, motion, useAnimationControls, useReducedMotion } from 'framer-motion'
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Check,
  Eye,
  EyeOff,
  Hammer,
  Loader2,
  Lock,
  RadioTower,
  ShieldCheck,
  Wrench,
  Zap,
} from 'lucide-react'
import { useAppState } from '@/state/AppState'
import LoginScene from '@/components/login/LoginScene'
import Logo from '@/components/common/Logo'
import Wordmark from '@/components/common/Wordmark'

/** One card per department. `accent` tints the scene, the focus ring and the button. */
const DEPARTMENTS = [
  { id: 'admin', label: 'Super Admin', hint: 'Operations', icon: ShieldCheck, accent: '#F7861E', example: 'admin@railopt.gov.in' },
  { id: 'engineering', label: 'Engineering', hint: 'Permanent way', icon: Wrench, accent: '#F7861E', example: 'eng@railopt.gov.in' },
  { id: 'snt', label: 'S&T', hint: 'Signal & Telecom', icon: RadioTower, accent: '#F7861E', example: 'snt@railopt.gov.in' },
  { id: 'trd', label: 'TRD', hint: 'Traction', icon: Zap, accent: '#F7861E', example: 'trd@railopt.gov.in' },
  { id: 'technician', label: 'Technician', hint: 'Field jobs', icon: Hammer, accent: '#F7861E', example: 'tech@railopt.gov.in' },
]
const DEFAULT_ACCENT = '#F7861E'
const ICON_TINT = '#FFC48A'

/** Login-only colour tokens: frosted dark glass over the photo, Vande Bharat orange accent. Scoped, so the rest of the app keeps its theme. */
const LOGIN_THEME = {
  '--c-base': '101 99 94', // #65635E
  '--c-deep': '30 27 25',
  '--c-surface': '24 21 19',
  '--c-raised': '110 66 30',
  '--c-line': '112 104 99',
  '--c-hair': '70 66 62',
  '--c-ink': '255 255 255',
  '--c-muted': '210 205 198',
  '--c-faint': '178 172 164',
  '--c-danger': '255 150 140',
  '--c-warn': '255 176 90',
}

export default function Login() {
  const navigate = useNavigate()
  const { login, authenticate } = useAppState()
  const reduce = useReducedMotion()

  const [roleId, setRoleId] = useState(null)
  const [userId, setUserId] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [caps, setCaps] = useState(false)
  const [error, setError] = useState(null) // { msg, field }
  const [phase, setPhase] = useState('idle') // idle | loading | success
  const [offline, setOffline] = useState(false)

  // The login screen is a single fixed viewport: no page scrolling.
  useEffect(() => {
    const html = document.documentElement
    const prev = [html.style.overflow, document.body.style.overflow]
    html.style.overflow = 'hidden'
    document.body.style.overflow = 'hidden'
    return () => {
      html.style.overflow = prev[0]
      document.body.style.overflow = prev[1]
    }
  }, [])

  const dept = DEPARTMENTS.find((d) => d.id === roleId) || null
  const accent = dept?.accent || DEFAULT_ACCENT
  const idRef = useRef(null)
  const pwRef = useRef(null)
  const shakeCtl = { role: useAnimationControls(), id: useAnimationControls(), password: useAnimationControls() }

  const fail = (msg, field) => {
    setError({ msg, field })
    if (!reduce && shakeCtl[field]) shakeCtl[field].start({ x: [0, -8, 8, -6, 6, 0], transition: { duration: 0.4 } })
    setPhase('idle')
    if (field === 'id') idRef.current?.focus()
    if (field === 'password') {
      setPassword('')
      pwRef.current?.focus()
    }
  }

  const pickRole = (id) => {
    setRoleId(id)
    if (error) setError(null)
    // fill in the department's email, so only the password is left to type
    const picked = DEPARTMENTS.find((d) => d.id === id)
    if (picked) setUserId(picked.example)
    setPassword('')
    setTimeout(() => pwRef.current?.focus(), 60)
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    if (phase !== 'idle') return
    setError(null)
    if (!roleId) return fail('Choose your department first.', 'role')
    setPhase('loading')
    const res = await authenticate(roleId, userId, password)
    if (!res.ok) return fail(res.error, res.field)
    setOffline(Boolean(res.offline))
    setPhase('success')
    await new Promise((r) => setTimeout(r, reduce ? 300 : 1500))
    await login(roleId, res)
    navigate(roleId === 'admin' ? '/admin' : `/${roleId}`)
  }

  const trackCaps = (e) => setCaps(e.getModifierState?.('CapsLock') ?? false)

  return (
    <div className="dark relative h-screen h-[100dvh] overflow-hidden bg-base font-sans text-ink" style={LOGIN_THEME}>
      <LoginScene />

      <button
        type="button"
        onClick={() => navigate('/')}
        className="absolute left-4 top-4 z-20 inline-flex items-center gap-1.5 rounded-lg border border-white/20 bg-deep/60 px-3 py-1.5 text-xs font-semibold text-ink/90 backdrop-blur transition-colors hover:bg-deep/80 sm:left-7 sm:top-[27px]"
      >
        <ArrowLeft size={14} />
        <span>Back to Home</span>
      </button>

      <div className="absolute right-4 top-4 z-20 sm:right-7 sm:top-[27px]" aria-label="Orion">
        <Wordmark />
      </div>

      <main className="relative z-10 flex h-full items-center justify-center px-4 pb-[72px]">
        <div className="relative w-full max-w-[474px]">
            <div className="relative rounded-3xl border border-white/25 p-6 shadow-[0_30px_80px_-24px_rgba(0,0,0,0.6),inset_0_1px_0_rgba(255,255,255,0.22)] backdrop-blur-xl backdrop-saturate-150 sm:px-8 sm:pb-6 sm:pt-8" style={{ background: 'linear-gradient(160deg, rgba(40,34,32,0.58), rgba(22,19,18,0.68))' }}>
          <motion.div
            initial={reduce ? false : { opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
          >
            <h2 className="text-3xl font-semibold leading-9 tracking-tight">Welcome back</h2>
            <p className="text-sm text-muted">Choose your department, then sign in.</p>
          </motion.div>

          <form onSubmit={handleSubmit} noValidate className="mt-3" style={{ '--acc': accent, '--acc-soft': `${accent}33` }}>
            {/* department cards: native radios, so arrow keys / tab / screen readers just work */}
            <motion.fieldset animate={shakeCtl.role}>
              <legend className="mb-2 text-[11px] font-bold uppercase leading-4 tracking-wider text-faint">Department</legend>
              <div className="grid grid-cols-3 gap-2" role="radiogroup" aria-label="Department">
                {DEPARTMENTS.map((d, i) => {
                  const Icon = d.icon
                  const on = roleId === d.id
                  return (
                    <motion.label
                      key={d.id}
                      initial={reduce ? false : { opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.12 + i * 0.05, duration: 0.35 }}
                      whileHover={reduce ? undefined : { y: -2 }}
                      whileTap={reduce ? undefined : { scale: 0.97 }}
                      className={`group relative cursor-pointer overflow-hidden rounded-xl border px-3 pb-[7px] pt-2 transition-colors focus-within:ring-2 focus-within:ring-[var(--acc)] ${
                        on ? 'border-transparent bg-raised' : 'border-white/15 bg-white/[0.07] hover:border-white/30'
                      }`}
                    >
                      <input
                        type="radio"
                        name="department"
                        value={d.id}
                        checked={on}
                        onChange={() => pickRole(d.id)}
                        className="sr-only"
                      />
                      {on && (
                        <motion.span
                          layoutId="dept-highlight"
                          className="absolute inset-0 rounded-xl border-2"
                          style={{ borderColor: d.accent, boxShadow: `0 0 22px ${d.accent}40, inset 0 0 18px ${d.accent}14` }}
                          transition={{ type: 'spring', stiffness: 420, damping: 34 }}
                        />
                      )}
                      <span
                        className="relative mb-1.5 flex h-6 w-6 items-center justify-center rounded-md transition-colors"
                        style={{ background: `${d.accent}${on ? '33' : '1f'}`, color: ICON_TINT }}
                      >
                        <Icon size={14} strokeWidth={2.1} />
                      </span>
                      <span className="relative block text-[13px] font-semibold leading-4">{d.label}</span>
                      <span className="relative block whitespace-nowrap text-[11px] leading-[14px] text-muted">{d.hint}</span>
                      {on && (
                        <motion.span
                          initial={{ scale: 0 }}
                          animate={{ scale: 1 }}
                          className="absolute right-2 top-2 flex h-4 w-4 items-center justify-center rounded-full text-[#1D0E04]"
                          style={{ background: d.accent }}
                        >
                          <Check size={11} strokeWidth={3.2} />
                        </motion.span>
                      )}
                    </motion.label>
                  )
                })}
              </div>
            </motion.fieldset>

            <motion.div animate={shakeCtl.id} className="mt-3.5">
              <FloatField
                id="login-user"
                label="User ID / Email"
                inputRef={idRef}
                value={userId}
                onChange={(v) => {
                  setUserId(v)
                  if (error) setError(null)
                }}
                autoComplete="username"
                invalid={error?.field === 'id'}
              />
            </motion.div>

            <motion.div animate={shakeCtl.password} className="mt-[11px]">
              <FloatField
                id="login-password"
                label="Password"
                inputRef={pwRef}
                type={showPw ? 'text' : 'password'}
                value={password}
                onChange={(v) => {
                  setPassword(v)
                  if (error) setError(null)
                }}
                onKeyEvent={trackCaps}
                onBlur={() => setCaps(false)}
                autoComplete="current-password"
                invalid={error?.field === 'password'}
                icon={Lock}
                trailing={
                  <button
                    type="button"
                    onClick={() => setShowPw((v) => !v)}
                    aria-label={showPw ? 'Hide password' : 'Show password'}
                    aria-pressed={showPw}
                    className="flex h-8 w-8 items-center justify-center rounded-md text-muted transition-colors hover:bg-raised hover:text-ink"
                  >
                    {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                }
              />
              <AnimatePresence>
                {caps && (
                  <motion.p
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="mt-1.5 flex items-center gap-1.5 overflow-hidden text-xs font-medium text-warn"
                  >
                    <AlertCircle size={13} /> Caps Lock is on
                  </motion.p>
                )}
              </AnimatePresence>
            </motion.div>

            <div aria-live="assertive">
              <AnimatePresence mode="wait">
                {error && (
                  <motion.p
                    key={error.msg}
                    role="alert"
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="mt-2 flex items-start gap-1.5 text-[13px] font-medium text-danger"
                  >
                    <AlertCircle size={15} className="mt-px shrink-0" /> {error.msg}
                  </motion.p>
                )}
              </AnimatePresence>
            </div>

            <motion.button
              type="submit"
              disabled={phase !== 'idle'}
              whileHover={reduce || phase !== 'idle' ? undefined : { scale: 1.015 }}
              whileTap={reduce || phase !== 'idle' ? undefined : { scale: 0.98 }}
              className="relative mt-4 flex h-[50px] w-full items-center justify-center gap-2 overflow-hidden rounded-xl text-sm font-bold uppercase tracking-widest text-[#1D0E04] shadow-lg transition-[background-color,box-shadow] duration-500 disabled:cursor-default"
              style={{ background: `linear-gradient(135deg, #FFB04A, ${accent} 55%, #F26A0F)`, boxShadow: `0 14px 30px -12px ${accent}` }}
            >
              <AnimatePresence mode="wait" initial={false}>
                {phase === 'idle' && (
                  <motion.span key="idle" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="flex items-center gap-2">
                    Sign in <ArrowRight size={16} strokeWidth={2.6} />
                  </motion.span>
                )}
                {phase === 'loading' && (
                  <motion.span key="loading" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="flex items-center gap-2">
                    <Loader2 size={16} className="animate-spin" /> Verifying
                  </motion.span>
                )}
                {phase === 'success' && (
                  <motion.span key="ok" initial={{ opacity: 0, scale: 0.6 }} animate={{ opacity: 1, scale: 1 }} className="flex items-center gap-2">
                    <Check size={18} strokeWidth={3} /> Verified
                  </motion.span>
                )}
              </AnimatePresence>
            </motion.button>
          </form>

            </div>
        </div>
      </main>


      {/* ------------------------------------------------------ hand-off screen */}
      <AnimatePresence>
        {phase === 'success' && <Handoff accent={accent} label={dept?.label} offline={offline} reduce={reduce} />}
      </AnimatePresence>
    </div>
  )
}

/** Input with a label that floats up on focus / when filled. */
function FloatField({ id, label, value, onChange, type = 'text', inputRef, autoComplete, invalid, hint, icon: Icon, trailing, onKeyEvent, onBlur }) {
  return (
    <div>
      <div className="relative">
        <input
          id={id}
          ref={inputRef}
          type={type}
          value={value}
          placeholder=" "
          autoComplete={autoComplete}
          spellCheck={false}
          autoCapitalize="none"
          aria-invalid={invalid || undefined}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyEvent}
          onKeyUp={onKeyEvent}
          onBlur={onBlur}
          className={`peer h-[50px] w-full rounded-xl border bg-black/30 pb-1.5 pt-5 text-sm text-ink outline-none transition-[border-color,box-shadow] duration-200 ${
            Icon ? 'pl-10' : 'pl-3.5'
          } ${trailing ? 'pr-11' : 'pr-3.5'} ${
            invalid
              ? 'border-danger shadow-[0_0_0_3px_rgb(var(--c-danger)/0.18)]'
              : 'border-faint/60 focus:border-[var(--acc)] focus:shadow-[0_0_0_3px_var(--acc-soft)]'
          }`}
        />
        {Icon && <Icon size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-faint transition-colors peer-focus:text-[var(--acc)]" />}
        <label
          htmlFor={id}
          className={`pointer-events-none absolute top-1.5 text-[10px] font-bold uppercase tracking-wider text-faint transition-all duration-150 peer-placeholder-shown:top-[15px] peer-placeholder-shown:text-[13px] peer-placeholder-shown:font-medium peer-placeholder-shown:normal-case peer-placeholder-shown:tracking-normal peer-focus:top-1.5 peer-focus:text-[10px] peer-focus:font-bold peer-focus:uppercase peer-focus:tracking-wider peer-focus:text-[var(--acc)] ${
            Icon ? 'left-10' : 'left-3.5'
          }`}
        >
          {label}
        </label>
        {trailing && <div className="absolute right-1.5 top-1/2 -translate-y-1/2">{trailing}</div>}
      </div>
      {hint && <p className="mt-1 pl-1 font-mono text-[11px] text-faint">{hint}</p>}
    </div>
  )
}

/** Full-screen "Authorizing -> Loading workspace" transition shown after a successful sign-in. */
function Handoff({ accent, label, offline, reduce }) {
  const [step, setStep] = useState(0)
  useEffect(() => {
    const t = setTimeout(() => setStep(1), reduce ? 100 : 650)
    return () => clearTimeout(t)
  }, [reduce])
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.35 }}
      className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-[#2C2E30] text-slate-100"
      role="status"
      aria-live="polite"
    >
      <div
        aria-hidden
        className="absolute h-[420px] w-[420px] rounded-full opacity-20 blur-3xl"
        style={{ background: accent }}
      />
      <motion.div initial={{ scale: 0.7, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ type: 'spring', stiffness: 220, damping: 18 }} className="relative">
        <Logo size={64} animated />
      </motion.div>
      <div className="relative mt-6 h-6 overflow-hidden text-center font-mono text-sm text-slate-300">
        <AnimatePresence mode="wait" initial={false}>
          <motion.p key={step} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
            {step === 0 ? 'Authorizing…' : `Loading ${label} workspace…`}
          </motion.p>
        </AnimatePresence>
      </div>
      <div className="relative mt-4 h-[3px] w-56 overflow-hidden rounded-full bg-white/10">
        <motion.div
          className="h-full rounded-full"
          style={{ background: accent }}
          initial={{ width: '0%' }}
          animate={{ width: '100%' }}
          transition={{ duration: reduce ? 0.2 : 1.4, ease: 'easeInOut' }}
        />
      </div>
      {offline && (
        <p className="relative mt-5 font-mono text-[11px] uppercase tracking-wider text-rose-300/80">
          Server unreachable · signed in with built-in demo account
        </p>
      )}
    </motion.div>
  )
}
