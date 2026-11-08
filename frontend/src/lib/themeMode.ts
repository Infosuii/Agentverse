import { useSyncExternalStore } from 'react';

/** Light or dark appearance. Dark is the default; the choice is remembered in this browser only. */
export type ThemeMode = 'dark' | 'light';

export const THEME_STORAGE_KEY = 'jane-avenue-theme';
const THEME_COLOR: Record<ThemeMode, string> = { dark: '#0d1411', light: '#f8faf9' };

const listeners = new Set<() => void>();

function current(): ThemeMode {
  return document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
}

export function setThemeMode(mode: ThemeMode): void {
  document.documentElement.dataset.theme = mode;
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', THEME_COLOR[mode]);
  try {
    localStorage.setItem(THEME_STORAGE_KEY, mode);
  } catch {
    // Private windows can refuse storage; the theme still applies for this visit.
  }
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useThemeMode(): ThemeMode {
  return useSyncExternalStore(subscribe, current, () => 'dark');
}
