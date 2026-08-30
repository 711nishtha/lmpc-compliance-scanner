/* App-wide theme control. Single source of truth for which palette is active.
 *
 * Resolution order: saved choice -> OS prefers-color-scheme -> light.
 * The initial value is applied in index.html BEFORE React mounts (see the inline
 * script there) so there is no flash of the wrong palette on first paint. */

const KEY = 'lmpc-theme'

export function systemTheme() {
  return typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-color-scheme: dark)').matches
    ? 'dark'
    : 'light'
}

export function storedTheme() {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'dark' || v === 'light' ? v : null
  } catch {
    return null // private mode / storage blocked
  }
}

export function resolveTheme() {
  return storedTheme() ?? systemTheme()
}

export function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme)
  // Lets the browser paint form controls/scrollbars to match.
  document.documentElement.style.colorScheme = theme
  try {
    localStorage.setItem(KEY, theme)
  } catch {
    /* not fatal — the theme still applies for this session */
  }
}
