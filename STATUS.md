# 🧵 STITCHIQ — Project Status & Handoff

> **Single source of truth for project state.** Read this first, then [`README.md`](./README.md),
> [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md), and the master spec
> [`AI-Embroidery-Software-Prompt.md`](./AI-Embroidery-Software-Prompt.md).

| Field | Value |
|---|---|
| **Project** | STITCHIQ — AI-powered embroidery design & digitizing platform |
| **Document version** | **v5** |
| **Times updated** | **5** |
| **Last updated** | 2026-07-01 |
| **Current phase** | **Phase 2 (Interactive Editing) — progressing.** Selection, recolor, undo/redo done |
| **Git branch** | `main` |
| **Latest code commit** | `05117e9` (on-canvas selection + undo/redo + tests) |
| **Working tree** | clean |
| **Tracked files** | 65 |
| **Location** | `/Users/INDIA/Downloads/EmDesign_Automater` |

---

## 📌 For the next model / session — READ THIS FIRST

1. **Current reality:** Scaffold + **Phase 1 complete** + **Phase 2 progressing**. Open a real
   `.DST`/`.PES` → render → **click a color on the canvas to select it** → recolor (picker/thread
   swatch) → **undo/redo** → export `.DST` → **worksheet PDF**. Verified: pytest 8/8, **vitest 13/13**,
   Vite proxy. Remaining features are typed stubs — see [§5](#-5-feature-status-matrix).
2. **Chosen scope (by the user):** build **vertically**, one phase at a time ([§14](#-14-full-project-roadmap-phases-010)).
3. **Next task:** **reorder color stops** (finishes Phase 2 for stitch files), then **Phase 3
   (auto-digitize)** — the real **vector object model** arrives with the digitizer, since parsed
   files are stitch-only (`design.objects` empty). See [§14](#-14-full-project-roadmap-phases-010).
4. **⚠️ MANDATORY — every change is logged in THIS FILE.** Before finishing any task: bump
   **Document version** + **Times updated**; update **Last updated** + **Latest code commit**; add a
   [§2](#-2-update-history--changelog) row (**newest on top**); flip [§5](#-5-feature-status-matrix)
   rows (`🔴`→`🟡`→`🟢`); move [§7](#-7-whats-remaining)→[§6](#-6-whats-done-verified); tick the phase
   in [§14](#-14-full-project-roadmap-phases-010); commit the doc with the code.

---

## 🗂 Table of Contents
1. [TL;DR](#-1-tldr) · 2. [Changelog](#-2-update-history--changelog) · 3. [Tech Stack](#-3-tech-stack-exact-installed-versions) ·
4. [Repo](#-4-repository-structure) · 5. [Feature Matrix](#-5-feature-status-matrix) · 6. [DONE](#-6-whats-done-verified) ·
7. [REMAINING](#-7-whats-remaining) · 8. [Decisions](#-8-key-decisions--rationale) · 9. [Gotchas](#-9-environment--gotchas) ·
10. [Next Steps](#-10-next-steps-do-these-in-order) · 11. [Run & Verify](#-11-how-to-run--verification-baseline) ·
12. [Risks](#-12-known-risks--unverified-claims) · 13. [Data Model](#-13-data-model-reference) ·
14. [Roadmap](#-14-full-project-roadmap-phases-010) · 15. [Phase 1 Deep-Dive](#-15-phase-1-deep-dive--file-io--canvas)

---

## ✅ 1. TL;DR

- **Stack:** TypeScript (React + Vite) frontend · Python (FastAPI) backend · PostgreSQL/Supabase (schema written, not applied).
- **Built:** scaffold **+ Phase 1 (complete)** + **Phase 2 (progressing)** — open/parse files, Konva render, **click-to-select + recolor + thread palette + undo/redo**, export machine files, **worksheet PDF**. Shared typed data model, DB schema, docs.
- **Verified:** backend **pytest 8/8**; frontend **vitest 13/13** (editing logic) + typecheck + build (281 modules); all endpoints via TestClient + Vite proxy.
- **Still stubbed:** auto-digitize, thread nearest-match, convert, persistence/auth, AI/ML.
- **Next:** reorder stops → Phase 3 auto-digitize (the vector object model comes with it). *(In-browser click/keyboard wiring not eyeballed — §12.)*

---

## 🔄 2. Update History / Changelog

> Add a new row every time the project changes. **Newest at top.**

| # | Date | Author | Type | Summary |
|---|------|--------|------|---------|
| 5 | 2026-07-01 | Claude (Opus 4.8) | ✨ Feature | **Phase 2: on-canvas selection + undo/redo + frontend tests** — commit `05117e9`. Click a run → select its stop; Toolbar ↶/↷ + Ctrl/Cmd+Z shortcuts; extracted pure `buildRuns`/`computeBounds` → `lib/stitches.ts`. **vitest 13/13** (run-builder, units, store undo/redo) — editing logic now unit-tested. |
| 4 | 2026-06-30 | Claude (Opus 4.8) | ✨ Feature | **Phase 1 tail + Phase 2 start** — commit `12a18f7`. Worksheet **PDF** (ReportLab 5.0.0) + `/worksheet/pdf`; `GET /threads`. Frontend: color-stop select/highlight/recolor/rename, ThreadPalette, Worksheet button. pytest 8/8. |
| 3 | 2026-06-30 | Claude (Opus 4.8) | ✨ Feature | **Phase 1 core (File I/O + Canvas)** — commit `d9fbc28`. pyembroidery read/write, `/files/parse` `/export` `/export/validate` `/worksheet`; Konva render, Open/Export, StitchPlayer. pytest 5/5. |
| 2 | 2026-06-30 | Claude (Opus 4.8) | 📝 Docs | Full roadmap (§14) + pyembroidery-grounded Phase 1 deep-dive (§15). STATUS.md v1 `3e34389`. |
| 1 | 2026-06-30 | Claude (Opus 4.8) | 🏗 Scaffold | Greenfield monorepo: TS/React + Python/FastAPI, 11 stub endpoints, shared data model, DB schema, docs. `d6a4fd1`. |

**Type legend:** 🏗 Scaffold · ✨ Feature · 🐛 Fix · ♻️ Refactor · 📝 Docs · ⬆️ Deps · 🚀 Deploy

---

## 🧰 3. Tech Stack (exact installed versions)

**Frontend** (`apps/frontend`, **TypeScript**): react/react-dom 18.3.1 · vite 5.4.21 · typescript 5.9.3 ·
konva 9.3.22 + react-konva 18.2.16 (**used**) · three 0.169 + @react-three/fiber 8.18 (stub) · zustand 5.0.14 ·
@tanstack/react-query 5.101.2 · zod 3.25.76 · eslint 8.57.1 · **vitest 2.1.9** (13 tests).

**Backend** (`apps/backend`, **Python 3.14**):
| Package | Role | Installed? |
|---|---|---|
| fastapi 0.138.2 · uvicorn 0.49.0 · pydantic 2.13.4 (+settings) · python-multipart | core | ✅ |
| **pyembroidery 1.5.1** · **reportlab 5.0.0** | embroidery I/O · worksheet PDF | ✅ used |
| pytest 8.x · httpx · reportlab | tests | ✅ dev (`requirements-dev.txt`) |
| opencv-python-headless · pillow · numpy · scipy · supabase | Phases 3/6/8 | ❌ not installed |

> Deps: `requirements.txt` (core) · `requirements-dev.txt` (pytest + reportlab) · `requirements-features.txt` (heavy libs).

---

## 📁 4. Repository Structure

```
apps/frontend/src/
  App.tsx (+ undo/redo shortcuts)  main.tsx  index.css
  types/design.ts                shared data model (TS)
  lib/stitches.ts                pure buildRuns / computeBounds (unit-tested)
  lib/units.ts                   mm↔px helpers (unit-tested)
  api/client.ts                  parse · export · worksheetPdf · listThreads · validate
  store/designStore.ts           design · selectedStop · playHead · updateColorStop · undo/redo (unit-tested)
  components/
    toolbar/Toolbar.tsx          Open · Export · Worksheet · Undo/Redo (live)
    canvas/StitchCanvas.tsx      Konva render + zoom/pan + click-to-select (live)
    panels/ColorObjectList.tsx · PropertiesPanel.tsx · ThreadPalette.tsx   (live)
    player/StitchPlayer.tsx (live) · trueview/TrueView3D.tsx (stub)
  {lib,store}/*.test.ts          vitest (13 tests)
apps/backend/app/
  main.py  config.py  models/design.py            shared data model (Pydantic)
  routers/  files · export · worksheet · threads(list) (live) · convert · digitize · designs · threads/match (stub)
  services/ embroidery_io · worksheet_pdf · threads.list_threads (live) · digitizer · nearest_thread (stub)
  tests/ test_embroidery_io.py · test_worksheet.py · make_fixtures.py · fixtures/sample.dst,.pes
db/schema.sql (not applied) · docs/ · STATUS.md · README.md · AI-Embroidery-Software-Prompt.md
```

---

## 📊 5. Feature Status Matrix

**Status:** 🔴 Stub · 🟡 In progress / partial · 🟢 Done & verified

### Backend endpoints (`/api`)
| Endpoint | Status | Behavior |
|---|---|---|
| `/health` · `/files/parse` · `/export` · `/export/validate` | 🟢 | ok · parse → Design · stream file · checks |
| `/worksheet` · `/worksheet/pdf` | 🟢 | Worksheet **JSON + PDF** |
| `/threads` (GET) | 🟢 | catalog (brand filter) |
| `/threads/match` · `/convert` · `/digitize` · `/designs` POST | 🔴 | 501 |
| `/designs` (GET) | 🟡 | in-memory |

### Backend services
| Function | Status |
|---|---|
| `read_embroidery`/`write_embroidery` · `build_worksheet`/`render_pdf` · `list_threads` | 🟢 |
| `nearest_thread` · `digitize_image` | 🔴 |

### Frontend components
| Component | Status | Notes |
|---|---|---|
| App shell · api client · types · lib/stitches · lib/units | 🟢 | pure libs unit-tested |
| StitchCanvas | 🟢 | polylines (pure `buildRuns`), fit-to-view, zoom/pan, playHead, **click-to-select** |
| ColorObjectList · ThreadPalette · StitchPlayer | 🟢 | select · apply swatch · animate |
| designStore | 🟢 | design · playHead · selectStop · updateColorStop · **undo/redo** |
| Toolbar | 🟡 | Open/Export/Worksheet/**Undo/Redo** live; digitizing tools stub |
| PropertiesPanel | 🟡 | recolor/rename stop ✅; object props (density/underlay) TBD |
| TrueView3D | 🔴 | Phase 7 |

### Infrastructure
| Item | Status | Notes |
|---|---|---|
| Monorepo · shared data model | 🟢 | camelCase-on-wire verified |
| Tests | 🟡 | **pytest 8 + vitest 13**; no CI yet |
| DB applied · Supabase · deploy · AI/ML · `.STIQ` | 🔴 | Phases 6/8/X |

---

## 🟢 6. What's DONE (verified)

**Scaffold + Phase 1 + Phase 1-tail (Updates #1–4):** monorepo, shared data model (TS ⇄ Pydantic),
FastAPI on py3.14, parse/export/validate/worksheet(JSON+**PDF**), Konva render, Open/Export/Worksheet UI,
StitchPlayer, color-stop recolor + ThreadPalette, pytest 8/8, upload verified via the Vite proxy.

**Phase 2 progress (Update #5, commit `05117e9`) — each confirmed by running it:**
1. **On-canvas selection** — click a stitch run → its color stop selects & highlights (others dim); click empty → deselect.
2. **Undo/redo** — Zustand history (`past`/`future`) + Toolbar ↶/↷ + Ctrl/Cmd+Z / Ctrl+Shift+Z / Ctrl+Y.
3. **Pure, tested render logic** — `buildRuns`/`computeBounds` extracted to `lib/stitches.ts`.
4. **Frontend tests** — **vitest 13/13** (run-builder split/limit/fallback, bounds, units, store recolor + undo/redo).

---

## 🔴 7. What's REMAINING

Full plan in [§14](#-14-full-project-roadmap-phases-010). Immediate:

### A. Phase 2 — interactive editing (IN PROGRESS)
- **Done:** color-stop select (list + **on-canvas click**), highlight, recolor/rename, ThreadPalette apply, **undo/redo**.
- **Left:** **reorder color stops** (re-sequence the stitch blocks + renumber); canvas rulers/grid; surface
  `validate` warnings pre-export. The vector **object model** + object props (density/underlay/angle — §4.3)
  come with the **digitizer (Phase 3)** — parsed files are stitch-only (`design.objects` empty).

### B. Phases 3–10 & cross-cutting
- Auto-digitize (OpenCV, 3) · lettering (4) · export/convert package (5) · Supabase persistence/auth (6) ·
  TrueView 3D (7) · AI engine + `nearest_thread` (8) · generative + assistant (9) · collab/API/mobile (10).
- Cross-cutting: **CI** (run pytest + vitest), Dockerfiles/deploy, logging, authz/upload-limits/rate-limits.

---

## 🧭 8. Key Decisions & Rationale

| Decision | Why |
|---|---|
| **TypeScript** + **Python** | User request; Python mandatory for pyembroidery/reportlab/AI. |
| Build **vertically**, phase by phase | User scope; full spec is multi-year. |
| **Color stop** is the editable unit (Phase 2) | Parsed files are stitch-only (no vector objects yet). Object model waits for the digitizer (Phase 3) that produces objects with real params — not fabricated onto imported stitches. |
| **Color stops from `get_as_colorblocks`** | DST stores no color → `threadlist` empty; colorblocks give filler + work for PES. |
| Round-trip asserts on **bounds**, not stitch count | DST writer adds ties/splits → count changes; bounds stable. |
| Pure `buildRuns` extracted from `StitchCanvas` | Makes the render/selection logic **unit-testable** without a browser. |
| npm workspaces · tiered py deps · single tsconfig · ESLint 8 · lazy heavy imports | See Updates #1–2. |

---

## ⚠️ 9. Environment & Gotchas

- **Python 3.14.3** — `pyembroidery`, `reportlab 5.0.0`, `pytest` install clean (**confirmed**). `opencv`/`scipy` untested; fall back to **3.11** (present) if a wheel is missing.
- **DST has no color** — parsed `.DST` shows filler colors; `.PES` preserves real ones. Recolor via Properties/ThreadPalette.
- **Round-trip stitch count is not stable** (writer normalizes) — compare **bounds**.
- **Parsed files are stitch-only** — `design.objects` is empty; the editable unit is the **color stop** until the digitizer (Phase 3) creates objects.
- **pnpm not installed** → `npm`. **venv** at `apps/backend/.venv` (gitignored). **Vite proxies** `/api`+`/health` → `:8000`.
- **Port hygiene:** `lsof -ti tcp:8000 | xargs kill -9` before booting (a stale server serving old code causes confusion).

---

## 🎯 10. Next Steps (do these IN ORDER)

1. **Reorder color stops** — up/down re-sequences the stitch blocks + renumbers stops (finishes Phase 2 for stitch files).
2. **Surface `validate` warnings** in the UI before export; add canvas rulers/grid.
3. **Phase 3 — auto-digitize** (OpenCV): image → regions → stitch types → `Design` **with objects** — this is
   where the vector object model + `PropertiesPanel` density/underlay editing become real. **Deps:** opencv/numpy/pillow.
4. **CI** — GitHub Actions running `pytest` + `vitest` + typecheck on push.

> After each step: re-run §11 checks and **update this file** (§2 + §5 + metadata).

---

## 🧪 11. How to Run & Verification Baseline

### Run
```bash
# Backend (apps/backend):  source .venv/bin/activate && uvicorn app.main:app --reload --port 8000
# Frontend (repo root):    npm run dev:frontend           # http://localhost:5173   ·   Both: npm run dev
```
### Fresh-clone setup
```bash
npm install
cd apps/backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt   # core + tests (incl. reportlab)
python tests/make_fixtures.py                             # (re)generate fixtures
```
### Baseline (last confirmed 2026-07-01, Update #5)
| Check | Command | Expected | Result |
|---|---|---|---|
| Backend tests | `cd apps/backend && python -m pytest tests -q` | **8 passed** | ✅ |
| Frontend tests | `npm test -w apps/frontend` | **vitest 13 passed** | ✅ |
| Parse / Export / Validate / Worksheet PDF / Threads | curl fixture → endpoints | 200; PES round-trips; `%PDF-`; 5 threads | ✅ |
| Via **Vite proxy** | `:5173/api/{files/parse,worksheet/pdf,threads}` | 200 | ✅ |
| Frontend typecheck / build | `npm run typecheck` · `build -w apps/frontend` | 0 errors · **281 modules** | ✅ |

---

## 🚧 12. Known Risks / Unverified Claims

- **In-browser event wiring NOT eyeballed** (narrower now — the pure logic is vitest-tested): canvas paint,
  **clicking a run to select**, live recolor, **Undo/Redo buttons + Ctrl+Z**, and Open/Export/Worksheet downloads.
  Open `:5173`, load `apps/backend/tests/fixtures/sample.dst`, and confirm. *(Logic tested; Konva/DOM events not.)*
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
| 1 | File I/O + Canvas | 🟢 Done | L | open/view/export designs + worksheet PDF |
| **2** | **Interactive editing** | 🟡 **In progress** | L | select (canvas) + recolor + undo/redo ✅ · reorder TBD |
| 3 | Auto-digitizing v1 (OpenCV) | ⬜ **Next** | XL | image → stitches (+ real object model) |
| 4 | Lettering & monogramming | ⬜ | L | text → stitches |
| 5 | Production output & formats | ⬜ | M | export packages, convert, 25+ formats |
| 6 | Persistence & accounts (Supabase) | ⬜ | M | save/load, auth, versions, teams |
| 7 | TrueView 3D simulation | ⬜ | L | realistic preview |
| 8 | AI engine (+ thread match) | ⬜ | XL | smart digitizing, path opt, quality scoring |
| 9 | Generative & assistant | ⬜ | XL | text-to-design, STITCH-GPT |
| 10 | Platform & scale | ⬜ | XL | collab, cloud API, mobile |
| X | Cross-cutting (tests/CI/deploy/security) | 🟡 Ongoing | — | ships everything safely |

### Phase 2 — Interactive Editing 🟡 IN PROGRESS (size L)
- **Done:** color-stop selection (list + **on-canvas click**) ↔ highlight; recolor/rename; `ThreadPalette` apply;
  **undo/redo** (+ shortcuts); pure `buildRuns` extracted & unit-tested.
- **Left:** reorder stops; rulers/grid; surface validate warnings. Vector **object model** + object props
  (density/underlay/angle — §4.3) move to **Phase 3** (they need a source that produces objects).
  **Files:** `store/designStore.ts`, `StitchCanvas`, `lib/stitches.ts`.

### Phase 3 — Auto-Digitizing v1 (OpenCV) ⬜ (XL) — *next*
- `digitizer.digitize_image`: quantize colors, segment regions, assign stitch types by size, generate fill/satin,
  order stops, plan paths + trims → a `Design` **with `objects`** (unblocks object-level PropertiesPanel editing).
  Wire `POST /api/digitize` + upload dialog. **Deps:** opencv/numpy/pillow. Classical CV is approximate (neural = Phase 8); keep as fallback.

### Phases 4–10 (summaries)
- **4 Lettering:** glyph → satin/fill + underlay (§4.10). **5 Production:** export package + `/convert` + brand map (§4.8).
  **6 Supabase:** apply `db/schema.sql`, auth, CRUD + Storage (**needs user keys**). **7 TrueView 3D:** thread geometry (§4.7).
  **8 AI:** SAM/CNN/RL + quality scoring + Lab k-d thread match (§4.2/§6). **9 Generative:** diffusion + STITCH-GPT (§4.1/§4.11).
  **10 Platform:** collab/cloud API/mobile (§4.12).

### Phase X — Cross-Cutting (start now)
- Tests (pytest ✅ + vitest ✅; add **CI**) · Dockerfiles + Vercel/Railway/Fly/Modal deploy (§7) · logging/Sentry · authz, upload limits, rate limiting.

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
| Color blocks | `pattern.get_as_colorblocks()` → `(stitches, thread)` | **use for color stops** (DST + PES) |
| Extents / count | `pattern.bounds()` · `count_stitches()` | dimensions / count |
| Write | `add_thread`, `add_stitch_absolute(cmd, x×10, y×10)`, `pe.write(pattern, filename)` | mm→tenths ×10 |

Implemented in `services/embroidery_io.py`, `worksheet_pdf.py`, `threads.py`; routers `files`/`export`/`worksheet`/`threads`;
frontend `StitchCanvas`, `lib/stitches.ts`, `Toolbar`, `StitchPlayer`, panels, `store/designStore`, `api/client`.
Verify: `pytest -q` (8) + `npm test` (13). Manual: open `tests/fixtures/sample.dst`, click a stop, recolor, undo, Export, Worksheet.

---

*End of STATUS.md — keep this file current. When in doubt, trust the code over this document, and fix the document.*
