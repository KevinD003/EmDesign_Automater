"""One-shot refactor tool: split the monolithic digitizer into a package.

R001. `app/services/digitizer.py` had grown to 4,731 lines around a single
1,032-line function, which made every later change riskier than it needed to be.

This tool is mechanical on purpose: it moves whole top-level definitions
without editing a single statement inside them, computes the imports each new
module needs from the AST, and leaves `digitizer.py` as a facade that re-exports
the full public surface so no caller or test changes.

The proof that it is a pure refactor is the four byte-identity stream locks in
`tests/test_swarm_perf_lock.py`: they sha256 the whole stitch stream, so if any
behaviour moved by a single coordinate the hashes change and the locks fail.

Run once:  .venv/bin/python scripts/split_digitizer.py --write
           .venv/bin/ruff check app/services/digitizer/ --fix

The ruff pass only sorts the generated import blocks; it reports no fixable
finding inside a moved body, and the count over `app/` is 12 before and after.
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import re

BACKEND = pathlib.Path(__file__).resolve().parents[1]
SRC = BACKEND / "app" / "services" / "digitizer.py"
PKG = BACKEND / "app" / "services" / "digitizer"

# Layer order: a module may only import from those before it.
ORDER = ["constants", "geometry", "skeleton", "columns", "fills", "satin",
         "underlay", "routing", "planning", "pipeline"]

# Explicit placement wins over the name heuristic. These are the functions whose
# names lie about where they belong (a "fill" helper that is really a generic
# polyline util, a "walk" that is really underlay, and so on).
OVERRIDE = {
    "_resample_closed": "geometry",
    "_resample_open": "geometry",
    "_warp_fit": "geometry",
    "_drop_floor_reversals": "geometry",
    "_subdivide_long": "geometry",
    "_edge_avoiding_angle": "fills",
    "_fill_angle": "fills",
    "_satin_border": "satin",
    "_fill_border": "satin",
    # Medial axis: thinning, then the branch graph built on it.
    "_zhang_suen_thin": "skeleton",
    "_thin_state": "skeleton",
    "_thin_terms": "skeleton",
    "_thin_step_ok": "skeleton",
    "_prune_spurs": "skeleton",
    "_skeleton_branches": "skeleton",
    "_skeleton_adjacency": "skeleton",
    "_order_branches": "skeleton",
    "_free_ends": "skeleton",
    "_extend_branch_ends": "skeleton",
    "_axis_branches": "skeleton",
    "_nearest_axis": "skeleton",
    # Column geometry: stations along an axis and the boundary they reach.
    "_column_ends": "columns",
    "_column_grid": "columns",
    "_axis_samples": "columns",
    "_axis_frame": "columns",
    "_arc_at": "columns",
    "_boundary_points": "columns",
    "_march_to_edge": "columns",
    "_raycast_columns": "columns",
    "_assign_boundary": "columns",
    "_pace_by_boundary": "columns",
    "_extreme_per_station": "columns",
    "_emit_columns": "columns",
    "_min_stitch_px": "columns",
    "_enforce_floor": "columns",
    "_edge_walk": "underlay",
    "_center_walk": "underlay",
    "_run_along": "underlay",
    "_manual_run": "underlay",
    "_axis_underlay": "underlay",
    "digitize_image": "pipeline",
    "rebuild_design": "pipeline",
    # Rebinds LIVE_STATE below with `global`, so it must live where it is defined.
    "set_penetration_floor": "constants",
}

# The one module-level name that is REBOUND at runtime rather than mutated in
# place. A plain `from constants import _PENETRATION_FLOOR_MM` would snapshot it
# at import time, so `set_penetration_floor()` would silently stop working in
# every module but its own. Reads outside `constants` are rewritten to go through
# the module object, which is the only edit this tool makes inside a body.
#
# `_CLASSIFICATION_LOG` and `_DROP_LOG` need no such treatment: they are only ever
# `.clear()`ed and `.append()`ed, so every module shares the one list object.
LIVE_STATE = "_PENETRATION_FLOOR_MM"


def heuristic(name: str) -> str:
    n = name
    if any(k in n for k in ("underlay",)):
        return "underlay"
    if any(k in n for k in ("satin", "column", "axis", "skeleton", "thin", "spur",
                            "branch", "boundary", "arc", "frame", "pace", "_extreme",
                            "free_ends", "raycast", "emit_columns", "enforce_floor",
                            "min_stitch")):
        return "satin"
    if any(k in n for k in ("fill", "scanline", "stagger")):
        return "fills"
    if any(k in n for k in ("route", "lock", "tie", "trim", "travel",
                            "merge_adjacent", "coalesce")):
        return "routing"
    if any(k in n for k in ("cluster", "palette", "sketch", "verify", "texture",
                            "speck", "linework", "substrate", "background", "ink",
                            "band_ratio", "interior", "angle")):
        return "planning"
    return "geometry"


def place(name: str) -> str:
    return OVERRIDE.get(name, heuristic(name))


HEADERS = {
    "constants": '"""Tunables for the digitizing pipeline (R001 split).\n\n'
                 "Every magic number lives here so a change is visible in one diff.\n"
                 'Values are unchanged from the pre-split module.\n"""',
    "geometry": '"""Geometry and stream primitives — the lowest layer (R001 split)."""',
    "skeleton": '"""Medial axis: Zhang-Suen thinning and the branch graph over it."""',
    "columns": '"""Column geometry: stations along an axis, the boundary they reach,\n'
               'pacing, and the penetration floor."""',
    "fills": '"""Fill generators: scanline, contour, spiral, radial, and fill angle."""',
    "satin": '"""Satin generators built on the column geometry, plus borders."""',
    "underlay": '"""Underlay generators and the walks they are built from."""',
    "routing": '"""Stitch-order routing: travel, ties, trims, colour merging."""',
    "planning": '"""Colour planning: clustering, sketch-verify, texture, linework."""',
    # Carries the original module docstring, which describes exactly this stage.
    "pipeline": '"""Auto-digitizing pipeline entry points: digitize_image, rebuild_design.\n\n'
                "Pipeline: decode -> scale to hoop -> k-means color quantization -> per-color\n"
                "masks -> contour regions -> scanline (boustrophedon) fill stitches -> Design\n"
                "with objects, color stops, and a machine-valid stitch stream (COLOR_CHANGE /\n"
                "JUMP / TRIM / END).\n\n"
                "Honest scope: the stitch stage is classical CV; the segmentation stage in\n"
                "front of it is a neural matte. cv2/numpy are imported lazily inside the\n"
                'functions so the app boots without them.\n"""',
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    src = SRC.read_text(encoding="utf-8")
    lines = src.split("\n")
    tree = ast.parse(src)

    defs: dict[str, tuple[int, int]] = {}
    consts: list[tuple[str, int, int]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = min([d.lineno for d in node.decorator_list] + [node.lineno])
            defs[node.name] = (start, node.end_lineno)
        elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            consts.append((node.targets[0].id, node.lineno, node.end_lineno))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            # FABRIC_PROFILES and the three runtime logs are annotated assignments.
            consts.append((node.target.id, node.lineno, node.end_lineno))

    mod = {name: place(name) for name in defs}
    const_names = {c[0] for c in consts}

    # Verify the layering before writing anything.
    rank = {m: i for i, m in enumerate(ORDER)}
    problems = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for sub in ast.walk(node):
            if (isinstance(sub, ast.Name) and sub.id in defs and sub.id != node.name
                    and rank[mod[sub.id]] > rank[mod[node.name]]):
                problems.append(f"{node.name} [{mod[node.name]}] -> {sub.id} [{mod[sub.id]}]")
    if problems:
        print("LAYERING VIOLATIONS — fix OVERRIDE before writing:")
        for p in sorted(set(problems)):
            print("   ", p)
        raise SystemExit(1)
    print("layering: clean (no back-edges)")

    # Comments immediately above a definition belong with it.
    # Comments travel with the definition they document, and none may be dropped.
    # A comment block ABOVE a definition is its header. A block BELOW one, with no
    # blank line between, is a trailing note on that same definition (the inline
    # continuations under `MIN_REGION_MM2`, the Chaikin sweep under
    # `SMOOTH_MIN_POINTS`, the outward-bias note under `UNDERLAY_REPAIR_PASSES`).
    # Header capture wins where the two would overlap, so nothing is duplicated.
    def lead(start: int) -> int:
        i = start
        while i - 1 >= 1 and lines[i - 2].lstrip().startswith("#"):
            i -= 1
        return i

    spans = [(lead(a), b, a) for a, b in defs.values()] + [(lead(a), b, a) for _, a, b in consts]
    spans.sort()
    leads = {s for s, _, _ in spans}
    ends: dict[int, int] = {}
    for s, e, _ in spans:
        j = e
        while j + 1 <= len(lines) and (j + 1) not in leads and lines[j].lstrip().startswith("#"):
            j += 1
        ends[s] = j

    def block(start: int, end: int) -> str:
        """Source of one definition, 1-indexed inclusive, with the comments it owns."""
        s = lead(start)
        return "\n".join(lines[s - 1:ends[s]])

    bodies: dict[str, list[str]] = {m: [] for m in ORDER}
    for name, (a, b) in sorted(defs.items(), key=lambda kv: kv[1][0]):
        bodies[mod[name]].append(block(a, b))
    # Constants keep source order, with any comment block above them, and come
    # before the one def that lives here (the setter that rebinds LIVE_STATE).
    bodies["constants"] = [block(a, b) for _, a, b in consts] + bodies["constants"]

    # Nothing but the header may be left behind. Checked, not assumed.
    carried = set()
    for s, _, _ in spans:
        carried.update(range(s, ends[s] + 1))
    header_end = max(n.end_lineno for n in tree.body[:5])
    lost = [i for i in range(header_end + 1, len(lines) + 1)
            if i not in carried and lines[i - 1].strip()]
    if lost:
        print(f"SOURCE LOSS — {len(lost)} line(s) belong to no module:")
        for i in lost[:20]:
            print(f"    L{i}: {lines[i - 1][:80]}")
        raise SystemExit(1)
    print(f"coverage: every line below the header carried ({len(carried)} lines)")

    # What each module needs from the others.
    def referenced(text: str) -> set[str]:
        try:
            t = ast.parse(text)
        except SyntaxError:
            return set()
        return {n.id for n in ast.walk(t) if isinstance(n, ast.Name)}

    written = {}
    rewrites = 0
    for m in ORDER:
        text = "\n\n\n".join(bodies[m])
        if m != "constants" and LIVE_STATE in text:
            text, n = re.subn(rf"(?<![\w.]){LIVE_STATE}\b", f"constants.{LIVE_STATE}", text)
            rewrites += n
            print(f"  {m}: {n} read(s) of {LIVE_STATE} routed through the module object")
        used = referenced(text)
        header = [HEADERS[m], "", "from __future__ import annotations", ""]
        if "pairwise" in used:
            header.append("from itertools import pairwise")
        model_names = ["ColorStop", "ConnectMethod", "Design", "DesignObject",
                       "Point", "Stitch", "StitchType", "UnderlayType"]
        need_models = sorted(n for n in model_names if n in used)
        if need_models:
            header.append(f"from app.models.design import {', '.join(need_models)}")
        if "segmentation" in used:
            header.append("from app.services import segmentation")
        if f"constants.{LIVE_STATE}" in text:
            header.append("from app.services.digitizer import constants")
        if m != "constants":
            need_c = sorted(n for n in const_names if n in used)
            if need_c:
                header.append("from app.services.digitizer.constants import (")
                header += [f"    {n}," for n in need_c]
                header.append(")")
        for earlier in ORDER[: ORDER.index(m)]:
            if earlier == "constants":
                continue
            need = sorted(n for n, mm in mod.items() if mm == earlier and n in used)
            if need:
                header.append(f"from app.services.digitizer.{earlier} import (")
                header += [f"    {n}," for n in need]
                header.append(")")
        written[m] = "\n".join(header) + "\n\n\n" + text + "\n"

    # Facade: re-export everything the old module exposed.
    export_consts = sorted(const_names - {LIVE_STATE})
    public = sorted(set(defs) | set(export_consts))
    facade = ['"""Digitizing pipeline — facade over the split package (R001).',
              "",
              "The implementation lives in sibling modules; this keeps the import path",
              "`app.services.digitizer` working unchanged for every caller and test.",
              '"""',
              "",
              "from __future__ import annotations",
              "",
              "from app.services.digitizer import constants"]
    for m in ORDER:
        names = sorted(n for n, mm in mod.items() if mm == m)
        if m == "constants":
            names = sorted(set(names) | set(export_consts))
        if not names:
            continue
        facade.append(f"from app.services.digitizer.{m} import (")
        facade += [f"    {n}," for n in names]
        facade.append(")")
    facade += [
        "",
        "",
        "def __getattr__(name: str):",
        f'    """Keep `digitizer.{LIVE_STATE}` live rather than a snapshot.',
        "",
        "    `set_penetration_floor()` rebinds it inside `constants`, so re-exporting",
        "    it eagerly would freeze the facade at the import-time value.",
        '    """',
        f'    if name == "{LIVE_STATE}":',
        f"        return constants.{LIVE_STATE}",
        "    raise AttributeError(name)",
    ]
    facade.append("")
    facade.append("__all__ = [")
    facade += [f'    "{n}",' for n in public]
    facade.append("]")
    written["__init__"] = "\n".join(facade) + "\n"

    for m, text in written.items():
        print(f"  {m:11s} {len(text.splitlines()):5d} lines")
    if not args.write:
        print("\n(dry run — pass --write to create the package)")
        return
    PKG.mkdir(exist_ok=True)
    for m, text in written.items():
        (PKG / f"{m}.py").write_text(text, encoding="utf-8")
    SRC.unlink()
    print(f"\nwrote {len(written)} modules to {PKG}, removed the monolith")


if __name__ == "__main__":
    main()
