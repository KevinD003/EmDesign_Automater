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
 * The regression this file exists for (v2 Part 44).
 *
 * `.dz-root` carries the light/dark token set, and the tokens are selected by a
 * `data-theme` attribute on that same element. AuthPages rendered `.dz-root`
 * without one, so sign-in / sign-up / forgot always resolved to the dark default
 * — a light-mode user went from a white dashboard to a black sign-in page. Every
 * unit test passed; only a screenshot showed it.
 *
 * A DOM test would be the natural guard, but the frontend has no jsdom and no
 * testing-library, and adding both to catch one missing attribute is a poor
 * trade. Scanning the source for the pairing costs nothing and fails on exactly
 * the mistake that was made.
 */
describe('every .dz-root render site sets data-theme', () => {
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
    // Each JSX opening tag whose className mentions dz-root.
    for (const tag of text.match(/<[a-zA-Z][^>]*className={?["'`][^"'`]*\bdz-root\b[^>]*>/g) ?? []) {
      if (!tag.includes('data-theme')) {
        offenders.push(`${path.relative(SRC, file)}: ${tag.slice(0, 90)}`);
      }
    }
  }

  it('has no .dz-root without a theme', () => {
    expect(offenders).toEqual([]);
  });
});
