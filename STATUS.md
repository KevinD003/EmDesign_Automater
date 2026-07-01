# 🧵 STITCHIQ — Project Status & Handoff

> **Single source of truth for project state.** Any model or developer picking up this
> project should read this file first, then [`README.md`](./README.md),
> [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md), and the master spec
> [`AI-Embroidery-Software-Prompt.md`](./AI-Embroidery-Software-Prompt.md).

| Field | Value |
|---|---|
| **Project** | STITCHIQ — AI-powered embroidery design & digitizing platform |
| **Document version** | **v2** |
| **Times updated** | **2** |
| **Last updated** | 2026-06-30 |
| **Current phase** | Scaffold complete — **no feature logic yet**. Next: Phase 1 (see §14–15) |
| **Git branch** | `main` |
| **Latest code commit** | `d6a4fd1` (scaffold — no code has changed since; only docs) |
| **Working tree** | clean |
| **Tracked files** | 55 |
| **Location** | `/Users/INDIA/Downloads/EmDesign_Automater` |

---

## 📌 For the next model / session — READ THIS FIRST

1. **Current reality:** The project is a **booting scaffold only**. Frontend (TypeScript/React)
   and backend (Python/FastAPI) both start and are wired together, but **every feature is a
   typed stub**. Backend feature endpoints return HTTP `501`; frontend panels render placeholder
   text. Nothing parses, renders, digitizes, or exports yet.
2. **Chosen scope (by the user):** *Scaffold only*, shaped around **File I/O + canvas editor**
   as the first real feature. Do not build the whole spec at once — it is a multi-year product.
   The full phased plan is in [§14](#-14-full-project-roadmap-phases-010).
3. **Next task:** implement **Phase 1 — File I/O + Canvas**. Quick list in
   [§10](#-10-next-steps-do-these-in-order); **full technical plan (pyembroidery-grounded) in
   [§15](#-15-phase-1-deep-dive--file-io--canvas-current-work)**; whole roadmap in
   [§14](#-14-full-project-roadmap-phases-010).
4. **⚠️ MANDATORY — every change to this project is logged in THIS FILE.** Before you finish any task:
   - Bump **Document version** and **Times updated** in the metadata table above.
   - Update **Last updated**; add a row to [§2 Update History](#-2-update-history--changelog) (**newest on top**).
   - Flip the relevant rows in [§5 Feature Status Matrix](#-5-feature-status-matrix):
     `🔴 Stub` → `🟡 In progress` → `🟢 Done`.
   - Move completed items from [§7 Remaining](#-7-whats-remaining) to [§6 Done](#-6-whats-done-verified);
     tick the phase in [§14](#-14-full-project-roadmap-phases-010).
   - Commit the doc **with** the code change (or as a `docs:` commit).

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
10. [Next Steps (quick list)](#-10-next-steps-do-these-in-order)
11. [How to Run & Verification Baseline](#-11-how-to-run--verification-baseline)
12. [Known Risks / Unverified Claims](#-12-known-risks--unverified-claims)
13. [Data Model Reference](#-13-data-model-reference)
14. [Full Project Roadmap (Phases 0–10)](#-14-full-project-roadmap-phases-010)
15. [Phase 1 Deep-Dive — File I/O + Canvas](#-15-phase-1-deep-dive--file-io--canvas-current-work)

---

## ✅ 1. TL;DR

- **Stack:** TypeScript (React + Vite) frontend · Python (FastAPI) backend · PostgreSQL/Supabase (schema written, not applied).
- **Built:** monorepo scaffold — app shell, 11 stubbed API endpoints, a shared typed data model mirrored between TS and Python, DB schema, docs.
- **Verified working:** backend boots (`/health`, OpenAPI, stub responses); frontend typechecks, builds (279 modules), and the dev server serves.
- **NOT built:** all feature logic (parsing, rendering, digitizing, export, PDF, thread matching, persistence, auth, AI/ML). No tests. No deployment config.
- **First slice to implement:** open an embroidery file → render stitches on the Konva canvas → export ([§15](#-15-phase-1-deep-dive--file-io--canvas-current-work)).

---

## 🔄 2. Update History / Changelog

> Add a new row every time the project changes. **Newest at top.**

| # | Date | Author | Type | Summary |
|---|------|--------|------|---------|
| 2 | 2026-06-30 | Claude (Opus 4.8) | 📝 Docs | Added the **full project roadmap** (Phases 0–10, §14) and a **pyembroidery-grounded Phase 1 deep-dive** (§15). Confirmed the real pyembroidery v1.5.1 API on Python 3.14. Committed STATUS.md v1 (`3e34389`) beforehand. No code changes. |
| 1 | 2026-06-30 | Claude (Opus 4.8) | 🏗 Scaffold | Initial greenfield scaffold: TypeScript/React frontend + Python/FastAPI backend monorepo. 11 stub endpoints, shared data model (TS ⇄ Pydantic), DB schema, docs. Verified backend boot + frontend typecheck/build/dev-serve. Committed `d6a4fd1` (54 files); STATUS.md added in `3e34389`. |

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
| pyembroidery | 1.5.1 | 45+ embroidery formats I/O | ✅ installed in venv (listed in features file) |
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
├── STATUS.md                       ← THIS FILE (project state / handoff / roadmap)
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

**Status:** 🔴 Stub (not implemented) · 🟡 In progress / partial · 🟢 Done & verified

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
2. **Shared data model** — `Design`/`DesignObject`/`ColorStop`/`Thread`/`Worksheet`/`ValidationReport` +
   enums — mirrored in `types/design.ts` and `models/design.py`. Verified serialization: Python
   `width_mm` → JSON `widthMm` (camelCase alias works).
3. **Backend boots on Python 3.14** — `uvicorn app.main:app` starts; `GET /health` →
   `{"status":"ok"}`; OpenAPI (`/openapi.json`, `/docs`) lists **all 11 endpoints**.
4. **Stub behavior correct** — `GET /api/designs` → `200 []` (in-memory works); unimplemented
   endpoints → `501` with a clear detail message.
5. **Frontend typecheck** — `tsc --noEmit` clean (0 errors).
6. **Frontend production build** — `vite build` transforms **279 modules** (konva, three,
   react-konva all resolve), emits `dist/`.
7. **Frontend dev server** — `vite` boots in ~84 ms, serves `200` at `http://localhost:5173`,
   HTML references the TS entry `/src/main.tsx`.
8. **`pyembroidery` installs + imports on Python 3.14** — `read`/`write_dst`/`EmbPattern` present;
   full API confirmed (see [§15](#-15-phase-1-deep-dive--file-io--canvas-current-work)).

---

## 🔴 7. What's REMAINING

Grouped by priority. **Everything here is unimplemented.** Full phased plan in [§14](#-14-full-project-roadmap-phases-010).

### A. Phase 1 — File I/O + canvas (do first; see §15)
- Backend `POST /api/files/parse` → real pyembroidery decode → `Design` (+ `embroidery_io.read_embroidery`).
- Frontend `StitchCanvas` Konva rendering of `Design.stitches`; populate `ColorObjectList`.
- Backend `POST /api/export` + `write_embroidery` (Design → .DST/.PES).
- Backend `POST /api/worksheet` + `render_pdf` (ReportLab PDF).
- Frontend `StitchPlayer` animation.

### B. Phases 2–5 — core editor & production
- Interactive editing (properties, thread palette, selection, undo/redo) — Phase 2.
- Auto-digitizing (OpenCV) — Phase 3. Lettering — Phase 4. Full export/convert/validate — Phase 5.

### C. Phase 6 — persistence & accounts
- Supabase project + apply `db/schema.sql`; auth; `designs` CRUD; versions; teams; `.STIQ` master format.

### D. Phases 7–10 — advanced (future)
- TrueView 3D (7); AI engine SAM/CNN/RL/quality-scoring (8); generative + STITCH-GPT (9); collab/cloud API/mobile (10).

### E. Cross-cutting (start now, never "done")
- Tests (pytest + vitest) + CI; Dockerfiles + deployment; logging/observability; auth/validation/rate-limiting.

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
| Made **git commits** (scaffold + docs) | Standard for a new project; local only. Rollback: `git reset --soft HEAD~1` or `rm -rf .git`. | Yes |

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

The **File-I/O + canvas** vertical slice — makes the app actually do something end-to-end.
**> Full technical detail (API cheat-sheet, mapping, acceptance criteria) for every step is in
[§15 Phase 1 Deep-Dive](#-15-phase-1-deep-dive--file-io--canvas-current-work).**

1. `app/services/embroidery_io.py` → `read_embroidery` (pyembroidery decode → `Design`).
2. `app/routers/files.py` → wire `POST /api/files/parse`; remove the `501`.
3. `components/canvas/StitchCanvas.tsx` → render stitches in Konva; `ColorObjectList` populates.
4. `Toolbar` "Open" → file picker → `api.parseFile` → `setDesign`.
5. `write_embroidery` + `POST /api/export` (Design → .DST/.PES).
6. `worksheet_pdf` + `POST /api/worksheet` (ReportLab PDF).
7. `StitchPlayer` animation over `Design.stitches`.

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

**Tests:** none exist yet — there is no test suite to run. Add one (Phase X / §14).

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

## 🗺 14. Full Project Roadmap (Phases 0–10)

> **Build vertically, not horizontally.** Each phase is a thin end-to-end slice that ships
> something usable; the next phase deepens it. Sizes are *relative complexity*, not calendar
> promises: **S** = hours · **M** = 1–2 days · **L** = ~a week · **XL** = multi-week.
> Workflow every phase: **implement → run/verify → update this file (§2 + §5 + tick below).**

### Overview

| Phase | Name | Status | Size | What it unlocks |
|---|---|---|---|---|
| 0 | Scaffold | 🟢 Done | — | the whole codebase |
| **1** | **File I/O + Canvas** | ⬜ **Next** | L | open, view, export real designs ([§15](#-15-phase-1-deep-dive--file-io--canvas-current-work)) |
| 2 | Interactive editing | ⬜ | L | select/edit objects, properties, threads |
| 3 | Auto-digitizing v1 (OpenCV) | ⬜ | XL | image → stitches |
| 4 | Lettering & monogramming | ⬜ | L | text → stitches |
| 5 | Production output & formats | ⬜ | M | worksheets, export packages, 25+ formats |
| 6 | Persistence & accounts (Supabase) | ⬜ | M | save/load, auth, versions, teams |
| 7 | TrueView 3D simulation | ⬜ | L | realistic preview |
| 8 | AI engine | ⬜ | XL | smart digitizing, path optimization, quality scoring |
| 9 | Generative & assistant | ⬜ | XL | text-to-design, STITCH-GPT, NL editing |
| 10 | Platform & scale | ⬜ | XL | real-time collab, cloud API, mobile, machine monitoring |
| X | Cross-cutting (tests/CI/deploy/security) | 🟡 Ongoing | — | ships everything safely |

### Phase 1 — File I/O + Canvas ⬜  *(full detail in [§15](#-15-phase-1-deep-dive--file-io--canvas-current-work))*
- **Goal:** open a real `.DST`/`.PES` → render stitches on the Konva canvas → export → worksheet PDF.
- **Depends on:** pyembroidery (✅), reportlab (features, for the PDF).
- **Acceptance:** open real file → render → edit a color → export `.PES` → re-open (stitch count stable) → worksheet PDF.

### Phase 2 — Interactive Editing ⬜  (size L)
- **Goal:** turn the viewer into an editor — select objects, edit stitch properties, manage threads.
- **Tasks:** canvas hit-test selection ↔ `ColorObjectList`; `PropertiesPanel` bound to the selected
  `DesignObject` (density, stitch angle, underlay, pull-comp — spec §4.3); `ThreadPalette` loads the
  catalog + drag-to-assign; reorder color stops; undo/redo (Zustand history); zoom/pan/grid/rulers.
- **Files:** `components/panels/*`, `store/designStore.ts` (add `updateObject`, `reorder`, history), `StitchCanvas`.
- **Spec:** §3, §4.3, §4.4. **Acceptance:** change a selected object's density and see it reflected; assign a thread; undo restores.

### Phase 3 — Auto-Digitizing v1 (classical OpenCV) ⬜  (size XL)
- **Goal:** upload an image → get an editable stitch `Design` (pure CV + heuristics, no AI yet).
- **Tasks:** implement `digitizer.digitize_image` — color quantization (k-means), region segmentation
  (contours/threshold), per-region stitch-type by size (satin for narrow, tatami fill for large, run
  for thin lines), fill/satin generation, color-stop ordering, nearest-neighbor path planning + trims.
  Wire `POST /api/digitize` + an upload dialog with fabric/hoop inputs.
- **Files:** `services/digitizer.py`, `routers/digitize.py`, new frontend digitize dialog.
- **Deps:** opencv-python-headless, numpy, pillow (features — may need py3.11–3.12).
- **Spec:** §4.2, §4.5, §4.6. **Acceptance:** a simple logo → recognizable stitched regions, correct color count, editable on the canvas.
- **Honesty note:** classical CV output is approximate; neural quality arrives in Phase 8. Keep this path as the fallback.

### Phase 4 — Lettering & Monogramming ⬜  (size L)
- **Goal:** type text → generate satin/fill lettering with proper underlay.
- **Tasks:** font glyph → outline (freetype/fonttools) → satin columns / fill per glyph; kerning,
  baseline, arc/envelope layouts, monogram frames; auto-underlay; density rules. New lettering tool + panel.
- **Spec:** §4.10. **Deps:** freetype-py / fonttools. **Acceptance:** "ABC" in a chosen font → clean satin lettering, editable, exportable.

### Phase 5 — Production Output & Formats ⬜  (size M)
- **Goal:** complete the production pipeline.
- **Tasks:** finish `POST /api/export` package (machine file + master JSON + worksheet PDF + thread
  color card + TrueView PNG + placement guide); `POST /api/export/validate` (jump/size/stitch-count/
  tie-off checks — spec §4.8); `POST /api/convert` (any→any via pyembroidery's 29 read/write formats);
  format decision tree by machine brand.
- **Files:** `routers/export.py`, `routers/convert.py`, `services/worksheet_pdf.py`, `services/embroidery_io.py`.
- **Spec:** §4.8, §4.9. **Acceptance:** export a full ZIP package; validation flags a deliberately-bad design; DST↔PES convert round-trips.

### Phase 6 — Persistence & Accounts (Supabase) ⬜  (size M)
- **Goal:** users save/load designs; auth; versions; teams.
- **Tasks:** create Supabase project; apply `db/schema.sql`; wire Supabase auth (frontend) + service
  client (backend); implement `designs` CRUD against Postgres + Supabase Storage for files;
  `design_versions` snapshots; RLS review.
- **Files:** `routers/designs.py`, new `services/supabase_*.py`, frontend auth pages, `config.py` (keys).
- **Deps:** supabase (features); **user must provide** a Supabase project URL + keys.
- **Spec:** §8. **Acceptance:** sign in → save a design → reload → it's there; another user can't read it (RLS).

### Phase 7 — TrueView 3D Simulation ⬜  (size L)
- **Goal:** realistic thread preview.
- **Tasks:** implement `TrueView3D` — per-stitch thread geometry (tubes/quads) with normal/specular
  for sheen, soft shadowing, a fabric background; 2D↔3D toggle; export TrueView PNG.
- **Files:** `components/trueview/TrueView3D.tsx`, materials/shaders.
- **Spec:** §4.7. **Acceptance:** a design renders as recognizable 3D thread matching the 2D layout.

### Phase 8 — AI Engine ⬜  (size XL)
- **Goal:** replace heuristics with learned models; add quality scoring.
- **Tasks:** SAM/U-Net region segmentation; CNN (ResNet/EfficientNet) stitch-type classifier;
  graph + RL stitch-path optimizer (NetworkX + custom); predictive stitch-quality scoring; k-d tree
  Lab thread match (`services/threads.nearest_thread`). Serve via ONNX Runtime; GPU inference (Modal/RunPod).
- **Spec:** §4.2, §4.5, §6. **Deps:** torch, onnxruntime, GPU, training data.
- **Acceptance:** AI digitize beats the Phase-3 CV baseline on a test set; quality score correlates with real defects.
- **Note:** largest phase; needs data + GPU budget. Keep the Phase-3 CV path as fallback.

### Phase 9 — Generative & Assistant ⬜  (size XL)
- **Goal:** text-to-design + an embroidery-expert chat assistant.
- **Tasks:** fine-tuned diffusion for embroidery-friendly art → digitize pipeline; "STITCH-GPT"
  assistant (Claude-backed) grounded in the current design; natural-language editing ("make the
  outline thicker"); generative variations.
- **Spec:** §4.1, §4.11, §6. **Acceptance:** a prompt yields a stitchable design; the assistant answers digitizing questions about the open design.

### Phase 10 — Platform & Scale ⬜  (size XL)
- **Goal:** productionize the platform.
- **Tasks:** real-time collaborative editing (CRDT/WebSocket); public cloud API (spec §4.12); mobile
  app; machine monitoring/analytics; billing/subscription tiers.
- **Spec:** §4.12, §6. **Acceptance:** two users edit live; external API create-design works; mobile viewer.

### Phase X — Cross-Cutting (start in Phase 1, never "done")
- **Testing:** pytest (backend) + vitest/RTL (frontend) + an embroidery round-trip test; meaningful coverage on services.
- **CI/CD:** GitHub Actions (typecheck, lint, test, build) on every push.
- **Deployment:** Dockerfile(s); Vercel (frontend) + Railway/Fly.io (backend) + Modal/RunPod (GPU) — spec §7.
- **Observability:** structured logging, error tracking (Sentry), request tracing.
- **Security:** authz on every endpoint, input validation, upload file-type/size limits, rate limiting, secret management.

---

## 🔧 15. Phase 1 Deep-Dive — File I/O + Canvas (current work)

**Objective.** A complete vertical slice proving the architecture: **open a real embroidery file →
render its stitches on the canvas → export it → generate a worksheet.** After this, STITCHIQ is a
real (minimal) embroidery viewer/converter, and every later phase plugs into a proven pipeline
(upload → backend parse → `Design` → canvas render → export).

### pyembroidery API cheat-sheet — CONFIRMED on v1.5.1 / Python 3.14
| Need | API | Notes |
|---|---|---|
| Read a file | `pe.read(filename)` | auto-detects by extension; takes a **filename string** |
| Read by format | `pe.read_dst(f)`, `read_pes(f)`, … (29 read/write fns) | accept file-like objects |
| Stitches | `pattern.stitches` → `list[[x, y, cmd_int]]` | coords in **1/10 mm** → divide by 10 for mm |
| Command ints | `pe.STITCH=0, JUMP=1, TRIM=2, STOP=3, END=4, COLOR_CHANGE=5` | **map via `pe.*` constants, don't hardcode ints** |
| Threads | `pattern.threadlist` → `list[EmbThread]` | `.hex_color()`, `.description`, `.catalog_number`, `.brand`, `.get_red/green/blue()`, `.weight` |
| Color blocks | `pattern.get_as_colorblocks()` | yields `(stitches, thread)` per stop → build `ColorStop`s + per-stop counts |
| Extents | `pattern.bounds()` → `(minx, miny, maxx, maxy)` | in 1/10 mm → width/height |
| Counts | `pattern.count_stitches()`, `count_color_changes()` | |
| Build | `pattern.add_stitch_absolute(cmd, x_tenths, y_tenths)`, `add_thread(thread)` | mm→tenths = ×10 |
| Write | `pe.write(pattern, filename)` / `write_dst(pattern, f)` | `f` can be a `BytesIO` |
| Formats | `pe.supported_formats()` | 45+ read/write |

**Command mapping (build from constants, not literals):**
`CMD = {pe.STITCH:'STITCH', pe.JUMP:'JUMP', pe.TRIM:'TRIM', pe.STOP:'STOP', pe.END:'END', pe.COLOR_CHANGE:'COLOR_CHANGE'}`
and the reverse for export. Unknown commands → skip + log.

### Tasks (each: file → what → acceptance)

**1.1 `embroidery_io.read_embroidery(data: bytes, ext: str) -> Design`** — `services/embroidery_io.py`
1. Write `data` to `tempfile.NamedTemporaryFile(suffix=f'.{ext}')`; `pattern = pe.read(path)`; clean up.
2. `stitches = [Stitch(x=x/10, y=y/10, command=CMD.get(c,'STITCH')) for x,y,c in pattern.stitches]`.
3. `minx,miny,maxx,maxy = pattern.bounds()` → `width_mm=(maxx-minx)/10`, `height_mm=(maxy-miny)/10`.
4. Build `color_stops` from `get_as_colorblocks()`: `stop_number`, `thread_brand=thread.brand`,
   `catalog_number`, `thread_name=thread.description`, `hex=thread.hex_color()`, `stitch_count=len(block)`.
5. `stitch_count = pattern.count_stitches()`; `name` from the filename; `status='digitized'`.
- **Edge cases:** unsupported `ext` → `ValueError` (→ 415); no stitches → return with empty lists + a warning.
- **Acceptance:** for a known fixture, `stitch_count`, number of color stops, and width/height match expectations.

**1.2 `POST /api/files/parse`** — `routers/files.py`
- `data = await file.read()`; derive `ext` from `file.filename`; `return read_embroidery(data, ext)`;
  map `ValueError`→400/415. Remove the `501`.
- **Acceptance:** `curl -F "file=@sample.dst" localhost:8000/api/files/parse` → `200` with `Design` JSON (camelCase).

**1.3 `StitchCanvas` Konva rendering** — `components/canvas/StitchCanvas.tsx`
- Walk `stitches`; accumulate consecutive `STITCH` points into the current polyline; on
  `JUMP`/`TRIM`/`COLOR_CHANGE`/`END`, flush it. Assign each run the current color stop's `hex`
  (advance the stop index on `COLOR_CHANGE`).
- Render each run as a Konva `<Line points={[x1,y1,…]} stroke={hex} strokeWidth={~1.2}/>`;
  mm→px via `lib/units.mmToPx`; compute fit-to-view scale + offset from design bounds; add wheel-zoom
  + drag-pan (Konva `draggable`).
- **Acceptance:** opening a design shows recognizable geometry; stop colors correct; zoom/pan smooth.

**1.4 Upload flow** — `components/toolbar/Toolbar.tsx` + `store/designStore.ts`
- "Open" triggers a hidden `<input type="file" accept=".dst,.pes,.jef,.exp,.vp3,…">`; on change →
  `const d = await api.parseFile(file); setDesign(d);`. `ColorObjectList` populates from the store automatically.
- **Acceptance:** click Open → pick a file → canvas + object list fill; errors show a toast/message.

**1.5 Export** — `embroidery_io.write_embroidery` + `routers/export.py`
- `write_embroidery(design, ext)`: `p=pe.EmbPattern()`; for each stitch `p.add_stitch_absolute(REV_CMD[cmd], x*10, y*10)`;
  add threads from `color_stops`; write to a `BytesIO` via `write_<ext>`; return bytes.
- `POST /api/export` returns a `StreamingResponse` (full package comes in Phase 5). Start with `.DST` + `.PES`.
- **Acceptance:** export → re-parse the exported bytes → `stitch_count` preserved (round-trip stable).

**1.6 Worksheet** — `services/worksheet_pdf.py` + `routers/worksheet.py`
- `build_worksheet(design)`: aggregate the color sequence, count trims (`TRIM`) and color changes,
  estimate sew minutes (`stitch_count / 800` SPM), dimensions.
- `render_pdf(worksheet)`: ReportLab — header, dimensions, color table, sequence map (spec §4.9).
  `POST /api/worksheet` returns the PDF.
- **Deps:** reportlab (features; may need py3.11–3.12). **Acceptance:** POST a design → PDF with a correct color table.

**1.7 StitchPlayer** — `components/player/StitchPlayer.tsx`
- Slider `0..stitches.length`; render only stitches up to the cursor; Play advances via
  `requestAnimationFrame`; speed control.
- **Acceptance:** Play animates the needle path; scrub works.

### Phase 1 — Definition of Done
Open a real `.DST` → render → change one color → export `.PES` → re-open the export (stitch count
stable) → download a worksheet PDF. All via the entry paths a user actually clicks.

### Test fixtures & verification
- **Fixture (don't use copyrighted designs):** generate one — a small script builds an `EmbPattern`
  (e.g., a filled circle + a 2-color shape) and `write_dst` to `apps/backend/tests/fixtures/sample.dst`.
  Commit the fixture.
- **Backend test (pytest):** round-trip — read fixture → `Design` → `write_embroidery` → read again →
  assert stitch counts / thread count match. (This also bootstraps Phase X testing.)
- **Manual:** open the fixture in the UI; confirm render + colors; export; re-open; worksheet.
- **Install for Phase 1:** `pyembroidery` (✅ in venv) and, for 1.6, `reportlab`.

---

*End of STATUS.md — keep this file current. When in doubt, trust the code over this document, and fix the document.*
