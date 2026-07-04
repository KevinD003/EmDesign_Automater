# 🧵 STITCHIQ

AI-assisted embroidery design & digitizing platform — a working, browser-based embroidery studio.
Built from [`AI-Embroidery-Software-Prompt.md`](./AI-Embroidery-Software-Prompt.md).

> **Status:** Phases 0–5 + 7 complete (see [`STATUS.md`](./STATUS.md) for the full changelog and
> feature matrix). Backend **63** tests, frontend **47** tests, all green. Two areas remain gated:
> **cloud sync/auth** (Phase 6 — needs a Supabase project + keys) and **neural AI** (Phases 8–9 — needs GPU + data).
> The digitizer today is a classical-CV baseline; the app has **not** been eyeballed in a browser by the authors
> (logic is unit-/e2e-tested, in-browser paint isn't — see STATUS §12).

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
| Data | PostgreSQL | Supabase schema in [`db/schema.sql`](./db/schema.sql) — **written, not applied** (Phase 6) |

> All UI is TypeScript/TSX. The single `apps/frontend/index.html` is a ~12-line Vite bootstrap that mounts React.

The data model is mirrored in two files — **edit both together**:
`apps/frontend/src/types/design.ts` ⇄ `apps/backend/app/models/design.py`.

## Setup & run

```bash
# Frontend deps (npm workspaces)
npm install

# Backend venv + deps  (Python 3.11–3.14; 3.14 confirmed. reportlab/opencv need wheels — use 3.12 if a build fails)
cd apps/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt   # core + tests (incl. reportlab, opencv, numpy, pillow)
cd ../..

# Run both (backend :8000, frontend :5173; Vite proxies /api → backend)
npm run dev
```
- App: http://localhost:5173 — open a design (`apps/backend/tests/fixtures/sample.dst`) or digitize an image.
- API docs: http://localhost:8000/docs

## Test

```bash
cd apps/backend && python -m pytest tests -q     # 63 passed
npm test -w apps/frontend                         # vitest 47 passed
npm run typecheck                                 # tsc --noEmit, clean
```

## Docs

- [`STATUS.md`](./STATUS.md) — the living project log (changelog, feature matrix, roadmap, risks). **Read this first.**
- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) · [`docs/DATA-MODEL.md`](./docs/DATA-MODEL.md)
- [`.github/workflows/ci.yml`](./.github/workflows/ci.yml) — CI config (written but **unverified** — no remote yet).
