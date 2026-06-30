"""Thread color matching (spec §4.4).

Scaffold stub. SciPy/NumPy are imported lazily inside the functions.
"""

from __future__ import annotations

from app.models.design import Thread


def nearest_thread(target_hex: str, catalog: list[Thread]) -> Thread:
    """Return the catalogue thread closest to ``target_hex`` in Lab space.

    TODO:
        # hex -> Lab, build k-d tree (scipy.spatial.cKDTree) over catalog Lab values,
        # query nearest. Falls back to Euclidean RGB if Lab missing.
    """
    raise NotImplementedError("nearest_thread — scaffold stub (spec §4.4)")
