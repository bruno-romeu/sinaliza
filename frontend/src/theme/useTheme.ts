import { useCallback, useState } from 'react'

export type ThemePreference = 'system' | 'light' | 'dark'

const STORAGE_KEY = 'sinaliza.theme'
const ORDER: ThemePreference[] = ['system', 'light', 'dark']

function isThemePreference(value: unknown): value is ThemePreference {
  return value === 'system' || value === 'light' || value === 'dark'
}

// Storage can be unavailable (private browsing, blocked site data) and then
// throws; the theme still works for the session, it just is not remembered.
function readStoredPreference(): ThemePreference {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return isThemePreference(raw) ? raw : 'system'
  } catch {
    return 'system'
  }
}

// Mirrors the inline script in `index.html` (same storage key, same logic),
// which runs before React mounts so the first paint never flashes the wrong
// theme. This re-applies it on every change after mount.
function applyPreference(preference: ThemePreference) {
  const root = document.documentElement
  if (preference === 'system') {
    root.removeAttribute('data-theme')
  } else {
    root.setAttribute('data-theme', preference)
  }
  try {
    localStorage.setItem(STORAGE_KEY, preference)
  } catch {
    // Not remembered across visits; the current page still switches theme.
  }
}

/**
 * No React context on purpose: `<Header>` (and so every authenticated page
 * via `<Page>`) calls this directly. The only shared state is the DOM
 * attribute + `localStorage`, which every instance reads/writes the same
 * way, so a context provider would add indirection without adding anything
 * — and would otherwise have to wrap every page-level test render.
 */
export function useTheme(): { preference: ThemePreference; cycle: () => void } {
  const [preference, setPreference] = useState<ThemePreference>(() => readStoredPreference())

  const cycle = useCallback(() => {
    setPreference((current) => {
      const next = ORDER[(ORDER.indexOf(current) + 1) % ORDER.length]
      applyPreference(next)
      return next
    })
  }, [])

  return { preference, cycle }
}
