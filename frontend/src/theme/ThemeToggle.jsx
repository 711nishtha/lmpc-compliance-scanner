import { useEffect, useState } from 'react'
import { applyTheme, resolveTheme, storedTheme } from './theme.js'

/** Nav control. Reflects the live theme and persists the user's choice. */
export default function ThemeToggle({ className = '' }) {
  const [theme, setTheme] = useState(() =>
    typeof document !== 'undefined'
      ? document.documentElement.getAttribute('data-theme') || resolveTheme()
      : 'light'
  )

  // Follow the OS only while the user has made no explicit choice.
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = (e) => {
      if (storedTheme()) return
      const next = e.matches ? 'dark' : 'light'
      document.documentElement.setAttribute('data-theme', next)
      document.documentElement.style.colorScheme = next
      setTheme(next)
    }
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  const toggle = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    applyTheme(next)
    setTheme(next)
  }

  const isDark = theme === 'dark'
  return (
    <button
      type="button"
      onClick={toggle}
      className={`theme-toggle ${className}`}
      aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
      title={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
    >
      <span aria-hidden="true">{isDark ? '☀' : '☾'}</span>
    </button>
  )
}
