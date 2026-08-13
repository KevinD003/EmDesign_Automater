"""Training-row extractor (v2 Part 64) — see docs/TRAINING-DATA-SPEC.md.

Emits one JSONL row per object/region with a declared provenance:
- STITCHIQ designs -> one row per DesignObject (provenance stitchiq_generated),
  with an artwork crop written next to the dataset;
- competitor machine files -> one row per stitch block (provenance
  machine_file_inference), decisions inferred and marked so.

Output: data/training/rows.jsonl + data/training/crops/*.png (data/ is
gitignored; the dataset is derived — rerun this script to rebuild it).

Rerun: .venv/bin/python scripts/extract_training_rows.py  (from apps/backend)
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import cv2

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from bench_competitor import CASES, block_features, infer_block_type, split_blocks

from app.models.design import enum_str
from app.services.digitizer import digitize_image
from app.services.embroidery_io import read_embroidery

OUT_DIR = BACKEND_ROOT / "data/training"

PROVENANCE = {
    "native_competitor_object",
    "machine_file_inference",
    "human_labeled",
    "stitchiq_generated",
}


def validate_row(row: dict) -> list[str]:
    """Schema check. Returns a list of violations (empty = valid)."""
    errs = []
    if row.get("schema_version") != 1:
        errs.append("schema_version must be 1")
    for key in ("row_id", "design_id", "source", "context", "decision", "stats"):
        if key not in row:
            errs.append(f"missing {key}")
    if row.get("provenance") not in PROVENANCE:
        errs.append(f"provenance {row.get('provenance')!r} not in {sorted(PROVENANCE)}")
    if row.get("decision_provenance") not in PROVENANCE:
        errs.append("decision_provenance missing or invalid")
    if not errs:
        if "bbox_mm" not in row["source"]:
            errs.append("source.bbox_mm required")
        if "stitch_type" not in row["decision"]:
            errs.append("decision.stitch_type required")
        if "label" not in row:
            errs.append("label required (null when no human annotation)")
        elif row["label"] is not None and row["provenance"] != "human_labeled":
            errs.append("non-null label requires provenance human_labeled")
    return errs


def _resample(points: list[tuple[float, float]], n: int = 64) -> list[list[float]]:
    if len(points) <= n:
        return [[round(x, 2), round(y, 2)] for x, y in points]
    step = len(points) / n
    return [[round(points[int(i * step)][0], 2), round(points[int(i * step)][1], 2)]
            for i in range(n)]


def _measured_angle(stitches, x0, y0, x1, y1) -> float | None:
    c = s2 = 0.0
    prev = None
    for s in stitches:
        if str(s.command) != "STITCH":
            prev = None
            continue
        if prev is not None:
            mx, my = (prev[0] + s.x) / 2, (prev[1] + s.y) / 2
            if x0 <= mx <= x1 and y0 <= my <= y1:
                dx, dy = s.x - prev[0], s.y - prev[1]
                length = math.hypot(dx, dy)
                if length > 1.0:
                    th = math.atan2(dy, dx)
                    c += math.cos(2 * th) * length
                    s2 += math.sin(2 * th) * length
        prev = (s.x, s.y)
    if c == 0 and s2 == 0:
        return None
    return round(math.degrees(0.5 * math.atan2(s2, c)) % 180.0, 1)


def rows_from_stitchiq(design, design_id: str, artwork_path: Path,
                       crops_dir: Path | None = None) -> list[dict]:
    """One row per DesignObject. Provenance: stitchiq_generated."""
    art = cv2.imread(str(artwork_path)) if artwork_path and artwork_path.exists() else None
    w_mm = float(design.width_mm) or 1.0
    rows = []
    for o in design.objects:
        if not o.contour:
            continue
        xs = [p.x for p in o.contour]
        ys = [p.y for p in o.contour]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        area = abs(sum(a.x * b.y - b.x * a.y for a, b in
                       zip(o.contour, o.contour[1:] + o.contour[:1]))) / 2
        crop_path = None
        if art is not None and crops_dir is not None:
            # mm -> artwork pixels via uniform width scale (artwork is the
            # digitizer's own input, so width maps 1:1 onto design width)
            sx = art.shape[1] / w_mm
            pad = 2.0
            cx0 = max(0, int((x0 - pad) * sx))
            cy0 = max(0, int((y0 - pad) * sx))
            cx1 = min(art.shape[1], int((x1 + pad) * sx))
            cy1 = min(art.shape[0], int((y1 + pad) * sx))
            if cx1 > cx0 and cy1 > cy0:
                crops_dir.mkdir(parents=True, exist_ok=True)
                crop_path = str(crops_dir / f"{design_id}-obj{o.sequence_order}.png")
                cv2.imwrite(crop_path, art[cy0:cy1, cx0:cx1])
        st = enum_str(o.stitch_type)
        ut = enum_str(o.underlay_type)
        rows.append({
            "schema_version": 1,
            "row_id": f"{design_id}/obj-{o.sequence_order}",
            "design_id": design_id,
            "provenance": "stitchiq_generated",
            "source": {
                "artwork_path": str(artwork_path) if artwork_path else None,
                "crop_path": crop_path,
                "bbox_mm": [round(v, 2) for v in (x0, y0, x1, y1)],
                "contour_mm": _resample([(p.x, p.y) for p in o.contour]),
                "hole_count": len(o.holes or []),
                "region_mm2": round(area, 2),
            },
            "context": {
                "n_objects_in_design": len(design.objects),
                "color_stop": o.color_stop,
                "palette_size": len(design.color_stops),
                "design_size_mm": [round(float(design.width_mm), 1),
                                   round(float(design.height_mm), 1)],
            },
            "decision": {
                "stitch_type": st,
                "angle_deg": round(float(o.stitch_angle), 1),
                "density": round(float(o.density), 3),
                "underlay": ut,
                "pull_comp_mm": round(float(o.pull_compensation or 0.0), 2),
                "has_flow_line": bool(o.flow_line),
                "has_flow_divide": bool(o.flow_divide),
            },
            "decision_provenance": "stitchiq_generated",
            "stats": {
                "stream_span": o.stream_span,
                "median_seg_mm": None,
                "measured_angle_deg": _measured_angle(design.stitches, x0, y0, x1, y1),
            },
            "label": None,
        })
    return rows


def rows_from_machine_file(design, design_id: str, file_path: Path) -> list[dict]:
    """One row per stitch block. Provenance: machine_file_inference."""
    rows = []
    for i, block in enumerate(split_blocks(design), 1):
        feat = block_features(block)
        xs = [p[0] for p in block]
        ys = [p[1] for p in block]
        rows.append({
            "schema_version": 1,
            "row_id": f"{design_id}/block-{i}",
            "design_id": design_id,
            "provenance": "machine_file_inference",
            "source": {
                "artwork_path": None,
                "crop_path": None,
                "bbox_mm": [round(min(xs), 2), round(min(ys), 2),
                            round(max(xs), 2), round(max(ys), 2)],
                "contour_mm": None,       # machine files carry no outlines
                "hole_count": None,       # not observable from a stream
                "region_mm2": feat["bbox_mm2"],
            },
            "context": {
                "n_objects_in_design": None,
                "color_stop": None,
                "palette_size": len(design.color_stops),
                "design_size_mm": [round(float(design.width_mm), 1),
                                   round(float(design.height_mm), 1)],
            },
            "decision": {
                "stitch_type": infer_block_type(feat),
                "angle_deg": feat["angle_deg"],
                "density": None,          # not observable
                "underlay": None,         # not observable
                "pull_comp_mm": None,     # not observable
                "has_flow_line": False,
                "has_flow_divide": False,
            },
            "decision_provenance": "machine_file_inference",
            "stats": {
                "stitch_count": feat["n"],
                "median_seg_mm": feat["median_len"],
                "measured_angle_deg": feat["angle_deg"],
            },
            "label": None,
        })
    return rows


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    crops = OUT_DIR / "crops"
    all_rows: list[dict] = []
    for case in CASES:
        if case["kind"] in ("fixture", "render_only"):
            if not case["artwork"].exists():
                print(f"skip {case['id']}: artwork missing")
                continue
            cv2.setRNGSeed(1234)
            d = digitize_image(case["artwork"].read_bytes(), "cotton", "100x100",
                               case["colors"])
            all_rows += rows_from_stitchiq(d, case["id"], case["artwork"], crops)
        elif case["kind"] == "machine_file":
            if not case["file"].exists():
                print(f"skip {case['id']}: file missing")
                continue
            d = read_embroidery(case["file"].read_bytes(), case["file"].suffix.lstrip("."))
            all_rows += rows_from_machine_file(d, case["id"], case["file"])

    bad = [(r["row_id"], errs) for r in all_rows if (errs := validate_row(r))]
    if bad:
        raise SystemExit(f"schema violations: {bad[:5]}")

    out = OUT_DIR / "rows.jsonl"
    with out.open("w") as f:
        for r in all_rows:
            f.write(json.dumps(r) + "\n")
    by_prov: dict[str, int] = {}
    for r in all_rows:
        by_prov[r["provenance"]] = by_prov.get(r["provenance"], 0) + 1
    print(f"wrote {len(all_rows)} rows to {out}  ({by_prov})")


if __name__ == "__main__":
    main()
