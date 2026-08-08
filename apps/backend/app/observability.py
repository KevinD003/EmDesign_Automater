"""Error reporting for the API (CTO B1).

OFF unless `SENTRY_DSN` is set, so dev and the test suite are untouched — no
network, no global handlers, nothing to mock. The SDK is imported inside that
branch, so a deployment without a DSN does not even load it.

PRIVACY. A stitch stream is the customer's intellectual property and a design
name is often their client's brand. `send_default_pii` stays off, and
`before_send` strips request bodies and query strings from events: a report
carries the failing route and the stack, never the artwork.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("stitchiq.startup")

# Values that must never leave the process, matched case-insensitively against
# event keys before an event is sent.
_SENSITIVE_KEYS = frozenset({
    "authorization", "cookie", "set-cookie", "apikey", "api_key", "token",
    "access_token", "refresh_token", "password", "pin",
    "supabase_service_key", "supabase_anon_key",
})


def _scrub(event: dict, _hint: dict) -> dict:
    """Drop request bodies and secret-shaped headers before the event ships."""
    request = event.get("request")
    if isinstance(request, dict):
        # The body of a /api/designs POST is an entire Design; of /api/digitize,
        # someone's artwork. Neither belongs in an error report.
        request.pop("data", None)
        request.pop("query_string", None)
        headers = request.get("headers")
        if isinstance(headers, dict):
            request["headers"] = {
                k: ("[redacted]" if k.lower() in _SENSITIVE_KEYS else v)
                for k, v in headers.items()
            }
    extra = event.get("extra")
    if isinstance(extra, dict):
        for key in list(extra):
            if key.lower() in _SENSITIVE_KEYS:
                extra[key] = "[redacted]"
    return event


def init_observability() -> bool:
    """Wire Sentry if a DSN is configured. Returns True when reporting is live.

    Never raises: an observability failure must not stop the API from booting —
    that would turn a monitoring outage into an application outage.
    """
    dsn = (os.environ.get("SENTRY_DSN") or "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
    except ImportError:  # optional dependency; absent in slim installs
        logger.warning("SENTRY_DSN is set but sentry-sdk is not installed — "
                       "error reporting is OFF. Add sentry-sdk to the image.")
        return False
    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=os.environ.get("APP_ENV", "development"),
            release=os.environ.get("RELEASE") or os.environ.get("GIT_SHA"),
            # Errors are the point. A digitize is one long request, so tracing
            # every one buys noise; 10% is enough to spot a latency regression.
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            send_default_pii=False,
            before_send=_scrub,
        )
    except Exception as exc:  # noqa: BLE001 - see docstring: never fatal
        logger.warning("Sentry init failed (%s) — continuing without error reporting.", exc)
        return False
    logger.info("Sentry error reporting enabled.")
    return True
