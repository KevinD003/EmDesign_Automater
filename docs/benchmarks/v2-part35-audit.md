# v2 Part 35 — Accounts, admin, plans, email recovery + the new dashboard (and an honest production verdict)

**Date:** 2026-08-02 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Request:** "Is it ready for production? Delete the old dashboard completely; prepare a
new dashboard with Claude Design on Node.js — super design, SEO/GEO, login, admin,
premium plan gating, forgot password, send email, everything."

---

## 1. Is it production-ready? The honest verdict

**Supervised LAN (~100 users): YES** — that has been the tested launch topology since
the Part 19–21 hardening (authz, session TTL, rate limiting, credential-leak review).

**Public internet: NOT YET — and here is the exact remaining list:**

| Needed for public production | State after Part 35 |
|---|---|
| Login / signup / sessions | ✅ shipped earlier (PBKDF2, 12h TTL, token eviction) |
| Forgot-password by email | ✅ **this part** — single-use 30-min tokens, sessions revoked on reset |
| Real SMTP delivery | ◐ wired by env (`SMTP_HOST/PORT/USER/PASS`); needs a provider account — without it, emails spool to `data/outbox/*.eml` |
| Roles + admin panel | ✅ **this part** — first profile = operator; last-admin demotion refused |
| Plans + premium gating | ✅ **this part** — free/pro/studio, enforced via `STITCHIQ_ENFORCE_PLANS=1` |
| Billing / payments | ✗ deliberately not wired — plans are admin-assigned; a payment processor changes who calls `set_plan`, not the gate |
| HTTPS + deployment | ✗ operator task (reverse proxy / host); CORS + rate limiting exist |
| Multi-process scale | ◐ single-worker by design (CPU work threadpooled); >1 worker needs the Supabase path + a shared rate limiter |
| SEO / GEO surface | ✅ **this part** |

## 2. What was measured before building: the tier/feature map

A 4-agent survey mapped every endpoint's auth and cost before gating: only design CRUD
required auth; every processing endpoint was anonymous. The premium gates chosen (and
wired) are the classic paid deliverables: **production package ZIP, worksheet PDF,
optimizer, converter (PRO)** and **photo pipeline + large hoops beyond 130×180mm
(STUDIO)**. Enforcement is **opt-in** (`STITCHIQ_ENFORCE_PLANS=1`) so the shipped LAN
topology and the entire pre-existing test corpus run unchanged — the gate returns 402
with a plain-language upgrade message only when the operator turns it on. Admins bypass.

## 3. The account-recovery loop (tested end-to-end, not declared)

`POST /auth/local/forgot-password` → always **202** (the response is identical for
known and unknown addresses — no account enumeration; the no-enumeration test also
proves only the real address got mail). The mailer sends via SMTP when configured,
otherwise writes a real `.eml` to the gitignored outbox — and the test **reads the
token out of that .eml**, exactly as a user would: reset → old PIN dead, new PIN works,
**every live session revoked**, link **single-use** (second redemption → 400), TTL 30
minutes. A mid-build defect worth recording: the default quoted-printable encoding
soft-wrapped the reset link mid-token; the fix (7bit, ASCII body) is commented in the
mailer because the outbox fallback IS the delivery mechanism on a LAN install.

Login now accepts username **or** email in one field. Signup takes an optional
recovery email; the Account page can add it later.

## 4. The new dashboard (old one deleted)

`components/dashboard/` (2 components + the `da-*` CSS layer) is **gone**. The new
`components/dash/` suite runs on the existing React + TypeScript + Vite (Node.js)
stack with **hash routing** (`lib/routes.ts`, unit-tested) — chosen over a router
dependency because password-reset **emails need URLs that survive a static host**:
`/#/reset?token=…` needs no server rewrites.

Pages: **Overview** (library stats + current design + activity), **Analytics**
(histogram, thread usage, needle-down vs travel split, capability table),
**Account & plan** (profile, recovery email, tier ladder), **Admin** (user table with
live plan/role dropdowns, platform counters, feature matrix), plus full-page
**Login / Signup / Forgot / Reset** screens.

Design method (dataviz skill): tokens per mode on `.dz-root` — **light and dark are
both real themes** (toggle + OS preference; the Studio deliberately stays dark like
every pro canvas tool). Series colour `#2a78d6` light / `#3987e5` dark — **validator
run, all checks pass in both modes**. Single-series charts carry the series token and
no legend; only the peak histogram bin is direct-labeled; every mark has a tooltip;
bars keep 2px surface gaps and 4px rounded data ends on the baseline; thread-usage
bars are the documented exception where colour IS the data (the actual thread hex).

Verified by driving the real app end to end with Playwright against a live backend on
a clean store: signup → admin dashboard → theme toggle (both modes rendered) →
account (recovery email saved at signup, shown) → admin plan change (dropdown →
server → row + counters update, badge flips to STUDIO) → forgot-password (confirmation
state; `.eml` spooled) → **digitize the neckline panel in the Studio and read its
analytics** (11,184 stitches, quality 90/A, 14 stops, 78.8% needle-down, all three
digitizer warnings surfaced). Contact sheet: `v2-part35-dashboard.png`.

Two layout/logic defects were caught by *looking at the render*, not by tests: the
histogram card stretched to its taller neighbour leaving dead space (`align-items:
start`), and the admin counters didn't refresh after a plan change (now re-fetched).

## 5. SEO / GEO

- `index.html`: full meta (description/keywords/canonical/robots), Open Graph +
  Twitter card with a generated 1200×630 `og.png`, and **JSON-LD
  `SoftwareApplication`** structured data with the honest feature list.
- `public/robots.txt` (AI crawlers welcome), `sitemap.xml`, `manifest.webmanifest`,
  and **`llms.txt`** — the GEO surface: a structured plain-text summary AI search
  engines can quote, whose every claim traces to a measured audit in this repo.
- `<noscript>` fallback keeps a crawlable description without JavaScript.
- Placeholder domain `stitchiq.example.com` is deliberate — swap at deploy.

## 6. Known limits, stated plainly

- **Forgot-password timing.** The *response* is byte-identical for known and unknown
  addresses (pinned by test), but a known address does more work — mint, rewrite the
  store, write the mail — so timing can still distinguish them. Closing that needs a
  queued send; recorded in the code rather than papered over.
- **Plans + Supabase.** Plans live in the local account store. On a Supabase
  deployment a valid cloud JWT resolves to no local profile, so enforcement now
  **fails open** there (`enforcing()` returns False when Supabase is the auth
  backend). Without that guard, flipping the switch on a cloud install would have
  read *every* caller — including paying ones — as free and refused them all. Pinned
  by test; wiring plans into Supabase's users table is what turns it back on.
- **No billing.** Plans are admin-assigned by design.

## 7. Guardrails

Backend: **747 passed + 2 xfailed**, including 8 new account tests (reset loop,
no-enumeration, email login, admin authz + last-admin lockout guard, gate
402/bypass/inert-by-default, Supabase fail-open, free hoop cap). Two pre-existing
tests updated because the `/me` wire shape deliberately widened. Frontend: tsc clean,
vitest **127 passed** (4 new route tests), vite production build passes. Ruff back to
the **19**-error baseline (the four new I001s from wiring gate imports were fixed).
Stream locks untouched — no digitizer changes.

**Review honesty:** an adversarial 3-agent review workflow (security / correctness /
regressions) was launched over this diff and **died on usage credits without
returning any findings** — it is not evidence of anything. The diff was reviewed by
hand instead, which is what surfaced the Supabase fail-open defect above, a dead
`<html>` dataset stamp in the dashboard shell (removed), and confirmed the deleted
dashboard CSS took no Studio classes with it (`.panel*` survive; no dangling `da-*`
references remain).

## Files

- `apps/backend`: `services/user_store.py` (+email/role/plan/reset), `services/mailer.py`,
  `services/plans.py`, `routers/auth_local.py` (+3 endpoints), `routers/admin.py`,
  gates in `routers/{export,worksheet,optimize,convert,digitize}.py`, `main.py`,
  `tests/test_part35_accounts.py`
- `apps/frontend`: `components/dash/*` (7 files), `lib/routes.ts` (+test),
  `api/client.ts`, `lib/auth.ts`, `App.tsx`, `index.css` (dz-layer; old dashboard CSS
  removed), `index.html`, `public/{robots.txt,sitemap.xml,llms.txt,manifest.webmanifest,og.png}`
- Deleted: `components/dashboard/Dashboard.tsx`, `components/dashboard/DesignAnalytics.tsx`
