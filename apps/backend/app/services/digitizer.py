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
            objects.append(
                DesignObject(
                    sequence_order=seq,
                    name=f"Region {seq} ({hexcol})",
                    stitch_type=StitchType.TATAMI,
                    color_stop=stop_no,
                    density=1.0 / ROW_SPACING_MM,  # rows per mm
                    stitch_angle=0.0,
                    underlay_type=UnderlayType.NONE,
                    pull_compensation=0.0,
                    entry_point=Point(x=pts[0][0] * mm_per_px, y=pts[0][1] * mm_per_px),
                    exit_point=Point(x=pts[-1][0] * mm_per_px, y=pts[-1][1] * mm_per_px),
                    connect_method=ConnectMethod.TRIM,
                    stitch_count=count,
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
