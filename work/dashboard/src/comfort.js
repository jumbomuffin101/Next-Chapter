// Display preferences, saved in this browser:
// comfort mode (calmer reading for neurodivergent users: no motion, no ALL CAPS, a plainer font) and light/dark theme.
const KEY = 'tkh-comfort'

export function readComfort() {
  try { return localStorage.getItem(KEY) === 'on' } catch { return false }
}

// The CSS keys off <html data-comfort="on">, so it reaches the navbar and dialogs too
export function applyComfort(on) {
  document.documentElement.dataset.comfort = on ? 'on' : 'off'
}

export function saveComfort(on) {
  applyComfort(on)
  try { localStorage.setItem(KEY, on ? 'on' : 'off') } catch { /* storage blocked: applies until the page reloads */ }
}

// Scrolling that jumps instead of gliding when comfort mode or the device's "reduce motion" asks for it
export const scrollBehavior = () =>
  readComfort() || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'

// ---- light / dark theme: 'light' (default) | 'dark' | 'system' (follow the device)
const THEME_KEY = 'tkh-theme'
const deviceDark = () => Boolean(window.matchMedia?.('(prefers-color-scheme: dark)').matches)

export function readTheme() {
  try { return localStorage.getItem(THEME_KEY) || 'light' } catch { return 'light' }
}

export function applyTheme(choice) {
  document.documentElement.dataset.theme = choice === 'dark' || (choice === 'system' && deviceDark()) ? 'dark' : 'light'
}

export function saveTheme(choice) {
  applyTheme(choice)
  try { localStorage.setItem(THEME_KEY, choice) } catch { /* storage blocked: applies until the page reloads */ }
}

// With 'system', switch live when the device changes between light and dark
export function followDeviceTheme() {
  window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener?.('change', () => { if (readTheme() === 'system') applyTheme('system') })
}
