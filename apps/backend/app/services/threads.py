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


def nearest_thread(target_hex: str, catalog: list[Thread]) -> Thread:
    """Return the catalogue thread closest to ``target_hex`` in Lab space.

    TODO (Phase 8, needs SciPy): hex -> Lab, k-d tree nearest neighbour.
    """
    raise NotImplementedError("nearest_thread — scaffold stub (spec §4.4, Phase 8)")
