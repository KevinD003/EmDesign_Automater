"""Auto-digitizing pipeline — image to stitches (spec §4.2).

Scaffold stub. OpenCV/NumPy are imported lazily inside the functions.
"""

from __future__ import annotations

from app.models.design import Design


def digitize_image(data: bytes, fabric_type: str, hoop_size: str) -> Design:
    """Convert an image into a stitch Design.

    TODO (classical-CV first, AI later):
        import cv2, numpy as np
        # 1 segment regions  2 assign stitch types  3 order colors
        # 4 plan stitch paths  5 quality risk pass  -> Design
    """
    raise NotImplementedError("digitize_image — scaffold stub (spec §4.2)")
