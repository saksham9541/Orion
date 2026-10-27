import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'railopt-theme'
const THEME_COLOR = { dark: '#0E1821', light: '#F4F6F9' }

function getInitialTheme() {
  if (typeof window === 'undefined') return 'light'
  const stored = window.localStorage.getItem(STORAGE_KEY)
  if (stored === 'light' || stored === 'dark') return stored
  // The portal opens in light theme; index.html's inline script already
  // applied the theme before first paint, this just keeps React in sync.
  return document.documentElement.classList.contains('dark') ? 'dark' : 'light'
}

/**
 * Single source of truth for the app's colour theme. Applies the `dark` /
 * `light` class to <html> (which every CSS variable in index.css keys off
 * of), persists the choice, and keeps the mobile theme-color meta in step.
 */
export function useTheme() {
  const [theme, setTheme] = useState(getInitialTheme)

  useEffect(() => {
    const root = document.documentElement
    root.classList.remove('light', 'dark')
    root.classList.add(theme)
    root.style.colorScheme = theme
    window.localStorage.setItem(STORAGE_KEY, theme)

    const meta = document.querySelector('meta[name="theme-color"]')
    if (meta) meta.setAttribute('content', THEME_COLOR[theme])
  }, [theme])

  const toggle = useCallback(() => {
    setTheme((t) => (t === 'dark' ? 'light' : 'dark'))
  }, [])

  return { theme, toggle, isDark: theme === 'dark' }
}
