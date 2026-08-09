import { readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { initialTheme, type ThemeEnv } from './theme';

function env(saved: string | null, prefersLight: boolean): ThemeEnv {
  return { read: () => saved, prefersLight: () => prefersLight };
}

describe('initialTheme', () => {
  it('honours a saved choice over the OS preference', () => {
    expect(initialTheme(env('light', false))).toBe('light');
    expect(initialTheme(env('dark', true))).toBe('dark');
  });

  it('falls back to the OS preference when nothing is saved', () => {
    expect(initialTheme(env(null, true))).toBe('light');
    expect(initialTheme(env(null, false))).toBe('dark');
  });

  it('ignores a corrupted stored value rather than trusting it', () => {
    expect(initialTheme(env('purple', true))).toBe('light');
    expect(initialTheme(env('', false))).toBe('dark');
  });
});

/**
 * THE CONTRACT INVERTED, AND THIS FILE INVERTED WITH IT (Atelier handoff).
 *
 * The original regression (v2 Part 44): `.dz-root` carried the token set and
 * selected it with a `data-theme` attribute on that same element. AuthPages
 * rendered `.dz-root` without one, so sign-in always resolved to the dark
 * default — a light-mode user went from a white dashboard to a black sign-in
 * page. Every unit test passed; only a screenshot showed it. So this file
 * asserted that EVERY `.dz-root` site carries `data-theme`.
 *
 * That rule is now exactly backwards. `data-theme` lives on <html>, stamped
 * once in main.tsx and owned by useTheme(), because a `.dz-root`-scoped
 * attribute could only ever theme the dashboard subtree: the Studio was
 * hard-dark and portalled overlays — command palette, dialogs, toasts — sat
 * outside it entirely. A `data-theme` on `.dz-root` today would be worse than
 * redundant; it would pin that subtree to the value resolved at mount and
 * leave it behind when the viewer toggles.
 *
 * Same technique, opposite assertion, and the same defect class either way: a
 * surface whose theme disagrees with the rest of the app.
 */
describe('data-theme is stamped on <html>, never on .dz-root', () => {
  const SRC = path.resolve(__dirname, '..');

  function tsxFiles(dir: string): string[] {
    return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
      const full = path.join(dir, e.name);
      if (e.isDirectory()) return tsxFiles(full);
      return e.isFile() && e.name.endsWith('.tsx') ? [full] : [];
    });
  }

  const offenders: string[] = [];
  for (const file of tsxFiles(SRC)) {
    const text = readFileSync(file, 'utf8');
    for (const tag of text.match(/<[a-zA-Z][^>]*className={?["'`][^"'`]*\bdz-root\b[^>]*>/g) ?? []) {
      if (tag.includes('data-theme')) {
        offenders.push(`${path.relative(SRC, file)}: ${tag.slice(0, 90)}`);
      }
    }
  }

  it('has no .dz-root carrying its own data-theme', () => {
    expect(offenders).toEqual([]);
  });

  it('stamps the resolved theme on <html> before first paint', () => {
    // Not in useTheme() alone: that hook only runs while the dashboard is
    // mounted, so landing straight on the Studio would leave <html> bare and
    // atelier.css would fall through to its light :root values.
    const main = readFileSync(path.join(SRC, 'main.tsx'), 'utf8');
    expect(main).toMatch(/documentElement\.setAttribute\(\s*'data-theme'/);
    expect(main).toContain('initialTheme()');
  });

  it('routes every theme change through the one hook', () => {
    const shell = readFileSync(path.join(SRC, 'components/dash/DashShell.tsx'), 'utf8');
    expect(shell).toContain('useTheme()');
    expect(shell).not.toMatch(/useState<Theme>/);
  });
});
