# 🧵 STITCHIQ — Project Status & Handoff

> **Single source of truth for project state.** Read this first, then [`README.md`](./README.md),
> [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md), and the master spec
> [`AI-Embroidery-Software-Prompt.md`](./AI-Embroidery-Software-Prompt.md).

| Field | Value |
|---|---|
| **Project** | STITCHIQ — AI-powered embroidery design & digitizing platform |
| **Document version** | **v33** |
| **Times updated** | **33** |
| **Last updated** | 2026-07-28 |
| **Current phase** | Phases 0–8(v1) + manual digitizing done, hardened, **and usability-fixed** (fresh-install deps + lettering glyphs/detail + canvas visibility + banner stacking). Phase 8/9 *neural* AI remains (needs GPU/data) |
| **Git branch** | `claude/code-quality-improvements-hyu6dg` |
| **Latest code commit** | `0d7125b` (make features work out of the box) |
| **Working tree** | clean |
| **Tracked files** | 105 |
| **Location** | `/Users/INDIA/Downloads/EmDesign_Automater` |

---

## 📌 For the next model / session — READ THIS FIRST

1. **Current reality:** The app is a working (minimal) embroidery studio. Three input paths:
   **Open** a real `.DST`/`.PES`, **Digitize a PNG/JPG image**, or **Text** (lettering) — all → stitches +
   **real vector objects** (with holes/counters + underlay). Then: render → click-to-select →
   recolor/rename/reorder → undo/redo → export any format → worksheet PDF. Digitized/lettered objects are
   **editable**: select one, change density/angle/underlay, Apply → server rebuilds the stitches.
   Export to .DST/.PES/.JEF/.EXP/.VP3, convert via API, or download a **full production package ZIP**
   (machine file + master + worksheet + color card + preview + summary). A **2D/TrueView-3D** toggle shows a
   lit 3D thread preview; snap any color to the nearest catalog thread; edit density/angle/underlay/**pull-comp**.
   A **Check** button surfaces pre-export validation (hoop-fit blocks); **Save/Saved** persists designs in-browser;
   **Open** re-imports a master `.stiq.json`; the worksheet shows thread length per color; a **Studio ⇄ Dashboard**
   nav toggle adds a **real metrics page** (My designs / stitches / colors from the signed-in cloud account).
   **Cloud persistence is LIVE** — Save/list/open designs to a real Supabase Postgres with **per-user auth
   (signup/login)** — cloud Save/Open in the UI. **Phase 8 v1**: **Optimize** (cut stitch-path travel) +
   **Quality** (score + findings) buttons; **manual digitizing** (draw Run/Satin/Fill). Verified: **pytest 81/81,
   vitest 57/57**, e2e via Vite proxy, in-browser render confirmed in Chrome (§12), **+ live auth/cloud round-trip
   with multi-user isolation + manual-draw + adversarial-review hardening**.
2. **Chosen scope (by the user):** build **vertically**, one phase at a time ([§14](#-14-full-project-roadmap-phases-010)).
3. **Next task (pick one):** Everything buildable with this stack is now built — Phases 0–8(v1) + manual
   digitizing, all verified in Chrome. Remaining is either **gated** or **outward**: (a) **neural AI** (Phases
   8-neural/9 — learned digitizing, text-to-design; needs GPU + training data); (b) **push to GitHub** to exercise
   the CI config (needs explicit user authorization — data-publishing action); (c) polish: **satin-stroke lettering
   v1.1**, password reset, Supabase Storage for master/preview URLs, per-stroke satin.
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

- **Stack:** TypeScript (React + Vite) frontend · Python (FastAPI) backend · PostgreSQL/Supabase (schema **applied & live** — designs CRUD).
- **Built:** **Phases 0–5 essentially done**: open/parse, **image auto-digitize** (TATAMI + SATIN + underlay + **holes/counters**), **text lettering**, **object-level editing** (→ server rebuild), Konva render, full color-stop editing, **export any format + convert + full production package ZIP**, worksheet PDF.
- **Verified:** **pytest 83/83** · **vitest 57/57** · typecheck/build · e2e lettering→digitize→edit→rebuild→validate→export/convert/package/thread-match/**optimize+quality+manual-draw** through the Vite proxy · **live Supabase auth + per-user cloud CRUD + real Dashboard + Phase 8 path-opt + manual digitizing (multi-user isolation) verified in Chrome**.
- **Still stubbed:** *neural* AI/ML (learned digitizing, text-to-design — Phases 8/9, need GPU/data), satin-stroke lettering, password reset. (Auth, cloud sync, path-opt + quality scoring are live.)
- **Next:** Phase 6 polish (password reset / Storage URLs), lettering v1.1, or push to GitHub (CI unverified).

---

## 🔄 2. Update History / Changelog

> Add a new row every time the project changes. **Newest at top.**

| # | Date | Author | Type | Summary |
|---|------|--------|------|---------|
| 33 | 2026-07-28 | Claude (Fable 5) | 🐛 Fix | **Make features work out of the box — 9 defects from a full e2e + in-browser sweep** — commit `0d7125b`. User reported "features run partially / results not good"; every feature was exercised over HTTP and in headless Chrome. Fixes, worst-first: **(1, fresh install broken)** the documented setup (`requirements.txt`+`-dev`) omitted **pyembroidery** → Open/Export/Convert/Package all failed on a fresh clone; moved to core requirements. **(2)** black-on-black canvas: stitches rendered on a near-black stage → dark designs (e.g. black lettering) were invisible; added a **light fabric backdrop** + stitches draw at **physical 0.4mm thread width** → fills read as embroidery. **(3)** Check/Quality/Optimize banners all rendered in one fixed corner — hid each other and **blocked clicks on Studio⇄Dashboard**; now they stack below the toolbar. **(4)** lettering accepted unsupported chars (emoji → .notdef tofu boxes → garbage stitch rectangles); per-char detection vs U+0378 rejects them with a clear 422. **(5)** lettering dropped sub-4mm² details ('i'/'j' dots at small sizes); lettering digitizes at 0.5mm² min-region ('i'@8mm keeps its dot, +2 tests). **(6)** tatami row pitch 0.6→0.45mm (full coverage, was fabric-through-fill). **(7)** page-nav Studio/Dashboard toggle reused the absolutely-positioned `.view-toggle` class → sat on top of Sign-in. **(8)** DST stops surfaced pyembroidery filler threads literally named "Random" → now "Color n (file has no color data)". **(9)** favicon 404. **pytest 81→83** (the emoji test previously FAILED on Linux fonts — now passes), vitest 57, typecheck+build clean, zero console errors/failed requests in Chrome re-verify. README refreshed (stale counts/claims). |
| 32 | 2026-07-04 | Claude (Opus 4.8) | 🛠 Fix | **Harden session code — 6 bugs from an adversarial multi-agent review** — commit `24c9aef`. A 42-agent Workflow (5 review dimensions × 3 skeptics/finding) raised 12, **confirmed 7** (deduped to 6 root causes), rejected 5. Fixes, worst-first: **(1, data loss)** `create_design` only error-checked the `designs` INSERT — a failed `design_objects`/`color_stops`/`design_versions` write was swallowed → phantom 201 that lists but 404s on open; now every child write `raise_for_status`es + compensating-DELETEs the orphan row on failure. **(2, data loss)** `setDesign` left `activeTool`/`draft` dirty → loading a file mid-draw then Finish wiped an imported .DST; now resets tool+draft + `onFinishDraw` re-guards `isImportedNotEditable` (**verified in Chrome**: Open mid-draw keeps the 87-st import). **(3)** in-memory ids derived from `len()` reused after delete → monotonic `itertools.count`. **(4)** `list_designs`/`design_stats` truncated at PostgREST's 1000-row cap → added `_get_all` pagination. **(5)** malformed `design_id` → 400→502; now uuid-validated → 404. **(6)** RUNNING_DOUBLE/TRIPLE duplicated the turnaround vertex (0-length stitch) → drop the junction point. Plus 502 bodies no longer leak the internal Supabase URL/query/uuids. **pytest 78→81** (+3 regression), vitest 57; live cloud round-trip + browser re-verify; typecheck+build clean. |
| 31 | 2026-07-04 | Claude (Opus 4.8) | ✨ Feature | **Manual digitizing — draw Run/Satin/Fill on the canvas** — commit `7a7bdfb`. Lights up the dead toolbar tools. Backend: `rebuild_design` gains a **RUNNING branch** (`_manual_run` + `_resample_open`) so a drawn **open path** stitches ALONG it (single/double/triple pass) instead of area-filling; Fill=tatami/Satin=column reuse existing branches. Frontend: store `activeTool` + `draft` points (setTool/addDraftPoint/undoDraftPoint); **StitchCanvas draw mode** (click drops points → design-mm via the fit Group, live polyline + hoop + crosshair); Toolbar wires **Select/Run/Satin/Fill** + Finish/⌫/Cancel; `lib/manual` builds the object (contour + stitch-type spec) → commits via `/api/designs/rebuild` (new design, or appended to a digitized one; imported files blocked with a message). **Esc** cancels. **Verified in Chrome**: draw Fill quad → 536-st tatami; add Run path → running chevron (16 st); both editable objects; **Undo reverts**. **pytest 75→78** (+3), **vitest 52→57** (+5); typecheck+build clean. |
| 30 | 2026-07-04 | Claude (Opus 4.8) | ✨ Feature | **Phase 8 v1 — optimization engine (path opt + quality)** — commit `fe2482d`. Classical/deterministic baseline (neural digitizing & text-to-design need GPU/data → future). `services/optimizer.py`: **`optimize_path`** — since `rebuild_design` already groups objects by color, the win is a **nearest-neighbour tour within each color** to cut needle travel/jumps → reassign sequence_order + rebuild; returns before/after metrics; no-op when not regenerable or no gain. **`analyze_quality`** — 0–100 score + grade + findings (over-long >12.7mm stitches, sub-0.5mm stitches, excessive color changes/jumps). New `POST /api/optimize/{path,quality}` + models (PathMetrics/OptimizeReport/OptimizeResult/QualityFinding/QualityReport, TS mirror). Toolbar **Quality** + **Optimize** buttons with report banners; Optimize uses `replaceDesign` (Undo reverts). **Verified in Chrome**: digitize 8-object logo → Quality **A·100/100** → Optimize cut travel **328.8→272.9mm (−55.9mm)**, objects renumbered, Undo works. **pytest 70→75** (+5); vitest 52; typecheck+build clean. |
| 29 | 2026-07-04 | Claude (Opus 4.8) | ✨ Feature | **Real per-user Dashboard from cloud data + toolbar wrap** — commit `09a74ac`. New `GET /api/designs/stats` (owner-scoped aggregate: design count, summed stitches/colors, recent list) → `services/supabase_store.design_stats`. `lib/dashboard.ts` rewritten: signed-in shows **real cloud metrics** (My designs / Total stitches / Colors used), signed-out falls back to this-browser saved designs (colors = "—", no local source); refetches on login/logout. Retires the placeholder revenue/users/conversion KPIs. Also fixed: the button-heavy toolbar now **flex-wraps** to a 2nd row instead of overflowing the page (the ☁ buttons had widened it past 1280px). **Verified in Chrome**: sign up → Open sample.dst → ☁ Save → Dashboard shows *My designs 1 · Total stitches 87 · Colors used 2* from cloud + recent activity. **pytest 69→70, vitest 52** (dashboard tests rewritten for the new shape); typecheck+build clean. |
| 28 | 2026-07-04 | Claude (Opus 4.8) | ✨ Feature | **Phase 6 — per-user auth + cloud Save/Open UI (§8)** — commit `0d96ee8`. Backend `routers/auth.py` (signup/login/me over Supabase GoTrue; signup admin-creates a confirmed user then logs in) + `deps.current_user` (verifies bearer token → 401 when Supabase on, `local-dev` sentinel when off). `designs` CRUD now **scoped to the acting user** (list/get/delete filter by owner; create attributes to the user + mirrors auth.users→public.users). Frontend `lib/auth` + `store/authStore` + `AuthBar` (sign-in popover / logged-in email + logout) in the top nav; Toolbar **☁ Save / ☁ Open** (per-user cloud) beside local Save; client attaches bearer token, surfaces `{detail}` errors, handles 204. **Verified live in Chrome**: signup→logged-in→Open sample.dst→☁ Save→☁ Open lists it→reload keeps session; **multi-user isolation** over HTTP (B can't see/GET A's designs; unauth/bad-pw→401). **pytest 65→69, vitest 47→52**; typecheck+build clean. Phase 6 now essentially complete. |
| 27 | 2026-07-04 | Claude (Opus 4.8) | ✨ Feature | **Phase 6 — Supabase cloud persistence (§8)** — commit `d93696d`. User provided real Supabase keys + DB password; **`db/schema.sql` (10 tables) applied to the live project** (via psycopg direct connection). `services/supabase_store.py` (PostgREST + Auth-admin over the service key; get-or-create system owner user for the RLS FK chain) + `designs.py` CRUD now persist to Supabase — create writes designs/design_objects/color_stops + a full-fidelity `design_versions` snapshot; get restores stitches+contours; delete cascades; **graceful in-memory fallback** keeps app + offline pytest running keyless. Seeded `thread_database` (5 threads). **Verified end-to-end over real HTTP against live Supabase**: POST→201 (uuid+ts), list, full-fidelity GET, DELETE→204→404. **pytest 65/65** (+2 `test_designs.py`); httpx→core dep. Secrets in gitignored `apps/backend/.env` only. *(Remaining Phase 6: per-user auth/login UI + frontend "cloud save" wiring — backend attributes to one system user for now.)* |
| 26 | 2026-07-04 | Claude (Fable 5) | ✅ Verify | **In-browser render VERIFIED** (no code change). Drove the real app in system Chrome via Playwright + screenshots: shell, Open→canvas paints stitches, stop-select→highlight+Properties, TrueView 3D→lit thread tubes, Digitize PNG→correct fill + nested objects, Check→banner. Retires the long-standing "paint not eyeballed" caveat (§12). Only console msg: `/favicon.ico` 404 (cosmetic). |
| 25 | 2026-07-04 | Claude (Fable 5) | 📝 Docs | **README rewrite** — commit `e04a78a`. Replaced the stale "scaffold only, no features" README with an accurate description of the working studio (inputs, editing/rebuild, TrueView 3D, validation, export/convert/package, local save, dashboard), real stack, setup/run/test, honest gates. Points to STATUS.md. |
| 24 | 2026-07-04 | Claude (Fable 5) | ✨ Feature | **Download editable master (.stiq.json)** — commit `88d00e7`. `serializeMasterDesign` + Toolbar **Master** button download; completes the master round-trip (previously the master was only inside the package zip). **vitest 47/47** (+2 serialize→parse fidelity). |
| 23 | 2026-07-04 | Claude (Opus 4.8) | ✨ Feature | **Studio dashboard page (Phase 6 groundwork)** — commit `7cc6c96`. `lib/dashboard.ts` (pure: formatters + activity derivation + `fetchDashboard`, unit-tested), `components/dashboard/Dashboard.tsx` (loading/error/empty/data states), App **Studio ⇄ Dashboard** nav toggle, dashboard/stat-card/activity CSS. Revenue/users/conversion have **no source yet** → honest "—" (Phase 6); **recent activity is real** from `lib/storage.ts` saved designs. Frontend-only, no backend/data-model change. **vitest 45/45** (+10), typecheck/lint/build clean. |
| 22 | 2026-07-04 | Claude (Fable 5) | ✨ Feature | **Thread length per color on the worksheet (§4.9)** — commit `b3e977e`. `build_worksheet` computes thread consumed per color (STITCH segment sum; jumps break the run) → `WorksheetColorRow.threadLengthMm` (TS+Pydantic); PDF shows metres. **pytest 63/63** (+1). |
| 21 | 2026-07-04 | Claude (Fable 5) | ✨ Feature | **Stronger pre-export validation (§4.8)** — commit `5e4f06f`. Hoop-fit is now a blocking issue (design bigger than its hoop can't be stitched); >15 color changes warns. **pytest 62/62** (+3). |
| 20 | 2026-07-04 | Claude (Fable 5) | ✨ Feature | **Re-open master .stiq.json** — commit `d23c24e`. `lib/masterFile.ts` parseMasterDesign (JSON → validated Design, keeps objects/contours) + isMasterFilename; Toolbar Open routes .json → local parse, embroidery → backend. Closes the export→edit→re-open loop. **vitest 35/35** (+5); export→import contract verified vs a real package zip. |
| 19 | 2026-07-04 | Claude (Fable 5) | ✨ Feature | **Local design persistence (save/load in-browser)** — commit `e7ba3d3`. `lib/storage.ts` (localStorage save/list/load/delete, injectable KV → unit-tested); store `setDesignId`; Toolbar **Save** + **Saved (n)** popover (load/delete). Closes "lose your work on refresh" without keys; cloud sync stays Phase 6. **vitest 30/30** (+5). |
| 18 | 2026-07-04 | Claude (Fable 5) | ✨ Feature | **Pre-export validation surfaced in the UI (§4.8)** — commit `9dae09e`. Toolbar **Check** button + validate-before-Export; dismissible report banner (blocking issues vs warnings vs all-clear). `/api/export/validate` existed since Phase 1 but was untested/unwired — now `test_validate.py` (empty/ok/oversize/long-stitch). **pytest 59/59** (+4); e2e via proxy. |
| 17 | 2026-07-03 | Claude (Fable 5) | ✨ Feature | **Appliqué stitch type (§4.3) + satin hardening** — commit `b1a6c35`. rebuild APPLIQUE branch = placement outline → tackdown → 2mm satin border (`_run_along`/`_satin_border`/`_resample_closed`); `_satin_zigzag` subdivides cross-width zigs so wide columns stay ≤12.7mm; PropertiesPanel stitch-type selector. **pytest 55/55** (+4); e2e: 2 objs→APPLIQUE→1220 st, max 2.0mm, exports PES. |
| 16 | 2026-07-03 | Claude (Fable 5) | ✨ Feature | **Pull compensation (§4.6)** — commit `407a327`. Wires up the dead `DesignObject.pull_compensation` field: digitizer assigns a fabric-dependent default (knit 0.4–0.5, woven 0.15–0.2mm) and dilates the top fill/satin to counter fabric pull; rebuild honors edits; PropertiesPanel pull-comp input. **pytest 51/51** (+4); e2e: pull 0→1mm widens 71.5→72.25mm. v1 = uniform dilation (directional is future). |
| 15 | 2026-07-03 | Claude (Fable 5) | ✨ Feature | **Thread nearest-match (§4.4 complete)** — commit `c5e942d`. `hex_to_lab` (pure sRGB→Lab D65) + `nearest_thread` (CIE76 ΔE); `POST /api/threads/match` implemented (was 501), 422 on bad hex; ThreadPalette "nearest catalog thread" button snaps a stop's color to an orderable thread. **pytest 47/47** (+5); e2e via proxy (black→Black, red→Flame, blue→Royal Blue). |
| 14 | 2026-07-03 | Claude (Fable 5) | ✨ Feature | **Phase 7: TrueView 3D thread preview** — commit `af37f26`. `lib/thread3d.buildThreadScene` (pure, tested) → `TrueView3D` renders TubeGeometry per color run with lighting + fabric plane; drag-rotate + scroll-zoom (no OrbitControls dep); 2D/3D toggle. **vitest 25/25** (+4). ⚠️ 3D **paint not eyeballed** (headless) — geometry math tested, render needs a human. |
| 13 | 2026-07-02 | Claude (Fable 5) | ✨ Feature | **Phase 5: production export package (ZIP) + brand map** — commit `afbe3b2`. `POST /api/export/package` → ZIP (machine file + master .STIQ JSON + worksheet PDF + color-card PDF + preview PNG + summary); `GET /api/formats` (brand→format table); Toolbar **Package** button. **pytest 42/42**; e2e 6-artifact ZIP via proxy. |
| 12 | 2026-07-02 | Claude (Fable 5) | ✨ Feature | **Phase 4 lettering + holes + 4 digitizer bug fixes** — commit `d9c8fea`. Text→stitches (PIL render → digitizer) `POST /api/lettering` + Toolbar Text button; `DesignObject.holes` (donut/counter carve via RETR_CCOMP + rebuild). Adversarial review of the diff surfaced 4 bugs (its verifier agents died on a session limit → I confirmed each by reproduction): **phantom color stops** (spurious thread change on every design), **satin rotation crop** (narrow letters half-height), **400→1200px res cap** (wide text collapsed), **empty-result 422**. **pytest 38/38** (+5 regression); e2e via proxy. |
| 11 | 2026-07-01 | Claude (Fable 5) | ✨ Feature | **Phase 5 start: convert endpoint + export picker + CI config** — commit `b3aaf13`. `POST /api/convert` (base64 any→any, color-loss warnings, 400/415 errors); Toolbar export dropdown (.DST/.PES/.JEF/.EXP/.VP3); `.github/workflows/ci.yml` (**unverified — no remote**). **pytest 28/28**; e2e dst→jef via proxy. |
| 10 | 2026-07-01 | Claude (Fable 5) | ✨ Feature | **Phase 3 complete: underlay generation (§4.6)** — commit `b212b44`. Edge-walk under fills (0.6mm inset, 2mm running stitch), center-walk under satin columns; digitize assigns `underlay_type`, rebuild honors it (toggleable per object); Properties underlay selector. **pytest 24/24**; e2e via proxy: underlay 1011 → NONE 790 stitches. |
| 9 | 2026-07-01 | Claude (Opus 4.8) | ✨ Feature | **Phase 3: object-level editing + server-side rebuild** — commit `f5ddf89`. `DesignObject.contour` (mm outline, TS⇄Pydantic); `rebuild_design` re-fills every object from its contour with current density/angle (angled tatami via rotate-scan); `POST /api/designs/rebuild`; objects listed under stops; Properties object mode (density/angle → Apply). **pytest 21/21, vitest 21/21**; e2e halve-density 885→309 stitches via proxy; imported designs → 422. |
| 8 | 2026-07-01 | Claude (Opus 4.8) | ✨ Feature | **Phase 3: satin detection + digitize params dialog** — commit `df14eb0`. minAreaRect classifier (0.8–4mm, aspect ≥2.5) → rotated-zigzag **SATIN columns** (any angle); `DigitizeDialog` (fabric/hoop/max-colors). **pytest 16/16** (+3); SATIN confirmed e2e via proxy. Threshold is physical mm → hoop-dependent (by design). |
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
  routers/  auth(signup/login/me) · files · digitize · export(+package) · worksheet · convert · lettering · threads · designs CRUD (all live, Supabase-backed + owner-scoped)
  services/ embroidery_io · digitizer · worksheet_pdf · threads(list+nearest) · supabase_store · supabase_auth (all live) · deps.current_user (bearer gate)
  tests/ test_embroidery_io · test_worksheet · test_digitizer · test_designs · … · make_fixtures · fixtures/sample.dst,.pes
db/schema.sql (**applied to live Supabase**) · docs/ · STATUS.md · README.md · AI-Embroidery-Software-Prompt.md
```

---

## 📊 5. Feature Status Matrix

**Status:** 🔴 Stub · 🟡 In progress / partial · 🟢 Done & verified

### Backend endpoints (`/api`)
| Endpoint | Status | Behavior |
|---|---|---|
| `/health` · `/files/parse` · `/export` · `/export/validate` | 🟢 | ok · parse → Design · stream file · checks |
| `/worksheet` · `/worksheet/pdf` | 🟢 | Worksheet **JSON + PDF** |
| **`/digitize`** | 🟢 | **image → Design with objects (TATAMI fills + SATIN columns + contours)** |
| **`/designs/rebuild`** | 🟢 | **re-fill objects from contours with edited params (422 if not regenerable)** |
| **`/convert`** | 🟢 | **base64 any→any + color-loss warnings** |
| **`/lettering`** | 🟢 | **text → Design (PIL render → digitizer); 422 on unsupported glyphs** |
| **`/export/package`** · **`/formats`** | 🟢 | **production ZIP (6 artifacts)** · brand→format map |
| `/threads` (GET) | 🟢 | catalog (brand filter) |
| **`/threads/match`** | 🟢 | **nearest catalog thread (CIE Lab); 422 bad hex** |
| **`/auth/signup`·`/login`·`/me`** | 🟢 | **Supabase GoTrue proxy; bearer-token gate (`deps.current_user`)** |
| **`/designs` CRUD (POST/GET/GET id/DELETE)** | 🟢 | **owner-scoped Supabase persistence + version snapshot; keyless in-memory fallback** |
| **`/designs/stats`** | 🟢 | **per-user aggregate (count · stitches · colors · recent) for the Dashboard** |
| **`/optimize/path`** · **`/optimize/quality`** | 🟢 | **Phase 8: nearest-neighbour path opt (cut travel/jumps) · 0–100 quality score + findings** |

### Backend services
| Function | Status |
|---|---|
| `read_embroidery`/`write_embroidery` · `build_worksheet`/`render_pdf` · `list_threads` · **`nearest_thread`** (CIE Lab) · **`digitize_image`** (holes + satin/underlay, no-crop rotation) · **`rebuild_design`** · **`generate_lettering`** · **`build_package`** | 🟢 |

### Frontend components
| Component | Status | Notes |
|---|---|---|
| App shell · api client · types · lib/* | 🟢 | pure libs unit-tested |
| StitchCanvas · ColorObjectList · ThreadPalette · StitchPlayer · PropertiesPanel | 🟢 | select stops **+ objects** · recolor · rename · reorder · nearest-match · **edit stitch-type(+appliqué)/density/angle/underlay/pull-comp → rebuild** · animate |
| **TrueView3D** + 2D/3D toggle | 🟢 | thread tubes + lighting + fabric; drag-rotate/zoom (**render verified in Chrome — §12**) |
| designStore | 🟢 | + reorderStop · **selectObject/updateObject/replaceDesign** · undo/redo |
| Toolbar (Digitize/Lettering dialogs) | 🟢 | Open/Digitize/Text/Save/Saved/Check/Quality/Optimize/Export/Package/Worksheet/Undo/Redo + **manual Run/Satin/Fill draw tools** live |
| Local persistence (`lib/storage.ts`) | 🟢 | save/load/delete via localStorage (unit-tested); **cloud Save/Open now live too** |
| **Auth + cloud sync (`lib/auth`,`authStore`,`AuthBar`)** | 🟢 | sign-in popover · session persists · ☁ Save/Open per-user (verified in Chrome) |
| Master file (`lib/masterFile.ts`) | 🟢 | **Open** a `.stiq.json` → editable Design (objects/contours kept) · **Master** button downloads it (round-trip tested) |
| **Studio Dashboard** + Studio⇄Dashboard nav | 🟢 | **real per-user metrics** (My designs / stitches / colors) from cloud `/api/designs/stats` when signed in; local fallback when not |
| **Dashboard** (`lib/dashboard.ts` + `Dashboard.tsx`) | 🟢 | signed-in → **real cloud KPIs** + recent activity; signed-out → this-browser saved designs (colors "—"); refetches on login/logout; loading/error/empty states; pure logic unit-tested |

### Infrastructure
| Item | Status | Notes |
|---|---|---|
| Monorepo · shared data model | 🟢 | camelCase-on-wire verified |
| Tests | 🟡 | **pytest 83 + vitest 57**; CI config written (**unverified**) |
| **DB schema applied · Supabase designs CRUD** | 🟢 | 10 tables live; `services/supabase_store.py` create/list/get/delete verified over HTTP (§8) |
| **Per-user auth (signup/login) + cloud Save/Open** | 🟢 | GoTrue proxy · bearer-token gate · owner-scoped CRUD; verified in Chrome (§8) |
| Deploy · AI/ML · `.STIQ` binary | 🔴 | Phases 8 / X |

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

**Phase 3 tail (Update #8, commit `df14eb0`):**
5. **Satin detection** — narrow elongated regions (0.8–4mm wide, aspect ≥2.5) become rotated-zigzag
   **SATIN columns** with correct `stitch_angle`; wide shapes stay TATAMI. pytest **16/16**; SATIN
   confirmed through the real HTTP proxy path (−45° bar → `Satin 1`, 400 stitches).
6. **Digitize params dialog** — fabric/hoop/max-colors chosen before digitizing (was hardcoded defaults).

**Object-level editing (Update #9, commit `f5ddf89`):**
7. **Contours stored** — every digitized object carries its region outline in mm (`DesignObject.contour`).
8. **Server-side rebuild** — `POST /api/designs/rebuild` re-fills all objects from contours with their
   current density/angle/type (angled tatami via rotate-scan). E2e via proxy: halve density → 885→309
   stitches, bounds stable; imported (contour-less) designs correctly rejected 422.
9. **Object editing UI** — objects nested under stops in the left panel; Properties object mode
   (density/angle → Apply); undo restores the pre-rebuild design. pytest **21/21**, vitest **21/21**.

**Underlay — Phase 3 complete (Update #10, commit `b212b44`):**
10. **Edge-walk / center-walk underlay** (§4.6) — generated by digitize (fills → EDGE_WALK, satins →
    CENTER_WALK), honored + toggleable via rebuild, selectable in Properties. pytest **24/24**;
    e2e via proxy: underlay on 1011 stitches → NONE 790.

**Convert — Phase 5 start (Update #11, commit `b3aaf13`):**
11. **`POST /api/convert`** — base64 any→any through `read_embroidery`/`write_embroidery`; color-loss
    warnings for colorless formats (dst/exp/…); 400 bad base64 / 415 unknown format. pytest **28/28**;
    e2e dst→jef via proxy (valid JEF, threads preserved). Toolbar export dropdown (.DST/.PES/.JEF/.EXP/.VP3).
12. **CI config** — `.github/workflows/ci.yml` (pytest py3.12 + typecheck/vitest/build node22).
    **UNVERIFIED**: repo has no remote; the first GitHub push exercises it.

**Lettering + holes + digitizer fixes (Update #12, commit `d9c8fea`):**
13. **Lettering** (§4.10) — `POST /api/lettering`: PIL renders text → the digitizer turns it into
    contoured, editable, rebuildable objects with underlay. Toolbar **Text** + LetteringDialog. v1 = tatami fills.
14. **Holes/counters** — `DesignObject.holes`; RETR_CCOMP hierarchy carves an 'o'/'O' counter out of the
    fill (was solid), on both digitize and rebuild.
15. **4 digitizer bugs fixed** (found by adversarial review of the diff; verified by reproduction since the
    review's verifier agents hit a session limit): phantom empty color stops + dangling COLOR_CHANGE
    (every design carried a spurious thread change); satin rotation cropping (narrow letters ~half height);
    resolution cap 400→1200px (wide text collapsed); empty-result → 422. **pytest 38/38** (+5 regression).

**Production package — Phase 5 done (Update #13, commit `afbe3b2`):**
16. **Export package ZIP** (§4.8) — `POST /api/export/package` bundles machine file + master .STIQ JSON +
    worksheet PDF + thread color-card PDF + preview PNG (PIL) + summary txt. `GET /api/formats` returns the
    machine-brand format map. Toolbar **Package** button. **pytest 42/42**; e2e 6-artifact ZIP via proxy.

**TrueView 3D — Phase 7 done (Update #14, commit `af37f26`):**
17. **TrueView 3D** (§4.7) — `lib/thread3d.buildThreadScene` (pure, tested) → `TrueView3D` renders one
    TubeGeometry per color run with `MeshStandardMaterial` sheen, a fabric plane, ambient + 2 directional
    lights; drag-rotate + scroll-zoom via local state (no OrbitControls dep). 2D/3D toggle. **vitest 25/25**.
    ⚠️ The 3D **paint is not eyeballed** (headless) — geometry math tested; render/lighting/camera need a human.

**Threads + pull compensation (Updates #15–16, commits `c5e942d`, `407a327`):**
18. **Thread nearest-match** (§4.4) — `hex_to_lab` + `nearest_thread` (CIE76 ΔE); `POST /api/threads/match`;
    ThreadPalette "nearest catalog thread" snaps a color to an orderable thread. **pytest 47/47**; e2e via proxy.
19. **Pull compensation** (§4.6) — wires the previously-dead `pull_compensation` field: fabric-dependent
    default + top-layer dilation on digitize, honored/editable on rebuild, PropertiesPanel input. **pytest 51/51**;
    e2e pull 0→1mm widens 71.5→72.25mm. (v1 = uniform dilation; directional is future.)

**Appliqué + satin hardening (Update #17, commit `b1a6c35`):**
20. **Appliqué** (§4.3) — object stitch-type APPLIQUE → rebuild emits placement outline + tackdown +
    2mm satin border along the contour (`_run_along`/`_satin_border` + arc-length `_resample_closed`).
    PropertiesPanel stitch-type selector. **pytest 55/55**; e2e 2 objs→APPLIQUE→1220 st, max 2.0mm, exports PES.
21. **Satin hardening** — `_satin_zigzag` subdivides cross-width zigs by max-stitch, so a wide region
    mis-set to SATIN stays machine-valid (≤12.7mm) instead of emitting one giant stitch.

---

## 🔴 7. What's REMAINING

### A. Phase 3 — ✅ nothing remaining (complete as of Update #10)

### B. Phases 4–10 & cross-cutting
- export package ZIP + brand map (rest of 5) · Supabase persistence/auth (6) · TrueView 3D (7) ·
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
- **Digitizer assumptions:** background ≈ corner color; ≤8 colors; regions <4mm² dropped; wide shapes →
  TATAMI (0.6mm rows) + edge-walk underlay; narrow elongated (0.8–4mm, aspect ≥2.5) → SATIN + center-walk.
- **pnpm not installed** → `npm`. **venv** at `apps/backend/.venv`. **Vite proxies** `/api`+`/health` → `:8000`.
- **Port hygiene:** `lsof -ti tcp:8000 | xargs kill -9` before booting.

---

## 🎯 10. Next Steps (do these IN ORDER)

1. **Phase 6** — Supabase persistence/auth: apply `db/schema.sql`, wire `designs` CRUD + Storage + auth. **Needs the user's Supabase project URL + keys** (blocked until provided).
2. **Phase 7** — TrueView 3D preview (Three.js `TrueView3D` real impl).
3. **Push to GitHub** to exercise the CI config (currently unverified).
4. **Lettering v1.1** — per-stroke satin (skeletonize glyphs) instead of tatami fill; fix tiny-lowercase dot drop.

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
| Backend tests | `python -m pytest tests -q` | **81 passed** | ✅ |
| Frontend tests | `npm test -w apps/frontend` | **vitest 57 passed** | ✅ |
| Supabase CRUD e2e | POST/GET/DELETE `:8000/api/designs` (live project) | 201 (uuid) · full-fidelity GET · 204→404 | ✅ |
| Rebuild e2e | digitize → halve density → `:5173/api/designs/rebuild` | fewer stitches, bounds stable; imported → 422 | ✅ |
| Underlay e2e | digitize (EDGE_WALK default) → rebuild with NONE | 1011 → 790 stitches | ✅ |
| Convert e2e | dst→jef via `:5173/api/convert` | valid JEF, threads kept, warning | ✅ |
| Lettering e2e | text → `:5173/api/lettering` → export | 1 stop, objects with holes, valid file | ✅ |
| Package e2e | design → `:5173/api/export/package` | 6-artifact ZIP (machine/master/2×PDF/PNG/txt) | ✅ |
| Digitize e2e | PNG → `:5173/api/digitize` → `/api/export?format=dst` → re-read | 200 · objects>0 · valid DST | ✅ |
| Satin e2e | thin-bar PNG (100x100 hoop) → `:5173/api/digitize` | SATIN object with angle | ✅ |
| Parse / Export / Worksheet PDF / Threads | curl fixture → endpoints | 200 · `%PDF-` · 5 threads | ✅ |
| Frontend typecheck / build | `npm run typecheck` · `build -w apps/frontend` | 0 errors · builds | ✅ |

---

## 🚧 12. Known Risks / Unverified Claims

- ✅ **In-browser rendering VERIFIED (2026-07-04, Playwright + system Chrome).** Drove the real app at `:5173`
  and captured screenshots: studio shell renders; **Open sample.dst → stitches paint on the Konva canvas**
  + color list populates (87 st, 40×40mm); **click a stop → highlights + Properties editor opens**; **TrueView 3D
  → lit thread tubes on a fabric plane in perspective**; **Digitize a PNG → correct tatami-filled circle+square,
  nested object list, 935 st**; **Check → "✓ Ready to stitch" banner**. Only console msg: one `/favicon.ico` 404 (cosmetic).
  (Remaining unverified: fine-grained interactions like drag-pan/undo-keys and PDF/zip *download* file contents, though their logic is tested.)
- **Lettering v1 is tatami-filled** (not per-stroke satin — the classic look): fine for chunky text, heavier/blockier
  than pro satin lettering. Tiny lowercase (~8mm) can drop the dot on 'i'/'j'. Satin strokes = v1.1.
- **Digitizer quality is approximate** (classical CV): uniform-background assumption, no pull-comp, only
  edge/center-walk underlay — fine for bold logos, poor for photos/gradients. Phase 8 addresses this.
- **Adversarial review caveat (Update #12):** the workflow that reviewed this diff had its 14 verifier
  agents die on a session limit, so its `confirmed:[]` was meaningless. The 4 fixed bugs were confirmed
  by manual reproduction instead; other lenses (geometry, contract) never completed — a fuller re-review is worthwhile.
- **Satin threshold is physical mm** (0.8–4mm × aspect ≥2.5) — the same image can digitize as satin at a
  100x100 hoop and tatami at 130x180. By design; verified both ways via proxy.
- **Design persistence** unimplemented (needs Supabase). **supabase untested on py3.14.**
- **CI config unverified** — no GitHub remote; the workflow has never run.
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
| 3 | Auto-digitizing v1 (OpenCV) | 🟢 **Done** | XL | TATAMI+SATIN + underlay + dialog + object-edit/rebuild |
| 4 | Lettering & monogramming | 🟢 **Done (v1)** | L | text → tatami-filled stitches ✅ · satin strokes = v1.1 |
| 5 | Production output & formats | 🟢 **Done** | M | convert + multi-format export + production package ZIP + brand map |
| 6 | Persistence & accounts (Supabase) | 🟢 **Done (v1)** | M | schema applied · **auth (signup/login)** · owner-scoped cloud CRUD + version snapshots ✅ · teams/password-reset = later |
| 7 | TrueView 3D simulation | 🟢 **Done** | L | lit thread tubes + fabric, drag/zoom (**render verified in Chrome**) |
| 8 | AI engine (+ thread match) | 🟡 **v1** | XL | ✅ thread match · ✅ **path optimization** · ✅ **quality scoring** (classical); neural digitizing = future (GPU/data) |
| 9 | Generative & assistant | ⬜ | XL | text-to-design, STITCH-GPT |
| 10 | Platform & scale | ⬜ | XL | collab, cloud API, mobile |
| X | Cross-cutting (tests/CI/deploy/security) | 🟡 Ongoing | — | ships everything safely |

### Phase 3 — Auto-Digitizing v1 🟢 DONE (size XL)
`digitize_image` (quantize → segment → TATAMI fills + **SATIN columns** + **edge/center-walk underlay**
→ Design with objects, **contours**, stops), `POST /api/digitize` + params dialog, **object editing
(density/angle/underlay) with server-side `rebuild_design`** (`POST /api/designs/rebuild`), 16 tests, all e2e verified.
Quality notes: classical CV baseline (uniform background assumed); neural digitizing + more underlay
types (double-zigzag/parallel/contour) are Phase 8.

### Phases 4–10 (summaries)
- **4 Lettering:** 🟢 v1 done — PIL render → digitizer (tatami + underlay + holes); satin strokes = v1.1. **5 Production:** 🟢 done — convert + multi-format export + production package ZIP + brand map (§4.8).
  **6 Supabase:** apply `db/schema.sql`, auth, CRUD + Storage (**needs user keys**). **7 TrueView 3D:** 🟢 done — lit thread tubes + fabric, drag/zoom (§4.7; paint unverified).
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
Verify: `pytest -q` (63) + `npm test` (47). Manual: Open `tests/fixtures/sample.dst` **and** Digitize a PNG
(params dialog appears); click a stop or object, recolor, edit density/underlay → Apply, reorder ▲▼, undo, Export, Worksheet.

---

*End of STATUS.md — keep this file current. When in doubt, trust the code over this document, and fix the document.*
