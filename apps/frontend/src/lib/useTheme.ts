/**
 * Widened theme control (replaces the DashShell-local useState).
 *
 * lib/theme.ts already resolves the right initial value; the gap was that only
 * `.dz-root` ever received `data-theme`, so the Studio and the toast layer sat
 * outside it. Stamping <html> instead means one attribute themes every surface,
 * including portalled overlays (command palette, dialogs) that are not DOM
 * children of the dashboard.
 *
 * Drop-in: replace `const [theme, setTheme] = useState<Theme>(initialTheme)`
 * in DashShell with `const { theme, toggle } = useTheme()`, and delete the
 * `data-theme={theme}` prop on .dz-root (the attribute now lives on <html>).
 */
import { useCallback, useEffect, useState } from 'react';
import { initialTheme, saveTheme, type Theme } from './theme';

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    saveTheme(theme);
  }, [theme]);

  const toggle = useCallback(() => setTheme((t) => (t === 'dark' ? 'light' : 'dark')), []);

  return { theme, setTheme, toggle };
}
