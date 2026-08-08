/**
 * Sentry wiring for the SPA (CTO B1).
 *
 * OFF unless `VITE_SENTRY_DSN` is set at build time, which keeps local dev and
 * the test environment completely untouched — no network calls, no global
 * handlers, nothing to mock. Sentry is imported LAZILY inside that branch so a
 * build without a DSN does not pay for the SDK on the critical path.
 *
 * PRIVACY: a design name can be a customer's brand, and a stitch stream is the
 * user's intellectual property. `sendDefaultPii` stays off and the breadcrumb
 * hook strips request bodies, so an error report carries the failing URL and
 * stack — never the artwork.
 */

const DSN = import.meta.env.VITE_SENTRY_DSN as string | undefined;
const RELEASE = import.meta.env.VITE_RELEASE as string | undefined;
const ENVIRONMENT = (import.meta.env.MODE as string) || 'development';

/** True when error reporting is actually wired (a DSN was supplied). */
export function observabilityEnabled(): boolean {
  return Boolean(DSN);
}

/**
 * Initialise error reporting. Safe to call unconditionally and more than once:
 * without a DSN it returns immediately, so callers need no branching.
 */
export async function initObservability(): Promise<void> {
  if (!DSN) return;
  const Sentry = await import('@sentry/react');
  Sentry.init({
    dsn: DSN,
    release: RELEASE,
    environment: ENVIRONMENT,
    // Errors are the point; traces are sampled thin because a digitize is one
    // long request and full tracing on every one buys noise, not insight.
    tracesSampleRate: 0.1,
    sendDefaultPii: false,
    beforeBreadcrumb(crumb) {
      // fetch/xhr breadcrumbs carry the request body by default — that body is
      // an entire Design (stitches, contours, thread names). Keep the URL and
      // status, drop the payload.
      if (crumb.category === 'fetch' || crumb.category === 'xhr') {
        return { ...crumb, data: { url: crumb.data?.url, status_code: crumb.data?.status_code } };
      }
      return crumb;
    },
  });
}
