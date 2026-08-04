/**
 * Drive the real app in a real browser and capture screenshots (v2 Part 44, R003).
 *
 * The standing gap was never "rendering is broken" — it was that every check of
 * it happened in a throwaway script. This is that check, committed.
 *
 * It complements `apps/backend/scripts/visual_regression.py`, which is the
 * automatic gate: that one renders the stitch stream server-side, runs in pytest,
 * is deterministic to the pixel, and needs no browser. This one answers the
 * different question the Python harness structurally cannot — does the Konva
 * canvas in an actual browser paint what the backend produced? Two independent
 * renderers; only a browser can check the second.
 *
 * It is deliberately NOT wired into `npm test`. It needs both servers up, and
 * browser text rendering varies enough between machines that pixel-gating it
 * would produce failures that mean nothing. Screenshots are for a human to look
 * at; the gate is the Python one.
 *
 *   npm run dev                      # backend :8000 + frontend :5173
 *   node tools/visual/app-screenshots.mjs
 *   node tools/visual/app-screenshots.mjs --base http://localhost:4173 --out /tmp/shots
 */

import { chromium } from 'playwright';
import { mkdir } from 'node:fs/promises';
import { existsSync, readdirSync } from 'node:fs';
import path from 'node:path';

/**
 * Some environments ship Chromium already, at a build number that does not match
 * whatever `playwright` in node_modules expects. Rather than fail with "run npx
 * playwright install" — which is wrong advice where the browser is pre-provisioned
 * and often not permitted — point at the binary that is actually there.
 * Override with CHROMIUM_PATH if yours lives somewhere else.
 */
function findChromium() {
  if (process.env.CHROMIUM_PATH) return process.env.CHROMIUM_PATH;
  const candidates = [];
  const pool = '/opt/pw-browsers';
  if (existsSync(pool)) {
    // Any build number, newest first — never pin one, it changes under you.
    for (const dir of readdirSync(pool).filter((d) => d.startsWith('chromium-')).sort().reverse()) {
      candidates.push(path.join(pool, dir, 'chrome-linux', 'chrome'));
    }
  }
  candidates.push('/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome');
  return candidates.find((p) => existsSync(p));
}

const args = process.argv.slice(2);
const argOf = (name, fallback) => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
};

const BASE = argOf('--base', 'http://localhost:5173');
const OUT = argOf('--out', path.join('docs', 'benchmarks', 'app-screenshots'));

/**
 * Each entry is one thing worth being able to look at after a change.
 * Hashes match `apps/frontend/src/lib/routes.ts` — anything unrecognised there
 * falls through to the studio, so a typo here would silently screenshot the
 * studio six times instead of failing.
 */
const PAGES = [
  { name: 'studio', hash: '#/', wait: 'main.canvas-area' },
  { name: 'dashboard-overview', hash: '#/dashboard', wait: 'main.dz-content' },
  { name: 'dashboard-analytics', hash: '#/dashboard/analytics', wait: 'main.dz-content' },
  { name: 'dashboard-account', hash: '#/dashboard/account', wait: 'main.dz-content' },
  { name: 'auth-login', hash: '#/login', wait: 'form.dz-auth-form' },
  { name: 'auth-signup', hash: '#/signup', wait: 'form.dz-auth-form' },
  { name: 'auth-forgot', hash: '#/forgot', wait: 'form.dz-auth-form' },
];

const THEMES = ['light', 'dark'];

async function main() {
  await mkdir(OUT, { recursive: true });
  const executablePath = findChromium();
  if (executablePath) console.log(`chromium: ${executablePath}`);
  const browser = await chromium.launch(executablePath ? { executablePath } : {});
  const failures = [];

  for (const theme of THEMES) {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 1,
      colorScheme: theme,
      // Freeze animation so a screenshot is not a race against a transition.
      reducedMotion: 'reduce',
    });
    const page = await context.newPage();
    // A 401/403 from an authenticated endpoint is the CORRECT behaviour while
    // signed out, which is how this harness runs. Failing on it would make the
    // check red on every clean run, and a check that is always red is muted
    // within a week. Uncaught JS exceptions always count.
    const expected = /(401|403) \(?(Unauthorized|Forbidden)/i;
    const consoleErrors = [];
    page.on('console', (m) => {
      if (m.type() === 'error' && !expected.test(m.text())) consoleErrors.push(m.text());
    });
    page.on('pageerror', (e) => consoleErrors.push(`uncaught: ${e}`));

    for (const spec of PAGES) {
      const url = `${BASE}/${spec.hash}`;
      try {
        await page.goto(url, { waitUntil: 'networkidle', timeout: 20000 });
        await page.waitForSelector(spec.wait, { timeout: 10000 });
        const file = path.join(OUT, `${spec.name}-${theme}.png`);
        await page.screenshot({ path: file, fullPage: true });
        console.log(`  ok   ${spec.name}-${theme}`);
      } catch (err) {
        failures.push(`${spec.name}-${theme}: ${err.message.split('\n')[0]}`);
        console.log(`  FAIL ${spec.name}-${theme}: ${err.message.split('\n')[0]}`);
      }
    }

    // A page that paints but throws is still broken, and a screenshot hides it.
    if (consoleErrors.length) {
      failures.push(`${theme}: ${consoleErrors.length} console error(s): ${consoleErrors[0]}`);
    }
    await context.close();
  }

  await browser.close();
  console.log(`\nscreenshots -> ${OUT}`);
  if (failures.length) {
    console.error(`\n${failures.length} problem(s):`);
    failures.forEach((f) => console.error(`  - ${f}`));
    process.exit(1);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
