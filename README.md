# 🧵 STITCHIQ

**AI-assisted embroidery digitizing studio, in your browser.** Upload an image and STITCHIQ turns
it into machine-ready embroidery: color separation, TATAMI fills, SATIN columns, underlay, pull
compensation — all re-editable on a 2D/3D canvas, then exported to real machine formats
(.DST/.PES/.JEF/.EXP/.VP3 and more). The digitizer is a **classical computer-vision pipeline**
(OpenCV k-means + contours), not a neural network — deterministic, fast, and honest about it.
Built from [`AI-Embroidery-Software-Prompt.md`](./AI-Embroidery-Software-Prompt.md).

## Quickstart

Prereqs: Node 18+, Python 3.11–3.14 (3.14 confirmed; reportlab/opencv need wheels — use 3.12 if a build fails).

```bash
# 1. Frontend deps (npm workspaces)
npm install

# 2. Backend venv + deps (core + tests, incl. reportlab, opencv, numpy, pillow)
cd apps/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cd ../..

# 3. Run both (backend :8000, frontend :5173; Vite proxies /api → backend)
npm run dev
```

- **App:** http://localhost:5173
- **API docs:** http://localhost:8000/docs

## Your first design in 5 minutes

1. Open http://localhost:5173 and click **Digitize** in the toolbar. It accepts
   `.png` / `.jpg` / `.jpeg` / `.bmp` / `.webp` — sample images live in
   `apps/backend/tests/fixtures/quality_bench/`.
2. In the dialog, pick your **Fabric** (cotton, polo/knit, denim, fleece, cap, towel — fleece and
   cotton produce visibly different densities), **Hoop (mm)** (100x100, 130x180, 200x200, 260x160),
   and **Max colors** (2–8). Click **Digitize**.
3. Your design appears on the canvas, and the **Quality** panel on the right auto-scores it
   0–100 with findings (long/tiny stitches, jump rate, hoop fit). No extra click needed.
4. Pick a format from the format dropdown (.DST / .PES / .JEF / .EXP / .VP3) and click
   **Export** to download a machine file — or **Package** for the full production ZIP
   (machine file + editable master + worksheet PDF + thread color-card PDF + preview PNG).

Other ways in:

- **Open** — load an existing machine file (`.dst .pes .pec .jef .exp .vp3 .vip .xxx .sew .u01`;
  try `apps/backend/tests/fixtures/sample.dst`) or a STITCHIQ master (`.stiq.json`).
- **Text** — lettering: type text, get stitches, with a letter-spacing control.

## What it does

Three ways in, full editing, every way out:

- **Open** a real machine file (`.DST/.PES/.JEF/.EXP/.VP3/…` via `pyembroidery`) **or** a STITCHIQ master (`.stiq.json`).
- **Digitize** a PNG/JPG image → k-means color separation → contour regions → TATAMI fills + SATIN columns for
  narrow shapes + edge/center-walk underlay + pull compensation + carved holes (letter counters). Objects keep
  their contours, so they're **re-editable**.
- **Text → stitches** (lettering) via a system font rendered through the digitizer.
- **Edit** on a Konva canvas: click a color stop or object; recolor / rename / reorder stops; snap a color to the
  nearest catalog thread (CIE-Lab); change an object's stitch type (incl. **appliqué**), density, angle, underlay,
  pull-comp → the server **rebuilds** the stitches from the stored contours. Undo/redo throughout.
- **Preview** in 2D or a lit **TrueView 3D** thread render (Three.js).
- **Validate** before export (hoop-fit is blocking, long stitches / many color changes warn).
- **Export** to any format, **convert** between formats, or download a full **production package ZIP**
  (machine file + master `.stiq.json` + worksheet PDF + thread color-card PDF + preview PNG + summary, with
  per-color thread length). **Save** designs in-browser (localStorage) and reload them.
- **Studio ⇄ Dashboard** nav with a metrics page (KPIs honestly show "—" until Phase 6; recent activity is real).

## Stack

| Layer | Language | Tech |
|---|---|---|
| Frontend | **TypeScript** | React + Vite · Konva (2D canvas) · Three.js (TrueView 3D) · Zustand · TanStack Query · vitest |
| Backend | **Python 3.14** | FastAPI + Uvicorn · Pydantic v2 · **pyembroidery** (45+ formats) · **OpenCV/NumPy/Pillow** (digitize) · **ReportLab** (PDF) · pytest |
| Data | PostgreSQL | Supabase schema in [`db/schema.sql`](./db/schema.sql) — applied to a live project; keyless in-memory fallback for local dev |

> All UI is TypeScript/TSX. The single `apps/frontend/index.html` is a ~12-line Vite bootstrap that mounts React.

The data model is mirrored in two files — **edit both together**:
`apps/frontend/src/types/design.ts` ⇄ `apps/backend/app/models/design.py`.

## Status — the honest version

- **Neural AI is gated** (Phases 8-neural/9 — needs GPU + data). Today's digitizer is a classical-CV
  baseline: deterministic OpenCV, no ML model.
- **Cloud sync works keyless** out of the box (in-memory fallback — data lost on backend restart).
  Point it at a Supabase project via `apps/backend/.env` for real persistence.
- **No physical machine sew-outs performed yet.** Exports are format-valid and validated in
  software; test on scrap fabric before production runs.
- See [`STATUS.md`](./STATUS.md) for the full changelog, feature matrix, roadmap, and risks.

## Test

```bash
cd apps/backend && python -m pytest tests -q     # 83 passed
npm test -w apps/frontend                         # vitest 57 passed
npm run typecheck                                 # tsc --noEmit, clean
```

## Docs

- [`docs/USER-GUIDE.md`](./docs/USER-GUIDE.md) — step-by-step guide to every tool and panel.
- [`docs/FAQ.md`](./docs/FAQ.md) — common questions and troubleshooting.
- [`STATUS.md`](./STATUS.md) — the living project log (changelog, feature matrix, roadmap, risks).
- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) · [`docs/DATA-MODEL.md`](./docs/DATA-MODEL.md)
- [`.github/workflows/ci.yml`](./.github/workflows/ci.yml) — CI config (written but **unverified** — no remote yet).
