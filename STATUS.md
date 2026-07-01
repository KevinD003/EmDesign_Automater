# 🧵 STITCHIQ — Project Status & Handoff

> **Single source of truth for project state.** Any model or developer picking up this
> project should read this file first, then [`README.md`](./README.md),
> [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md), and the master spec
> [`AI-Embroidery-Software-Prompt.md`](./AI-Embroidery-Software-Prompt.md).

| Field | Value |
|---|---|
| **Project** | STITCHIQ — AI-powered embroidery design & digitizing platform |
| **Document version** | **v4** |
| **Times updated** | **4** |
| **Last updated** | 2026-06-30 |
| **Current phase** | **Phase 1 COMPLETE ✅** (File I/O + Canvas). **Phase 2 (Interactive Editing) in progress** |
| **Git branch** | `main` |
| **Latest code commit** | `12a18f7` (worksheet PDF + color-stop editing) |
| **Working tree** | clean |
| **Tracked files** | 61 |
| **Location** | `/Users/INDIA/Downloads/EmDesign_Automater` |

---

## 📌 For the next model / session — READ THIS FIRST

1. **Current reality:** Scaffold + **Phase 1 complete** + **Phase 2 started**. Open a real
   `.DST`/`.PES` → render on the Konva canvas → **select a color, recolor it (picker or thread
   swatch)** → export `.DST` → download a **worksheet PDF**. Verified end-to-end (pytest 8/8 +
   Vite proxy). Remaining features are typed stubs — see [§5](#-5-feature-status-matrix).
2. **Chosen scope (by the user):** build **vertically**, one phase at a time ([§14](#-14-full-project-roadmap-phases-010)).
3. **Next task:** continue **Phase 2** — a **vector object model** (parsed files are stitch-only, so
   `design.objects` is empty), on-canvas object selection, undo/redo, rulers/grid. Then Phase 3
   (auto-digitize). See [§14](#-14-full-project-roadmap-phases-010).
4. **⚠️ MANDATORY — every change to this project is logged in THIS FILE.** Before you finish any task:
   - Bump **Document version** + **Times updated**; update **Last updated** + **Latest code commit**.
   - Add a row to [§2 Update History](#-2-update-history--changelog) (**newest on top**).
   - Flip the relevant rows in [§5 Feature Status Matrix](#-5-feature-status-matrix): `🔴` → `🟡` → `🟢`.
   - Move items from [§7 Remaining](#-7-whats-remaining) to [§6 Done](#-6-whats-done-verified); tick the phase in [§14](#-14-full-project-roadmap-phases-010).
   - Commit the doc **with** the code change (or as a `docs:` commit).

---

## 🗂 Table of Contents
1. [TL;DR](#-1-tldr) · 2. [Changelog](#-2-update-history--changelog) · 3. [Tech Stack](#-3-tech-stack-exact-installed-versions) ·
4. [Repo Structure](#-4-repository-structure) · 5. [Feature Status Matrix](#-5-feature-status-matrix) ·
6. [DONE](#-6-whats-done-verified) · 7. [REMAINING](#-7-whats-remaining) · 8. [Decisions](#-8-key-decisions--rationale) ·
9. [Gotchas](#-9-environment--gotchas) · 10. [Next Steps](#-10-next-steps-do-these-in-order) ·
11. [Run & Verify](#-11-how-to-run--verification-baseline) · 12. [Risks](#-12-known-risks--unverified-claims) ·
13. [Data Model](#-13-data-model-reference) · 14. [Roadmap](#-14-full-project-roadmap-phases-010) ·
15. [Phase 1 Deep-Dive](#-15-phase-1-deep-dive--file-io--canvas)

---

## ✅ 1. TL;DR

- **Stack:** TypeScript (React + Vite) frontend · Python (FastAPI) backend · PostgreSQL/Supabase (schema written, not applied).
- **Built:** scaffold **+ Phase 1 (complete)** + **Phase 2 start** — open/parse embroidery files, Konva render, **color-stop select + recolor + thread palette**, export machine files, **worksheet PDF**. Shared typed data model, DB schema, docs.
- **Verified:** backend **pytest 8/8** + all endpoints (TestClient + Vite proxy); frontend **typecheck + build (280 modules)**. *(In-browser interaction not eyeballed — §12.)*
- **Still stubbed:** auto-digitize, thread nearest-match, convert, persistence/auth, AI/ML.
- **Next:** Phase 2 object model + on-canvas selection + undo ([§14](#-14-full-project-roadmap-phases-010)).

---

## 🔄 2. Update History / Changelog

> Add a new row every time the project changes. **Newest at top.**

| # | Date | Author | Type | Summary |
|---|------|--------|------|---------|
| 4 | 2026-06-30 | Claude (Opus 4.8) | ✨ Feature | **Phase 1 tail + Phase 2 start** — commit `12a18f7`. Worksheet **PDF** (ReportLab 5.0.0 on py3.14) + `POST /api/worksheet/pdf`; `GET /api/threads` (catalog). Frontend: color-stop **select/highlight/recolor/rename**, Properties editor, **ThreadPalette**, Worksheet button. pytest **8/8**; verified via Vite proxy. |
| 3 | 2026-06-30 | Claude (Opus 4.8) | ✨ Feature | **Phase 1 core (File I/O + Canvas)** — commit `d9fbc28`. Backend: pyembroidery read/write, `/files/parse`, `/export`, `/export/validate`, `/worksheet` (JSON). Frontend: Konva rendering + zoom/pan, Open/Export, StitchPlayer. pytest 5/5 + fixtures. |
| 2 | 2026-06-30 | Claude (Opus 4.8) | 📝 Docs | Full roadmap (Phases 0–10, §14) + pyembroidery-grounded Phase 1 deep-dive (§15). STATUS.md v1 committed `3e34389`. |
| 1 | 2026-06-30 | Claude (Opus 4.8) | 🏗 Scaffold | Greenfield monorepo scaffold: TS/React + Python/FastAPI, 11 stub endpoints, shared data model, DB schema, docs. Commit `d6a4fd1`. |

**Type legend:** 🏗 Scaffold · ✨ Feature · 🐛 Fix · ♻️ Refactor · 📝 Docs · ⬆️ Deps · 🚀 Deploy

---

## 🧰 3. Tech Stack (exact installed versions)

**Frontend** (`apps/frontend`, **TypeScript**): react/react-dom 18.3.1 · vite 5.4.21 · typescript 5.9.3 ·
konva 9.3.22 + react-konva 18.2.16 (**used**) · three 0.169.0 + @react-three/fiber 8.18.0 (stub) ·
zustand 5.0.14 (**used**) · @tanstack/react-query 5.101.2 (**used** — ThreadPalette) · zod 3.25.76 · eslint 8.57.1.

**Backend** (`apps/backend`, **Python 3.14**):
| Package | Version | Installed? |
|---|---|---|
| fastapi 0.138.2 · uvicorn 0.49.0 · pydantic 2.13.4 (+settings 2.14.2) · python-multipart 0.0.32 | | ✅ core |
| **pyembroidery 1.5.1** · **reportlab 5.0.0** | embroidery I/O · worksheet PDF | ✅ **used** |
| pytest 8.x · httpx · reportlab | tests | ✅ dev (`requirements-dev.txt`) |
| opencv-python-headless · pillow · numpy · scipy · supabase | Phases 3/6/8 | ❌ not installed |

> Deps: `requirements.txt` (core) · `requirements-dev.txt` (pytest + reportlab) · `requirements-features.txt` (heavy libs).

---

## 📁 4. Repository Structure

```
apps/frontend/src/
  App.tsx  main.tsx  index.css
  types/design.ts              ← shared data model (TS)
  api/client.ts                parse · export · exportDesign · worksheet · worksheetPdf · listThreads · validate
  store/designStore.ts         design · selectedStop · playHead · selectStop · updateColorStop
  components/
    toolbar/Toolbar.tsx        Open · Export .DST · Worksheet (all live)
    canvas/StitchCanvas.tsx    Konva render + zoom/pan + stop highlight (live)
    panels/ColorObjectList.tsx selectable color stops (live)
    panels/PropertiesPanel.tsx recolor/rename selected stop (live)
    panels/ThreadPalette.tsx   load catalog + apply to stop (live)
    player/StitchPlayer.tsx    animation (live)
    trueview/TrueView3D.tsx    (stub → Phase 7)
apps/backend/app/
  main.py  config.py  models/design.py   ← shared data model (Pydantic)
  routers/  files · export · worksheet (live) · threads (list live, match stub) · convert · digitize · designs (stub)
  services/ embroidery_io · worksheet_pdf · threads.list_threads (live) · digitizer · threads.nearest_thread (stub)
  data/threads_madeira_sample.json
  tests/ test_embroidery_io.py · test_worksheet.py · make_fixtures.py · fixtures/sample.dst,.pes
db/schema.sql (not applied) · docs/ · README.md · AI-Embroidery-Software-Prompt.md · STATUS.md
```

---

## 📊 5. Feature Status Matrix

**Status:** 🔴 Stub · 🟡 In progress / partial · 🟢 Done & verified

### Backend endpoints (`/api`)
| Endpoint | Status | Behavior | File |
|---|---|---|---|
| `/health` | 🟢 | ok | `main.py` |
| `/files/parse` | 🟢 | upload → `Design` (pyembroidery) | `routers/files.py` |
| `/export` | 🟢 | `Design` → streams machine file | `routers/export.py` |
| `/export/validate` | 🟢 | jump/size/long-stitch checks | `routers/export.py` |
| `/worksheet` · `/worksheet/pdf` | 🟢 | Worksheet **JSON + PDF** | `routers/worksheet.py` |
| `/threads` (GET) | 🟢 | catalog (brand filter) | `routers/threads.py` |
| `/threads/match` (POST) | 🔴 | 501 (Phase 8) | `routers/threads.py` |
| `/convert`, `/digitize`, `/designs` POST | 🔴 | 501 | respective routers |
| `/designs` (GET) | 🟡 | in-memory | `routers/designs.py` |

### Backend services
| Function | Status | File |
|---|---|---|
| `read_embroidery` / `write_embroidery` | 🟢 | `services/embroidery_io.py` |
| `build_worksheet` / `render_pdf` | 🟢 | `services/worksheet_pdf.py` |
| `list_threads` | 🟢 | `services/threads.py` |
| `nearest_thread` · `digitize_image` | 🔴 | `services/threads.py` · `digitizer.py` |

### Frontend components
| Component | Status | Notes |
|---|---|---|
| App shell · api client · shared types | 🟢 | |
| StitchCanvas | 🟢 | polylines, fit-to-view, zoom/pan, playHead, **stop highlight** |
| ColorObjectList | 🟢 | selectable color stops |
| ThreadPalette | 🟢 | loads catalog, applies swatch to selected stop |
| StitchPlayer | 🟢 | play/scrub/reset |
| Toolbar | 🟡 | Open/Export/**Worksheet** live; digitizing tools stub |
| PropertiesPanel | 🟡 | recolor/rename stop ✅; object props (density/underlay) TBD |
| designStore | 🟡 | design · playHead · **selectStop · updateColorStop**; needs undo/object edits |
| TrueView3D | 🔴 | Phase 7 |

### Infrastructure
| Item | Status | Notes |
|---|---|---|
| Monorepo · shared data model | 🟢 | camelCase-on-wire verified |
| Tests (pytest) | 🟡 | **8 tests** (embroidery_io + worksheet/threads); no frontend tests / CI |
| DB applied · Supabase · deploy · AI/ML · `.STIQ` | 🔴 | Phases 6/8/X |

---

## 🟢 6. What's DONE (verified)

**Scaffold + Phase 1 (Updates #1–3):** monorepo, shared data model (TS ⇄ Pydantic), FastAPI on py3.14,
parse/export/validate/worksheet-JSON, Konva render (zoom/pan), Open/Export UI, StitchPlayer, pytest 5/5,
upload verified through the Vite dev proxy (real browser path).

**Phase 1 tail + Phase 2 start (Update #4, commit `12a18f7`) — each confirmed by running it:**
1. **Worksheet PDF** — `POST /api/worksheet/pdf` → valid `%PDF` (ReportLab 5.0.0 on py3.14); "Worksheet" button downloads it.
2. **Threads** — `GET /api/threads` serves the sample catalog (brand filter); `ThreadPalette` loads it (verified via proxy).
3. **Color-stop editing** — select a stop (canvas **highlights** it, dims others), recolor via picker or **thread swatch**, rename.
4. **Tests** — pytest **8/8** (parse, DST+PES round-trip via bounds, unsupported-ext, worksheet totals, **PDF %PDF bytes**, thread catalog).

---

## 🔴 7. What's REMAINING

Full plan in [§14](#-14-full-project-roadmap-phases-010). Immediate:

### A. Phase 2 — interactive editing (IN PROGRESS)
- **Done:** color-stop select/highlight/recolor/rename; ThreadPalette apply.
- **Left:** vector **object model** (parsed `.DST`/`.PES` are **stitch-only** → `design.objects` empty);
  object-level props (density/underlay/angle — §4.3); reorder color stops; **undo/redo** (Zustand history);
  canvas rulers/grid; on-canvas object selection; surface `validate` warnings before export.

### B. Phases 3–10 & cross-cutting
- Auto-digitize (OpenCV, 3) · lettering (4) · full export/convert package (5) · Supabase persistence/auth (6) ·
  TrueView 3D (7) · AI engine + `nearest_thread`/`/threads/match` (8) · generative + assistant (9) · collab/API/mobile (10).
- Cross-cutting: **frontend tests + CI**, Dockerfiles/deploy, logging, authz/upload-limits/rate-limits.

---

## 🧭 8. Key Decisions & Rationale

| Decision | Why |
|---|---|
| **TypeScript** + **Python** | User request; Python mandatory for pyembroidery/reportlab/AI. |
| Build **vertically**, phase by phase | User scope; full spec is multi-year. |
| **Color stops from `get_as_colorblocks`** | DST stores no color → `threadlist` empty; colorblocks give filler colors + work for PES. |
| Round-trip asserts on **bounds**, not stitch count | DST writer adds ties/splits long moves → count changes; bounds stable. |
| **Color stop** is the editable unit (Phase 2 start) | Parsed files are stitch-only (no vector objects yet); stops are what exist to edit. |
| npm workspaces · tiered py deps · single tsconfig · ESLint 8 · lazy heavy imports | See Updates #1–2 (pnpm absent; py3.14 wheel risk; `TS6310`; stability; boot without heavy libs). |

---

## ⚠️ 9. Environment & Gotchas

- **Python 3.14.3** — `pyembroidery`, `reportlab 5.0.0`, `pytest` install clean (**confirmed**). `opencv`/`scipy` still untested; fall back to **3.11** (present) if a wheel is missing.
- **DST has no color** — parsed `.DST` shows filler colors; `.PES` preserves real ones. Recolor via Properties/ThreadPalette.
- **Round-trip stitch count is not stable** (writer normalizes) — compare **bounds**.
- **Parsed files are stitch-only** — `design.objects` is empty; the editable unit is the **color stop** until Phase 2 adds an object model.
- **pnpm not installed** → `npm`. **venv** at `apps/backend/.venv` (gitignored). **Vite proxies** `/api`+`/health` → `:8000`.
- **Port hygiene:** `lsof -ti tcp:8000 | xargs kill -9` before booting (a stale server serving old code causes confusion).

---

## 🎯 10. Next Steps (do these IN ORDER)

1. **Object model (Phase 2 core)** — define how vector objects relate to stitches; populate `design.objects`
   (or a Phase-2 editing layer) so `PropertiesPanel` can edit density/underlay/angle (§4.3).
2. **On-canvas selection** — click a stitch run → select its stop/object (currently selection is list-only).
3. **Undo/redo** — Zustand history around `design` mutations.
4. **Reorder color stops** + surface `validate` warnings pre-export.
5. **Frontend tests** — vitest + a StitchCanvas run-builder unit test; then CI.

> After each step: re-run §11 checks and **update this file** (§2 + §5 + metadata).

---

## 🧪 11. How to Run & Verification Baseline

### Run
```bash
# Backend (apps/backend):  source .venv/bin/activate && uvicorn app.main:app --reload --port 8000
# Frontend (repo root):    npm run dev:frontend           # http://localhost:5173
# Both:                    npm run dev
```
### Fresh-clone setup
```bash
npm install
cd apps/backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt   # core + tests (incl. reportlab)
# pip install -r requirements-features.txt                # heavy libs (Phase 3+; may need py3.11)
python tests/make_fixtures.py                             # (re)generate fixtures
```
### Baseline (last confirmed 2026-06-30, Update #4)
| Check | Command | Expected | Result |
|---|---|---|---|
| Backend tests | `python -m pytest tests -q` | **8 passed** | ✅ |
| Parse / Export / Validate | curl fixture → endpoints | 200; PES round-trips | ✅ |
| Worksheet PDF | POST design → `/api/worksheet/pdf` | 200, `%PDF-` bytes | ✅ |
| Threads | `GET /api/threads` | 200, 5 threads | ✅ |
| Via **Vite proxy** | curl `:5173/api/{threads,worksheet/pdf,files/parse}` | 200 | ✅ |
| Frontend typecheck / build | `npm run typecheck` · `build -w apps/frontend` | 0 errors · 280 modules | ✅ |

---

## 🚧 12. Known Risks / Unverified Claims

- **In-browser interaction NOT eyeballed.** Build + typecheck + all endpoints-via-proxy pass, but no one has
  opened `:5173` to confirm: canvas paints, **clicking a stop highlights it**, the color picker/thread swatch
  **recolors live**, and Open/Export/Worksheet buttons download. **Open it and check** — *most likely to surprise you.*
- **Auto-digitize, `/threads/match`, convert, persistence** unimplemented.
- **opencv/scipy untested on py3.14**; **DB schema unvalidated** against live Postgres.

---

## 🧬 13. Data Model Reference

Mirrored in [`apps/frontend/src/types/design.ts`](./apps/frontend/src/types/design.ts) ⇄
[`apps/backend/app/models/design.py`](./apps/backend/app/models/design.py). **Edit both together.**
Entities: `Stitch` · `StitchType`/`UnderlayType`/`ConnectMethod` · `Thread` · `ColorStop` · `DesignObject` ·
`Design` · `Worksheet` · `ValidationReport` · `Convert*`. camelCase alias makes JSON match TS (`width_mm` ⇄ `widthMm`).

---

## 🗺 14. Full Project Roadmap (Phases 0–10)

> **Build vertically.** Sizes: **S** hours · **M** 1–2 days · **L** ~a week · **XL** multi-week. Every phase: **implement → verify → update this file.**

| Phase | Name | Status | Size | Unlocks |
|---|---|---|---|---|
| 0 | Scaffold | 🟢 Done | — | the codebase |
| 1 | File I/O + Canvas | 🟢 **Done** | L | open/view/export designs + worksheet PDF |
| **2** | **Interactive editing** | 🟡 **In progress** | L | select/recolor ✅ · object model, undo TBD |
| 3 | Auto-digitizing v1 (OpenCV) | ⬜ | XL | image → stitches |
| 4 | Lettering & monogramming | ⬜ | L | text → stitches |
| 5 | Production output & formats | ⬜ | M | export packages, convert, 25+ formats |
| 6 | Persistence & accounts (Supabase) | ⬜ | M | save/load, auth, versions, teams |
| 7 | TrueView 3D simulation | ⬜ | L | realistic preview |
| 8 | AI engine (+ thread match) | ⬜ | XL | smart digitizing, path opt, quality scoring |
| 9 | Generative & assistant | ⬜ | XL | text-to-design, STITCH-GPT |
| 10 | Platform & scale | ⬜ | XL | collab, cloud API, mobile |
| X | Cross-cutting (tests/CI/deploy/security) | 🟡 Ongoing | — | ships everything safely |

### Phase 1 — File I/O + Canvas 🟢 DONE (see [§15](#-15-phase-1-deep-dive--file-io--canvas))
Parse, export, validate, worksheet JSON **+ PDF**, Konva render, upload/export/worksheet UI, stitch player, tests.

### Phase 2 — Interactive Editing 🟡 IN PROGRESS (size L)
- **Done:** color-stop selection ↔ canvas highlight; recolor/rename via Properties; `ThreadPalette` apply.
- **Left:** vector **object model** (parsed files are stitch-only → `design.objects` empty); object props
  (density/underlay/angle — §4.3); reorder stops; undo/redo; on-canvas selection; rulers/grid.
  **Files:** `components/panels/*`, `store/designStore.ts`, `StitchCanvas`.

### Phase 3 — Auto-Digitizing v1 (OpenCV) ⬜ (XL)
- `digitizer.digitize_image`: quantize colors, segment regions, assign stitch types by size, generate
  fill/satin, order stops, plan paths + trims. Wire `POST /api/digitize` + upload dialog. **Deps:** opencv/numpy/pillow.
  Classical CV is approximate (neural is Phase 8); keep as fallback.

### Phases 4–10 (summaries)
- **4 Lettering:** font glyph → satin/fill + underlay (§4.10). **5 Production:** full export package + `/convert`
  + brand format map (§4.8). **6 Supabase:** apply `db/schema.sql`, auth, `designs` CRUD + Storage (**needs user keys**).
  **7 TrueView 3D:** thread geometry (§4.7). **8 AI:** SAM/CNN/RL + quality scoring + Lab k-d thread match (§4.2/§6).
  **9 Generative:** diffusion text-to-design + STITCH-GPT (§4.1/§4.11). **10 Platform:** collab/cloud API/mobile (§4.12).

### Phase X — Cross-Cutting (start now)
- Tests (pytest ✅; add vitest + CI) · Dockerfiles + Vercel/Railway/Fly/Modal deploy (§7) · logging/Sentry · authz, upload limits, rate limiting.

---

## 🔧 15. Phase 1 Deep-Dive — File I/O + Canvas

> **Status: 🟢 DONE & verified** (Updates #3–4). Kept as reference for how file I/O works.

### pyembroidery API cheat-sheet — CONFIRMED on v1.5.1 / Python 3.14
| Need | API | Notes |
|---|---|---|
| Read | `pe.read(filename)` | write the upload to a temp file first |
| Stitches | `pattern.stitches` → `[[x,y,cmd_int]]` | **1/10 mm** → ÷10 for mm |
| Commands | `pe.STITCH=0 JUMP=1 TRIM=2 STOP=3 END=4 COLOR_CHANGE=5` | map via `pe.*` (see `embroidery_io._CMD_TO_STR`) |
| Threads | `pattern.threadlist` (**empty for DST**) | `.hex_color()`, `.description`, `.catalog_number`, `.brand` |
| Color blocks | `pattern.get_as_colorblocks()` → `(stitches, thread)` | **use this for color stops** (DST + PES) |
| Extents / count | `pattern.bounds()` · `count_stitches()` | dimensions / stitch count |
| Write | `add_thread`, `add_stitch_absolute(cmd, x×10, y×10)`, `pe.write(pattern, filename)` | mm→tenths ×10 |

### Implemented in
- `services/embroidery_io.py` (`read_embroidery`/`write_embroidery`), `services/worksheet_pdf.py`
  (`build_worksheet`/`render_pdf`), `services/threads.py` (`list_threads`).
- Routers `files`, `export`, `worksheet`, `threads`. Frontend `StitchCanvas`, `Toolbar`, `StitchPlayer`,
  `ColorObjectList`, `PropertiesPanel`, `ThreadPalette`, `store/designStore`, `api/client`.

### Verify
`python -m pytest tests -q` → **8 passing**. Manual: open `apps/backend/tests/fixtures/sample.dst` in the UI,
confirm render + colors, click a stop (highlights), recolor it, Export, Worksheet (PDF).

---

*End of STATUS.md — keep this file current. When in doubt, trust the code over this document, and fix the document.*
