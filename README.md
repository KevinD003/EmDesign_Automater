# 🧵 STITCHIQ

AI-powered embroidery design & digitizing platform. Monorepo **scaffold** built from
[`AI-Embroidery-Software-Prompt.md`](./AI-Embroidery-Software-Prompt.md).

> **Status: scaffold only.** Structure, configs, the shared typed data model, and stub
> endpoints/components exist and the app **boots** — but no features are implemented yet.
> Every feature is a typed stub with a `TODO` pointing at its spec section.

## Stack

| Layer | Language | Tech |
|---|---|---|
| Frontend | **TypeScript** | React + Vite, Konva (canvas), Three.js (TrueView), Zustand, TanStack Query, Zod |
| Backend | **Python** | FastAPI + Uvicorn, Pydantic v2; *feature libs* pyembroidery, OpenCV, Pillow, ReportLab, NumPy/SciPy |
| Data | PostgreSQL | Supabase (schema in [`db/schema.sql`](./db/schema.sql), **not applied**) |

> **"Not HTML":** all UI is TypeScript/TSX. The single `apps/frontend/index.html` is a
> ~12-line Vite bootstrap that mounts the React root — a framework requirement, not application HTML.

## Layout

```
apps/frontend   TypeScript / React / Vite   (app shell + stub panels)
apps/backend    Python / FastAPI            (stub routers + services)
db/schema.sql   PostgreSQL schema (spec §8)
docs/           architecture + data-model notes
```

The shared data model lives in two mirrored files — keep them in sync:
`apps/frontend/src/types/design.ts` ⇄ `apps/backend/app/models/design.py`.

## Setup & run

### Backend (Python 3.11+)
```bash
cd apps/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt           # core — boots the app
# pip install -r requirements-features.txt # heavy libs — needed when implementing stubs
uvicorn app.main:app --reload --port 8000
```
- Health: http://localhost:8000/health → `{"status":"ok"}`
- API docs: http://localhost:8000/docs (every stub endpoint, typed; stubs return `501`)

### Frontend (Node 20+)
```bash
npm install                  # root install (npm workspaces)
npm run dev:frontend         # Vite → http://localhost:5173
```

### Both at once
```bash
npm install && npm run backend:setup   # one-time
npm run dev                             # frontend + backend together
```

## Next steps (file-I/O + canvas slice)

1. `app/services/embroidery_io.py` → wire `POST /api/files/parse` (pyembroidery decode → `Design`).
2. `components/canvas/StitchCanvas.tsx` → render stitches in Konva; fill `ColorObjectList`.
3. `POST /api/export` (Design → .DST/.PES) and `POST /api/worksheet` (ReportLab PDF, spec §4.9).
4. `components/player/StitchPlayer.tsx` → animate the stitch sequence.

See [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) and [`docs/DATA-MODEL.md`](./docs/DATA-MODEL.md).
