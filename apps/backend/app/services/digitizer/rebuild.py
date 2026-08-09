"""Regenerating a design from its objects (`rebuild_design`).

Split out of `pipeline.py` in v2 Phase B1.5. The two entry points share
generators but nothing else — measured: `rebuild_design` referenced ZERO
names defined in pipeline.py — and keeping both in one file had the module
bumping the 1,500-line layering gate on every change, four times in a row.
"""

from __future__ import annotations

import math

from app.models.design import (
    Design,
    DesignObject,
    Point,
    Stitch,
    enum_str,
)
from app.services.digitizer import (
    constants,
)
from app.services.digitizer.constants import (
    CONNECT_MM,
    CONTOUR_ROW_MAX_STEP_MM,
    FILL_UNDERLAY_ANGLE_OFFSET_DEG,
    FILL_UNDERLAY_PITCH_MULT,
    MAX_STITCH_MM,
    MIN_STITCH_MM,
    SATIN_SPACING_MM,
    TRAVEL_STEP_MM,
    TRIM_MIN_GAP_MM,
    UNDERLAY_ZIGZAG_INSET_MM,
    UNDERLAY_ZIGZAG_PITCH_MULT,
)
from app.services.digitizer.fills import (
    _contour_fill,
    _fill_angle,
    _radial_fill,
    _scanline_angled,
    _spiral_fill,
)
from app.services.digitizer.generation import (
    spine_satin,
)
from app.services.digitizer.geometry import (
    _dilate_pull,
    _fabric_profile,
    _flow_divide_valid,
    _flow_line_angle,
    _flow_side_angles,
    _split_mask_by_line,
)
from app.services.digitizer.provenance import (
    is_unedited,
    object_params_hash,
    rebuild_is_a_noop,
)
from app.services.digitizer.routing import (
    _finish_rebuild_segment,
    _lock_stream,
    travel_route_pad_px,
)
from app.services.digitizer.satin import (
    _satin_axis_deg,
    _satin_zigzag,
    rebuild_fill_border,
)
from app.services.digitizer.underlay import (
    _applique_phases,
    _manual_run,
    _rebuild_underlay,
    _with_underlay,
)

# How far a stored satin angle may sit from this contour's recomputed axis and
# still count as "digitize wrote this, the user did not touch it".
#
# This tolerance was 0.15 degrees and that is BELOW THE NOISE FLOOR of the
# comparison it makes. The stored angle is rounded to 1dp and was measured by
# digitize on ITS raster (13.3px/mm); rebuild recomputes `minAreaRect` on the
# same contour re-quantized to its own 10px/mm grid with integer truncation.
# The two disagree by requantization alone. Measured on a fresh digitize with
# NO edits at all, so every delta below is pure noise:
#
#   04_thin_line_outline   6 satins, max delta 0.000 deg -> 6/6 took the spine
#   05_wordmark_caps       6 satins, max delta 3.700 deg -> 4/6
#   06_wordmark_script     7 satins, max delta 0.637 deg -> 2/7
#
# So on a script wordmark five of seven untouched satin columns were sent to
# the bounding-rect sweep — the very path B1.5 moved them off — because the
# gate could not tell requantization from an edit.
#
# The numeric comparison is now the FALLBACK. The primary test is provenance:
# `is_unedited` says whether this object still matches the fingerprint digitize
# stored on it, and an unedited object's angle IS digitize's own by definition,
# whatever the raster says. Only an object the user actually changed reaches
# the numeric test, and there the tolerance is set above the measured noise —
# a deliberate angle edit is a UI drag, whole degrees, not hundredths.
SATIN_ANGLE_AUTO_TOL_DEG = 1.0


def _angle_is_digitizes_own(obj, want: float, raw_rect) -> bool:
    """True when this satin's stored angle is provenance rather than an edit.

    Spine satin is only correct when the angle is digitize's own: a medial axis
    has no single angle, so running it on a user-set angle would silently
    discard that angle and re-break probe P4. See SATIN_ANGLE_AUTO_TOL_DEG for
    why the numeric test alone was not good enough.
    """
    if is_unedited(obj):
        return True
    delta = abs((want % 180.0) - _satin_axis_deg(raw_rect))
    return min(delta, 180.0 - delta) <= SATIN_ANGLE_AUTO_TOL_DEG


def rebuild_design(design: Design, *, force: bool = False) -> Design:
    """Regenerate the whole stitch stream from object contours + parameters.

    Every object must carry a ``contour`` (only digitized designs do). Objects are
    re-filled with their CURRENT stitch_type / density / stitch_angle, so editing a
    parameter and rebuilding applies the edit. Raises ValueError if not regenerable.

    ``force`` skips the unedited-design pass-through and REGENERATES regardless.

    That pass-through is a correctness feature — an untouched object must not be
    re-stitched — but it also made the fidelity probe self-fulfilling: P6 asked
    whether rebuilding an unedited design reproduced its stream, and the
    pass-through returned the very same object, so every assertion compared the
    design to itself and passed no matter how far the two paths had drifted
    (CTO verdict V2). Five more probes were hollowed out the same way. `force`
    exists so the test suite can measure the generators rather than the
    short-circuit; production never sets it.
    """
    import cv2
    import numpy as np

    objs = sorted(design.objects, key=lambda o: o.sequence_order)
    if not objs:
        raise ValueError("Design has no objects to rebuild (imported stitch files are not regenerable)")
    if any(not o.contour for o in objs):
        raise ValueError("Some objects have no contour — design is not regenerable")
    # An object whose color_stop matches no stop used to be silently filtered
    # out of the emission loop below — the object simply vanished from the
    # rebuilt design (CTO A8/C9). Corrupt references now fail loudly and name
    # the objects, so the caller fixes the data instead of losing stitches.
    known_stops = {c.stop_number for c in design.color_stops}
    orphans = [o for o in objs if o.color_stop not in known_stops]
    if orphans:
        names = ", ".join(f"{o.name} (color_stop={o.color_stop})" for o in orphans)
        raise ValueError(
            f"Objects reference color stops that do not exist: {names}. "
            f"Known stops: {sorted(known_stops)}."
        )

    # Nothing to rebuild? Return the design untouched — see `rebuild_is_a_noop`.
    if not force and rebuild_is_a_noop(design, objs):
        return design

    xs = [p.x for o in objs for p in o.contour]
    ys = [p.y for o in objs for p in o.contour]
    minx, miny = min(xs), min(ys)
    w_mm = max(max(xs) - minx, 1.0)
    h_mm = max(max(ys) - miny, 1.0)
    # 10px/mm = a 0.1mm raster, matching DST's own coordinate resolution
    # (CTO A8/C6). The old 4px/mm (0.25mm grid) roughened every edge on each
    # rebuild and the damage accumulated across repeated edits. The 2000px
    # canvas cap keeps full resolution up to a 200mm design — beyond every
    # supported hoop — and degrades gracefully past it.
    # REBUILD ON THE GRID DIGITIZE ACTUALLY USED, when the design records one
    # (CTO verdict STEP 3, `Design.source_mm_per_px`). Every generator here is a
    # raster operation — thinning, distance transforms, scanlines, contour
    # tracing — so the grid is part of what produced the original stitches.
    # digitize ran at 0.075 mm/px on the bench corpus and rebuild picked 0.1
    # from the object bounding box, a third coarser, and the two paths then
    # measured different stroke widths and laid rows at a different pitch on the
    # same shape.
    #
    # The canvas cap still applies: a stored value that would blow the raster
    # past 2000px on the long side is clamped rather than trusted, so a design
    # digitized from a huge source cannot make an edit allocate an enormous
    # canvas. No stored value (an older save, or an imported stitch file that
    # never had a raster) falls back to the previous behaviour exactly.
    cap_px_per_mm = min(10.0, 2000.0 / max(w_mm, h_mm))
    stored = design.source_mm_per_px
    if stored and stored > 0:
        px_per_mm = min(1.0 / float(stored), 2000.0 / max(w_mm, h_mm))
    else:
        px_per_mm = cap_px_per_mm
    mm_per_px = 1.0 / px_per_mm
    pad = 2
    cw, ch = int(w_mm * px_per_mm) + 2 * pad, int(h_mm * px_per_mm) + 2 * pad

    def to_px(p: Point) -> tuple[int, int]:
        return (int((p.x - minx) * px_per_mm) + pad, int((p.y - miny) * px_per_mm) + pad)

    def to_mm(x: float, y: float) -> tuple[float, float]:
        return ((x - pad) * mm_per_px + minx, (y - pad) * mm_per_px + miny)

    # THE FABRIC PROFILE, which rebuild ignored entirely until now. digitize
    # takes its underlay step, edge inset and fill row pitch from
    # `_fabric_profile(design.fabric_type)`; rebuild hard-coded the cotton
    # constants, so editing one object on a fleece design re-stitched it with
    # cotton underlay spacing (2.0 vs 1.5mm) and a cotton edge inset (0.6 vs
    # 0.8mm). `Design.fabric_type` was there the whole time.
    #
    # Only the three quantities with NO per-object override are taken from the
    # profile. Row pitch and pull comp are NOT: digitize baked them onto the
    # object at emission and the user may since have edited them, so the stored
    # value wins — except for `fill_row_px` below, which paces a tatami
    # remainder inside a SATIN object and therefore has no per-object row pitch
    # to inherit.
    prof = _fabric_profile(design.fabric_type or "")
    fill_row_px = max(1, round(prof["row_mm"] / mm_per_px))
    under_step_px_prof = max(1, round(prof["under_mm"] / mm_per_px))
    edge_inset_px_prof = max(1, round(prof["inset_mm"] / mm_per_px))

    max_step_px = max(2, round(MAX_STITCH_MM / mm_per_px))
    # Fills subdivide on their own, tighter grid (CTO A6): tatami rows cap at
    # MAX_FILL_STITCH_MM, not the general run cap — see the constant's note.
    fill_step_px = max(2, round(constants.MAX_FILL_STITCH_MM / mm_per_px))
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
            for hole in o.holes or []:
                cv2.fillPoly(mask, [np.array([to_px(p) for p in hole], np.int32)], 0)

            st = enum_str(o.stitch_type)
            ut = enum_str(o.underlay_type)
            spacing_mm = 1.0 / max(float(o.density) or 1.0, 0.2)
            spacing_px = max(1, round(spacing_mm / mm_per_px))
            under_step_px = under_step_px_prof
            top = _dilate_pull(mask, float(o.pull_compensation or 0.0), mm_per_px)  # honor edited pull comp
            applique_phases = None
            # Set only when the satin column actually came off the medial axis;
            # the underlay then walks that same axis instead of the rect midline.
            satin_axis_pts = None
            # THE ANGLE THE TOP ROWS ARE ACTUALLY SEWN AT, which is what the
            # PARALLEL underlay must cross at 90 degrees. digitize maintains
            # this invariant by construction — it passes the very `fill_angle`
            # it just filled with — while rebuild passed the raw stored
            # `stitch_angle`, which is a different number in three cases:
            #
            #   * CONTOUR/SPIRAL/RADIAL fills, where rebuild's own code says the
            #     stored angle "does not describe this object". digitize
            #     substitutes the region's principal axis; rebuild used the
            #     stored 0.0 and so laid every crossing layer at a flat 90.
            #   * a Stitch Flow line, which overrides the angle for the top rows
            #     only — so a user who draws a flow line 90 degrees off gets an
            #     underlay running PARALLEL to the rows it is meant to brace,
            #     nesting between them at 3x their pitch instead of supporting
            #     them, and showing through as a ridge every third row.
            #   * a divided flow, where there are two top angles and no single
            #     one is right — the region's own axis is the honest choice,
            #     for the same reason digitize gives it to contour fills.
            top_row_angle = float(o.stitch_angle)
            if st == "APPLIQUE":
                # placement → STOP → tackdown → STOP → satin cover; the STOP
                # rationale and phase recipe live on _applique_phases (A4).
                applique_phases = _applique_phases(poly, mm_per_px, connect_px,
                                                   SATIN_SPACING_MM)
                pts = [p for phase in applique_phases for p in phase]
            elif st == "SATIN":
                # The edited `stitch_angle` is authoritative (CTO A5/C4): the
                # walk axis is the stored angle, not a recomputed minAreaRect —
                # recomputing is what made the edit a silent no-op. digitize
                # records the normalized axis of this same contour's rect, so an
                # unedited rebuild reproduces the old frame to 0.1°. Both rect
                # consumers use only the center and the long-axis flip test, so
                # pre-normalized extents make the angle the walk axis verbatim.
                raw_rect = cv2.minAreaRect(poly)
                want = float(o.stitch_angle)
                if want < 0.0 and abs(want - float(raw_rect[2])) <= 0.06:
                    # Legacy save: pre-A5 digitize recorded RAW rect[2], which
                    # this cv2 reports negative — a value the normalized store
                    # never produces. When the stored angle IS this contour's
                    # raw rect angle, it is provenance, not an edit: use the
                    # normalized axis it always meant, reproducing the old
                    # rebuild exactly. A deliberate negative edit that doesn't
                    # coincide with the raw angle still folds via % 180 below.
                    want = _satin_axis_deg(raw_rect)
                rect = (raw_rect[0], (2.0, 1.0), want % 180.0)
                # SPINE SATIN AT PARITY WITH DIGITIZE (v2 Phase B1.5).
                #
                # digitize sews satin off the MEDIAL AXIS: columns follow the
                # stroke, so a ring, an arc or a bend works. Rebuild used the
                # bounding-rect zigzag, which "only ever worked for a straight
                # bar" (Part 4) — so editing one parameter of a curved satin
                # replaced a spine-followed column with a rect sweep. Same
                # generator now, same arguments, including digitize's
                # wide-remainder tatami fallback.
                #
                # WHY IT IS CONDITIONAL, and this is the load-bearing part: a
                # spine has no single angle, so running it unconditionally
                # would silently undo A5 and re-break probe P4 (an edited
                # `stitch_angle` must change the stream). The stored angle is
                # compared against this contour's own normalized axis — equal
                # means "auto", i.e. the user never touched it, and the spine
                # is what digitize would do; different means the user asked
                # for a specific angle, which only the rect sweep can honour.
                # That is also how the commercial tools behave: a satin column
                # follows its spine, and an explicit angle is an override.
                #
                # AND why it is gated on WIDTH too: a shape wider than the
                # satin cap has a medial axis but cannot be covered by
                # columns, so the spine path would hand most of it back as
                # `wide_mask` and tatami it. That is right for digitize, which
                # is CLASSIFYING; it is wrong here, where the user has
                # explicitly asked this object to be SATIN. The rect sweep
                # spans any width, which is exactly why Part 4 retained it for
                # user-forced satin — measured: the 30x8mm probe bar (8mm, over
                # the 4.5mm cap) came back as horizontal tatami rows. The width
                # test uses the SKELETON's own measured width and not the
                # distance-transform median, which under-reads a rectangle badly
                # (3.6mm for that 8mm bar, which would have sailed under the cap
                # and been tatami'd) — the DT median below is only the cheap
                # pre-measure that picks the hi-res upscale factor.
                #
                # THE SHARED GENERATION CORE (STEP 3c) — see `generation.py`.
                # This sweep and digitize's were separate implementations of the
                # same thing and drifted three times, all shipped by 250e850:
                # pull compensation applied twice (the core takes the UNDILATED
                # mask and adds pull to the column half-width itself), the
                # wide remainder paced at the satin pitch instead of the fill
                # pitch, and the remainder's angle silently defaulting to 0.
                # There is one implementation now, so a fourth is not available.
                _dt = cv2.distanceTransform((mask > 0).astype(np.uint8), cv2.DIST_L2, 5)
                stroke_mm = (float(np.median(_dt[_dt > 0])) * 2.0 * mm_per_px
                             if (_dt > 0).any() else 0.0)
                if _angle_is_digitizes_own(o, want, raw_rect):
                    attempt = spine_satin(
                        mask, mm_per_px=mm_per_px, spacing_px=spacing_px,
                        max_step_px=max_step_px, fill_step_px=fill_step_px,
                        connect_px=connect_px,
                        pull_mm=float(o.pull_compensation or 0.0),
                        stroke_mm=stroke_mm, row_px=fill_row_px,
                    )
                    if attempt.viable:
                        pts = attempt.points
                        # The underlay must follow the SAME axis the top layer
                        # does — see `_rebuild_underlay`'s note on `axis_pts`.
                        satin_axis_pts = attempt.axis_pts
                    else:
                        # Too wide for columns, or the thinning could not
                        # resolve it. digitize would reclassify as tatami, but
                        # the user has explicitly asked for SATIN here, and the
                        # rect sweep spans any width — which is exactly why
                        # Part 4 retained it for user-forced satin.
                        pts = _satin_zigzag(top, rect, spacing_px, connect_px, max_step_px)
                else:
                    pts = _satin_zigzag(top, rect, spacing_px, connect_px, max_step_px)
            elif st in ("SPIRAL_FILL", "RADIAL_FILL"):
                # Curved fills (v2 Part 26): user-selectable via the properties
                # panel. `stitch_angle` does not describe either and is ignored.
                fill_fn = _spiral_fill if st == "SPIRAL_FILL" else _radial_fill
                pts = fill_fn(top, spacing_px, max_step_px, connect_px)
                top_row_angle = _fill_angle(top)
            elif st == "CONTOUR_FILL":
                # Rows follow the outline, so `stitch_angle` does not describe
                # this object and is deliberately not consulted (v2 Part 24b).
                # Without this branch an edit-and-rebuild would silently convert a
                # contour fill back into straight rows at whatever angle the
                # object happened to be carrying.
                pts = _contour_fill(
                    top, spacing_px,
                    max(1, min(max_step_px, round(CONTOUR_ROW_MAX_STEP_MM / mm_per_px))),
                    connect_px,
                )
                top_row_angle = _fill_angle(top)
            elif st in ("RUNNING_SINGLE", "RUNNING_DOUBLE", "RUNNING_TRIPLE", "MANUAL"):
                # Running stitch ALONG the drawn path (open polyline), not an
                # area fill. Pitch is density-aware with the 2.5mm pro default
                # (CTO A7/C7): the machine cap was being reused as the pitch —
                # 6mm floats — and `density` on run objects was ignored. A run
                # stores pitch as 1/density (see the dark-linework emitter);
                # density 0 means unset and takes the default.
                passes = {"RUNNING_DOUBLE": 2, "RUNNING_TRIPLE": 3}.get(st, 1)
                run_d = float(o.density or 0.0)
                pitch_mm = (min(max(1.0 / run_d, MIN_STITCH_MM), MAX_STITCH_MM)
                            if run_d > 0 else constants.RUN_PITCH_MM)
                pts = _manual_run(poly, max(1, round(pitch_mm / mm_per_px)), passes)
            elif st == "TATAMI":
                # Stitch Flow (v2 Part 62): a stored direction line beats the
                # stored angle; no line means exactly the old behaviour.
                # Divided flow (v2 Part 63): a valid divide line splits the
                # region into two half-planes, each sewing at its own angle
                # (side assignment documented on _flow_side_angles). Each
                # side's scanline opens with a jump point, so concatenation is
                # safe, and _route_travel below routes the crossing in-mask.
                if _flow_divide_valid(o.flow_divide):
                    d0, d1 = o.flow_divide[0], o.flow_divide[-1]
                    a_px = ((d0.x - minx) * px_per_mm + pad, (d0.y - miny) * px_per_mm + pad)
                    b_px = ((d1.x - minx) * px_per_mm + pad, (d1.y - miny) * px_per_mm + pad)
                    ang_pos, ang_neg = _flow_side_angles(
                        o.flow_divide, o.flow_line, o.flow_line_b, float(o.stitch_angle),
                    )
                    top_row_angle = _fill_angle(top)
                    pts = []
                    for side_mask, ang in zip(_split_mask_by_line(top, a_px, b_px),
                                              (ang_pos, ang_neg)):
                        if cv2.countNonZero(side_mask):
                            pts += _scanline_angled(
                                side_mask, ang, spacing_px, fill_step_px, connect_px,
                            )
                else:
                    top_row_angle = _flow_line_angle(o.flow_line, float(o.stitch_angle))
                    pts = _scanline_angled(
                        top, top_row_angle, spacing_px, fill_step_px, connect_px,
                    )
            else:
                # There is deliberately no catch-all fill here (v2 Part 43). This
                # branch used to be `else: tatami`, which is how eleven declared
                # stitch types quietly produced tatami and nobody found out. If a
                # new StitchType member ever lands without a generator, it fails
                # here and names itself rather than shipping the wrong stitch.
                raise ValueError(
                    f"{o.name}: no generator for stitch type {st!r}. Every StitchType "
                    f"member needs a branch here — see the enum docstring in models/design.py."
                )
            # Fill finish parity with digitize — see `rebuild_fill_border`.
            if st in ("TATAMI", "CONTOUR_FILL", "SPIRAL_FILL", "RADIAL_FILL") and pts:
                pts = pts + rebuild_fill_border(
                    poly, [np.array([to_px(p) for p in h], np.int32) for h in (o.holes or [])],
                    mask, mm_per_px, connect_px, pts[-1][:2],
                )

            # Underlay: the SELECTED type dispatched to its real generator
            # (CTO A5/C5) — see _rebuild_underlay for the honesty contract.
            under = _rebuild_underlay(
                st, ut, mask, rect if st == "SATIN" else None,
                top_row_angle, spacing_px, under_step_px, connect_px,
                max_step_px, mm_per_px,
                (constants._PENETRATION_FLOOR_MM / mm_per_px) if constants._PENETRATION_FLOOR_MM else 0.0,
                MAX_STITCH_MM / mm_per_px,
                edge_inset_px_prof,
                prof["under_mm"] * UNDERLAY_ZIGZAG_PITCH_MULT / mm_per_px,
                UNDERLAY_ZIGZAG_INSET_MM / mm_per_px,
                FILL_UNDERLAY_PITCH_MULT, FILL_UNDERLAY_ANGLE_OFFSET_DEG,
                axis_pts=satin_axis_pts,
            )
            if under:
                pts = _with_underlay(under, pts, connect_px)
            # Finishing chain shared with the digitizer — see
            # _finish_rebuild_segment (coalesce → travel-route → floor).
            # Both of these used to be computed inline here with values that had
            # drifted from digitize's — the pad omitted the border half-width
            # (2px against digitize's 8), and the coalesce clamp ignored the
            # fill row pitch and never passed the satin floor. Measured on P1's
            # own ring rebuilt after a 1% density nudge: 98 needle paths across
            # the open counter, against 0 for digitize. Shared functions now,
            # not copied constants (CTO verdict STEP 0).
            route_pad = travel_route_pad_px(float(o.pull_compensation or 0.0), mm_per_px)
            # APPLIQUE's cover phase is a satin, so it earns the zigzag floor
            # repair; only true area fills get the row-pitch clamp, because a
            # run's 1/density spacing is not a row pitch.
            seg_is_satin = st in ("SATIN", "APPLIQUE")
            seg_row_px = (float(spacing_px)
                          if st in ("TATAMI", "CONTOUR_FILL", "SPIRAL_FILL", "RADIAL_FILL")
                          else None)

            def _finish(seg):
                return _finish_rebuild_segment(
                    seg, mask, mm_per_px, route_pad,  # noqa: B023
                    MIN_STITCH_MM, TRAVEL_STEP_MM, MAX_STITCH_MM,
                    is_satin=seg_is_satin, fill_row_px=seg_row_px,  # noqa: B023
                )

            if applique_phases is not None:
                applique_phases = [f for f in (_finish(p) for p in applique_phases)
                                   if len(f) >= 2]
                pts = [p for phase in applique_phases for p in phase]
            else:
                pts = _finish(pts)
            if len(pts) < 2:
                # THIS USED TO BE `continue`, and it deleted the object.
                #
                # Not a theoretical risk: measured on 05_wordmark_caps and
                # 06_wordmark_script, a rect sweep across a curved script stroke
                # produced under two points and each design came back one object
                # short, with no error, no log and no visible sign until you
                # counted. The user sees a letter missing from their wordmark.
                #
                # Silence is the wrong default for "a generator produced
                # nothing". Fixing the cause (see the 250e850 residuals) stopped
                # it firing on the whole corpus; this makes sure the next cause
                # announces itself instead of quietly costing someone a letter.
                raise ValueError(
                    f"{o.name} ({st}): only {len(pts)} point(s) survived to "
                    f"emission, too few to sew. The object would otherwise be "
                    f"dropped from the design without a trace. This usually "
                    f"means the contour is degenerate at the rebuild raster, or "
                    f"a generator fell back to a path that cannot span this shape."
                )

            if stitches and stitches[-1].command != "COLOR_CHANGE":
                last = stitches[-1]
                ex, ey = to_mm(pts[0][0], pts[0][1])
                # Trim only when the connecting thread would be long enough to
                # matter (v2 Part 48) — digitize's rule, which rebuild did not
                # have: it trimmed at EVERY object transition. A trim costs
                # roughly 2.5s of machine time, and below TRIM_MIN_GAP_MM the
                # machine carries a short thread to the next region, which is
                # what commercial digitizers do.
                if math.hypot(ex - last.x, ey - last.y) >= TRIM_MIN_GAP_MM:
                    stitches.append(Stitch(x=last.x, y=last.y, command="TRIM"))
                stitches.append(Stitch(x=ex, y=ey, command="JUMP"))
            obj_start = len(stitches)
            if applique_phases is not None:
                for pi, phase in enumerate(applique_phases):
                    for x, y, jump in phase:
                        mx, my = to_mm(x, y)
                        stitches.append(Stitch(x=mx, y=my,
                                               command="JUMP" if jump else "STITCH"))
                    if pi < len(applique_phases) - 1:
                        last = stitches[-1]
                        stitches.append(Stitch(x=last.x, y=last.y, command="STOP"))
            else:
                for x, y, jump in pts:
                    mx, my = to_mm(x, y)
                    stitches.append(Stitch(x=mx, y=my, command="JUMP" if jump else "STITCH"))

            entry = to_mm(pts[0][0], pts[0][1])
            exit_ = to_mm(pts[-1][0], pts[-1][1])
            regenerated = o.model_copy(
                update={
                    "stitch_count": len(stitches) - obj_start,
                    "entry_point": Point(x=entry[0], y=entry[1]),
                    "exit_point": Point(x=exit_[0], y=exit_[1]),
                }
            )
            # Re-stamp provenance so the NEXT rebuild can pass this object
            # through; without it every rebuild would regenerate everything
            # forever and the damage would keep accumulating.
            regenerated.params_hash = object_params_hash(regenerated)
            new_objects.append(regenerated)
        stop_counts[stop.stop_number] = len(stitches) - stop_start

    if stitches:
        last = stitches[-1]
        stitches.append(Stitch(x=last.x, y=last.y, command="END"))

    # Rebuilt streams get the same thread locks as freshly digitized ones
    # (v2 Part 25) — otherwise one parameter edit would silently strip every
    # tie the original stream carried.
    stitches = _lock_stream(stitches)

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
