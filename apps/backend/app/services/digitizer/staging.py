"""What the collection pass hands the generation pass (v2 Part 52, R004-impl).

Up to Part 51 `digitize_image` was one loop: for each colour cluster, find its
regions and immediately sew them. That structure has a consequence Part 51
measured rather than guessed — **the union of the design's object contours does
not exist until every object has already been sewn**, so a generator could never
be handed the field Part 50 validated.

Part 51's numbers, on the photographed sew-out, per pixel over tatami territory:

    union of every object contour   32.34 deg   <- what Part 50 validated
    per colour cluster, composited  35.31 deg
    segmentation foreground         38.84 deg   <- the only seed available in a
                                                   one-pass pipeline, and the
                                                   substitution that made D2 lose
                                                   to a constant angle

So the seed is not a tuning knob, it is most of the answer, and getting the good
one requires knowing every region before sewing any of them. These types are that
split made explicit: pass A fills a `DigitizePlan`, the field is solved from its
`seed_mask`, and pass B sews from the same plan without re-deriving anything.

Nothing here decides HOW a generator uses the field. Part 51 established that a
straight fill row can only take the field's regional mean and loses 45% of its
value doing so; whether tatami or satin consumes it first is a later measurement.
This module exists so that whichever one goes first gets the validated field
rather than a cheaper lookalike.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class RegionPlan:
    """One top-level contour of one cluster, decided but not yet sewn.

    `contour`/`holes` are the SMOOTHED outlines — smoothing happens in the
    collection pass so the seed mask and the stored contour that drives rebuild
    are the same geometry the generator sees. `raw_contour` is kept because the
    drop log's centroid is taken from the unsmoothed outline, exactly as it was
    before the split.
    """

    top_index: int
    net_area_px: float
    raw_contour: np.ndarray
    dropped: bool
    contour: np.ndarray | None = None
    holes: list[np.ndarray] = field(default_factory=list)


@dataclass
class ClusterPlan:
    """One work item — a colour cluster, or a deferred detail pass over one.

    `mask` is the prepared cluster mask AFTER opening, texture morphology and the
    substrate rule, i.e. exactly the array the generation pass used to allocate
    its scratch buffers before the split.
    """

    phase: str
    cluster_idx: int
    center: np.ndarray
    mask: np.ndarray
    tops: list[int]
    centroids: list[tuple[float, float]]
    regions: list[RegionPlan]


@dataclass
class DigitizePlan:
    """Everything the generation pass needs, plus the field solved from it.

    `seed_mask` is the union of the surviving regions' own outlines — the seed
    class that scored 32.34, not the foreground silhouette that scored 38.84.
    `field` is solved ONCE for the whole design; per-cluster and per-region
    solving were both measured worse in Part 51 and are not offered here.
    """

    clusters: list[ClusterPlan] = field(default_factory=list)
    seed_mask: np.ndarray | None = None
    field: object | None = None
    substrate_px: int = 0

    @property
    def region_count(self) -> int:
        return sum(1 for c in self.clusters for r in c.regions if not r.dropped)


@dataclass
class FieldArtifact:
    """A light snapshot of what pass A produced, kept for inspection.

    Deliberately NOT the whole `DigitizePlan`. The plan holds a full-frame mask
    per colour cluster and every contour in the design; retaining that across
    calls would pin tens of megabytes on a long-lived server for the sake of a
    diagnostic. A generator that wants the field reads `plan.field` directly
    inside the pipeline — this exists so a measurement can ask, from outside,
    WHICH seed the field was actually solved from. Part 51's whole finding was
    that a plausible-looking substitution there costs 6.5 deg, and the only way
    to keep that honest is to be able to check it from a real run.
    """

    seed_mask: np.ndarray | None = None
    field: object | None = None
    region_count: int = 0
    cluster_count: int = 0
    seed_px: int = 0


_LAST: FieldArtifact | None = None


def remember(plan: DigitizePlan) -> None:
    """Snapshot the plan's field artifact for `last_field_artifact()`."""
    global _LAST
    seed = plan.seed_mask
    _LAST = FieldArtifact(
        seed_mask=None if seed is None else seed.copy(),
        field=plan.field,
        region_count=plan.region_count,
        cluster_count=len(plan.clusters),
        seed_px=0 if seed is None else int(cv2.countNonZero(seed)),
    )


def last_field_artifact() -> FieldArtifact | None:
    """The seed and field from the most recent digitize, or None before any."""
    return _LAST


def add_to_seed(seed: np.ndarray, contour: np.ndarray,
                holes: list[np.ndarray] | None = None) -> None:
    """OR one region's filled outline into the seed, working in its own bbox.

    Deliberately NOT `drawContours` over a full-size scratch per region. That is
    the shape behind the Parts 48 and 49 blowups: the contour loop runs once per
    region BEFORE the speck filter, so any full-frame operation inside it is
    multiplied by the NOISE count — 70,516 contours on a 900x900 random image
    against 251 in the panel's busiest colour. Bounding-box work is proportional
    to the region's own area, so the total is bounded by the image, not by how
    many pieces the input happens to be in.

    Compositing through a local buffer rather than drawing straight into `seed`
    also keeps one region's holes from punching through a neighbour that was
    already written — detail sewn inside a larger shape's counter is a real case,
    not a hypothetical.
    """
    x, y, w, h = cv2.boundingRect(contour)
    if w <= 0 or h <= 0:
        return
    local = np.zeros((h, w), np.uint8)
    cv2.drawContours(local, [contour - (x, y)], -1, 255, thickness=cv2.FILLED)
    for hole in (holes or []):
        cv2.drawContours(local, [hole - (x, y)], -1, 0, thickness=cv2.FILLED)
    np.bitwise_or(seed[y:y + h, x:x + w], local, out=seed[y:y + h, x:x + w])
