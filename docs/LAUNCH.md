# STITCHIQ Launch Runbook

Localhost / LAN deployment, ~100 users. Every command here is copy-pasteable as written.
Verified environment: venv Python 3.11.15, uvicorn 0.51.0, fastapi 0.140.10.

Security posture and the keyless-mode caveat were corrected in v2 Part 21 after an adversarial
review found (and this branch fixed) missing authorization; §4 records the verification.
An earlier draft with the original measured load numbers is at `git show 3a1d279:docs/LAUNCH.md`.

## 0. Preflight

Run this first, on the machine that will serve users:

```bash
cd /home/user/EmDesign_Automater/apps/backend
.venv/bin/python scripts/preflight.py
```

`scripts/preflight.py` is stdlib-only by design, so it still runs when backend dependencies are
broken — which is exactly when you need it.

### What it actually checks

Ten checks, in the order printed:

| Check name | What must be true |
|---|---|
| `python-version` | interpreter ≥ 3.11 (`MIN_PYTHON`) |
| `venv` | running inside `apps/backend/.venv` |
| `backend-imports` | all 9 runtime modules importable: `fastapi`, `uvicorn`, `pydantic`, `cv2`, `numpy`, `PIL`, `reportlab`, `pyembroidery`, `httpx` |
| `node` | `node` on PATH at ≥ v20 (`MIN_NODE_MAJOR`) — needed for the frontend build (§2) |
| `port-8000` | uvicorn's port is bindable |
| `port-5173` | vite's port is bindable |
| `fonts` | a TrueType font resolves via `app.services.lettering.find_font()` |
| `disk-space` | ≥ 1 GB free on the repo volume, ≥ 5 GB recommended |
| `frontend-deps` | both `node_modules` dirs present (repo root + `apps/frontend`) |
| `env-file` | `apps/backend/.env` present → Supabase mode; absent → keyless |

### Exit codes

- **0** — no check FAILed. WARNs may be present and are *not* fatal.
- **1** — at least one check FAILed. Do not launch; fix and re-run.

A check that raises an exception is reported as FAIL rather than crashing the run, so the exit
code is always meaningful.

### Reading the WARNs

WARN never blocks launch, but each one means something:

- `port-8000` / `port-5173` — "port in use". Usually the app is still running from an earlier
  session; kill it, or launch dies with "address already in use".
- `env-file` — no `apps/backend/.env`, i.e. **keyless mode**. This is a launch decision, not
  noise: it forces `--workers 1` (§1). Designs ARE per-user isolated in this mode (§4).
- `frontend-deps` — run `npm install` before `npm run build` (§2).
- `disk-space` — under 5 GB. Uploads, exports and the build output all share this volume.

### Verified output on this machine

10 checks, 9 PASS + 1 WARN, exit 0:

```
PASS  python-version     3.11.15 (>=3.11 required)
PASS  venv               running inside venv (.../apps/backend/.venv)
PASS  backend-imports    all 9 backend modules importable
PASS  node               v22.22.2 (>=v20 required)
PASS  port-8000          127.0.0.1:8000 is free
PASS  port-5173          127.0.0.1:5173 is free
PASS  fonts              /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
PASS  disk-space         27.3 GB free at /home/user/EmDesign_Automater
PASS  frontend-deps      all 2 node_modules dirs present
WARN  env-file           no apps/backend/.env — Supabase off; designs fall back to local JSON files under data/designs/, single machine/worker only
```

**Run this the morning of launch, and again after any machine change** — OS update, Python or
node upgrade, a fresh `npm install`, a moved repo, or a different host.

## 1. Backend

### Launch command

```bash
cd /home/user/EmDesign_Automater/apps/backend
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

Verified: this exact line boots and serves `/health` with uvicorn 0.51.0. `--workers 4` also
boots (4 worker processes) — read the decision box before using it.

### WORKERS DECISION

Digitizing is CPU-bound (OpenCV/NumPy per request, one core saturated per digitize), so extra
workers *would* raise throughput. What caps the worker count is state that lives inside a single
process:

- `app/services/user_store.py` — local accounts/sessions. `UserStore.__init__` loads
  `data/local_users.json` into `self._data` **once**, and every `_save()` rewrites the whole file
  from that in-process snapshot. With >1 worker: a login/registration handled by worker A is
  invisible to worker B, and B's next write clobbers A's. Users get random "unknown user" /
  logged-out responses. This is the hard blocker.
- `app/middleware/rate_limit.py` — per-process sliding window, deliberately not shared, so N
  workers means N × the budget. Since v2 Part 21 the bucket key is the caller's session token
  (falling back to the forwarded client IP from a trusted local proxy), so users behind Vite's
  proxy no longer share one bucket — before that fix the whole LAN shared 12 req/s.
- `app/services/local_store.py` — designs are one JSON file per design under
  `data/designs/<user>/`, written atomically (tmp + `os.replace`). This part *is* multi-worker safe
  on one machine; it is not what forces `--workers 1`.

Rule:

| Mode | Workers |
|---|---|
| Keyless (no `apps/backend/.env`, or no Supabase keys in it) | exactly `--workers 1` |
| `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` set in `apps/backend/.env` | `--workers N`, N ≈ physical cores (`nproc`), capped at **4** |

The cap of 4 is RAM, not CPU: each worker loads its own OpenCV/NumPy. Supabase mode moves designs
and auth out of process memory; local accounts under `data/local_users.json` still are not shared,
so do not mix local-auth users with multi-worker.

### Dev alternative — NOT for launch

```bash
cd /home/user/EmDesign_Automater
npm run dev        # concurrently: vite (:5173) + uvicorn app.main:app --reload --port 8000
```

`--reload` restarts the process on any file touch: in-flight digitize jobs die mid-request and the
in-process auth/session snapshot is rebuilt from disk. Use for development only.

### `--host` choice

- Vite serves the UI and proxies `/api` (the default setup): the backend can stay on
  `--host 127.0.0.1`. Nothing off-machine needs to reach :8000.
- LAN clients call the API directly (no proxy, or a separately served build pointed at
  `http://<lan-ip>:8000`): use `--host 0.0.0.0`. See §3.

### Verification

```bash
curl -s http://127.0.0.1:8000/health
# {"status":"ok"}
```

`/health` is exempt from rate limiting, so it stays a valid probe under load.

## 2. Frontend

### Build

```bash
cd /home/user/EmDesign_Automater
npm run build          # -> npm run build --workspace apps/frontend -> tsc --noEmit && vite build
```

The typecheck is part of the build: `tsc --noEmit` runs first and a type error aborts before any
bundle is written. Output lands in `apps/frontend/dist/` (`index.html` + `assets/`). Verified run
on this branch, vite 5.4.21, 4.4 s: `index.html` 0.71 kB, `assets/index-*.css` 12.85 kB
(2.92 kB gzip), `assets/index-*.js` 1,343.17 kB (382.29 kB gzip). The ">500 kB chunk" warning is
expected (konva + three are in the main chunk) and is not a failure.

### Serve command for launch

```bash
cd /home/user/EmDesign_Automater
npm run preview -w apps/frontend -- --host --port 5173
```

Listens on **0.0.0.0:5173** (prints `Local: http://localhost:5173/` and
`Network: http://<lan-ip>:5173/`). Both flags are load-bearing:

- `--host` — without it vite preview binds loopback only; a LAN client gets connection-refused.
- `--port 5173` — **`preview` does not inherit `server.port`**. Bare `npm run preview -w apps/frontend`
  listens on **4173**, not 5173. Pin the port so it matches the CORS origin in `apps/backend/.env`.

`vite preview` **does** proxy `/api` and `/health` to `http://localhost:8000` — verified in this
container, not assumed: `curl http://127.0.0.1:5173/health` returned the backend's
`{"status":"ok",...}` and `curl http://127.0.0.1:5173/api/designs` returned `[]`, while an unknown
route (`/no-such-thing`) returned `index.html`. Vite 5's `preview.proxy` falls back to
`server.proxy`, so the single `proxy` block in `apps/frontend/vite.config.ts` covers both servers.
No `preview.proxy` entry is needed and none exists.

If the backend is not running, proxied `/api/*` requests return **HTTP 500 with an empty body**
(not 404) — a 404 from `/api/*` means a routing/path problem, a 500-with-no-body means uvicorn is
down. Start the backend (§1) before the frontend.

### dev vs preview

- `preview` serves the real production bundle from `dist/` — minified, tree-shaken, hashed assets,
  the exact bytes users get. It never rebuilds: re-run `npm run build` after any code change.
- `dev` (`npm run dev -w apps/frontend -- --host`) serves unminified modules with HMR and a
  websocket to every client; it also listens on 5173 and proxies identically (verified). It works
  as a launch fallback but ships dev-mode React and recompiles on request — slower first paint,
  and a stray file touch changes what users see mid-session.
- Use `preview` for launch. Use `dev` only while editing.

## 3. LAN access

### Backend half

```bash
cd /home/user/EmDesign_Automater/apps/backend
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
hostname -I            # the LAN IP clients will use
```

Constraints:

- `0.0.0.0` exposes :8000 to every host that can route to this machine. Trusted LAN only — there is
  no auth in front of the API surface itself.
- Browsers on other machines hit CORS: `cors_origins` defaults to `["http://localhost:5173"]`
  (`app/config.py`). A LAN client loading the UI from `http://<lan-ip>:5173` is a *different*
  origin and will be blocked until that origin is added to `CORS_ORIGINS` in `apps/backend/.env`
  (JSON list, see `.env.example`).
- Verify from another machine: `curl -s http://<lan-ip>:8000/health` → `{"status":"ok"}`. If it
  hangs, it is the host firewall, not the app.

### Frontend half

```bash
hostname -I | awk '{print $1}'      # first LAN IP of this host, e.g. 192.168.1.50
ip -4 addr                          # fallback: pick the address on the LAN interface
cd /home/user/EmDesign_Automater
npm run preview -w apps/frontend -- --host --port 5173
```

Users open **`http://<LAN_IP>:5173/`** — the same URL for all ~100 of them. Nothing else to hand out.

- `--host` is required: vite (dev *and* preview) binds loopback only by default. Verified — without
  it, `curl http://<LAN_IP>:4173/` fails with "Couldn't connect", `http://127.0.0.1:4173/` returns
  200. With `--host` the startup banner prints a `Network:` URL instead of "use --host to expose".
- **The backend needs no LAN exposure when vite serves the UI.** Verified: with uvicorn on
  `--host 127.0.0.1 --port 8000`, a request to `http://<LAN_IP>:5173/health` from the LAN address
  returned `{"status":"ok",...}` and `http://<LAN_IP>:5173/api/designs` returned `[]`, while direct
  `http://<LAN_IP>:8000/health` was refused. The browser only ever talks to :5173; vite makes the
  loopback hop to :8000. This also sidesteps the CORS problem in the backend half — proxied calls
  are same-origin, so `CORS_ORIGINS` only matters if you skip the proxy.
- Firewall: allow inbound TCP **5173** on this host. Add **8000** only if you deliberately point
  clients at the API directly (then also set `CORS_ORIGINS`, see the backend half).
- Do not use `localhost` in anything you send to users — on their machine it resolves to their own
  box. Always the host's LAN IP.

## 4. Data & backups

### Correction to a common assumption

Server-side designs are **not** held in a per-process in-memory dict and are **not** lost on
restart. Verified empirically on this branch: POST a design → kill uvicorn → start a *new*
process → GET returns the same design. `app/services/local_store.py` writes one JSON file per
design (`data/designs/<user>/<id>.json`, atomic tmp + `os.replace`); the in-memory dict is used
**only** under pytest. Plan backups around files on disk, not around "a restart loses
everything".

The keyless risk is real, but it is about *privacy*, not durability — see the caveat below.

### Inventory

| What | Where | Survives backend restart? | Backup method |
|---|---|---|---|
| Designs saved in the browser | The user's own browser, `localStorage` keys `stitchiq:index` / `stitchiq:design:<id>` | Yes — it was never on the server | **None possible server-side.** Users must Export |
| Login session (browser) | `localStorage` key `stitchiq:session` | Yes, until the user clears site data | Not needed — re-login recreates it |
| Designs saved server-side, keyless | `apps/backend/data/designs/<user>/<id>.json` (or `$STITCHIQ_DESIGNS_DIR`) | **Yes** — one JSON file per design, atomic writes | `tar` the data dir (below) |
| Local accounts + sessions | `apps/backend/data/local_users.json` (`profiles`, `sessions`; PINs as `pin_hash` + `pin_salt`) | Yes | `tar` the data dir (below) |
| Designs saved server-side, Supabase | Postgres: `users`, `designs`, `design_objects`, `color_stops`, `exports`, `worksheets`, … (`db/schema.sql`) | Yes | Supabase's own backups; `pg_dump` for a manual snapshot |
| Thread catalog | `apps/backend/app/data/threads_madeira_sample.json` | Yes | **None needed — static app data, tracked in git** |
| Frontend bundle | `apps/frontend/dist/` | Yes | None needed — regenerate with `npm run build` (§2) |
| Server logs | `logs/` | Yes | Optional; see §5 |

### Keyless mode IS per-user isolated (fixed in v2 Part 21)

Earlier drafts of this runbook warned that keyless mode shared one library across all users.
**That was true, it was a real vulnerability, and it is fixed.** `app/deps.py` now resolves the
`Authorization: Bearer` token to a local account and returns **401** when it is missing or
invalid; designs are stored under the account's real user id, not a `local-dev` sentinel.

Verified by replaying the exact attack that found it, against a live server:

| Attempt | Result |
|---|---|
| Bob lists designs with his own token | `[]` — Alice's are invisible |
| Bob reads Alice's design by id | `404` |
| **Anonymous** (no `Authorization` header) lists designs | `401` |
| **Anonymous** DELETEs Alice's design | `401` |
| Alice re-reads her own design | `200`, intact |

Two consequences for launch day:

- **Users must create a profile** (username + PIN) before saving server-side. Until the first
  profile exists the server stays open, so create yours first.
- **Sessions expire after 12 hours** (`SESSION_TTL_HOURS`). A day-long event is fine; a
  multi-day one means users log in again.

Still true regardless of mode: server-side saves survive restarts, and users should Export
anything they care about onto their own machine.

### Manual backup — local files

Covers both `data/designs/` and `data/local_users.json`. Verified:

```bash
cd /home/user/EmDesign_Automater
mkdir -p ~/stitchiq-backups
tar czf ~/stitchiq-backups/stitchiq-data-$(date +%F).tar.gz -C apps/backend data
tar tzf ~/stitchiq-backups/stitchiq-data-$(date +%F).tar.gz    # verify contents
```

Safe to run while the server is up — design writes are atomic, so a snapshot never catches a
half-written file. Run it before launch and again at end of day.

> `apps/backend/data/local_users.json` is **tracked in git**. Accounts created at launch will
> show up as a dirty working tree, and a `git checkout` / `git stash` / `git reset` touching
> that path will destroy them. Back it up before any git operation.

### Manual backup — Supabase (ONLY if configured)

Applies only when `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` are set. Supabase already runs its own
backups; this is for an extra local snapshot, using `DATABASE_URL` from `apps/backend/.env`:

```bash
pg_dump "$DATABASE_URL" > ~/stitchiq-backups/stitchiq-db-$(date +%F).sql
```

`pg_dump` 16.13 is installed on this machine (`pg_dump --version` verified). The dump command
itself was **not** executed here — no Supabase project is configured in this container — so run
it once yourself before relying on it.

### What users should export

Server-side saves are a convenience, not an archive. Anything a user cares about should leave
the machine as a file: `POST /api/export` (single `.dst`/`.pes`) or `POST /api/export/package`
(ZIP production package). That is the only copy that survives a wiped data dir, a shared-bucket
deletion, or a move to a different host.

## 5. Logs

uvicorn and vite both write to **stdout/stderr only** — neither creates a log file on its own.
Run them under a redirect, or launch-day evidence disappears when the terminal closes.

`logs/` is untracked scratch output: `.gitignore` line 5 (`*.log`) covers it, so it never
appears in `git status` and is never committed. Nothing in the app reads it back.

### Backend, with logs persisted

Same flags as §1 (`--host 0.0.0.0 --port 8000 --workers 1` — re-read the WORKERS DECISION box
before changing `--workers`):

```bash
mkdir -p /home/user/EmDesign_Automater/logs
cd /home/user/EmDesign_Automater/apps/backend
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 >> ../../logs/backend.log 2>&1 &
```

`>>` appends, so a restart adds to the file instead of truncating it. `2>&1` is load-bearing:
uvicorn's startup banner *and* its tracebacks go to **stderr**, so without it you would keep the
successful requests and lose every error.

Verified — this exact command produced `logs/backend.log` containing:

```
INFO:     Started server process [17655]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     127.0.0.1:50018 - "GET /health HTTP/1.1" 200 OK
INFO:     127.0.0.1:50022 - "GET /api/designs HTTP/1.1" 200 OK
```

**Access logging is on by default** — uvicorn emits one line per request with client IP, method,
path and status. At ~100 users that is the bulk of the volume.

### Frontend, with logs persisted

Same command as §2:

```bash
cd /home/user/EmDesign_Automater
npm run preview -w apps/frontend -- --host --port 5173 >> logs/frontend.log 2>&1 &
```

Verified, but expect much less: `vite preview` logs a startup banner and **no per-request
lines**. After a successful page load the entire file was:

```
> @stitchiq/frontend@0.1.0 preview
> vite preview --host --port 5173

  ➜  Local:   http://localhost:5173/
  ➜  Network: http://192.0.2.2:5173/
```

An idle-looking `frontend.log` is therefore normal, not a fault. To confirm the frontend is
serving traffic, look at the proxied `/api` hits in `backend.log` instead.

### Watching

```bash
cd /home/user/EmDesign_Automater
tail -f logs/backend.log                        # live
tail -n 100 logs/backend.log                    # recent
grep -E '" (4|5)[0-9][0-9] ' logs/backend.log   # 4xx/5xx only (verified)
```

Both servers are backgrounded with `&`, so `tail -f` is how you watch them; quitting the tail
does not touch the server.

### Housekeeping

- One access-log line per request. Check size occasionally with `du -h logs/`. Preflight's
  `disk-space` check (§0) covers the volume, not this directory specifically.
- Rotate between sessions if it grows:
  `mv logs/backend.log logs/backend.$(date +%F).log`. Do it at a restart boundary — a running
  process keeps writing to the old file handle until it is restarted.
- Logs contain client IPs and requested paths. Same trust boundary as the LAN itself (§3).

## 6. Load evidence

<!-- filled by a later task -->

## 7. Troubleshooting

<!-- filled by a later task -->
