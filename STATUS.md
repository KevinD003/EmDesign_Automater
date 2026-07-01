# 🧵 STITCHIQ — Project Status & Handoff

> **Single source of truth for project state.** Any model or developer picking up this
> project should read this file first, then [`README.md`](./README.md),
> [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md), and the master spec
> [`AI-Embroidery-Software-Prompt.md`](./AI-Embroidery-Software-Prompt.md).

| Field | Value |
|---|---|
| **Project** | STITCHIQ — AI-powered embroidery design & digitizing platform |
| **Document version** | **v3** |
| **Times updated** | **3** |
| **Last updated** | 2026-06-30 |
| **Current phase** | **Phase 1 (File I/O + Canvas) — core done & verified.** Remaining: worksheet PDF, then Phase 2 |
| **Git branch** | `main` |
| **Latest code commit** | `d9fbc28` (Phase 1 core) |
| **Working tree** | clean |
| **Tracked files** | 60 |
| **Location** | `/Users/INDIA/Downloads/EmDesign_Automater` |

---

## 📌 For the next model / session — READ THIS FIRST

1. **Current reality:** Scaffold **plus Phase 1 core (File I/O + Canvas)**. You can open a real
   `.DST`/`.PES` → see it rendered on the Konva canvas → export it → get a worksheet (JSON).
   Verified end-to-end (pytest 5/5 + upload through the Vite dev proxy). *Most other* features are
   still typed stubs (`501` / placeholder) — see [§5](#-5-feature-status-matrix) for exactly what's done vs stubbed.
2. **Chosen scope (by the user):** build **vertically**, one phase at a time. Full phased plan in
   [§14](#-14-full-project-roadmap-phases-010). Do not build the whole spec at once.
3. **Next task:** finish the **Phase 1 tail** — worksheet **PDF** render via ReportLab
   (`render_pdf` in `services/worksheet_pdf.py`) — then start **Phase 2 (Interactive Editing)**.
   Phase 1 technical notes live in [§15](#-15-phase-1-deep-dive--file-io--canvas).
4. **⚠️ MANDATORY — every change to this project is logged in THIS FILE.** Before you finish any task:
   - Bump **Document version** and **Times updated** in the metadata table above.
   - Update **Last updated** + **Latest code commit**; add a row to [§2 Update History](#-2-update-history--changelog) (**newest on top**).
   - Flip the relevant rows in [§5 Feature Status Matrix](#-5-feature-status-matrix): `🔴 Stub` → `🟡 In progress` → `🟢 Done`.
   - Move completed items from [§7 Remaining](#-7-whats-remaining) to [§6 Done](#-6-whats-done-verified); tick the phase in [§14](#-14-full-project-roadmap-phases-010).
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
15. [Phase 1 Deep-Dive — File I/O + Canvas](#-15-phase-1-deep-dive--file-io--canvas)

---

## ✅ 1. TL;DR

- **Stack:** TypeScript (React + Vite) frontend · Python (FastAPI) backend · PostgreSQL/Supabase (schema written, not applied).
- **Built:** scaffold **+ Phase 1 core** — open/parse embroidery files, render stitches on the Konva canvas, export to machine files, worksheet (JSON). Shared typed data model, DB schema, docs.
- **Verified working:** backend **pytest 5/5** + all endpoints (TestClient + real HTTP); **upload through the Vite proxy**; frontend **typecheck + build (280 modules)**. *(In-browser canvas paint not eyeballed — see §12.)*
- **Still stubbed:** auto-digitize, thread matching, persistence/auth, AI/ML, and the worksheet **PDF** render (JSON works).
- **Next:** worksheet PDF (Phase 1 tail), then Phase 2 interactive editing ([§14](#-14-full-project-roadmap-phases-010)).

---

## 🔄 2. Update History / Changelog

> Add a new row every time the project changes. **Newest at top.**

| # | Date | Author | Type | Summary |
|---|------|--------|------|---------|
| 3 | 2026-06-30 | Claude (Opus 4.8) | ✨ Feature | **Phase 1 core (File I/O + Canvas)** — commit `d9fbc28`. Backend: pyembroidery read/write, `POST /api/files/parse`, `/export`, `/export/validate`, `/worksheet` (JSON). Frontend: Konva stitch rendering + zoom/pan, live Open/Export .DST, StitchPlayer. Tests: pytest 5/5 + generated `sample.dst`/`.pes` fixtures. Verified end-to-end via the Vite proxy. Remaining in Phase 1: worksheet **PDF** render. |
| 2 | 2026-06-30 | Claude (Opus 4.8) | 📝 Docs | Added the **full project roadmap** (Phases 0–10, §14) and a **pyembroidery-grounded Phase 1 deep-dive** (§15). Committed STATUS.md v1 (`3e34389`) beforehand. No code changes. |
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
| konva | 9.3.22 | 2D canvas engine (**used** — stitch rendering) |
| react-konva | 18.2.16 | React bindings for Konva |
| three | 0.169.0 | WebGL (TrueView 3D — still stub) |
| @react-three/fiber | 8.18.0 | React bindings for Three.js |
| zustand | 5.0.14 | client state (**used** — design + playHead) |
| @tanstack/react-query | 5.101.2 | server state |
| zod | 3.25.76 | runtime schema validation |
| eslint | 8.57.1 | linting (legacy `.eslintrc.cjs`) |

### Backend — `apps/backend` (language: **Python 3.14**)
| Package | Version | Role | Installed? |
|---|---|---|---|
| fastapi | 0.138.2 | API framework | ✅ core |
| uvicorn | 0.49.0 | ASGI server | ✅ core |
| pydantic (+settings) | 2.13.4 / 2.14.2 | data models / env | ✅ core |
| python-multipart | 0.0.32 | file uploads | ✅ core |
| pyembroidery | 1.5.1 | embroidery I/O | ✅ **used** (Phase 1) |
| pytest / httpx | 8.x / 0.27+ | tests | ✅ dev (`requirements-dev.txt`) |
| opencv-python-headless, pillow | ≥4.10 / ≥10.4 | auto-digitizing (Phase 3) | ❌ not installed |
| reportlab | ≥4.2 | worksheet **PDF** (Phase 1 tail) | ❌ **not installed** |
| numpy / scipy | ≥1.26 / ≥1.11 | math / k-d tree | ❌ not installed |
| supabase | ≥2.9 | auth + DB + storage (Phase 6) | ❌ not installed |

> Deps: `requirements.txt` (core, boots app) · `requirements-dev.txt` (pytest) · `requirements-features.txt` (heavy libs, lazy-imported).

---

## 📁 4. Repository Structure

```
EmDesign_Automater/
├── STATUS.md                       ← THIS FILE (state / handoff / roadmap)
├── README.md   AI-Embroidery-Software-Prompt.md (master spec)
├── package.json  package-lock.json  .gitignore  .env.example
├── docs/  ARCHITECTURE.md  DATA-MODEL.md
├── db/    schema.sql               PostgreSQL/Supabase schema (spec §8) — NOT applied
├── apps/
│   ├── frontend/                   TypeScript / React / Vite
│   │   └── src/
│   │       ├── App.tsx  main.tsx  index.css
│   │       ├── types/design.ts             ← shared data model (TS)
│   │       ├── api/client.ts               parse / export / worksheet / validate …
│   │       ├── store/designStore.ts        design + playHead
│   │       ├── lib/units.ts
│   │       └── components/
│   │           ├── toolbar/Toolbar.tsx          Open + Export (live)
│   │           ├── canvas/StitchCanvas.tsx      Konva rendering (live)
│   │           ├── panels/ColorObjectList.tsx   color sequence (live)
│   │           ├── panels/ThreadPalette.tsx     (stub)
│   │           ├── panels/PropertiesPanel.tsx   (stub → Phase 2)
│   │           ├── player/StitchPlayer.tsx      animation (live)
│   │           └── trueview/TrueView3D.tsx      (stub → Phase 7)
│   └── backend/                    Python / FastAPI
│       ├── requirements*.txt  pyproject.toml
│       ├── app/
│       │   ├── main.py  config.py
│       │   ├── models/design.py            ← shared data model (Pydantic)
│       │   ├── routers/  files, export, worksheet (live) · convert, digitize, threads, designs (stub)
│       │   └── services/ embroidery_io (live) · worksheet_pdf (build live, PDF stub) · digitizer, threads (stub)
│       └── tests/  test_embroidery_io.py  make_fixtures.py  fixtures/sample.dst,.pes
└── .venv (gitignored) · node_modules (gitignored)
```

---

## 📊 5. Feature Status Matrix

**Status:** 🔴 Stub · 🟡 In progress / partial · 🟢 Done & verified

### Backend endpoints (under `/api`)
| Endpoint | Method | Status | Behavior | File | Spec |
|---|---|---|---|---|---|
| `/health` | GET | 🟢 Done | `{"status":"ok"}` | `app/main.py` | — |
| `/api/files/parse` | POST | 🟢 **Done** | upload → `Design` (pyembroidery) | `routers/files.py` | §4.8 |
| `/api/export` | POST | 🟢 **Done** | `Design` → streams machine file | `routers/export.py` | §4.8 |
| `/api/export/validate` | POST | 🟢 **Done** | jump/size/long-stitch checks | `routers/export.py` | §4.8 |
| `/api/worksheet` | POST | 🟡 **Partial** | Worksheet **JSON** (PDF TBD) | `routers/worksheet.py` | §4.9 |
| `/api/convert` | POST | 🔴 Stub | 501 | `routers/convert.py` | §4.8 |
| `/api/digitize` | POST | 🔴 Stub | 501 | `routers/digitize.py` | §4.2 |
| `/api/threads`, `/threads/match` | GET/POST | 🔴 Stub | 501 | `routers/threads.py` | §4.4 |
| `/api/designs` (GET/GET id) | GET | 🟡 Partial | in-memory | `routers/designs.py` | §8 |
| `/api/designs` | POST | 🔴 Stub | 501 | `routers/designs.py` | §8 |

### Backend services
| Function | Status | File |
|---|---|---|
| `read_embroidery` / `write_embroidery` | 🟢 **Done** | `services/embroidery_io.py` |
| `build_worksheet` | 🟢 **Done** | `services/worksheet_pdf.py` |
| `render_pdf` | 🔴 Stub (needs reportlab) | `services/worksheet_pdf.py` |
| `digitize_image` | 🔴 Stub | `services/digitizer.py` |
| `nearest_thread` | 🔴 Stub | `services/threads.py` |

### Frontend components
| Component | Status | Notes |
|---|---|---|
| App shell / layout | 🟢 Done | |
| StitchCanvas | 🟢 **Done** | Konva polylines, fit-to-view, zoom/pan, playHead limit |
| Toolbar | 🟡 **Partial** | Open + Export **live**; digitizing tools stub (Phase 2) |
| ColorObjectList | 🟢 **Done** | shows color sequence + swatches |
| StitchPlayer | 🟢 **Done** | play/scrub/reset over stitches |
| designStore (Zustand) | 🟡 Partial | design + playHead; needs edit/undo actions (Phase 2) |
| api client | 🟢 Done | all endpoints incl. `exportDesign` |
| shared types | 🟢 Done | |
| ThreadPalette / PropertiesPanel / TrueView3D | 🔴 Stub | Phase 2 / Phase 7 |

### Infrastructure
| Item | Status | Notes |
|---|---|---|
| Monorepo / npm workspaces · shared data model | 🟢 Done | camelCase-on-wire verified |
| Tests (pytest) | 🟡 **Started** | `test_embroidery_io.py` (5 tests); no frontend tests, no CI |
| DB schema applied · Supabase · Dockerfile/deploy · AI/ML · `.STIQ` | 🔴 Not started | Phases 6/8/X |

---

## 🟢 6. What's DONE (verified)

**Scaffold (Updates #1–2):** monorepo, shared data model (TS ⇄ Pydantic, camelCase verified), FastAPI
app boots on Python 3.14, frontend typecheck/build/dev-serve. Full roadmap + Phase 1 plan documented.

**Phase 1 core (Update #3, commit `d9fbc28`) — each confirmed by running it:**
1. **Parse** — `POST /api/files/parse` decodes a real `.DST`/`.PES` via pyembroidery → `Design`
   (stitches in mm, color stops from `get_as_colorblocks`, dimensions from `bounds`). Verified: 200,
   40×40mm, 2 stops.
2. **Export** — `POST /api/export?format=…` streams a machine file; PES round-trips (threads preserved).
3. **Validate** — `POST /api/export/validate` flags long stitches / oversize / empty.
4. **Worksheet** — `POST /api/worksheet` returns the worksheet **JSON** (color sequence, trims, sew-time estimate).
5. **Canvas render** — `StitchCanvas` draws color-grouped Konva polylines with fit-to-view + zoom/pan.
6. **Upload/Export UI** — Toolbar "Open" parses a file into the store; "Export .DST" downloads.
7. **Stitch player** — play/scrub/reset animates the stitch sequence via `playHead`.
8. **Tests** — pytest 5/5 (parse dims/stops, DST + PES round-trip, unsupported-ext, worksheet) + committed fixtures.
9. **Integration** — upload verified **through the Vite dev proxy** (`:5173` → `:8000`), the real browser path.

---

## 🔴 7. What's REMAINING

Full phased plan in [§14](#-14-full-project-roadmap-phases-010). Immediate:

### A. Phase 1 tail
- **Worksheet PDF** — implement `worksheet_pdf.render_pdf` (ReportLab) + a download endpoint/button.
- (Optional) surface `validate` warnings in the UI before export.

### B. Phase 2 — interactive editing (next big phase)
- Canvas selection ↔ `ColorObjectList`; `PropertiesPanel` bound to a selected object (density,
  underlay, pull-comp — §4.3); `ThreadPalette` load + assign; recolor stops; undo/redo; rulers/grid.
- Note: parsed `.DST`/`.PES` files carry **stitches + color stops but no vector objects**
  (`design.objects` is empty). Object-level editing needs an object model — design it in Phase 2.

### C. Phases 3–10 & cross-cutting
- Auto-digitize (OpenCV, 3) · lettering (4) · full export/convert (5) · Supabase persistence/auth (6) ·
  TrueView 3D (7) · AI engine (8) · generative + assistant (9) · collab/API/mobile (10).
- Cross-cutting: frontend tests + CI, Dockerfiles/deploy, logging, authz/rate-limits.

---

## 🧭 8. Key Decisions & Rationale

| Decision | Why | Reversible? |
|---|---|---|
| **TypeScript** (frontend) + **Python** (backend) | User request; matches spec §7; Python mandatory for pyembroidery/AI libs. | Foundational |
| Build **vertically**, one phase at a time | User scope; full spec is multi-year. | — |
| **Color stops from `get_as_colorblocks`**, not `threadlist` | DST stores no color → `threadlist` empty on read; colorblocks supply filler colors and work for PES too. | Yes |
| Round-trip test asserts on **bounds**, not stitch count | DST writer adds ties/splits long moves → stitch count changes; bounds are the stable invariant. | Yes |
| Worksheet endpoint returns **JSON now**, PDF later | ReportLab is untested on Python 3.14; JSON is dependency-free and unblocks the UI. | Yes |
| **npm workspaces** (not pnpm) · **tiered Python deps** · **single tsconfig** · **ESLint 8** · **lazy heavy imports** | See Updates #1–2 rationale (pnpm absent; py3.14 wheel risk; `TS6310`; stability; boot without heavy libs). | Yes |
| Git commits per logical change (scaffold, docs, phase) | Clean history. Rollback: `git reset --soft HEAD~1`. | Yes |

---

## ⚠️ 9. Environment & Gotchas

- **Python 3.14.3** — very new. `reportlab`/`opencv`/`scipy` **untested**; may lack wheels. Fall back to **3.11–3.12** if `pip install -r requirements-features.txt` fails. Core + pyembroidery + pytest **do** install cleanly (confirmed).
- **DST has no color data** — parsed `.DST` shows filler/auto colors; `.PES` preserves real thread colors. Not a bug.
- **Round-trip stitch count is not stable** (writer normalizes). Compare **bounds**, not counts.
- **pnpm not installed** → use `npm`. **Backend venv** at `apps/backend/.venv` (gitignored).
- **Vite proxies** `/api` + `/health` → `http://localhost:8000` (`vite.config.ts`). Set `VITE_API_BASE_URL` in prod.
- **CORS** allows `http://localhost:5173` only (`app/config.py`). **Supabase** needs the user's keys (nothing wired).
- **Port 8000 hygiene:** kill stray servers with `lsof -ti tcp:8000 | xargs kill -9` before booting (a stale server serving old code causes confusing results).

---

## 🎯 10. Next Steps (do these IN ORDER)

1. **Worksheet PDF** — `services/worksheet_pdf.render_pdf` (ReportLab) + `GET/POST` download; add a "Worksheet" button. *(Install `reportlab`; if it fails on 3.14, use a 3.12 venv.)*
2. **Phase 2 kickoff** — canvas object/stitch **selection** + `PropertiesPanel` binding; `ThreadPalette` load via `api.listThreads` (implement `/api/threads` first: load `data/threads_madeira_sample.json`).
3. **Convert endpoint** — `POST /api/convert` (any→any) using the existing `read_embroidery`/`write_embroidery`.
4. **Frontend tests** — add vitest + a StitchCanvas run-builder unit test.

> After each step: re-run §11 checks and **update this file** (§2 changelog + §5 matrix + metadata).

---

## 🧪 11. How to Run & Verification Baseline

### Run
```bash
# Backend  (from apps/backend)
source .venv/bin/activate && uvicorn app.main:app --reload --port 8000    # /health, /docs
# Frontend (from repo root, new terminal)
npm run dev:frontend                                                       # http://localhost:5173
# Both:  npm run dev
```

### One-time setup on a fresh clone
```bash
npm install
cd apps/backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt   # core + tests (boots + tests)
# pip install -r requirements-features.txt                # heavy libs (Phase 3+/PDF; may need py3.11–3.12)
python tests/make_fixtures.py                             # (re)generate sample.dst/.pes
```

### Verification baseline (last confirmed 2026-06-30, Update #3)
| Check | Command | Expected | Result |
|---|---|---|---|
| Backend tests | `cd apps/backend && python -m pytest tests -q` | 5 passed | ✅ |
| Parse endpoint | `curl -F file=@tests/fixtures/sample.dst localhost:8000/api/files/parse` | 200, Design JSON | ✅ |
| Export round-trip | POST parsed design to `/api/export?format=pes` → re-read | threads preserved | ✅ |
| Validate | POST design to `/api/export/validate` | `passed:true` + warnings | ✅ |
| Upload via **Vite proxy** | `curl -F file=@… localhost:5173/api/files/parse` | 200 (proxied to :8000) | ✅ |
| Frontend typecheck / build | `npm run typecheck` · `npm run build -w apps/frontend` | 0 errors · 280 modules | ✅ |

---

## 🚧 12. Known Risks / Unverified Claims

- **In-browser canvas paint NOT eyeballed.** Typecheck + build + upload-via-proxy all pass, and the
  render logic is straightforward, but no one has opened `:5173` in a browser to confirm the stitches
  actually draw, zoom/pan feels right, and the player animates. **Open it and check** — *most likely to surprise you.*
- **Worksheet PDF, digitize, threads, persistence** are unimplemented — don't assume they work.
- **Feature libs untested on Python 3.14** (reportlab/opencv/scipy) — first install may fail; use 3.11–3.12.
- **DB schema unvalidated** against a live Postgres.

---

## 🧬 13. Data Model Reference

Mirrored in [`apps/frontend/src/types/design.ts`](./apps/frontend/src/types/design.ts) and
[`apps/backend/app/models/design.py`](./apps/backend/app/models/design.py). **Edit both together.**
Full details in [`docs/DATA-MODEL.md`](./docs/DATA-MODEL.md).

Entities: `Stitch` · `StitchType`/`UnderlayType`/`ConnectMethod` enums · `Thread` · `ColorStop` ·
`DesignObject` · `Design` · `Worksheet` · `ValidationReport` · `ConvertRequest`/`ConvertResponse`.
Python's camelCase alias generator makes JSON match the TS interfaces (`width_mm` ⇄ `widthMm`).

---

## 🗺 14. Full Project Roadmap (Phases 0–10)

> **Build vertically.** Sizes are relative complexity, not calendar: **S** hours · **M** 1–2 days · **L** ~a week · **XL** multi-week.
> Every phase: **implement → run/verify → update this file (§2 + §5).**

| Phase | Name | Status | Size | Unlocks |
|---|---|---|---|---|
| 0 | Scaffold | 🟢 Done | — | the codebase |
| **1** | **File I/O + Canvas** | 🟡 **Core done** (PDF left) | L | open/view/export real designs |
| 2 | Interactive editing | ⬜ **Next** | L | select/edit objects, properties, threads |
| 3 | Auto-digitizing v1 (OpenCV) | ⬜ | XL | image → stitches |
| 4 | Lettering & monogramming | ⬜ | L | text → stitches |
| 5 | Production output & formats | ⬜ | M | worksheets, packages, 25+ formats |
| 6 | Persistence & accounts (Supabase) | ⬜ | M | save/load, auth, versions, teams |
| 7 | TrueView 3D simulation | ⬜ | L | realistic preview |
| 8 | AI engine | ⬜ | XL | smart digitizing, path optimization, quality scoring |
| 9 | Generative & assistant | ⬜ | XL | text-to-design, STITCH-GPT, NL editing |
| 10 | Platform & scale | ⬜ | XL | collab, cloud API, mobile, machine monitoring |
| X | Cross-cutting (tests/CI/deploy/security) | 🟡 Ongoing | — | ships everything safely |

### Phase 1 — File I/O + Canvas 🟡 (core done; see [§15](#-15-phase-1-deep-dive--file-io--canvas))
- **Done:** parse, export, validate, worksheet-JSON, Konva render, upload/export UI, stitch player, tests.
- **Left:** worksheet **PDF** (ReportLab); optionally surface validation warnings pre-export.

### Phase 2 — Interactive Editing ⬜ (size L) — *next*
- Canvas hit-test selection ↔ `ColorObjectList`; `PropertiesPanel` bound to the selected object
  (density, stitch angle, underlay, pull-comp — §4.3); `ThreadPalette` load + drag-assign; reorder
  stops; undo/redo (Zustand history); zoom/pan/grid/rulers. Needs a vector **object model** (parsed
  files are stitch-only). **Files:** `components/panels/*`, `store/designStore.ts`, `StitchCanvas`.

### Phase 3 — Auto-Digitizing v1 (OpenCV) ⬜ (XL)
- `digitizer.digitize_image`: quantize colors, segment regions, assign stitch types by size, generate
  fill/satin, order stops, plan paths + trims. Wire `POST /api/digitize` + upload dialog. **Deps:** opencv/numpy/pillow.
- **Honesty:** classical CV is approximate; neural quality is Phase 8. Keep CV as fallback.

### Phase 4 — Lettering ⬜ (L) · Phase 5 — Production output/formats ⬜ (M)
- 4: font glyph → satin/fill lettering with underlay (§4.10). 5: full export package + `/convert` +
  `/export/validate` decision tree + machine-brand format map (§4.8).

### Phase 6 — Persistence & Accounts (Supabase) ⬜ (M)
- Create project, apply `db/schema.sql`, wire auth + `designs` CRUD + Storage + `design_versions`. **User must provide keys.**

### Phase 7 — TrueView 3D ⬜ (L) · Phase 8 — AI engine ⬜ (XL) · Phase 9 — Generative + assistant ⬜ (XL) · Phase 10 — Platform & scale ⬜ (XL)
- 7: 3D thread geometry (§4.7). 8: SAM/CNN/RL + quality scoring + Lab k-d thread match (§4.2/§6). 9: diffusion text-to-design + STITCH-GPT (§4.1/§4.11). 10: collab/cloud API/mobile (§4.12).

### Phase X — Cross-Cutting (start now)
- Tests (pytest ✅ started; add vitest + CI) · Dockerfiles + Vercel/Railway/Fly/Modal deploy (§7) · logging/Sentry · authz, upload limits, rate limiting.

---

## 🔧 15. Phase 1 Deep-Dive — File I/O + Canvas

> **Status:** core **DONE & verified** (Update #3). Tasks 1.1–1.5 + 1.7 implemented; **1.6 worksheet
> PDF render is the remaining tail.** This section documents how it works + the confirmed API.

### pyembroidery API cheat-sheet — CONFIRMED on v1.5.1 / Python 3.14
| Need | API | Notes |
|---|---|---|
| Read a file | `pe.read(filename)` | filename string; we write the upload to a temp file first |
| Stitches | `pattern.stitches` → `[[x, y, cmd_int]]` | coords **1/10 mm** → ÷10 for mm |
| Command ints | `pe.STITCH=0, JUMP=1, TRIM=2, STOP=3, END=4, COLOR_CHANGE=5` | mapped via `pe.*` constants (see `embroidery_io._CMD_TO_STR`) |
| Threads | `pattern.threadlist` (**empty for DST!**) | `.hex_color()`, `.description`, `.catalog_number`, `.brand` |
| Color blocks | `pattern.get_as_colorblocks()` → `(stitch_list, EmbThread)` | **use this for color stops** (works for DST + PES) |
| Extents | `pattern.bounds()` → `(minx,miny,maxx,maxy)` | 1/10 mm → dimensions |
| Counts | `pattern.count_stitches()` | |
| Build/Write | `add_thread`, `add_stitch_absolute(cmd, x×10, y×10)`, `pe.write(pattern, filename)` | mm→tenths = ×10 |

### How it's implemented (files)
- **`services/embroidery_io.py`** — `read_embroidery(bytes, ext)` (temp-file → `pe.read` → `Design`)
  and `write_embroidery(design, ext)` (`Design` → `EmbPattern` → bytes). Command maps + supported-ext guards.
- **`routers/files.py`** `/files/parse` · **`routers/export.py`** `/export` (StreamingResponse) + `/export/validate`
  (long-stitch/size checks) · **`routers/worksheet.py`** `/worksheet` → `worksheet_pdf.build_worksheet`.
- **Frontend:** `StitchCanvas.tsx` (run-builder: STITCH runs → Konva `<Line>`, break on JUMP/TRIM/COLOR_CHANGE;
  fit-to-view + wheel-zoom + drag-pan; `limit` = playHead), `Toolbar.tsx` (Open/Export), `StitchPlayer.tsx`,
  `store/designStore.ts` (`playHead`), `api/client.ts` (`parseFile`, `exportDesign`).

### Remaining task 1.6 — worksheet PDF
- `worksheet_pdf.render_pdf(worksheet) -> bytes` with ReportLab: header, dimensions, color table,
  sequence map (spec §4.9). Add a download route + a "Worksheet" button. **Install `reportlab`** (try
  Python 3.12 if the 3.14 wheel is missing).

### Test fixtures & how to verify
- Fixtures generated by `tests/make_fixtures.py` → `tests/fixtures/sample.dst` + `.pes` (committed; 2-color ~40mm).
- `python -m pytest tests -q` → 5 passing (parse dims/stops, DST + PES round-trip via bounds, unsupported-ext, worksheet).
- Manual: open a fixture in the UI, confirm render + colors, export, re-open, check the color list + player.

---

*End of STATUS.md — keep this file current. When in doubt, trust the code over this document, and fix the document.*
