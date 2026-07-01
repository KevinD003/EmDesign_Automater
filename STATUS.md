# 🧵 STITCHIQ — Project Status & Handoff

> **Single source of truth for project state.** Any model or developer picking up this
> project should read this file first, then [`README.md`](./README.md),
> [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md), and the master spec
> [`AI-Embroidery-Software-Prompt.md`](./AI-Embroidery-Software-Prompt.md).

| Field | Value |
|---|---|
| **Project** | STITCHIQ — AI-powered embroidery design & digitizing platform |
| **Document version** | **v1** |
| **Times updated** | **1** (initial creation) |
| **Last updated** | 2026-06-30 |
| **Current phase** | Scaffold complete — **no feature logic yet** |
| **Git branch** | `main` |
| **Latest code commit** | `d6a4fd1` (scaffold; the state this file describes) |
| **Working tree** | code clean at `d6a4fd1`; this `STATUS.md` is new/untracked until committed |
| **Tracked files** | 54 (55 once this file is committed) |
| **Location** | `/Users/INDIA/Downloads/EmDesign_Automater` |

---

## 📌 For the next model / session — READ THIS FIRST

1. **Current reality:** The project is a **booting scaffold only**. Frontend (TypeScript/React)
   and backend (Python/FastAPI) both start and are wired together, but **every feature is a
   typed stub**. Backend feature endpoints return HTTP `501`; frontend panels render placeholder
   text. Nothing parses, renders, digitizes, or exports yet.
2. **Chosen scope (by the user):** *Scaffold only*, shaped around **File I/O + canvas editor**
   as the first real feature. Do not build the whole spec — it is a multi-year product.
3. **Next task:** implement the **File-I/O + canvas slice** (see [§10 Next Steps](#-10-next-steps-do-these-in-order)).
4. **When you make changes, UPDATE THIS FILE:**
   - Bump **Document version** and **Times updated** in the table above.
   - Update **Last updated** date and the **Git commit** field.
   - Add a row to [§2 Update History](#-2-update-history--changelog).
   - Flip the relevant rows in [§5 Feature Status Matrix](#-5-feature-status-matrix) from
     `🔴 Stub` → `🟡 In progress` → `🟢 Done`.
   - Move completed items from [§7 Remaining](#-7-whats-remaining) to [§6 Done](#-6-whats-done-verified).

---

## 🗂 Table of Contents
1. [TL;DR](#-1-tldr)
2. [Update History / Changelog](#-2-update-history--changelog)
3. [Tech Stack (exact versions)](#-3-tech-stack-exact-installed-versions)
4. [Repository Structure](#-4-repository-structure)
5. [Feature Status Matrix](#-5-feature-status-matrix)
6. [What's DONE (verified)](#-6-whats-done-verified)
7. [What's REMAINING](#-7-whats-remaining)
8. [Key Decisions & Rationale](#-8-key-decisions--rationale)
9. [Environment & Gotchas](#-9-environment--gotchas)
10. [Next Steps](#-10-next-steps-do-these-in-order)
11. [How to Run & Verification Baseline](#-11-how-to-run--verification-baseline)
12. [Known Risks / Unverified Claims](#-12-known-risks--unverified-claims)
13. [Data Model Reference](#-13-data-model-reference)

---

## ✅ 1. TL;DR

- **Stack:** TypeScript (React + Vite) frontend · Python (FastAPI) backend · PostgreSQL/Supabase (schema written, not applied).
- **Built:** monorepo scaffold — app shell, 11 stubbed API endpoints, a shared typed data model mirrored between TS and Python, DB schema, docs.
- **Verified working:** backend boots (`/health`, OpenAPI, stub responses); frontend typechecks, builds (279 modules), and the dev server serves.
- **NOT built:** all feature logic (parsing, rendering, digitizing, export, PDF, thread matching, persistence, auth, AI/ML). No tests. No deployment config.
- **First slice to implement:** open an embroidery file → render stitches on the Konva canvas → export.

---

## 🔄 2. Update History / Changelog

> Add a new row every time the project changes. Newest at top.

| # | Date | Author | Type | Summary |
|---|------|--------|------|---------|
| 1 | 2026-06-30 | Claude (Opus 4.8) | 🏗 Scaffold | Initial greenfield scaffold: TypeScript/React frontend + Python/FastAPI backend monorepo. 11 stub endpoints, shared data model (TS ⇄ Pydantic), DB schema, docs. Verified backend boot + frontend typecheck/build/dev-serve. Committed `d6a4fd1` (54 files). |

**Legend for "Type":** 🏗 Scaffold · ✨ Feature · 🐛 Fix · ♻️ Refactor · 📝 Docs · ⬆️ Deps · 🚀 Deploy

---

## 🧰 3. Tech Stack (exact installed versions)

### Frontend — `apps/frontend` (language: **TypeScript**)
| Package | Version | Role |
|---|---|---|
| react / react-dom | 18.3.1 | UI framework |
| vite | 5.4.21 | dev server + bundler |
| typescript | 5.9.3 | language / typecheck |
| konva | 9.3.22 | 2D canvas engine (stitch rendering) |
| react-konva | 18.2.16 | React bindings for Konva |
| three | 0.169.0 | WebGL (TrueView 3D) |
| @react-three/fiber | 8.18.0 | React bindings for Three.js |
| zustand | 5.0.14 | client state |
| @tanstack/react-query | 5.101.2 | server state / data fetching |
| zod | 3.25.76 | runtime schema validation |
| eslint | 8.57.1 | linting (legacy `.eslintrc.cjs`) |

### Backend — `apps/backend` (language: **Python 3.14**)
| Package | Version | Role | Installed? |
|---|---|---|---|
| fastapi | 0.138.2 | API framework | ✅ core |
| uvicorn | 0.49.0 | ASGI server | ✅ core |
| pydantic | 2.13.4 | data models | ✅ core |
| pydantic-settings | 2.14.2 | env config | ✅ core |
| python-multipart | 0.0.32 | file uploads | ✅ core |
| starlette | 1.3.1 | (FastAPI dep) | ✅ core |
| pyembroidery | 1.5.1 | 45+ embroidery formats I/O | ✅ verified installable (in venv; listed in features file) |
| opencv-python-headless | ≥4.10 | auto-digitizing | ❌ **not installed** |
| pillow | ≥10.4 | image I/O | ❌ **not installed** |
| reportlab | ≥4.2 | worksheet PDF | ❌ **not installed** |
| numpy / scipy | ≥1.26 / ≥1.11 | math / k-d tree | ❌ **not installed** |
| supabase | ≥2.9 | auth + DB + storage | ❌ **not installed** |

> Core deps → `apps/backend/requirements.txt`. Feature deps → `apps/backend/requirements-features.txt`
> (lazy-imported, so the app boots without them).

---

## 📁 4. Repository Structure

```
EmDesign_Automater/
├── STATUS.md                       ← THIS FILE (project state / handoff)
├── README.md                       setup + run instructions
├── AI-Embroidery-Software-Prompt.md  ← the master spec (source of all requirements)
├── package.json                    npm workspace root + dev scripts
├── package-lock.json
├── .gitignore  .env.example
├── docs/
│   ├── ARCHITECTURE.md             condensed architecture (spec §3)
│   └── DATA-MODEL.md               entity list + TS⇄Python mirror notes
├── db/
│   └── schema.sql                  PostgreSQL/Supabase schema (spec §8) — NOT applied
├── apps/
│   ├── frontend/                   TypeScript / React / Vite
│   │   ├── package.json  tsconfig.json  vite.config.ts  index.html  .eslintrc.cjs
│   │   └── src/
│   │       ├── main.tsx  App.tsx           app shell
│   │       ├── types/design.ts             ← shared data model (TS)
│   │       ├── api/client.ts               typed API client (calls all endpoints)
│   │       ├── store/designStore.ts        Zustand store
│   │       ├── lib/units.ts                mm↔px / unit helpers
│   │       └── components/
│   │           ├── toolbar/Toolbar.tsx
│   │           ├── canvas/StitchCanvas.tsx      ← Konva (first to implement)
│   │           ├── panels/ColorObjectList.tsx
│   │           ├── panels/ThreadPalette.tsx
│   │           ├── panels/PropertiesPanel.tsx
│   │           ├── player/StitchPlayer.tsx
│   │           └── trueview/TrueView3D.tsx      (r3f stub, not mounted in shell)
│   └── backend/                    Python / FastAPI
│       ├── requirements.txt  requirements-features.txt  pyproject.toml  .env.example
│       └── app/
│           ├── main.py  config.py          FastAPI app, CORS, /health, router registration
│           ├── models/design.py            ← shared data model (Pydantic, mirrors TS)
│           ├── routers/                     files, convert, digitize, worksheet,
│           │                                export, threads, designs (all stubs)
│           ├── services/                    embroidery_io, digitizer, worksheet_pdf, threads
│           └── data/threads_madeira_sample.json
└── .venv (gitignored) · node_modules (gitignored)
```

---

## 📊 5. Feature Status Matrix

**Status:** 🔴 Stub (not implemented) · 🟡 In progress · 🟢 Done & verified

### Backend endpoints (all under `/api`)
| Endpoint | Method | Status | Returns now | File | Spec |
|---|---|---|---|---|---|
| `/health` | GET | 🟢 Done | `{"status":"ok"}` | `app/main.py` | — |
| `/api/files/parse` | POST | 🔴 Stub **(NEXT)** | 501 | `app/routers/files.py` | §4.8 |
| `/api/convert` | POST | 🔴 Stub | 501 | `app/routers/convert.py` | §4.8 |
| `/api/digitize` | POST | 🔴 Stub | 501 | `app/routers/digitize.py` | §4.2 |
| `/api/worksheet` | POST | 🔴 Stub | 501 | `app/routers/worksheet.py` | §4.9 |
| `/api/export` | POST | 🔴 Stub | 501 | `app/routers/export.py` | §4.8 |
| `/api/export/validate` | POST | 🔴 Stub | 501 | `app/routers/export.py` | §4.8 |
| `/api/threads` | GET | 🔴 Stub | 501 | `app/routers/threads.py` | §4.4 |
| `/api/threads/match` | POST | 🔴 Stub | 501 | `app/routers/threads.py` | §4.4 |
| `/api/designs` | GET | 🟡 Partial | `200 []` (in-memory) | `app/routers/designs.py` | §8 |
| `/api/designs/{id}` | GET | 🟡 Partial | 404 (in-memory) | `app/routers/designs.py` | §8 |
| `/api/designs` | POST | 🔴 Stub | 501 | `app/routers/designs.py` | §8 |

### Backend services (business logic)
| Function | Status | File | Needs |
|---|---|---|---|
| `read_embroidery` / `write_embroidery` | 🔴 Stub | `app/services/embroidery_io.py` | pyembroidery |
| `digitize_image` | 🔴 Stub | `app/services/digitizer.py` | opencv, numpy |
| `build_worksheet` / `render_pdf` | 🔴 Stub | `app/services/worksheet_pdf.py` | reportlab |
| `nearest_thread` | 🔴 Stub | `app/services/threads.py` | scipy |

### Frontend components
| Component | Status | Notes | File |
|---|---|---|---|
| App shell / layout | 🟢 Done | grid layout renders | `src/App.tsx`, `src/index.css` |
| Toolbar | 🔴 Stub | buttons disabled | `src/components/toolbar/Toolbar.tsx` |
| StitchCanvas | 🔴 Stub **(NEXT)** | Konva stage mounts, no geometry | `src/components/canvas/StitchCanvas.tsx` |
| ColorObjectList | 🟡 Partial | renders from store if data present; selection wired; no data yet | `src/components/panels/ColorObjectList.tsx` |
| ThreadPalette | 🔴 Stub | placeholder | `src/components/panels/ThreadPalette.tsx` |
| PropertiesPanel | 🔴 Stub | placeholder | `src/components/panels/PropertiesPanel.tsx` |
| StitchPlayer | 🔴 Stub | disabled controls | `src/components/player/StitchPlayer.tsx` |
| TrueView3D | 🔴 Stub | r3f cube; not mounted in shell | `src/components/trueview/TrueView3D.tsx` |
| designStore (Zustand) | 🟡 Partial | `design`, `selectedObjectId`, setters; needs update/reorder actions | `src/store/designStore.ts` |
| api client | 🟢 Done | all endpoints wired (call the stubs) | `src/api/client.ts` |
| shared types | 🟢 Done | full data model | `src/types/design.ts` |

### Infrastructure
| Item | Status | Notes |
|---|---|---|
| Monorepo / npm workspaces | 🟢 Done | |
| Shared data model (TS ⇄ Pydantic) | 🟢 Done | camelCase-on-wire verified |
| DB schema (`db/schema.sql`) | 🟡 Written | **not applied** to any Supabase project |
| Supabase wiring (auth/persistence/storage) | 🔴 Not started | needs project + credentials |
| Tests / CI | 🔴 None | no test framework set up |
| Dockerfile / deployment | 🔴 None | target: Vercel + Railway/Fly.io (spec §7) |
| AI/ML models (SAM, CNN, RL, diffusion) | 🔴 Not started | future; needs GPU + training data |
| `.STIQ` master format | 🔴 Not started | currently represented as `Design` JSON |

---

## 🟢 6. What's DONE (verified)

Each item below was **confirmed by running it**, not assumed:

1. **Monorepo scaffold** — npm workspaces, 54 files committed (`d6a4fd1`), tree clean.
2. **Shared data model** — `Design`, `DesignObject`, `ColorStop`, `Thread`, `Worksheet`,
   `ValidationReport`, enums — mirrored in `types/design.ts` and `models/design.py`.
   Verified serialization: Python `width_mm` → JSON `widthMm` (camelCase alias works).
3. **Backend boots on Python 3.14** — `uvicorn app.main:app` starts; `GET /health` →
   `{"status":"ok"}`; OpenAPI (`/openapi.json`, `/docs`) lists **all 11 endpoints**.
4. **Stub behavior correct** — `GET /api/designs` → `200 []` (in-memory works);
   unimplemented endpoints → `501` with a clear detail message.
5. **Frontend typecheck** — `tsc --noEmit` clean (0 errors).
6. **Frontend production build** — `vite build` transforms **279 modules** (konva, three,
   react-konva all resolve), emits `dist/`.
7. **Frontend dev server** — `vite` boots in ~84 ms, serves `200` at `http://localhost:5173`,
   HTML references the TS entry `/src/main.tsx`.
8. **`pyembroidery` installs + imports on Python 3.14** — `read` / `write_dst` / `EmbPattern`
   API confirmed present (the next feature is unblocked).

---

## 🔴 7. What's REMAINING

Grouped by priority. **Everything here is unimplemented.**

### A. First slice — File I/O + canvas (do first; see §10)
- Backend: `POST /api/files/parse` → real pyembroidery decode → `Design` (+ `embroidery_io.read_embroidery`).
- Frontend: `StitchCanvas` Konva rendering of `Design.stitches`; populate `ColorObjectList`.
- Backend: `POST /api/export` + `write_embroidery` (Design → .DST/.PES).
- Backend: `POST /api/worksheet` + `render_pdf` (ReportLab PDF, spec §4.9).
- Frontend: `StitchPlayer` animation over the stitch sequence.

### B. Core digitizing & thread features
- `POST /api/digitize` — classical OpenCV pipeline (region detect → stitch-type assign →
  color sequence → path plan), later AI (spec §4.2).
- `GET /api/threads` + `POST /api/threads/match` — load thread DB, hex→Lab k-d tree (spec §4.4).
- `PropertiesPanel` editing (density, underlay, pull compensation, stitch angle).
- `ThreadPalette` — load + assign threads.
- `Toolbar` — wire digitizing tools.

### C. Persistence & platform
- Supabase: create project, apply `db/schema.sql`, wire auth + storage.
- `POST /api/designs` real persistence + `design_versions` snapshots.
- `.STIQ` master file format.

### D. Advanced / innovation (spec §6, future)
- AI: SAM segmentation, CNN stitch classifier, RL/graph path optimizer, diffusion generative design.
- TrueView 3D realistic simulation (`TrueView3D` real implementation).
- Real-time collaboration, predictive quality scoring, mobile app, cloud API platform (spec §4.12).

### E. Engineering hygiene (not yet set up)
- Test framework + tests (pytest backend, vitest frontend) + CI.
- Dockerfile(s) + deployment config (Vercel / Railway / Fly.io per spec §7).
- ESLint run in CI; Prettier; pre-commit hooks.
- Error handling, logging, request validation beyond the happy path.

---

## 🧭 8. Key Decisions & Rationale

| Decision | Why | Reversible? |
|---|---|---|
| **TypeScript** (frontend) + **Python** (backend) | User request ("most advanced/flexible non-HTML"); matches spec §7. Python is mandatory — pyembroidery/PyTorch/OpenCV are Python-only. | Foundational |
| **Scaffold-only** first pass | User chose it; full spec is a multi-year product. | — |
| **File I/O + canvas** as first feature | User chose it; pyembroidery makes it the most achievable, high-value backbone. | — |
| **npm workspaces** (not pnpm) | pnpm not installed on this machine; npm 11 is present and equivalent. | Yes — swap to pnpm later. |
| **Tiered Python deps** (`requirements.txt` core + `requirements-features.txt`) | Python 3.14 is new; heavy wheels may lag. Core (5 pkgs) guarantees boot; features lazy-imported. | Yes |
| **Single `tsconfig.json`** (dropped project references) | `tsc --noEmit` + composite refs threw `TS6310`. Simpler & robust for a scaffold. | Yes |
| **ESLint 8 legacy `.eslintrc.cjs`** (not 9 flat) | Stability; fewer moving parts for a scaffold. | Yes |
| Services **lazy-import** heavy libs | So the app boots before opencv/reportlab/etc. are installed. | Yes |
| Made an **initial git commit** | Standard for a new scaffold; local only. Rollback: `git reset --soft HEAD~1` or `rm -rf .git`. | Yes |

---

## ⚠️ 9. Environment & Gotchas

- **Python 3.14.3** is the local interpreter — **very new**. `opencv-python-headless`, `scipy`,
  `reportlab` are **untested** here and may lack 3.14 wheels. If `pip install -r requirements-features.txt`
  fails, use **Python 3.11–3.12** for the backend venv.
- **pnpm is NOT installed** — use `npm`. Scripts assume npm workspaces.
- **Backend venv** lives at `apps/backend/.venv` (gitignored). Activate before running uvicorn.
- **Vite dev proxy:** `/api` and `/health` are proxied to `http://localhost:8000` (see `vite.config.ts`).
  In production set `VITE_API_BASE_URL` to the deployed backend origin.
- **Supabase** requires the user's own project URL + keys (`.env`); nothing is wired yet.
- **CORS** allows `http://localhost:5173` only (see `app/config.py`).
- **`tsconfig` has `noUnusedLocals/Parameters: false`** (relaxed for stubs) — re-enable when implementing.
- **No secrets committed.** `.env` files are gitignored; only `.env.example` templates are tracked.

---

## 🎯 10. Next Steps (do these IN ORDER)

The **File-I/O + canvas** vertical slice — makes the app actually do something end-to-end:

1. **`app/services/embroidery_io.py` → `read_embroidery(data, fmt)`**
   Use `pyembroidery.read_*` to decode bytes; map `pattern.stitches` (1/10 mm) → `Design.stitches`
   (mm, via a command map), and `pattern.threadlist` → `Design.color_stops`. Compute `stitch_count`,
   `width_mm`, `height_mm`.
2. **`app/routers/files.py` → `POST /api/files/parse`**
   Read the `UploadFile`, call `read_embroidery`, return the `Design`. Remove the `501`.
3. **`apps/frontend/src/components/canvas/StitchCanvas.tsx`**
   Group consecutive `STITCH` commands into Konva `<Line>` polylines (mm→px via `lib/units.mmToPx`),
   color each run by its `ColorStop.hex`, skip `JUMP`/`TRIM` travel. Fit-to-view.
4. **Wire upload UI** — `Toolbar` "Open" button → file picker → `api.parseFile(file)` →
   `useDesignStore.setDesign(...)`. `ColorObjectList` will then populate automatically.
5. **`app/services/embroidery_io.py` → `write_embroidery`** + **`POST /api/export`**
   Build an `EmbPattern` from a `Design`, write `.DST`/`.PES`, return the file.
6. **`app/services/worksheet_pdf.py`** + **`POST /api/worksheet`** — derive the worksheet
   (spec §4.9) and render a PDF with ReportLab.
7. **`StitchPlayer`** — scrub/animate over `Design.stitches`.

> After each step: re-run the verification in §11 and **update this file** (§2 changelog + §5 matrix).

---

## 🧪 11. How to Run & Verification Baseline

### Run
```bash
# Backend
cd apps/backend
source .venv/bin/activate          # venv already created
uvicorn app.main:app --reload --port 8000
#   → http://localhost:8000/health  and  /docs

# Frontend (new terminal, from repo root)
npm run dev:frontend               # → http://localhost:5173

# Both at once (from repo root)
npm run dev
```

### One-time setup on a fresh clone
```bash
npm install                                        # frontend deps (workspace root)
cd apps/backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt                    # core (boots the app)
pip install -r requirements-features.txt           # heavy libs (for features; may need py3.11–3.12)
```

### Verification baseline (last confirmed 2026-06-30, Update #1)
| Check | Command | Expected | Last result |
|---|---|---|---|
| Backend health | `curl localhost:8000/health` | `{"status":"ok"}` | ✅ pass |
| Endpoints registered | `curl localhost:8000/openapi.json` | 11 `/api/*` paths + `/health` | ✅ pass |
| Stub behavior | `curl localhost:8000/api/threads` | `501` | ✅ pass |
| Frontend typecheck | `npm run typecheck` | 0 errors | ✅ pass |
| Frontend build | `npm run build --workspace apps/frontend` | 279 modules, `dist/` | ✅ pass |
| Frontend dev serve | `npm run dev:frontend` + `curl localhost:5173` | `200`, refs `/src/main.tsx` | ✅ pass |

**Tests:** none exist yet — there is no test suite to run. Add one (§7E).

---

## 🚧 12. Known Risks / Unverified Claims

- **In-browser render not confirmed.** Build + typecheck + dev-serve all pass, but the React app
  was **not opened in a real browser** during scaffold creation. Open `http://localhost:5173`
  and confirm the panels paint and no console errors appear. *(Most likely to surprise you.)*
- **Feature libraries untested on Python 3.14** — opencv/scipy/reportlab/pillow/numpy/supabase are
  **not installed**. First `pip install -r requirements-features.txt` may hit a missing-wheel/build
  error; fall back to Python 3.11–3.12.
- **DB schema unvalidated against a live Postgres** — `db/schema.sql` is written but never executed;
  syntax/RLS may need adjustment when first applied to Supabase.
- **`_IncludedRouter` note:** FastAPI 0.138 represents included routers lazily in `app.routes`
  (they don't flatten). This is normal — routing and OpenAPI work correctly (verified).

---

## 🧬 13. Data Model Reference

Mirrored in [`apps/frontend/src/types/design.ts`](./apps/frontend/src/types/design.ts) and
[`apps/backend/app/models/design.py`](./apps/backend/app/models/design.py). **Edit both together.**
Full details in [`docs/DATA-MODEL.md`](./docs/DATA-MODEL.md).

Core entities: `Stitch` (x, y, command) · `StitchType` enum · `UnderlayType` enum · `ConnectMethod`
enum · `Thread` · `ColorStop` · `DesignObject` · `Design` · `Worksheet` · `ValidationReport` ·
`ConvertRequest`/`ConvertResponse`. Python uses a camelCase alias generator so JSON matches the TS
interfaces exactly (`width_mm` ⇄ `widthMm`).

---

*End of STATUS.md — keep this file current. When in doubt, trust the code over this document, and fix the document.*
