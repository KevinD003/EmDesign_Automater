# Data model (the scaffold's one piece of real code)

Mirrored field-for-field in two files. **Edit both together.**
- TypeScript: [`apps/frontend/src/types/design.ts`](../apps/frontend/src/types/design.ts)
- Pydantic v2: [`apps/backend/app/models/design.py`](../apps/backend/app/models/design.py)

The Python models use a camelCase alias generator, so JSON on the wire matches the TS
interfaces exactly (e.g. Python `width_mm` ⇄ JSON `widthMm` ⇄ TS `widthMm`).

## Entities (derived from spec §8, §4.3, §4.8, §4.9)

| Type | Meaning |
|---|---|
| `Stitch` | `{ x, y, command }`, command ∈ STITCH/JUMP/TRIM/COLOR_CHANGE/STOP/END. Raw list pyembroidery emits + Konva renders. |
| `StitchType` | enum: Satin, Tatami(Fill), Running ×3, Backstitch, Zigzag, Motif, Appliqué, … (§4.3) |
| `UnderlayType` | enum: None, CenterWalk, EdgeWalk, DoubleZigzag, Parallel, Contour (§4.3) |
| `ConnectMethod` | enum: Trim, TravelRun, Jump |
| `Thread` | brand, productLine, catalogNumber, colorName, hex, lab{l,a,b}, weight, fiberType (§8 `thread_database`) |
| `ColorStop` | stopNumber, threadBrand, catalogNumber, threadName, hex, stitchCount (§8 `color_stops`) |
| `DesignObject` | sequenceOrder, name, stitchType, colorStop, density, stitchAngle, underlayType, pullCompensation, entry/exitPoint, connectMethod, stitchCount (§8 `design_objects`) |
| `Design` | name, width/heightMm, hoopSize, fabricType, stitchCount, colorStops[], objects[], stitches[], version, status, createdAt (§8 `designs`) |
| `Worksheet` | derived production view (§4.9) |
| `ValidationReport` | `{ passed, issues[], warnings[] }` (§4.8) |
| `ConvertRequest/Response` | format conversion payloads (§4.8) |

The proprietary `.STIQ` "master file" (spec §4.8) is represented as serialized `Design`
JSON in this scaffold — no binary format yet.
