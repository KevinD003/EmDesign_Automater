"""Auto-digitizing pipeline v1 — classical OpenCV, no ML (spec §4.2).

Pipeline: decode → scale to hoop → k-means color quantization → per-color masks →
contour regions → scanline (boustrophedon) fill stitches → Design with objects,
color stops, and a machine-valid stitch stream (COLOR_CHANGE / JUMP / TRIM / END).

Honest scope: this is the approximate classical-CV baseline (Phase 3). Satin
detection, underlay, pull compensation, and neural quality land in Phase 8.
cv2/numpy are imported lazily so the app boots without them.
"""

from __future__ import annotations

from app.models.design import (
    ColorStop,
    ConnectMethod,
    Design,
    DesignObject,
    Point,
    Stitch,
    StitchType,
    UnderlayType,
)

# Tunables (mm unless noted) — see spec "Quick Reference" table.
ROW_SPACING_MM = 0.6      # fill row pitch (~4-6 stitches/mm density class)
MAX_STITCH_MM = 6.0       # subdivide longer runs (machine safety << 12.7mm)
MIN_REGION_MM2 = 4.0      # drop specks smaller than this
CONNECT_MM = 3.0          # row-to-row travel below this = stitch, else JUMP
DEFAULT_MAX_COLORS = 6

# Satin classification (spec: min column 0.8mm, max width 10-12mm; we cap at 4mm
# where satin clearly beats tatami, and require an elongated shape).
SATIN_MIN_W_MM = 0.8
SATIN_MAX_W_MM = 4.0
SATIN_ASPECT = 2.5
SATIN_SPACING_MM = 0.4    # zigzag pitch along the column


def _parse_hoop(hoop_size: str) -> tuple[float, float]:
    try:
        w, h = hoop_size.lower().replace("mm", "").split("x")
        return max(float(w), 10.0), max(float(h), 10.0)
    except Exception:  # noqa: BLE001 - bad input → default hoop
        return 100.0, 100.0


def _is_background(center_bgr, corners_bgr) -> bool:
    """A cluster is background if it sits close to the average corner color."""
    import numpy as np

    return bool(np.linalg.norm(center_bgr.astype(float) - corners_bgr.astype(float)) < 40.0)


def digitize_image(
    data: bytes,
    fabric_type: str = "cotton",
    hoop_size: str = "100x100",
    max_colors: int = DEFAULT_MAX_COLORS,
) -> Design:
    """Convert an image into a stitch Design (classical CV baseline)."""
    import cv2
    import numpy as np

    buf = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image (expected PNG/JPEG/BMP/WebP)")

    hoop_w, hoop_h = _parse_hoop(hoop_size)
    ih, iw = img.shape[:2]
    mm_per_px = min(hoop_w / iw, hoop_h / ih) * 0.9  # 90% of hoop
    # Work at a bounded resolution for speed; keep mm scale consistent.
    if max(iw, ih) > 400:
        f = 400.0 / max(iw, ih)
        img = cv2.resize(img, (int(iw * f), int(ih * f)), interpolation=cv2.INTER_AREA)
        mm_per_px /= f
        ih, iw = img.shape[:2]

    # K-means quantization in BGR.
    k = max(2, min(int(max_colors) + 1, 8))  # +1 slot for background
    Z = img.reshape(-1, 3).astype(np.float32)
    _, labels, centers = cv2.kmeans(
        Z, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0), 3, cv2.KMEANS_PP_CENTERS
    )
    labels = labels.reshape(ih, iw)
    centers = centers.astype(np.uint8)

    corners = np.array(
        [img[0, 0], img[0, -1], img[-1, 0], img[-1, -1]], dtype=np.float32
    ).mean(axis=0)

    # Collect foreground clusters, darkest-first stitching order (spec §4.2).
    clusters = [
        (int(c.astype(int).sum()), idx, c) for idx, c in enumerate(centers) if not _is_background(c, corners)
    ]
    clusters.sort(key=lambda t: t[0])
    if not clusters:  # image was all "background" — keep the darkest cluster anyway
        darkest = min(range(len(centers)), key=lambda i: int(centers[i].astype(int).sum()))
        clusters = [(0, darkest, centers[darkest])]

    row_px = max(1, round(ROW_SPACING_MM / mm_per_px))
    max_step_px = max(2, round(MAX_STITCH_MM / mm_per_px))
    min_area_px = MIN_REGION_MM2 / (mm_per_px * mm_per_px)
    connect_px = CONNECT_MM / mm_per_px

    stitches: list[Stitch] = []
    color_stops: list[ColorStop] = []
    objects: list[DesignObject] = []
    seq = 0

    for stop_no, (_, cluster_idx, center) in enumerate(clusters, start=1):
        mask = (labels == cluster_idx).astype(np.uint8) * 255
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        b, g, r = (int(v) for v in center)
        hexcol = f"#{r:02x}{g:02x}{b:02x}"

        if stop_no > 1 and stitches:
            prev = stitches[-1]
            stitches.append(Stitch(x=prev.x, y=prev.y, command="COLOR_CHANGE"))

        stop_start = len(stitches)
        for contour in contours:
            if cv2.contourArea(contour) < min_area_px:
                continue
            region = np.zeros_like(mask)
            cv2.drawContours(region, [contour], -1, 255, thickness=cv2.FILLED)

            # Narrow elongated region → satin column; otherwise tatami fill.
            rect = cv2.minAreaRect(contour)
            w_mm = min(rect[1]) * mm_per_px
            l_mm = max(rect[1]) * mm_per_px
            is_satin = SATIN_MIN_W_MM <= w_mm <= SATIN_MAX_W_MM and l_mm / max(w_mm, 0.01) >= SATIN_ASPECT
            if is_satin:
                satin_step_px = max(1, round(SATIN_SPACING_MM / mm_per_px))
                pts = _satin_zigzag(region, rect, satin_step_px, connect_px)
            else:
                pts = _scanline_fill(region, row_px, max_step_px, connect_px)
            if len(pts) < 2:
                continue
            obj_start = len(stitches)
            if stitches and stitches[-1].command != "COLOR_CHANGE":
                stitches.append(Stitch(x=stitches[-1].x, y=stitches[-1].y, command="TRIM"))
                stitches.append(Stitch(x=pts[0][0] * mm_per_px, y=pts[0][1] * mm_per_px, command="JUMP"))
            for (x, y, jump) in pts:
                stitches.append(
                    Stitch(x=x * mm_per_px, y=y * mm_per_px, command="JUMP" if jump else "STITCH")
                )
            seq += 1
            count = len(stitches) - obj_start
            outline = [
                Point(x=float(px_) * mm_per_px, y=float(py_) * mm_per_px)
                for px_, py_ in contour.reshape(-1, 2)
            ]
            objects.append(
                DesignObject(
                    sequence_order=seq,
                    name=f"{'Satin' if is_satin else 'Fill'} {seq} ({hexcol})",
                    stitch_type=StitchType.SATIN if is_satin else StitchType.TATAMI,
                    color_stop=stop_no,
                    density=1.0 / (SATIN_SPACING_MM if is_satin else ROW_SPACING_MM),
                    stitch_angle=round(float(rect[2]), 1) if is_satin else 0.0,
                    underlay_type=UnderlayType.NONE,
                    pull_compensation=0.0,
                    entry_point=Point(x=pts[0][0] * mm_per_px, y=pts[0][1] * mm_per_px),
                    exit_point=Point(x=pts[-1][0] * mm_per_px, y=pts[-1][1] * mm_per_px),
                    connect_method=ConnectMethod.TRIM,
                    stitch_count=count,
                    contour=outline,
                )
            )

        color_stops.append(
            ColorStop(
                stop_number=stop_no,
                thread_brand="Auto",
                catalog_number="",
                thread_name=f"Color {stop_no}",
                hex=hexcol,
                stitch_count=len(stitches) - stop_start,
            )
        )

    if stitches:
        last = stitches[-1]
        stitches.append(Stitch(x=last.x, y=last.y, command="END"))

    xs = [s.x for s in stitches if s.command == "STITCH"] or [0.0]
    ys = [s.y for s in stitches if s.command == "STITCH"] or [0.0]

    return Design(
        name="Digitized image",
        width_mm=round(max(xs) - min(xs), 2),
        height_mm=round(max(ys) - min(ys), 2),
        hoop_size=hoop_size,
        fabric_type=fabric_type,
        stitch_count=sum(1 for s in stitches if s.command == "STITCH"),
        color_stops=color_stops,
        objects=objects,
        stitches=stitches,
        status="digitized",
    )


def _scanline_fill(region, row_px: int, max_step_px: int, connect_px: float):
    """Boustrophedon scanline fill of a filled-contour mask.

    Returns [(x_px, y_px, is_jump)] — stitch points row by row, alternating
    direction; long runs subdivided; far row-to-row moves flagged as jumps.
    """
    import numpy as np

    pts: list[tuple[float, float, bool]] = []
    h = region.shape[0]
    left_to_right = True
    for y in range(0, h, row_px):
        cols = np.flatnonzero(region[y])
        if cols.size == 0:
            continue
        # Split the row into contiguous runs (handles concave shapes/holes).
        splits = np.flatnonzero(np.diff(cols) > 1)
        runs = np.split(cols, splits + 1)
        segs = [(int(rn[0]), int(rn[-1])) for rn in runs if rn.size >= 2]
        if not segs:
            continue
        segs.sort(key=lambda s: s[0], reverse=not left_to_right)
        for x0, x1 in segs:
            a, b = (x0, x1) if left_to_right else (x1, x0)
            first = not pts or _dist(pts[-1], (a, y)) > connect_px
            pts.append((float(a), float(y), first))
            n = max(1, round(abs(b - a) / max_step_px))
            for i in range(1, n + 1):
                pts.append((a + (b - a) * i / n, float(y), False))
        left_to_right = not left_to_right
    return pts


def _dist(p, q) -> float:
    return float(((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5)


def _satin_zigzag(region, rect, step_px: int, connect_px: float):
    """Satin column for a narrow elongated region.

    Rotates the mask so the region's long axis is horizontal, walks columns at
    ``step_px``, emits alternating top/bottom edge points (the zigzag), then maps
    the points back through the inverse rotation. Returns [(x_px, y_px, is_jump)].
    """
    import cv2
    import numpy as np

    (cx, cy), (rw, rh), ang = rect
    if rw < rh:  # normalize: long axis → horizontal
        ang += 90.0
    M = cv2.getRotationMatrix2D((float(cx), float(cy)), ang, 1.0)
    h, w = region.shape
    rot = cv2.warpAffine(region, M, (w, h))
    Minv = cv2.invertAffineTransform(M)

    pts: list[tuple[float, float, bool]] = []
    top = True
    for x in range(0, w, step_px):
        rows = np.flatnonzero(rot[:, x])
        if rows.size < 2:
            continue
        y0, y1 = int(rows[0]), int(rows[-1])
        pair = ((x, y0), (x, y1)) if top else ((x, y1), (x, y0))
        for i, (px_, py_) in enumerate(pair):
            X = Minv[0, 0] * px_ + Minv[0, 1] * py_ + Minv[0, 2]
            Y = Minv[1, 0] * px_ + Minv[1, 1] * py_ + Minv[1, 2]
            # Jump only on a gap BETWEEN columns (i == 0); the cross-width zig
            # itself (i == 1) is always a stitch, whatever the column width.
            jump = i == 0 and bool(pts) and _dist(pts[-1], (X, Y)) > connect_px
            pts.append((float(X), float(Y), jump))
        top = not top
    if pts:
        pts[0] = (pts[0][0], pts[0][1], True)  # enter the column with a jump
    return pts


def _scanline_angled(region, angle_deg: float, row_px: int, max_step_px: int, connect_px: float):
    """Scanline fill at an arbitrary angle: rotate the mask so rows are horizontal,
    fill, then map points back through the inverse rotation."""
    import cv2
    import numpy as np

    if abs(angle_deg) < 0.5:
        return _scanline_fill(region, row_px, max_step_px, connect_px)
    h, w = region.shape
    M = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), float(angle_deg), 1.0)
    rot = cv2.warpAffine(region, M, (w, h))
    Minv = cv2.invertAffineTransform(M)
    out = []
    for x, y, jump in _scanline_fill(rot, row_px, max_step_px, connect_px):
        X = Minv[0, 0] * x + Minv[0, 1] * y + Minv[0, 2]
        Y = Minv[1, 0] * x + Minv[1, 1] * y + Minv[1, 2]
        out.append((float(X), float(Y), jump))
    return out


def rebuild_design(design: Design) -> Design:
    """Regenerate the whole stitch stream from object contours + parameters.

    Every object must carry a ``contour`` (only digitized designs do). Objects are
    re-filled with their CURRENT stitch_type / density / stitch_angle, so editing a
    parameter and rebuilding applies the edit. Raises ValueError if not regenerable.
    """
    import cv2
    import numpy as np

    objs = sorted(design.objects, key=lambda o: o.sequence_order)
    if not objs:
        raise ValueError("Design has no objects to rebuild (imported stitch files are not regenerable)")
    if any(not o.contour for o in objs):
        raise ValueError("Some objects have no contour — design is not regenerable")

    xs = [p.x for o in objs for p in o.contour]
    ys = [p.y for o in objs for p in o.contour]
    minx, miny = min(xs), min(ys)
    w_mm = max(max(xs) - minx, 1.0)
    h_mm = max(max(ys) - miny, 1.0)
    px_per_mm = min(4.0, 800.0 / max(w_mm, h_mm))  # ≤800px canvas
    mm_per_px = 1.0 / px_per_mm
    pad = 2
    cw, ch = int(w_mm * px_per_mm) + 2 * pad, int(h_mm * px_per_mm) + 2 * pad

    def to_px(p: Point) -> tuple[int, int]:
        return (int((p.x - minx) * px_per_mm) + pad, int((p.y - miny) * px_per_mm) + pad)

    def to_mm(x: float, y: float) -> tuple[float, float]:
        return ((x - pad) * mm_per_px + minx, (y - pad) * mm_per_px + miny)

    max_step_px = max(2, round(MAX_STITCH_MM / mm_per_px))
    connect_px = CONNECT_MM / mm_per_px

    stitches: list[Stitch] = []
    new_objects: list[DesignObject] = []
    stop_counts: dict[int, int] = {}

    ordered_stops = sorted(design.color_stops, key=lambda c: c.stop_number)
    for stop_i, stop in enumerate(ordered_stops):
        if stop_i > 0 and stitches:
            prev = stitches[-1]
            stitches.append(Stitch(x=prev.x, y=prev.y, command="COLOR_CHANGE"))
        stop_start = len(stitches)

        for o in (ob for ob in objs if ob.color_stop == stop.stop_number):
            mask = np.zeros((ch, cw), np.uint8)
            poly = np.array([to_px(p) for p in o.contour], np.int32)
            cv2.fillPoly(mask, [poly], 255)

            st = o.stitch_type.value if hasattr(o.stitch_type, "value") else o.stitch_type
            spacing_mm = 1.0 / max(float(o.density) or 1.0, 0.2)
            spacing_px = max(1, round(spacing_mm / mm_per_px))
            if st == "SATIN":
                rect = cv2.minAreaRect(poly)
                pts = _satin_zigzag(mask, rect, spacing_px, connect_px)
            else:
                pts = _scanline_angled(mask, float(o.stitch_angle), spacing_px, max_step_px, connect_px)
            if len(pts) < 2:
                continue

            if stitches and stitches[-1].command != "COLOR_CHANGE":
                last = stitches[-1]
                stitches.append(Stitch(x=last.x, y=last.y, command="TRIM"))
                ex, ey = to_mm(pts[0][0], pts[0][1])
                stitches.append(Stitch(x=ex, y=ey, command="JUMP"))
            obj_start = len(stitches)
            for x, y, jump in pts:
                mx, my = to_mm(x, y)
                stitches.append(Stitch(x=mx, y=my, command="JUMP" if jump else "STITCH"))

            entry = to_mm(pts[0][0], pts[0][1])
            exit_ = to_mm(pts[-1][0], pts[-1][1])
            new_objects.append(
                o.model_copy(
                    update={
                        "stitch_count": len(stitches) - obj_start,
                        "entry_point": Point(x=entry[0], y=entry[1]),
                        "exit_point": Point(x=exit_[0], y=exit_[1]),
                    }
                )
            )
        stop_counts[stop.stop_number] = len(stitches) - stop_start

    if stitches:
        last = stitches[-1]
        stitches.append(Stitch(x=last.x, y=last.y, command="END"))

    sxs = [s.x for s in stitches if s.command == "STITCH"] or [0.0]
    sys_ = [s.y for s in stitches if s.command == "STITCH"] or [0.0]
    new_stops = [
        c.model_copy(update={"stitch_count": stop_counts.get(c.stop_number, 0)}) for c in ordered_stops
    ]
    return design.model_copy(
        update={
            "stitches": stitches,
            "objects": new_objects,
            "color_stops": new_stops,
            "stitch_count": sum(1 for s in stitches if s.command == "STITCH"),
            "width_mm": round(max(sxs) - min(sxs), 2),
            "height_mm": round(max(sys_) - min(sys_), 2),
        }
    )
