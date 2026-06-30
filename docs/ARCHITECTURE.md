# Architecture (condensed from spec §3)

STITCHIQ is a web-first, cloud-native embroidery design platform. Data flows:

```
user input (file / image / text)
   → backend processing (parse · digitize · optimize)
      → Design model (typed, shared FE↔BE)
         → canvas render + edit (frontend)
            → export (machine file + worksheet PDF)
```

## Frontend (TypeScript / React)
- **Canvas editor** — Konva (`StitchCanvas`): renders the `Stitch[]` map, objects, color stops.
- **TrueView** — Three.js / react-three-fiber (`TrueView3D`): realistic 3D thread simulation (stub).
- **Panels** — `ColorObjectList` (stitch sequence), `ThreadPalette` (brand filter), `PropertiesPanel` (per-object density/underlay/pull-comp).
- **Stitch Player** — animate the stitch sequence.
- **State** — Zustand (`designStore`); server state via TanStack Query; runtime validation via Zod.

## Backend (Python / FastAPI)
Microservice-style routers under `/api`, all currently stubs (`501`):
| Endpoint | Purpose | Spec |
|---|---|---|
| `POST /api/files/parse` | embroidery file → `Design` (pyembroidery) | §4.8 |
| `POST /api/convert` | format → format | §4.8 |
| `POST /api/digitize` | image → `Design` (OpenCV) | §4.2 |
| `POST /api/worksheet` | `Design` → production PDF (ReportLab) | §4.9 |
| `POST /api/export` / `…/validate` | production package + checks | §4.8 |
| `GET /api/threads`, `POST /api/threads/match` | thread catalog + nearest-Lab match | §4.4 |
| CRUD `/api/designs` | design persistence (Supabase) | §8 |

## AI layer (future)
Segmentation (SAM/U-Net), stitch-type classifier (CNN), path optimizer (graph + RL),
generative design (fine-tuned diffusion). **Out of scope for the scaffold** — classical
OpenCV/heuristics planned first, ML models layered in later (need GPU + training data).

## Deployment (target, spec §7)
Frontend → Vercel · Backend → Railway/Fly.io (Docker) · GPU inference → Modal/RunPod · DB → Supabase.
