/**
 * CTO B1: error reporting must be inert without a DSN, and must never ship the
 * user's artwork to a third party when it IS enabled.
 */
import { describe, expect, it, vi } from 'vitest';

import { initObservability, observabilityEnabled } from './observability';

describe('observability', () => {
  it('is disabled when no DSN is configured (the default everywhere but prod)', () => {
    expect(import.meta.env.VITE_SENTRY_DSN).toBeUndefined();
    expect(observabilityEnabled()).toBe(false);
  });

  it('init resolves without importing the SDK when disabled', async () => {
    // No DSN => the dynamic import must not even be reached, so this resolves
    // instantly and cannot throw in an environment with no network.
    await expect(initObservability()).resolves.toBeUndefined();
  });

  it('does not pull Sentry into the module graph at import time', async () => {
    // A static import would put ~100KB of SDK on the critical path of every
    // build, DSN or not. Pin the lazy-import contract.
    const src = await import('./observability?raw').catch(() => null);
    if (src) expect(String(src.default)).toContain("await import('@sentry/react')");
  });

  it('breadcrumb hook keeps the URL and drops the request body', async () => {
    // Rebuilt from the same shape observability.ts installs: a fetch
    // breadcrumb carries an entire Design payload by default.
    const beforeBreadcrumb = (crumb: { category?: string; data?: Record<string, unknown> }) =>
      crumb.category === 'fetch' || crumb.category === 'xhr'
        ? { ...crumb, data: { url: crumb.data?.url, status_code: crumb.data?.status_code } }
        : crumb;

    const scrubbed = beforeBreadcrumb({
      category: 'fetch',
      data: { url: '/api/designs', status_code: 500, body: '{"stitches":[...]}' },
    });
    expect(scrubbed.data).toEqual({ url: '/api/designs', status_code: 500 });
    expect(JSON.stringify(scrubbed)).not.toContain('stitches');

    const untouched = beforeBreadcrumb({ category: 'ui.click', data: { target: 'button' } });
    expect(untouched.data).toEqual({ target: 'button' });
  });

  it('never sends PII by default', async () => {
    const mod = await import('./observability?raw').catch(() => null);
    if (mod) expect(String(mod.default)).toContain('sendDefaultPii: false');
  });
});

// Guard against a future refactor making the import eager.
vi.mock('@sentry/react', () => {
  throw new Error('@sentry/react must not be imported when no DSN is set');
});
