"""The shared generation core: one implementation, two callers.

CTO verdict 2026-08-09, STEP 3c. The architecture question was ruled (c) — one
generation core with `digitize_image` and `rebuild_design` as thin wrappers —
because the alternative had been tried and kept failing the same way. Both
paths called the same generators, each computed the arguments itself, and the
arguments drifted. Every divergence found in this series was that shape:

    route_pad             8px on one path, 2px on the other
    coalesce clamp        fill row pitch honoured on one, ignored on the other
    penetration floor     passed for satin on one, never on the other
    border sweep width    derived twice, identically, waiting to drift
    satin underlay axis   medial axis on one, bounding-rect midline on the other
    pull compensation     applied once on one path, twice on the other
    wide-remainder pitch  fill row pitch on one, satin column pitch on the other
    wide-remainder angle  measured on one, silently 0.0 on the other
    parallel underlay     crossed the real row angle on one, a stale stored one
                          on the other
    trim gate             TRIM_MIN_GAP_MM on one, unconditional on the other

Ten of them, none catchable by a stitch hash — the hash moves with the
regression. The finishing chain was unified first (`routing.coalesce_params`,
`routing.travel_route_pad_px`, `satin.fill_border_width_px`). This module
unifies the satin generation core, which is where three of the ten lived and
where the geometry is most intricate.

WHAT IS *NOT* HERE, AND WHY. digitize CLASSIFIES — it decides from pixels
whether a region should be satin at all, which holes to knock out, whether a
band wants a contour fill, and which underlay recipe a stroke's width earns.
Rebuild does not classify: the stored object already says what it is, because
the user may have overridden any of it. That asymmetry is the competitor model
(the object is the source of truth) and it is deliberate, so classification
stays in `pipeline.py`. What both paths must agree on is what a *decided*
object turns into, and that is what lives here.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.digitizer.constants import (
    NO_AXIS_SPECK_MM2,
    SATIN_MAX_UNCOVERED,
    SATIN_MAX_W_MM,
)
from app.services.digitizer.fills import _fill_angle, _fill_by_component
from app.services.digitizer.satin import _skeleton_satin_hires


@dataclass(frozen=True)
class SatinAttempt:
    """What sweeping satin columns along a region's medial axis produced.

    Both callers need the same measurements but use them for different
    decisions, so the attempt reports and does not decide: `digitize_image`
    turns `reason` into a classification, `rebuild_design` uses `viable` to
    choose between the spine and the bounding-rect sweep for an object the user
    has already declared SATIN.
    """

    points: list                 # columns + tatami remainder; [] when not viable
    median_w_mm: float           # the SKELETON's own stroke width, not the DT median
    uncovered_share: float       # fraction of the region columns could not cover
    axis_pts: object | None      # the medial axis, for an underlay that must follow it
    wide_mask: object | None
    viable: bool
    reason: str                  # satin | no_medial_axis | wider_than_satin_cap | not_stroke_like
    remainder_tatami: bool       # a too-wide patch was tatami'd into `points`


def spine_satin(region, *, mm_per_px: float, spacing_px: int, max_step_px: int,
                fill_step_px: int, connect_px: float, pull_mm: float,
                stroke_mm: float, row_px: int) -> SatinAttempt:
    """Satin columns along the medial axis, plus the tatami remainder.

    ``region`` MUST BE UNDILATED. Pull compensation is added to the column
    half-width here; handing in a mask that has already been `_dilate_pull`-ed
    applies it twice and pushes a stroke over the width cap — measured, and the
    exact defect `250e850` shipped on the rebuild path while `pipeline.py`
    carried a comment warning against it.

    ``stroke_mm`` is the caller's cheap pre-measure of the region's typical
    stroke width, used only to pick the hi-res upscale factor. ``row_px`` is the
    FILL row pitch for the remainder — a tatami patch is paced like a fill, not
    like the satin column it sits inside; those are separate fabric-profile keys
    that happen to coincide on cotton.
    """
    import cv2

    cand, median_w, wide_mask, axis_pts = _skeleton_satin_hires(
        region, mm_per_px, spacing_px, max_step_px,
        (pull_mm / 2.0) / mm_per_px, stroke_mm / mm_per_px,
    )
    region_px = max(cv2.countNonZero(region), 1)
    uncovered = cv2.countNonZero(wide_mask) / region_px

    # Two independent conditions, and both callers apply exactly these.
    #
    # Width: the stroke must fit under the satin cap. The SKELETON's median, not
    # the distance transform's — the DT median under-reads a rectangle badly
    # (measured 3.6mm for an 8mm bar) and spikes at junctions where the axis is
    # far from every edge although the stroke is no wider.
    #
    # Reducibility: columns swept along the axis must actually account for the
    # shape. A disc has a medial axis, but columns capped at the satin width
    # cannot cover it, so its uncovered share stays high and it correctly is not
    # satin. This is what stops broad fills being forced into columns.
    if not cand:
        # NO AXIS SAMPLES AT ALL. This arm used to be labelled "a freckle, a
        # catchlight, a punctuation dot" and carried no size test, which made it
        # a blind spot rather than a case: `median_w` and the sample count are
        # both zero here, so EVERY width-based statistic — the classifier's
        # median, and any detector built on top of it — is structurally unable
        # to see these objects at all.
        #
        # They are not all freckles. `09_nonuniform_background` seq 1 reaches
        # this arm at 168mm²: a 14.6mm disc, whose medial axis genuinely IS a
        # single point, and which sews correctly at 100% coverage. The corpus's
        # actual freckles are 2.6 and 5.2mm². Both belong here — tatami is right
        # for a disc and right for a speck — but they are different cases and a
        # survey that cannot distinguish them will keep raising false alarms
        # (this one cost a round trip).
        #
        # So the arm now says which it is. The decision is unchanged: not satin
        # either way. `axis_pts` is empty in both, so callers already treat the
        # width as absent rather than as zero.
        area_mm2 = region_px * mm_per_px * mm_per_px
        reason = "no_medial_axis" if area_mm2 < NO_AXIS_SPECK_MM2 else "compact_no_axis"
        viable = False
    elif median_w > SATIN_MAX_W_MM:
        reason, viable = "wider_than_satin_cap", False
    elif uncovered > SATIN_MAX_UNCOVERED:
        reason, viable = "not_stroke_like", False
    else:
        reason, viable = "satin", True

    points: list = []
    remainder = False
    if viable:
        points = cand
        if cv2.countNonZero(wide_mask) > 0:
            # Parts too wide for a column are tatami'd fragment by fragment from
            # wherever the satin ended, rather than dropped. At the FILL row
            # pitch and at the remainder's OWN principal axis: omitting the
            # angle silently defaults it to 0.0 and lays horizontal rows across
            # whatever direction the stroke actually runs.
            points = points + _fill_by_component(
                wide_mask, row_px, fill_step_px, connect_px,
                start=points[-1][:2] if points else None,
                angle_deg=_fill_angle(wide_mask),
            )
            remainder = True

    return SatinAttempt(
        points=points,
        median_w_mm=median_w,
        uncovered_share=uncovered,
        axis_pts=axis_pts,
        wide_mask=wide_mask,
        viable=viable,
        reason=reason,
        remainder_tatami=remainder,
    )
