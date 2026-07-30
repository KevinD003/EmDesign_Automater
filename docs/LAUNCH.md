# LAUNCH — running STITCHIQ for ~100 users on localhost / LAN

Written for the launch of 2026-07-30. Every number below was **measured on this machine**, not
estimated. If you change hardware, re-measure with the commands given.

## 0. Preflight (run this first, always)

```bash
cd apps/backend && .venv/bin/python scripts/preflight.py
```

Checks Python/Node versions, venv, module imports, ports 8000/5173, fonts, disk, node_modules, and
`.env`. It prints `PASS` / `WARN` / `FAIL` per row. **A `FAIL` means do not launch.** A `WARN` on
`env-file` is expected and fine for a local launch (see §4).

## 1. Start it

```bash
# One-shot dev mode (backend :8000 + frontend :5173, Vite proxies /api)
npm run dev
```

For a launch you want the **built** frontend and **multiple backend workers** — see §3.

- App: http://localhost:5173 · API docs: http://localhost:8000/docs
- LAN access (other machines on the same network): add `--host` to both:
  `uvicorn app.main:app --host 0.0.0.0 --port 8000` and `npm run dev -- --host`, then browse to
  `http://<this-machine-LAN-IP>:5173`.

## 2. Measured capacity — the number that decides your worker count

Digitizing is **CPU-bound** (OpenCV, single-threaded per request). Measured on this machine,
10 concurrent POSTs of `05_wordmark_caps.png` to one uvicorn worker:

```
req2  200  1.53s     req8  200  6.81s
req3  200  2.58s     req6  200  7.90s
req1  200  3.66s     req9  200  8.95s
req4  200  4.70s     req7  200 10.04s
req5  200  5.76s     req10 200 11.13s
```

All 10 succeeded, none dropped, server healthy afterwards — but they **serialized**: ~1.1s of CPU
each, so the 10th user waited 11s. Single-fixture digitize latency alone is ~1–3s (fixture 01:
3.1s end-to-end; fixture 07, the heaviest, ~13s).

**Implication for 100 users:** they will not all click at once. If you expect up to ~10 simultaneous
digitizes, run **4–8 workers** (see §3) — that cuts the worst wait to ~2–3s. Rule of thumb:
`workers = CPU cores - 1`, since each worker saturates one core during a digitize.

## 3. Launch configuration (recommended)

```bash
# Terminal 1 — backend, multiple workers
cd apps/backend
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Terminal 2 — frontend, built and served (faster + smaller than dev mode)
npm run build
npx vite preview --host --port 5173
```

**Worker caveat:** local design/profile storage is **file-based per machine**, so multiple workers
on ONE machine are fine (they share the same `data/` directory), but do not run workers across
several machines without pointing them at a shared Supabase (§4).

## 4. Data, backup, and what persists

| What | Where | Notes |
|---|---|---|
| Local user profiles | `apps/backend/data/local_users.json` | usernames + PBKDF2-hashed PINs + session tokens |
| Local designs | `apps/backend/data/designs/<user>/<id>.json` | full design JSON incl. stitches |
| Supabase (optional) | `apps/backend/.env` | if configured, cloud storage is used instead |

Back up before and after the session — it is just files:

```bash
tar czf stitchiq-backup-$(date +%F-%H%M).tar.gz apps/backend/data/
```

Without `.env`, Supabase is off and the local JSON store is the source of truth. That is a
**supported launch configuration**, not a degraded one.

## 5. Health, logs, troubleshooting

- Liveness: `curl http://localhost:8000/health` → `{"status":"ok"}`
- Every request logs one line to logger `stitchiq.access`: method, path, status, duration, client
  IP, request id. Unhandled errors log a full traceback to `stitchiq.error` and return a clean
  `500 {"detail":"Internal server error","requestId":...}` — the id ties the user's screenshot to
  the log line.

| Symptom | Cause | Fix |
|---|---|---|
| `413` on upload | body over 25 MB | resize the image; the limit is `DEFAULT_MAX_BODY_BYTES` in `app/middleware/body_limit.py` |
| `415` on digitize | not a decodable image | file is corrupt or not PNG/JPG/BMP/WebP |
| `422` on digitize | missing/invalid form field | `file` is required; check `max_colors` is 2–8 |
| Digitize feels slow | CPU-bound, worker busy | add workers (§3); fixture-07-class art is ~13s |
| Port in use | previous run still up | `preflight.py` reports it; kill the old process |
| Text vanished from a design | glyphs under ~3mm | expected — see `docs/FAQ.md`; enlarge the text |
| Designs missing after restart | Supabase in keyless in-memory mode | configure `.env`, or rely on the local file store |

## 6. Known limits at launch (be honest with users)

- **No physical sew-outs have been performed.** Exports are format-valid and software-validated;
  test on scrap fabric before a production run (`docs/FABRIC_TEST_PROTOCOL.md`).
- **Sub-3mm lettering** does not render legibly — it is below what embroidery resolves; the
  digitizer drops it cleanly rather than emitting mush.
- Heavy art (fixture-07 class: many small objects, fine rings) takes ~13s per digitize.
- Rate limiting is **not** in place (that swarm task did not land) — a single client can queue many
  requests. For a supervised launch on a trusted LAN this is acceptable; do not expose the port to
  the public internet.
