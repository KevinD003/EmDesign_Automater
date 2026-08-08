# Deploying STITCHIQ

Two independently deployable apps. The container path (`docker compose up`) is
for local review, demos and self-hosting; the managed path (Fly/Railway +
Vercel/CF Pages) is what production uses.

## 0. Before anything: the two secrets rules

* Real secrets live only in `apps/backend/.env` (gitignored) or the platform's
  secret store. Never in `docker-compose.yml`, never in an image layer — the
  `.dockerignore` excludes `.env` for that reason.
* `APP_ENV=production` **refuses to boot** without all three `SUPABASE_*` keys,
  or with `STITCHIQ_OPEN_ACCESS=1` (CTO A10). That is deliberate: the dev
  fallbacks are sentinel auth and per-process storage, so a typo'd variable
  would otherwise ship a fully unauthenticated app that loses data on restart.

## 1. One machine (compose)

```bash
cp apps/backend/.env.example apps/backend/.env    # optional; dev mode without it
docker compose up --build                          # → http://localhost:8080
```

nginx serves the built SPA and proxies `/api` and `/health` to the backend, so
the browser talks to a single origin and there is no CORS in this topology.
Designs and local profiles live in the `stitchiq-data` volume — without it every
rebuild would wipe the user's saved work.

## 2. Backend → Fly / Railway

The image is `apps/backend/Dockerfile`. It runs **gunicorn with UvicornWorker**,
i.e. worker *processes*:

> The measured X1 stall is **1,198ms of frozen event loop during a single
> digitize**, and it happens with the handler already in the threadpool — the
> cause is GIL contention, not `async def`. More threads cannot fix that. Worker
> count is the only lever that keeps one digitize from freezing every other
> request, until the job queue lands (B1 2/3).

* `WEB_CONCURRENCY` — start at `(2 × cores) + 1`. Each worker holds the CV/NumPy
  stack, so budget ~400–600MB per worker.
* Required env: `APP_ENV=production`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`,
  `SUPABASE_SERVICE_KEY`, `CORS_ORIGINS=["https://your-frontend"]`.
* Optional: `SENTRY_DSN`, `RELEASE` (or `GIT_SHA`), `SENTRY_TRACES_SAMPLE_RATE`.
* Health: point **liveness** at `/health` and **readiness** at `/health/ready`.
  They are different questions — see §4.
* Persistent volume at `/data` unless Supabase holds everything.

## 3. Frontend → Vercel / Cloudflare Pages

Build from the repo root (it is an npm workspace):

* Build command: `npm ci && npm run build --workspace apps/frontend`
* Output directory: `apps/frontend/dist`
* Env: `VITE_API_BASE_URL=https://your-backend` — **compiled into the bundle**,
  so it is a build-time variable, not a runtime one. Optional:
  `VITE_SENTRY_DSN`, `VITE_RELEASE`.

Set the backend's `CORS_ORIGINS` to exactly this origin. Wildcard `*` is
accepted but silently disables credentialed requests (the CORS spec forbids the
combination), which breaks login — the app logs a warning when it happens.

## 4. `/health` vs `/health/ready` — why both

| | `/health` | `/health/ready` |
|---|---|---|
| Question | is the process alive and its loop responsive? | can it actually serve? |
| Touches I/O | never | yes — writes and deletes a probe file in the designs dir |
| Fails when | the process is dead **or the event loop is wedged** | the data volume did not mount / is read-only |
| Use for | liveness / restart | readiness / drain from the load balancer |

The split matters: a container whose volume failed to mount looks perfectly
healthy to a liveness probe and silently loses every save. Readiness returns
**503, not an exception**, so an orchestrator drains the instance instead of
restart-looping it.

## 5. Error reporting

Off unless a DSN is set, in both apps, and it never breaks the app: a missing
SDK or a bad DSN logs a warning and boots anyway. Payloads are scrubbed — the
backend drops request bodies, query strings and secret-shaped headers; the
frontend strips fetch/XHR bodies from breadcrumbs. A stitch stream is the
customer's intellectual property and must not reach a third party.

Bundle cost of the frontend SDK is **zero** without a DSN: `VITE_SENTRY_DSN` is
statically `undefined`, so Vite eliminates the dynamic import entirely
(measured — with a DSN it becomes a separate 163KB-gzip lazy chunk).

## 6. Applying the identity RLS (required once, per project)

`db/schema.sql` is a create-from-scratch script; a live database is updated with
the migration:

```bash
psql "$SUPABASE_DB_URL" -f db/migrations/001_identity_rls.sql
SUPABASE_URL=… SUPABASE_ANON_KEY=… python apps/backend/scripts/verify_rls.py
```

Exit 0 from the probe is the evidence that `users`, `teams` and `team_members`
are closed to the public anon key. Until it is run, treat S3 as open.
