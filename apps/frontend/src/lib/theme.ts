/**
 * Which theme the themed surfaces render in (v2 Part 35, extracted in Part 44).
 *
 * This lived inside DashShell, which meant only the dashboard could reach it.
 * The auth pages render the same `.dz-root` token surface but had no way to
 * stamp `data-theme`, so they always fell through to the dark default — you
 * could be on a white dashboard, click "Sign in", and land on a black page.
 * The committed browser harness caught that on its first run.
 *
 * The Studio stays deliberately dark regardless. It is a canvas tool, like every
 * professional editor, and a bright chrome around artwork misleads the eye.
 */

export type Theme = 'light' | 'dark';

export const THEME_KEY = 'stitchiq:theme';

/** What the browser can tell us, injected so the resolver is testable in node. */
export interface ThemeEnv {
  read: () => string | null;
  prefersLight: () => boolean;
}

const browserEnv: ThemeEnv = {
  read: () => {
    try {
      return localStorage.getItem(THEME_KEY);
    } catch {
      return null;
    }
  },
  prefersLight: () => window.matchMedia?.('(prefers-color-scheme: light)').matches ?? false,
};

/** Saved choice if there is one, otherwise the OS preference, otherwise dark. */
export function initialTheme(env: ThemeEnv = browserEnv): Theme {
  const saved = env.read();
  if (saved === 'light' || saved === 'dark') return saved;
  return env.prefersLight() ? 'light' : 'dark';
}

export function saveTheme(theme: Theme): void {
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    /* no storage */
  }
}
