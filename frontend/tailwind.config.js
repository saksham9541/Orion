/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    // `base` is the page-background colour token, and Tailwind's `text-base`
    // is also the 16px font-size class. With both defined, `text-base` set
    // the text colour to the page background: invisible text on any card.
    // Text colours therefore exclude `base`, so `text-base` can only ever
    // mean font size. (Use bg-base / border-base for the page colour.)
    textColor: ({ theme }) => {
      // eslint-disable-next-line no-unused-vars
      const { base, ...rest } = theme('colors')
      return rest
    },
    extend: {
      colors: {
        // Every token resolves through a CSS variable (set in index.css for
        // .dark / .light on <html>) so opacity modifiers like bg-base/90
        // keep working while the whole palette repaints on theme toggle.
        base: 'rgb(var(--c-base) / <alpha-value>)',
        deep: 'rgb(var(--c-deep) / <alpha-value>)',
        surface: 'rgb(var(--c-surface) / <alpha-value>)',
        raised: 'rgb(var(--c-raised) / <alpha-value>)',
        line: 'rgb(var(--c-line) / <alpha-value>)',
        hair: 'rgb(var(--c-hair) / <alpha-value>)',

        ink: 'rgb(var(--c-ink) / <alpha-value>)',
        muted: 'rgb(var(--c-muted) / <alpha-value>)',
        faint: 'rgb(var(--c-faint) / <alpha-value>)',

        // Department lamps. These are functional, not decorative — each one
        // identifies a maintenance department everywhere it appears.
        eng: 'rgb(var(--c-eng) / <alpha-value>)', // Engineering / permanent way
        snt: 'rgb(var(--c-snt) / <alpha-value>)', // Signal & Telecom
        trd: 'rgb(var(--c-trd) / <alpha-value>)', // Traction Distribution
        merge: 'rgb(var(--c-merge) / <alpha-value>)', // the colour of a shared block: all three, resolved

        danger: 'rgb(var(--c-danger) / <alpha-value>)',
        warn: 'rgb(var(--c-warn) / <alpha-value>)',
        ok: 'rgb(var(--c-ok) / <alpha-value>)',
        high: 'rgb(var(--c-high) / <alpha-value>)', // "High" severity, between warn and danger
        info: 'rgb(var(--c-info) / <alpha-value>)', // acknowledged / notified

        // Panel title bars stay dark in both themes, so their text tokens are
        // fixed rather than following ink/muted.
        bar: 'rgb(var(--c-bar) / <alpha-value>)',
        onbar: 'rgb(var(--c-onbar) / <alpha-value>)',
        barmuted: 'rgb(var(--c-barmuted) / <alpha-value>)',
      },
      fontFamily: {
        sans: ['Archivo', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        '7xl': ['4.75rem', { lineHeight: '0.94', letterSpacing: '-0.035em' }],
        '6xl': ['3.75rem', { lineHeight: '0.96', letterSpacing: '-0.03em' }],
        '5xl': ['3rem', { lineHeight: '1', letterSpacing: '-0.025em' }],
      },
      borderRadius: {
        panel: '10px',
        'panel-lg': '16px',
        lamp: '2px',
      },
      boxShadow: {
        panel: '0 1px 0 0 rgba(255,255,255,0.04) inset, 0 4px 24px -8px rgba(0,0,0,0.12), 0 12px 48px -16px rgba(0,0,0,0.10)',
        lift: '0 24px 56px -20px rgba(0,0,0,0.25)',
      },
      keyframes: {
        pulseRing: {
          '0%': { transform: 'scale(0.7)', opacity: '0.55' },
          '100%': { transform: 'scale(2.1)', opacity: '0' },
        },
        drift: {
          '0%,100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-6px)' },
        },
        sweep: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(320%)' },
        },
        blink: {
          '0%,45%': { opacity: '1' },
          '55%,100%': { opacity: '0.28' },
        },
        auroraA: {
          '0%, 100%': { transform: 'translate(0, 0) scale(1)' },
          '50%': { transform: 'translate(6%, 8%) scale(1.12)' },
        },
        auroraB: {
          '0%, 100%': { transform: 'translate(0, 0) scale(1.05)' },
          '50%': { transform: 'translate(-8%, 5%) scale(0.95)' },
        },
        auroraC: {
          '0%, 100%': { transform: 'translate(0, 0) scale(0.98)' },
          '50%': { transform: 'translate(4%, -7%) scale(1.08)' },
        },
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '200% 0' },
          '100%': { backgroundPosition: '-200% 0' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(24px) scale(0.97)' },
          '100%': { opacity: '1', transform: 'translateY(0) scale(1)' },
        },
        slideRight: {
          '0%': { opacity: '0', transform: 'translateX(-20px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.92)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        countUp: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        glowPulse: {
          '0%, 100%': { boxShadow: '0 0 20px -5px rgb(var(--c-eng) / 0.15)' },
          '50%': { boxShadow: '0 0 30px -5px rgb(var(--c-eng) / 0.3)' },
        },
      },
      animation: {
        pulseRing: 'pulseRing 2.6s ease-out infinite',
        drift: 'drift 6s ease-in-out infinite',
        sweep: 'sweep 3.2s ease-in-out infinite',
        blink: 'blink 1.8s ease-in-out infinite',
        auroraA: 'auroraA 22s ease-in-out infinite',
        auroraB: 'auroraB 26s ease-in-out infinite',
        auroraC: 'auroraC 19s ease-in-out infinite',
        fadeUp: 'fadeUp 0.6s cubic-bezier(0.16,1,0.3,1) both',
        shimmer: 'shimmer 2.4s ease-in-out infinite',
        slideUp: 'slideUp 0.7s cubic-bezier(0.16,1,0.3,1) both',
        slideRight: 'slideRight 0.6s cubic-bezier(0.16,1,0.3,1) both',
        scaleIn: 'scaleIn 0.5s cubic-bezier(0.16,1,0.3,1) both',
        countUp: 'countUp 0.5s cubic-bezier(0.16,1,0.3,1) both',
        glowPulse: 'glowPulse 3s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
