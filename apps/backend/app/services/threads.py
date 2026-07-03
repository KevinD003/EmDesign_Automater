"""Thread color management (spec §4.4).

``list_threads`` loads the bundled sample catalog. ``nearest_thread`` (Lab k-d tree)
is still a stub — it lands with SciPy in Phase 8.
"""

from __future__ import annotations

import json
import os

from app.models.design import Thread

_DATA = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "threads_madeira_sample.json")


def load_catalog() -> list[Thread]:
    """Load the bundled thread catalog (spec §4.4 / §8)."""
    with open(_DATA, encoding="utf-8") as fh:
        raw = json.load(fh)
    brand = raw.get("brand", "Unknown")
    product_line = raw.get("productLine", "")
    return [
        Thread(
            brand=brand,
            product_line=product_line,
            catalog_number=str(t.get("catalogNumber", "")),
            color_name=t.get("colorName", ""),
            hex=t.get("hex", "#000000"),
            weight=t.get("weight"),
            fiber_type=t.get("fiberType"),
        )
        for t in raw.get("threads", [])
    ]


def list_threads(brand: str | None = None) -> list[Thread]:
    """List catalog threads, optionally filtered by brand."""
    catalog = load_catalog()
    if brand:
        catalog = [t for t in catalog if t.brand.lower() == brand.lower()]
    return catalog


def hex_to_lab(hex_color: str) -> tuple[float, float, float]:
    """Convert #RRGGBB → CIE L*a*b* (D65). Pure Python — no NumPy/SciPy needed."""
    h = hex_color.strip().lstrip("#")
    if len(h) != 6:
        raise ValueError(f"Bad hex color: {hex_color!r}")
    try:
        r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError as exc:
        raise ValueError(f"Bad hex color: {hex_color!r}") from exc

    def lin(c: float) -> float:
        c /= 255.0
        return ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92

    rl, gl, bl = lin(r), lin(g), lin(b)
    # linear sRGB → XYZ (D65), then normalize by the D65 white point
    x = (rl * 0.4124 + gl * 0.3576 + bl * 0.1805) / 0.95047
    y = rl * 0.2126 + gl * 0.7152 + bl * 0.0722
    z = (rl * 0.0193 + gl * 0.1192 + bl * 0.9505) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def nearest_thread(target_hex: str, catalog: list[Thread]) -> Thread:
    """Return the catalogue thread closest to ``target_hex`` in Lab space (CIE76 ΔE)."""
    if not catalog:
        raise ValueError("Thread catalog is empty")
    tl, ta, tb = hex_to_lab(target_hex)  # raises ValueError on bad hex

    def dist2(thread: Thread) -> float:
        if thread.lab is not None:
            L, a, b = thread.lab.l, thread.lab.a, thread.lab.b
        else:
            L, a, b = hex_to_lab(thread.hex)
        return (L - tl) ** 2 + (a - ta) ** 2 + (b - tb) ** 2

    return min(catalog, key=dist2)
