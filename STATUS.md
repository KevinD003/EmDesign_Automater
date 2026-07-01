# 🧵 STITCHIQ — Project Status & Handoff

> **Single source of truth for project state.** Read this first, then [`README.md`](./README.md),
> [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md), and the master spec
> [`AI-Embroidery-Software-Prompt.md`](./AI-Embroidery-Software-Prompt.md).

| Field | Value |
|---|---|
| **Project** | STITCHIQ — AI-powered embroidery design & digitizing platform |
| **Document version** | **v7** |
| **Times updated** | **7** |
| **Last updated** | 2026-07-01 |
| **Current phase** | **Phase 3 (auto-digitize) core done** — classical CV v1 shipped. Phases 1–2 complete |
| **Git branch** | `main` |
| **Latest code commit** | `9eed902` (auto-digitize v1) |
| **Working tree** | clean |
| **Tracked files** | 66 |
| **Location** | `/Users/INDIA/Downloads/EmDesign_Automater` |

---

## 📌 For the next model / session — READ THIS FIRST

1. **Current reality:** The app is a working (minimal) embroidery studio. Two input paths:
   **Open** a real `.DST`/`.PES` **or Digitize a PNG/JPG image** (classical OpenCV → stitches +
   **real vector objects**). Then: render → click-to-select → recolor/rename/reorder → undo/redo →
   export `.DST` → worksheet PDF. Verified: **pytest 13/13, vitest 18/18**, e2e via Vite proxy.
2. **Chosen scope (by the user):** build **vertically**, one phase at a time ([§14](#-14-full-project-roadmap-phases-010)).
3. **Next task (pick one):** (a) **Phase 3 polish** — digitize params dialog (fabric/hoop/max colors),
   object-level PropertiesPanel editing (digitized designs now HAVE objects), satin detection for
   narrow regions; (b) **Phase 4 lettering**; or (c) **Phase X CI** (GitHub Actions: pytest+vitest+tsc).
4. **⚠️ MANDATORY — every change is logged in THIS FILE.** Before finishing any task: bump **Document
   version** + **Times updated**; update **Last updated** + **Latest code commit**; add a
   [§2](#-2-update-history--changelog) row (**newest on top**); flip [§5](#-5-feature-status-matrix) rows;
   move [§7](#-7-whats-remaining)→[§6](#-6-whats-done-verified); tick [§14](#-14-full-project-roadmap-phases-010);
   commit the doc with the code.

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
- **Built:** Phases 0–2 complete + **Phase 3 core**: file open/parse, **image auto-digitize (OpenCV k-means → contour regions → scanline fills → Design with objects)**, Konva render, full color-stop editing (select/recolor/rename/reorder/undo), export machine files, worksheet PDF.
- **Verified:** **pytest 13/13** · **vitest 18/18** · typecheck/build · e2e PNG→digitize→DST-export through the Vite proxy.
- **Still stubbed:** thread nearest-match, convert endpoint, persistence/auth, lettering, TrueView 3D, AI/ML.
- **Next:** Phase 3 polish (params dialog, object props editing, satin) / Phase 4 lettering / CI. *(In-browser event wiring not eyeballed — §12.)*

---

## 🔄 2. Update History / Changelog

> Add a new row every time the project changes. **Newest at top.**

| # | Date | Author | Type | Summary |
|---|------|--------|------|---------|
| 7 | 2026-07-01 | Claude (Opus 4.8) | ✨ Feature | **Phase 3 core: auto-digitize v1** — commit `9eed902`. OpenCV pipeline (k-means quantize → background drop → contour regions → boustrophedon fills) → `Design` with **real objects** + darkest-first stops; `POST /api/digitize` + Toolbar **Digitize** button. cv2 4.13/numpy 2.5/pillow 12.2 work on py3.14. **pytest 13/13** (+5); e2e PNG→DST verified via proxy. |
| 6 | 2026-07-01 | Claude (Opus 4.8) | ✨ Feature | **Phase 2: reorder color stops** — `dfe8901`. Pure `reorderColorStop` + store + ▲▼ UI. vitest 18/18. |
| 5 | 2026-07-01 | Claude (Opus 4.8) | ✨ Feature | **Phase 2: on-canvas selection + undo/redo + vitest** — `05117e9`. vitest 13/13. |
| 4 | 2026-06-30 | Claude (Opus 4.8) | ✨ Feature | **Phase 1 tail + Phase 2 start** — `12a18f7`. Worksheet PDF; threads catalog; recolor/rename + ThreadPalette. pytest 8/8. |
| 3 | 2026-06-30 | Claude (Opus 4.8) | ✨ Feature | **Phase 1 core** — `d9fbc28`. pyembroidery I/O, parse/export/validate/worksheet; Konva render; StitchPlayer. pytest 5/5. |
| 2 | 2026-06-30 | Claude (Opus 4.8) | 📝 Docs | Roadmap (§14) + Phase 1 deep-dive (§15). STATUS v1 `3e34389`. |
| 1 | 2026-06-30 | Claude (Opus 4.8) | 🏗 Scaffold | Greenfield monorepo. `d6a4fd1`. |

**Type legend:** 🏗 Scaffold · ✨ Feature · 🐛 Fix · ♻️ Refactor · 📝 Docs · ⬆️ Deps · 🚀 Deploy

---

## 🧰 3. Tech Stack (exact installed versions)

**Frontend** (`apps/frontend`, **TypeScript**): react/react-dom 18.3.1 · vite 5.4.21 · typescript 5.9.3 ·
konva 9.3.22 + react-konva 18.2.16 · three 0.169 + @react-three/fiber 8.18 (stub) · zustand 5.0.14 ·
@tanstack/react-query 5.101.2 · zod 3.25.76 · eslint 8.57.1 · **vitest 2.1.9** (18 tests).

**Backend** (`apps/backend`, **Python 3.14**):
| Package | Role | Installed? |
|---|---|---|
| fastapi 0.138.2 · uvicorn 0.49.0 · pydantic 2.13.4 (+settings) · python-multipart | core | ✅ |
| **pyembroidery 1.5.1** · **reportlab 5.0.0** | embroidery I/O · worksheet PDF | ✅ used |
| **opencv-python-headless 4.13.0 · numpy 2.5.0 · pillow 12.2.0** | **auto-digitize (Phase 3)** | ✅ **used — confirmed on py3.14** |
| pytest 8.x · httpx | tests | ✅ dev |
| scipy · supabase | Phases 8/6 | ❌ not installed |

> Deps: `requirements.txt` (core) · `requirements-dev.txt` (tests + reportlab + opencv/numpy/pillow) · `requirements-features.txt` (remaining heavy libs).

---

## 📁 4. Repository Structure

```
apps/frontend/src/
  App.tsx (+ undo/redo shortcuts)  main.tsx  index.css
  types/design.ts                shared data model (TS)
  lib/stitches.ts                pure buildRuns / computeBounds / reorderColorStop (unit-tested)
  lib/units.ts                   mm↔px helpers (unit-tested)
  api/client.ts                  parse · digitize · export · worksheetPdf · listThreads · validate
  store/designStore.ts           design · selectedStop · playHead · updateColorStop · reorderStop · undo/redo
  components/
    toolbar/Toolbar.tsx          Open · Digitize · Export · Worksheet · Undo/Redo (live)
    canvas/StitchCanvas.tsx      Konva render + zoom/pan + click-to-select (live)
    panels/ColorObjectList.tsx · PropertiesPanel.tsx (recolor/rename/reorder) · ThreadPalette.tsx (live)
    player/StitchPlayer.tsx (live) · trueview/TrueView3D.tsx (stub)
  {lib,store}/*.test.ts          vitest (18 tests)
apps/backend/app/
  main.py  config.py  models/design.py            shared data model (Pydantic)
  routers/  files · digitize · export · worksheet · threads(list) (live) · convert · designs · threads/match (stub)
  services/ embroidery_io · digitizer · worksheet_pdf · threads.list_threads (live) · nearest_thread (stub)
  tests/ test_embroidery_io · test_worksheet · test_digitizer · make_fixtures · fixtures/sample.dst,.pes
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
| **`/digitize`** | 🟢 | **image → Design with objects (OpenCV v1)** |
| `/threads` (GET) | 🟢 | catalog (brand filter) |
| `/threads/match` · `/convert` · `/designs` POST | 🔴 | 501 |
| `/designs` (GET) | 🟡 | in-memory |

### Backend services
| Function | Status |
|---|---|
| `read_embroidery`/`write_embroidery` · `build_worksheet`/`render_pdf` · `list_threads` · **`digitize_image`** | 🟢 |
| `nearest_thread` | 🔴 (Phase 8, scipy) |

### Frontend components
| Component | Status | Notes |
|---|---|---|
| App shell · api client · types · lib/* | 🟢 | pure libs unit-tested |
| StitchCanvas · ColorObjectList · ThreadPalette · StitchPlayer · PropertiesPanel | 🟢 | select · recolor · rename · reorder · animate |
| designStore | 🟢 | + reorderStop · undo/redo |
| Toolbar | 🟡 | Open/**Digitize**/Export/Worksheet/Undo/Redo live; digitize params dialog + digitizing tools TBD |
| TrueView3D | 🔴 | Phase 7 |

### Infrastructure
| Item | Status | Notes |
|---|---|---|
| Monorepo · shared data model | 🟢 | camelCase-on-wire verified |
| Tests | 🟡 | **pytest 13 + vitest 18**; no CI yet |
| DB applied · Supabase · deploy · AI/ML · `.STIQ` | 🔴 | Phases 6/8/X |

---

## 🟢 6. What's DONE (verified)

**Phases 0–2 (Updates #1–6):** monorepo + shared data model; parse/export/validate/worksheet(JSON+PDF);
Konva render + zoom/pan + click-to-select; recolor/rename/**reorder** color stops; ThreadPalette; undo/redo;
StitchPlayer; pytest + vitest suites; everything e2e-verified via the Vite proxy.

**Phase 3 core (Update #7, commit `9eed902`) — each confirmed by running it:**
1. **Auto-digitize** — PNG/JPG → k-means quantization → background drop (corner heuristic) → per-color
   contour regions → boustrophedon scanline fills (0.6mm rows, ≤6mm stitches) → machine-valid stream
   (JUMP/TRIM/COLOR_CHANGE/END) + **real `DesignObject`s** (TATAMI, density, entry/exit) + darkest-first stops.
2. **E2E via proxy** — real PNG → `/api/digitize` (885 stitches, 2 stops, 2 objects, 71.6mm) → `/api/export?format=dst` → re-read valid.
3. **Tests** — pytest **13/13**: +5 digitizer (objects produced, stream machine-valid ≤12.7mm, DST round-trip, garbage rejected, hoop fallback).
4. **py3.14 confirmed** for cv2/numpy/pillow (installed + functionally tested).

---

## 🔴 7. What's REMAINING

### A. Phase 3 polish
- **Digitize params dialog** (fabric/hoop/max-colors — v1 uses defaults cotton/100x100).
- **Object-level PropertiesPanel** editing (digitized designs now HAVE objects: density/angle per object → regenerate fills).
- **Satin detection** for narrow regions (currently everything is TATAMI fill); underlay generation (§4.6).

### B. Phases 4–10 & cross-cutting
- Lettering (4) · export package + `/convert` (5) · Supabase persistence/auth (6) · TrueView 3D (7) ·
  AI engine + `nearest_thread` (8) · generative + assistant (9) · collab/API/mobile (10).
- Cross-cutting: **CI** (pytest + vitest + tsc on push), Dockerfiles/deploy, logging, authz/upload-limits.

---

## 🧭 8. Key Decisions & Rationale

| Decision | Why |
|---|---|
| **TypeScript** + **Python** | User request; Python mandatory for pyembroidery/OpenCV/reportlab. |
| Build **vertically**, phase by phase | User scope; full spec is multi-year. |
| **Classical CV digitizer first** (k-means + contours + scanline) | No training data/GPU needed; honest approximate baseline; neural quality is Phase 8; stays as fallback. |
| **Background = cluster near corner-average color** | Simple, no ML; fails on non-uniform backgrounds → documented risk. |
| Digitizer emits **objects** + raw stitches together | Objects unlock §4.3 property editing; stitches keep export/render trivially working. |
| Color stop = editable unit for **imported** files; objects exist for **digitized** ones | Imported stitch files genuinely have no vector data. |
| Reorder = re-sequence COLOR_CHANGE blocks · bounds-based round-trip asserts · pure libs for testability | See Updates #3–6. |
| npm workspaces · tiered py deps · single tsconfig · ESLint 8 · lazy heavy imports | See Updates #1–2. |

---

## ⚠️ 9. Environment & Gotchas

- **Python 3.14.3** — pyembroidery, reportlab, **opencv 4.13/numpy 2.5/pillow 12.2** all install & work (**confirmed**). Only `scipy`/`supabase` remain untested.
- **DST has no color** — parsed `.DST` shows filler colors; `.PES` preserves real ones.
- **Round-trip stitch count is not stable** (writer normalizes) — compare **bounds**.
- **Imported files are stitch-only** (`objects` empty); **digitized designs have objects**.
- **Digitizer assumptions:** background ≈ corner color; ≤8 colors; regions <4mm² dropped; all fills TATAMI at 0.6mm rows.
- **pnpm not installed** → `npm`. **venv** at `apps/backend/.venv`. **Vite proxies** `/api`+`/health` → `:8000`.
- **Port hygiene:** `lsof -ti tcp:8000 | xargs kill -9` before booting.

---

## 🎯 10. Next Steps (do these IN ORDER)

1. **Digitize params dialog** — fabric/hoop/max-colors inputs before calling `/api/digitize`.
2. **Object-level editing** — PropertiesPanel edits density/angle for a selected `DesignObject` (digitized designs), regenerating that region's fill server-side.
3. **Satin detection** — narrow-region classifier (width < ~4mm → satin column instead of tatami) + basic underlay (§4.6).
4. **CI** — GitHub Actions: pytest + vitest + tsc on push.

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
pip install -r requirements.txt -r requirements-dev.txt   # core + tests (reportlab, opencv, numpy, pillow)
python tests/make_fixtures.py
```
### Baseline (last confirmed 2026-07-01, Update #7)
| Check | Command | Expected | Result |
|---|---|---|---|
| Backend tests | `python -m pytest tests -q` | **13 passed** | ✅ |
| Frontend tests | `npm test -w apps/frontend` | **vitest 18 passed** | ✅ |
| Digitize e2e | PNG → `:5173/api/digitize` → `/api/export?format=dst` → re-read | 200 · objects>0 · valid DST | ✅ |
| Parse / Export / Worksheet PDF / Threads | curl fixture → endpoints | 200 · `%PDF-` · 5 threads | ✅ |
| Frontend typecheck / build | `npm run typecheck` · `build -w apps/frontend` | 0 errors · builds | ✅ |

---

## 🚧 12. Known Risks / Unverified Claims

- **In-browser event wiring NOT eyeballed:** canvas paint, click-select, recolor, reorder ▲▼, undo, and the
  **Digitize button flow**. Open `:5173`, load a fixture AND digitize a simple PNG logo, confirm both paths.
- **Digitizer quality is approximate** (classical CV): uniform-background assumption, TATAMI-only fills, no
  underlay/pull-comp — fine for bold logos, poor for photos/gradients. Phase 8 addresses this.
- **`/threads/match`, `/convert`, persistence** unimplemented. **scipy/supabase untested on py3.14.**
- **DB schema unvalidated** against live Postgres.

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
| 1 | File I/O + Canvas | 🟢 Done | L | open/view/export + worksheet PDF |
| 2 | Interactive editing | 🟢 Done | L | select/recolor/rename/reorder/undo |
| **3** | **Auto-digitizing v1 (OpenCV)** | 🟡 **Core done** | XL | image → stitches + objects ✅ · params dialog, object-edit, satin TBD |
| 4 | Lettering & monogramming | ⬜ | L | text → stitches |
| 5 | Production output & formats | ⬜ | M | export packages, convert, 25+ formats |
| 6 | Persistence & accounts (Supabase) | ⬜ | M | save/load, auth, versions, teams |
| 7 | TrueView 3D simulation | ⬜ | L | realistic preview |
| 8 | AI engine (+ thread match) | ⬜ | XL | neural digitizing, path opt, quality scoring |
| 9 | Generative & assistant | ⬜ | XL | text-to-design, STITCH-GPT |
| 10 | Platform & scale | ⬜ | XL | collab, cloud API, mobile |
| X | Cross-cutting (tests/CI/deploy/security) | 🟡 Ongoing | — | ships everything safely |

### Phase 3 — Auto-Digitizing v1 🟡 CORE DONE (size XL)
- **Done:** `digitize_image` (quantize → segment → scanline fill → Design with objects + stops), `POST /api/digitize`, Toolbar Digitize, 5 tests, e2e verified.
- **Left:** params dialog (fabric/hoop/colors); object-level property editing + server-side fill regeneration; satin detection for narrow regions; underlay (§4.6).

### Phases 4–10 (summaries)
- **4 Lettering:** glyph → satin/fill + underlay (§4.10). **5 Production:** export package + `/convert` + brand map (§4.8).
  **6 Supabase:** apply `db/schema.sql`, auth, CRUD + Storage (**needs user keys**). **7 TrueView 3D:** thread geometry (§4.7).
  **8 AI:** SAM/CNN/RL + quality scoring + Lab k-d thread match (§4.2/§6). **9 Generative:** diffusion + STITCH-GPT (§4.1/§4.11).
  **10 Platform:** collab/cloud API/mobile (§4.12).

### Phase X — Cross-Cutting (start now)
- Tests (pytest ✅ + vitest ✅; add **CI**) · Dockerfiles + deploy (§7) · logging/Sentry · authz, upload limits, rate limiting.

---

## 🔧 15. Phase 1 Deep-Dive — File I/O + Canvas

> **Status: 🟢 DONE & verified.** Kept as reference for how file I/O works.

### pyembroidery API cheat-sheet — CONFIRMED on v1.5.1 / Python 3.14
| Need | API | Notes |
|---|---|---|
| Read | `pe.read(filename)` | write the upload to a temp file first |
| Stitches | `pattern.stitches` → `[[x,y,cmd_int]]` | **1/10 mm** → ÷10 for mm |
| Commands | `pe.STITCH=0 JUMP=1 TRIM=2 STOP=3 END=4 COLOR_CHANGE=5` | map via `pe.*` (`embroidery_io._CMD_TO_STR`) |
| Threads | `pattern.threadlist` (**empty for DST**) | `.hex_color()`, `.description`, `.catalog_number`, `.brand` |
| Color blocks | `pattern.get_as_colorblocks()` → `(stitches, thread)` | **use for color stops** (DST + PES) |
| Extents / count | `pattern.bounds()` · `count_stitches()` | dimensions / count |
| Write | `add_thread`, `add_stitch_absolute(cmd, x×10, y×10)`, `pe.write(pattern, filename)` | mm→tenths ×10 |

Implemented in `services/embroidery_io.py`, `worksheet_pdf.py`, `threads.py`, `digitizer.py`; routers
`files`/`digitize`/`export`/`worksheet`/`threads`; frontend `StitchCanvas`, `lib/stitches.ts`, `Toolbar`,
`StitchPlayer`, panels, `store/designStore`, `api/client`.
Verify: `pytest -q` (13) + `npm test` (18). Manual: Open `tests/fixtures/sample.dst` **and** Digitize a PNG;
click a stop, recolor, reorder ▲▼, undo, Export, Worksheet.

---

*End of STATUS.md — keep this file current. When in doubt, trust the code over this document, and fix the document.*
