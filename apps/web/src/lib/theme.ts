// Theme choice: light (default), dark, or follow the system. index.html applies it before the first paint.
export type ThemeChoice = 'light' | 'dark' | 'system'

const KEY = 'gigbid-theme'
const darkQuery = () => window.matchMedia('(prefers-color-scheme: dark)')

export function themeChoice(): ThemeChoice {
  try {
    const saved = localStorage.getItem(KEY)
    return saved === 'dark' || saved === 'system' ? saved : 'light'
  } catch {
    return 'light'
  }
}

export function applyTheme(choice: ThemeChoice): void {
  const dark = choice === 'dark' || (choice === 'system' && darkQuery().matches)
  document.documentElement.dataset.theme = dark ? 'dark' : 'light'
}

export function setThemeChoice(choice: ThemeChoice): void {
  try {
    localStorage.setItem(KEY, choice)
  } catch {
    // private mode: the choice still applies for this visit
  }
  applyTheme(choice)
}

/** Re-apply when the system theme changes, while the user follows the system. Returns an unsubscribe function. */
export function followSystem(onChange: () => void): () => void {
  const query = darkQuery()
  query.addEventListener('change', onChange)
  return () => query.removeEventListener('change', onChange)
}
