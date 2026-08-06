"""Tunables for the digitizing pipeline (R001 split).

Every magic number lives here so a change is visible in one diff.
Values are unchanged from the pre-split module.
"""

from __future__ import annotations

# Tunables (mm unless noted) — see spec "Quick Reference" table.
ROW_SPACING_MM = 0.45     # fill row pitch — full-coverage tatami (0.6 left fabric showing through)


MAX_STITCH_MM = 6.0       # subdivide longer runs (machine safety << 12.7mm)


# Warn the user when at least this share of the segmented foreground was
# dropped as unsewable (v2 Part 25). Calibrated on the corpus: every fixture at
# its intended hoop loses well under 2% (anti-aliasing specks), while the badge
# fixture forced into a 40x40mm hoop — the measured silent-failure case, 21
# objects down to 4 — loses far more. 3% sits between those populations.
DROPPED_SHARE_WARN = 0.03


# Source pixels per design millimetre above which the fine-detail warning fires.
# 10px/mm means a 2px source feature maps to 0.2mm — under the 0.25mm thread
# width — so anything drawn at that scale cannot survive. Calibrated against the
# corpus at intended hoops (all sit below it) and the badge fixture forced into
# small hoops (70x70 -> 10.2px/mm, 40x40 -> 15.9px/mm, both measured cases where
# most objects were destroyed).
FINE_DETAIL_SRC_PX_PER_MM = 10.0


MIN_REGION_MM2 = 2.0      # drop specks smaller than this. v1 used 4.0, which


                          # deleted the mascot's 2.6mm² freckles and similar
                          # deliberate small detail (v1 audit §5). 2.0 keeps them
                          # while still discarding anti-aliasing specks; going to
                          # 1.0 adds objects without recovering further detail.
CONNECT_MM = 3.0          # row-to-row travel below this = stitch, else JUMP


DEFAULT_MAX_COLORS = 6


# Satin classification. The spec allows columns from 0.8mm to 10-12mm; this
# project capped at 4mm "where satin clearly beats tatami".
#
# Raised 4.0 -> 4.5 in v2 Part 3, and the reason is worth stating plainly because
# it was surfaced by a test. `test_rotated_bar_becomes_satin_with_angle` uses a
# bar whose docstring calls it "~3.6mm wide" — the nominal `cv2.line` thickness.
# Rasterised at 45 degrees it is actually wider, confirmed three independent
# ways: perpendicular ray count 4.43mm, area/skeleton-length 4.25mm, largest
# inscribed circle 4.50mm. (The OLD rule passed that test only because
# minAreaRect fits the staircase corners and under-reads at 3.82mm.) So a
# measured-width rule correctly finds 4.4mm, and a 4.0mm cap excluded a bar that
# any embroiderer would satin — the cap was wrong, not the test.
#
# 4.5 remains far below the spec's 10-12mm, and it is safe now in a way it was
# not before: satin follows the medial axis with per-segment tatami fallback for
# anything too wide, where it used to be a bounding-rect zigzag good only for a
# straight bar. Measured corpus impact of 4.0 -> 4.5: exactly ONE additional
# object becomes satin (fixture 08), and no broad fill changes at any cap up to
# 6.0. A reviewer may still read this as tuning to pass a test; the measurements
# above and in the Part 3 audit are there to be checked.
SATIN_MAX_W_MM = 4.5


# The spec's 0.8mm minimum column is deliberately NOT enforced. Fixture 04 is
# drawn entirely in 0.28-0.62mm strokes, and satin is exactly what those want —
# a 0.8mm floor would send the thinnest real linework back to tatami, which is
# the defect this part exists to fix. The effective floor is the 0.5px half-width
# clamp in `_skeleton_satin`, i.e. one thread. Kept as a named constant because
# the spec figure is worth recording next to the cap it sits under.
SATIN_MIN_W_MM = 0.8


# `SATIN_ASPECT` and `SKELETON_MIN_WIDTH_MM` were deleted here, not merely left
# unread: with classification now driven by measured medial-axis width they had
# no remaining caller anywhere in the tree (`rebuild_design`'s explicit-SATIN
# path uses `_satin_zigzag` + `_center_walk`, neither of which consults them).
# Aspect ratio tested a property of the bounding BOX rather than of the shape,
# so a ring, arc or bend — uniformly thin but with a huge box — always failed it
# and was area-filled. That is why fixture 04 came out 100% tatami.
SATIN_SPACING_MM = 0.4    # zigzag pitch along the column


# Underlay (spec §4.6): edge-walk inside fills, center-walk under satin columns.
UNDERLAY_STEP_MM = 2.0    # running-stitch length


EDGE_INSET_MM = 0.6       # edge-walk offset inside the region edge


_MAX_WORK_PX = 1200.0     # cap working resolution (raise = more detail, slower)


_MIN_WORK_PX = 1200.0     # floor: small sources are upscaled to this (v2 Part 17)


# Only sources with real geometry are upscaled: below this, the anti-alias band
# a cubic upscale widens is as large (in mm) as the smallest real features, so
# the sub-thread gate can no longer separate blend halos from ink — measured on
# a 200px test square whose halo came out at 0.45mm, over the 0.35 gate. A
# 640px logo's halo at 1.875x measures ~0.15mm and is gated cleanly.
_UPSCALE_MIN_SRC_PX = 400.0


# Per-REGION upscale for the skeleton-satin stage (v2 Part 16). A 640px source
# in a 130mm hoop puts a 4mm letter at ~20px with 2-4px strokes — the medial
# axis of a 3px stroke is staircase noise, which is why small lettering came
# out as mush. Regions whose typical stroke is under SMALL_STROKE_PX are
# thinned and columned at up to SMALL_STROKE_MAX_SCALE x resolution, points
# scaled back after. A global upscale was tried first and rejected on
# measurement: 43.8s per fixture (18x) for quality gains only small strokes
# need. Per-region, only the small objects pay.
# Detail deferral thresholds (v2 Part 16): a component this small, whose
# surrounding ring is mostly a later-stitched cluster, is embedded detail — it
# stitches AFTER its background so the background can sew solid beneath it.
DETAIL_DEFER_MAX_MM2 = 60.0


DETAIL_EMBED_SHARE = 0.6


# Thinner than this is unstitchable blend-halo, not ink (v2 Part 17). Measured
# at 1.875x work resolution: upscale phantom halos 0.15mm; fixture 04's REAL
# hairlines 0.30-0.33mm (the coarse grid had inflated them to 0.5). 0.25 sits
# between the two measured populations; the first value tried (0.35) silently
# deleted all of fixture 04, which is why this constant carries its data.
MIN_FEATURE_W_MM = 0.25


SMALL_STROKE_PX = 8.0


SMALL_STROKE_MAX_SCALE = 3


# Zero-pixel margin kept around a region when `_skeleton_satin_hires` upscales
# only the region's box. INTER_CUBIC reads a 4x4 neighbourhood, so 3 zero source
# pixels already give every sample its full-canvas neighbourhood; 4 is a spare.
HIRES_CROP_PAD_PX = 4


# Margin for the windowed distance transform. One px is the proven requirement
# (see `_distance_transform`); 8 leaves the 5x5 chamfer's stepping room to spare
# at a cost of a few hundred pixels.
DT_WINDOW_PAD_PX = 8


# ── v2 Part 1: layer preservation + contour smoothing ────────────────────────
# Two clusters closer than this in BGR are the same thread in practice; merging
# them stops the engine emitting two colour stops (two thread changes) for what
# a human sees as one colour.
MERGE_DELTA = 18.0


# Squared-distance ratio above which a pixel counts as an anti-aliased blend of
# two palette colours rather than a member of either (0.5 on squared distance
# ≈ 0.71 on linear distance).
AMBIGUOUS_BLEND_RATIO = 0.5


# Two palette centres closer than this (BGR euclidean) are the same thread, so
# a pixel between them is not a blend and must not be discarded (v2 Part 36).
# Well under SPLIT_DELTA_BGR (30, "two real threads"), so it only ever catches
# k-means duplicates, never a genuine near-pair.
AMBIGUOUS_MIN_CENTRE_GAP = 12.0


# Skip the blend cut for a cluster when it would remove more than this share of
# that cluster's pixels — the shape is then mostly boundary (a thin stroke) and
# the cut destroys it rather than trimming it. Calibrated in v2 Part 36.
AMBIGUOUS_MAX_CUT_SHARE = 0.35


# Palette-recovery for stroke-only colours (v2 Part 36): histogram bin width,
# and the share of the foreground a missed colour mode must own to be seeded.
PALETTE_BIN = 4          # 64 levels per channel


THIN_PALETTE_MIN_SHARE = 0.01


PALETTE_UNIFORM_TOL = 6  # max deviation from the local median to count as core


# A cluster within this distance of the substrate (border) colour is the garment
# showing through, not ink. Deliberately much tighter than v1's global 40.0 —
# at 40 the cream muzzle of fixture 08 (Δ 34.8) was deleted as "background".
# A substrate-coloured region on FLAT artwork is the page when it is a large
# enclosed expanse — the inside of an outline ring, the counter of a script
# letter — and knocked-out artwork when it is small: type on a card, a
# catchlight, a letter counter. Share of the foreground, so it is scale-free.
#
# 0.05 is restored from the pre-Part-41 rule, which was right about flat art and
# wrong only in that Part 41 applied its removal to photographs of cloth as well.
# Measured share per enclosed component: fixture 02's wordmark tops out at 0.33%,
# fixture 06's script counter is 7.36%, fixture 04's ring interior 32.5%/54.7%.
SUBSTRATE_ENCLOSED_MAX_SHARE = 0.05
# ...and an absolute cap, because share alone keeps fixture 04's hub: the small
# circle at the centre of the ring is only 2.1% of the foreground and is still
# page, and stitching it laid 176 white stitches on white fabric.
#
# This is a HEURISTIC over a genuine ambiguity, and the pre-Part-41 code said so
# too: knocked-out type and a glyph counter are the same shape, separable only by
# scale. Measured on the cases that matter — fixture 02's wordmark glyphs top out
# at 17.6mm2, fixture 04's hub is 97.6mm2 — so 40mm2 sits between them with 2.3x
# margin below and 2.4x above. The old rule's 8.0mm2 is deliberately NOT reused:
# it was calibrated for catchlights (a mascot's is ~4mm2) and would have kept only
# the smaller half of the wordmark's letters, which is worse than dropping it.
SUBSTRATE_ENCLOSED_MAX_MM2 = 40.0
SUBSTRATE_DELTA = 12.0

# The colour planner's seed cap (v2 Part 59, making a long-standing literal
# explicit). Planning has used min(max_colors, 8) since the k-means planner
# landed; Part 57 measured that requests above it are inert — max_colors=12 and
# =8 produce byte-identical designs on every tier-A photograph — and no
# measurement has ever shown a quality gain from a larger palette. The cap is
# therefore kept, and the pipeline now SAYS so in Design.warnings instead of
# silently discarding the parameter (the Part 58 decision). Retries may still
# plan more than this when the outline check fails; the cap binds the request,
# not the recovery.
PLAN_MAX_COLORS = 8


# ...and an absolute cap, which is the discriminator that actually works: a
# highlight/catchlight is a few mm², a glyph counter at legible text sizes is
# tens of mm². Measured: mascot catchlight ≈4mm², the counter of a 25mm "O" ≈90mm².
SUBSTRATE_MAX_MM2 = 8.0


# Contour smoothing. Douglas-Peucker tolerance in mm, then Chaikin corner-cutting.
# Both are capped for small contours so fine features are not smoothed away —
# the audit requires fixture 08's freckles/catchlights and fixture 07's "L" to survive.
APPROX_EPS_MM = 0.10


CHAIKIN_ITERS = 1


SMOOTH_MIN_POINTS = 10    # below this a contour is left alone entirely
# Chaikin corner-cutting SHRINKS a polygon, and adjacent colour layers are
# smoothed independently, so an aggressive setting pulls neighbouring layers
# apart and opens bare-fabric wedges between them. Measured on fixture 01's
# gold/blue join (white area in the join region): v1 27.5% · 2 iterations at
# 0.18mm 41.1% (a real regression, caught in adversarial review) · 1 iteration
# at 0.10mm 27.8%, i.e. parity with v1 while still removing the pixel staircase.
# Anything stronger trades layer registration for edge smoothness — not worth it.


# Per-fabric stitch profiles (v2 Part 13). Until now only pull compensation was
# fabric-aware (the old PULL_BY_FABRIC scalar table); density, underlay step and
# edge inset were global constants — the single biggest feature gap against every
# competitor in docs/LAUNCH-READINESS-GAPS.md B1. Fields per fabric:
#   pull_mm   — pull compensation per side (values carried over from PULL_BY_FABRIC,
#               which tests/test_pullcomp.py pinned; higher for stretchy fabrics)
#   row_mm    — tatami fill row pitch (was global ROW_SPACING_MM = 0.45)
#   satin_mm  — satin zigzag pitch (was global SATIN_SPACING_MM = 0.4)
#   under_mm  — underlay running-stitch length (was global UNDERLAY_STEP_MM = 2.0);
#               shorter on high-loft fabrics so the underlay actually tacks the nap
#   inset_mm  — edge-walk inset (was global EDGE_INSET_MM = 0.6); deeper on loft
# COTTON IS EXACTLY THE OLD GLOBALS, so the ten-fixture regression corpus (all
# cotton) is byte-identical across this change — verified by bench diff, not
# asserted. All non-cotton values are PROVISIONAL from industry digitizing
# guidance (wovens 0.35-0.45mm, knits 0.45-0.5, fleece 0.5-0.6, terry 0.5-0.7 —
# citations in docs/COMPETITOR-COMPARISON.md) and carry the same unvalidated-on-
# fabric status as the floor: docs/FABRIC_TEST_PROTOCOL.md is the procedure.
# Known conservative approximation: `_min_stitch_px` derives the mitre's minimum
# column length from the pitch assuming SATIN_SPACING_MM; for a 0.5mm-pitch
# fabric the guard runs ~25% long (more protective, never less).
FABRIC_PROFILES: dict[str, dict[str, float]] = {
    "cotton":    {"pull_mm": 0.2,  "row_mm": 0.45, "satin_mm": 0.4,  "under_mm": 2.0, "inset_mm": 0.6},
    "denim":     {"pull_mm": 0.15, "row_mm": 0.40, "satin_mm": 0.35, "under_mm": 2.0, "inset_mm": 0.6},
    "twill":     {"pull_mm": 0.15, "row_mm": 0.40, "satin_mm": 0.35, "under_mm": 2.0, "inset_mm": 0.6},
    "poplin":    {"pull_mm": 0.15, "row_mm": 0.40, "satin_mm": 0.35, "under_mm": 2.0, "inset_mm": 0.6},
    "canvas":    {"pull_mm": 0.15, "row_mm": 0.40, "satin_mm": 0.35, "under_mm": 2.0, "inset_mm": 0.6},
    "polo/knit": {"pull_mm": 0.4,  "row_mm": 0.50, "satin_mm": 0.45, "under_mm": 1.8, "inset_mm": 0.7},
    "knit":      {"pull_mm": 0.4,  "row_mm": 0.50, "satin_mm": 0.45, "under_mm": 1.8, "inset_mm": 0.7},
    "jersey":    {"pull_mm": 0.45, "row_mm": 0.55, "satin_mm": 0.5,  "under_mm": 1.8, "inset_mm": 0.7},
    "fleece":    {"pull_mm": 0.5,  "row_mm": 0.55, "satin_mm": 0.5,  "under_mm": 1.5, "inset_mm": 0.8},
    "cap":       {"pull_mm": 0.3,  "row_mm": 0.45, "satin_mm": 0.4,  "under_mm": 1.8, "inset_mm": 0.6},
    # Terry is DENSER than fleece, not sparser: terry-specific guidance says 10-20%
    # tighter than flat fabrics so the loops cannot separate the stitching, while
    # loft-generic guides group it with fleece — the sources conflict, and the
    # protocol's terry sew-out is the tiebreaker (see COMPETITOR-COMPARISON.md).
    "towel":     {"pull_mm": 0.5,  "row_mm": 0.50, "satin_mm": 0.4,  "under_mm": 1.5, "inset_mm": 0.8},
    "terry":     {"pull_mm": 0.5,  "row_mm": 0.50, "satin_mm": 0.4,  "under_mm": 1.5, "inset_mm": 0.8},
}


FABRIC_DEFAULT = {"pull_mm": 0.25, "row_mm": 0.45, "satin_mm": 0.4, "under_mm": 2.0, "inset_mm": 0.6}


PULL_DEFAULT_MM = FABRIC_DEFAULT["pull_mm"]  # name kept: tests/test_pullcomp.py pins it


# A fill hole below this area is absorbed instead of knocked out (v2 Part 14).
# Rationale is thread-path, not thread-saving: every fill row crossing a hole
# narrower than CONNECT_MM lays a surface thread across it, so small knockouts
# read as mush (fixture 02's lettering), while the fabric bulk a small knockout
# avoids is negligible. 50mm2 is ~7x7mm — comfortably above letter-scale detail,
# far below feature-scale holes like 02's 26mm sun. Unvalidated on fabric, same
# standing as every stitch constant: docs/FABRIC_TEST_PROTOCOL.md.
HOLE_KNOCKOUT_MIN_MM2 = 50.0


# Fringe test for hole absorption: ring width probed around the hole, and the
# share of that ring the hole-owning cluster must occupy for the hole to count
# as the fringe of a continuing shape rather than a contained detail.
HOLE_FRINGE_RING_MM = 1.0


HOLE_FRINGE_MIN_SHARE = 0.3


# A connected component the 3x3 opening erases OUTRIGHT is restored when bigger
# than this — dust is 1-4 px, the smallest real letter is tens (v2 Part 14).
SPECK_KEEP_MM2 = 0.15


# Per-object classification diagnostics from the most recent digitize_image call.
# Read by the benchmark harness so the audit can explain every satin/tatami
# decision from measured geometry instead of assertion.
_CLASSIFICATION_LOG: list[dict] = []


# (area_mm2, perimeter_mm) of every region the speck filter dropped in the last
# digitize — the raw material for the too-small-to-sew warning, and inspectable
# by the bench when the warning's calibration is questioned.
_DROP_LOG: list[tuple[float, float]] = []


# A colour component smaller than this that is solidly surrounded by ONE other
# cluster is shading noise, not an element (v2 Part 29). 3mm² is a few
# thread widths long on each side — nothing sewable reads as an element at that size
# inside a field of another colour — and DETAIL_DEFER_MAX_MM2 (60mm²) is forty
# times larger, so genuine embedded detail (eyes, dots) is untouched.
SPECK_ABSORB_MAX_MM2 = 3.0


# The ring around a speck must be at least this share one single neighbour
# cluster before absorption — a speck BETWEEN two regions keeps its own vote.
SPECK_ABSORB_RING_SHARE = 0.7


# --- Gradient-band recovery for textured input (v2 Part 31) ------------------
# The peacock comparison's biggest colour finding: the three lost colours (teal
# neck transition, deep-navy shadow, pale-mint eye fringe) were all GRADIENT
# PARTNERS of kept colours, merged away by the k-means cap. And because the
# source is embroidery, its "gradients" are literally discrete thread bands —
# so recovering the dropped colours as their own bands is faithful rendering,
# not an approximation of blending. A cluster whose members split into two
# well-separated colour modes, each owning real area, is two threads.
SPLIT_DELTA_BGR = 30.0     # min mode separation; teal|brown-parent measured 49.8, mint|pale 32.8 — 36 missed mint by 3


SPLIT_MIN_AREA_MM2 = 30.0  # each half must be sewable area, not a shading tail


SPLIT_MAX_EXTRA = 3        # at most this many recovered shades per design


# --- Sketch-then-verify (v2 Part 33) -----------------------------------------
# The digitizing order a human uses: draw the outline sketch first, hold it
# against the original, and only when the structure agrees start deciding which
# colour fills where. The "sketch" here is the region-boundary map the colour
# plan implies (label boundaries + the foreground outline); verification
# measures it against the source's own edges. A low EDGE COVERAGE means the
# plan merged two regions the artwork separates (a missing line in the sketch)
# — the one failure a colour-count retry can actually fix.
SKETCH_EDGE_TOL_PX = 2       # a sketch stroke within this of a true edge matches


# Retry only when coverage falls below this. Calibrated against the corpus so
# flat artwork NEVER retries (byte-identity preserved); see the measured table
# in the Part 33 audit before moving it.
SKETCH_MIN_COVERAGE = 0.55


SKETCH_MAX_RETRIES = 2       # each retry re-plans with two more colours


# --- Dark-linework overlay for textured input (v2 Part 30) -------------------
# The peacock comparison scored "texture & stitch artistry" 3/10 with one root
# cause named buildable: the source patch edges nearly every element in dark
# stem stitch — leaf veins, petal boundaries, quill separations, crest stripes —
# and none of it survives segmentation, because a ~0.5mm dark line between two
# colour fields quantizes into whichever field is nearest. So the linework is
# recovered from the IMAGE, not the labels: a black-hat transform responds
# exactly to thin-dark-on-lighter structure, the same medial-axis tracer that
# routes satin turns the response into ordered polylines, and they are sewn as a
# final running-stitch pass in the palette's darkest thread — the top layer, as
# a hand digitizer sews outlines last.
OUTLINE_BLACKHAT_MM = 0.6   # black-hat kernel radius: lines up to ~1.2mm wide respond


OUTLINE_BLACKHAT_DELTA = 28  # min local-darkness response (0-255) to count as a line


OUTLINE_MAX_HALF_MM = 0.7   # thicker structure is a region, not a line — dropped


OUTLINE_MIN_MM = 4.0        # chains shorter than this are noise, not drawing


OUTLINE_RUN_MM = 1.4        # running-stitch length along the line (stem-stitch scale)


# Below this substrate luminance the cloth is darker than any thread the
# artwork could outline with, so the dark-linework pass has nothing real to
# find and would trace the gaps between elements (v2 Part 41).
DARK_CLOTH_LUM = 60.0


# Above this interior texture the image is photographic (a photo, a scan, a
# photographed sew-out) and colour areas carry shading the quantizer will
# shatter into speckle islands. Calibrated: the ten-fixture corpus (flat
# artwork) measures 0.00-4.10, the peacock embroidery photo 7.43; 6.0 sits in
# the gap, so the corpus takes the untouched path BY MEASUREMENT, not by hope.
TEXTURE_SMOOTH_MIN = 6.0


# Mean-shift parameters for the textured path. Chosen by counting >=50px
# colour-layer fragments on the embroidery photo: raw 341, sp10/sr40 218,
# sp14/sr52 159 (triple bilateral managed only 226). Fragments are the thing
# being fixed — each one becomes an island object or a hole in a fill.
TEXTURE_MS_SPATIAL = 14


TEXTURE_MS_COLOR = 52


# Fill stagger cycle, in rows (v2 Part 28). Without stagger, every row's
# interior penetrations land at the SAME positions along the row — measured on
# a 40x20mm rectangle: 588 of 588 interior penetrations vertically aligned with
# the previous row's, i.e. the needle punches columns of holes through the
# fabric and the fill reads as train tracks. This is the "valley effect" the
# Ink/Stitch fill documentation names, and every commercial digitizer staggers
# against it (concept adopted from their public docs; implementation our own).
# A 4-row cycle at 1/4-step offsets is the industry default.
FILL_STAGGER_ROWS = 4


# Penetrations closer than this fraction of a stitch step to a row END are
# dropped: the row edge itself penetrates there, and a second hole a few tenths
# of a millimetre inside it is the same-hole class of defect the floor guards.
# The resulting end gap is at most 1.3 steps, comparable to the 1.5-step worst
# case the previous rounding-based subdivision already produced.
_STAGGER_END_GUARD = 0.3


MIN_STITCH_MM = 0.5  # below this a needle penetration risks thread break / needle strike


# --- Travel runs, lock stitches and long-jump trims (v2 Part 25) -------------
# Before this part the stream had NO travel and NO locks: `ConnectMethod`
# declared TRIM / TRAVEL_RUN / JUMP and only TRIM was ever produced, there was
# no tie-off code anywhere, and the corpus carried 1,206 jump moves — 638 of
# them longer than the 12.7mm machine limit, the longest 87mm. An untrimmed
# long jump drags a thread trail across the design; a cut without a lock is an
# end that unravels in the wash.
#
# The blunt fix — trim every long jump — was counted and rejected: 695 jumps
# exceed 10mm, and at the ~2.5s a machine spends per trim that is half an hour
# of added runtime on this corpus alone. What professional files do instead is
# TRAVEL: a needle-up move whose path stays inside the object's own region is
# replaced by a running stitch that later stitching covers, and only a genuine
# cross-fabric move earns a trim.
#
# Travel pitch: 2.0mm, the standard travel-run length; sub-thread-visible under
# a fill or satin top layer.
TRAVEL_STEP_MM = 2.0


# A jump crossing open fabric longer than this gets a tie-off and a TRIM.
# Below it, the machine's own movement is short enough that the trail is
# accepted (and many machines auto-trim in this range themselves anyway).
TRIM_JUMP_MM = 10.0


# Lock-stitch geometry: a small triangle rather than the traditional
# stitch-in-place, because stitching in place puts repeated penetrations in one
# hole — the exact defect the 0.30mm penetration floor exists to prevent, and
# the floor metric would (rightly) flag our own ties. Legs 0.70 / 0.61 / 0.61mm
# all clear MIN_STITCH_MM; every same-side gap in the triangle clears the floor
# with the zigzag triple test applied (verified by the corpus floor count
# staying at 0 with ties emitted at every cut).
TIE_ALONG_MM = 0.7


TIE_LATERAL_MM = 0.5


# Fills may keep stitches down to this fraction of their own row pitch: the
# row-to-row connection IS one pitch long by construction, and deleting it
# recedes the fill edge (v2 Part 15). 0.95 keeps the pitch-length connection
# while anything meaningfully shorter still coalesces.
FILL_ROW_CONNECT_KEEP = 0.95


# Satin border finish on fills (v2 Part 15). 1.2mm is the narrow end of the
# 1-2mm range digitizing guides use for logo edges: wide enough to swallow the
# ragged row ends on a curve, narrow enough not to read as its own shape.
# Centered on the contour. Area-gated so specks are not double-stitched.
FILL_BORDER_MM = 1.2


FILL_BORDER_MIN_MM2 = 30.0


# --- Per-object fill angle (v2 Part 24) -------------------------------------
# Until Part 24 every tatami fill in every design was emitted at 0 degrees
# (`stitch_angle=... if is_satin else 0.0`), because `_fill_by_component` called
# `_scanline_fill`, which only knows horizontal rows. `_scanline_angled` — the
# rotate/fill/unrotate wrapper — already existed and was reachable ONLY through
# `rebuild_design`, i.e. only after a user hand-set an angle in the UI. The
# generator never used it.
#
# Why that is the single most visible difference from Wilcom/Hatch/Embird
# output: thread is directional, so a fill reflects light along its rows. One
# global angle makes every shape in a design reflect identically, which reads as
# printed rather than stitched, and it puts the row-end penetration seam on
# whichever edges happen to run horizontally — in logo artwork that is usually
# the longest, most-looked-at edge.
#
# Rows are laid ALONG the region's principal axis (major axis of the pixel
# covariance), which is what "auto angle" means in the desktop suites. Running
# along the length puts the ragged row ends on the two SHORT edges instead of
# the two long ones, so the visible seam lands on the smallest possible share of
# the perimeter.
#
# Below FILL_ANGLE_MIN_ELONGATION the shape has no meaningful long axis (disc,
# ring, square, blob) and the moment angle is numerical noise, so it falls back
# to 45 degrees — the default new fills get in Hatch and Wilcom, and the reason
# is the same one that makes 0 a bad default: 45 cannot coincide with the
# horizontal or vertical edges that dominate real artwork.
#
# 1.15 is the axis ratio at which the moment angle stops being noise. Measured
# on synthetic discs: a perfect disc lands at ratio 1.000, and a disc carrying
# one antialiased pixel of asymmetry still measures under 1.02, so 1.15 clears
# the noise floor by a wide margin while a 3:2 oval (ratio 1.22) still gets its
# own axis.
FILL_ANGLE_DEFAULT_DEG = 45.0


FILL_ANGLE_MIN_ELONGATION = 1.15


# --- Contour fill (v2 Part 24b) ---------------------------------------------
# Rows that follow the outline, for a region that is a wide STROKE rather than a
# blob — the thing the desktop suites sell as contour / curved fill, and the
# fourth of the six fill behaviours listed in the gap analysis.
#
# Applied to BANDS and never to blobs. A straight row crosses a ring at 90
# degrees at two points and runs along it at two others, so the ragged row-ends
# bunch on the inside of the curve and the fill reads as a stack of chords.
# Measured on a 40mm ring: contour rows cut jumps from 124 to 14 and spill from
# 5.6% to 2.7% at equal interior coverage.
#
# Contouring a SOLID shape tears. Its medial axis is a branching tree rather than
# a single curve, and the iso-distance rows crease along every branch: fixture
# 07's star came back with 1,708 separate missed-interior components when the
# trigger was loose enough to catch it.
#
# The test is therefore about SHAPE, not about which classification branch
# rejected the region. An earlier version keyed on `reason ==
# "wider_than_satin_cap"`, which silently missed every WIDE ring — a 10mm badge
# border trips the cheap `broad_fill_pregate` and never reaches that branch at
# all, so the most common contour-fill shape in real artwork was excluded.
CONTOUR_FILL_MIN_MM2 = 60.0


# `2 * peak_distance / sqrt(area)` — how thick a region is relative to its own
# extent. Shape survey: narrow ring 0.154, letter-O bowl 0.269, wide ring 0.276,
# square frame 0.303, very wide ring 0.405 | disc with a pinhole 0.505, solid
# star 0.731, disc 1.111.
#
# 0.30 rather than the 0.45 the shape survey alone would suggest, and the corpus
# is why. Measuring the regions that actually reach this branch: the two that
# GAIN sit at 0.151 (fixture 07's ring: +0.1 interior, jumps 630 -> 461) and
# 0.237 (fixture 03: jumps 144 -> 70). The three at 0.334, 0.430 and 0.439 all
# LOSE — together they cost 0.11 interior for +9.6% stitches, because a region
# that chunky has enough medial-axis branching for the rows to start creasing
# even though it still has a hole. The shape survey says where a band stops
# being a band; the corpus says where contouring stops paying, and that is the
# tighter of the two.
CONTOUR_FILL_MAX_BAND_RATIO = 0.30


# Contour rows are resampled at most this far apart. A straight fill row can be
# subdivided at the machine limit because a straight line has no chord error, but
# a row that follows a curve does: e ~= s^2 / (8r). Measured on the ring probe at
# its tightest radius (9.5mm), a 3.0mm step gives 0.118mm of chord error — under
# a third of a thread width, so the deviation is hidden inside the thread that
# draws it. Halving the step to 2.0mm bought +0.1 interior coverage for 48% more
# stitches, which is not a trade worth making.
CONTOUR_ROW_MAX_STEP_MM = 3.0


# --- Underlay selection by column width (v2 Part 24) -------------------------
# Until Part 24, `UnderlayType` declared six values and the generator assigned
# exactly two: CENTER_WALK for every satin object and EDGE_WALK for every fill,
# regardless of width, shape or fabric. DOUBLE_ZIGZAG, PARALLEL and CONTOUR were
# enum members with no generator behind them.
#
# Underlay is what makes satin sit UP off the fabric. A single centre run under a
# 6mm column supports nothing: the top stitching sinks between the two edges, and
# on a lofty fabric it disappears into the pile. The desktop suites all choose by
# cover type, object width and fabric; the width bands below are the ones the
# digitizing literature agrees on:
#
#   under ~2mm   centre run only     — a wider underlay would show past the edges
#   2 - 4mm      edge run            — two lines just inside the boundaries
#   over ~4mm    zigzag (both ways)  — a lattice that lifts the whole span
#
# The 4mm boundary matters more than the 2mm one: 4mm is roughly where a column
# stops being a stroke and starts being a bar, and it is also comfortably under
# SATIN_MAX_W_MM, so every column wide enough to need a lattice can get one.
UNDERLAY_EDGE_MIN_MM = 2.0


UNDERLAY_ZIGZAG_MIN_MM = 4.0


# Zigzag underlay pitch as a multiple of the fabric's underlay running length.
# Underlay is a scaffold, not coverage: too dense and it shows through the top
# stitching and stiffens the fabric.
UNDERLAY_ZIGZAG_PITCH_MULT = 1.0


# How far inside the boundary the zigzag turns, in mm. It must never reach the
# edge or it shows past the top stitching on the outside of a curve.
UNDERLAY_ZIGZAG_INSET_MM = 0.6


# Tatami (parallel) underlay under large fills. The standard commercial recipe
# for a fill is an edge run PLUS a low-density tatami layer running across the
# top fill's direction, which stops the fill sinking and stabilises the fabric
# before the top layer lands. Gated by area because a small fill is held
# adequately by its edge run alone and the extra layer would only add bulk.
FILL_UNDERLAY_MIN_MM2 = 100.0


# Underlay rows this many times the top pitch apart — a scaffold at roughly a
# third of the top layer's density.
FILL_UNDERLAY_PITCH_MULT = 3.0


# Offset from the top fill's angle. 90 degrees is the maximum possible crossing
# angle, which is what makes the layer support the top rows rather than nest
# between them.
FILL_UNDERLAY_ANGLE_OFFSET_DEG = 90.0


# Minimum spacing between consecutive SAME-SIDE penetrations in a satin column
# run. Distinct from MIN_STITCH_MM, which bounds how far the needle TRAVELS
# between penetrations: a satin column can travel 4mm across the stroke while the
# two entry points on one boundary sit a fraction of a millimetre apart. Packed
# tighter than this, the penetrations stop being stitches on the fabric and start
# being a perforated line through it — the failure mode Part 4 §8 flagged as
# unmeasured. Boundary-paced pitch reaches it on the concave side of a tight
# curve, where the inner boundary is much shorter than the outer one that sets
# the pitch.
#
# Reconciliation with the industry "running stitch never below 0.5mm" guidance
# (v2 Part 12): that guidance is a STITCH-LENGTH rule — needle travel between
# consecutive penetrations — and this codebase enforces it as MIN_STITCH_MM =
# 0.5, exactly the cited value. 0.30 here is not a more permissive version of
# that rule; it bounds a different quantity (same-side spacing, which consecutive
# stitch length cannot see) that the industry guides do not measure at all. Both
# values remain unvalidated on fabric — docs/FABRIC_TEST_PROTOCOL.md is the
# procedure for settling them empirically.
MIN_PENETRATION_MM = 0.30


# ENFORCED since v2 Part 6. Part 5 built the metric, measured the damage and left
# enforcement off so the decision could be taken on its own evidence rather than
# riding along with the instrument that found the problem. The evidence: every
# satin fixture in the corpus was violating, 8-24% of penetrations under the
# floor and hundreds at exactly 0.000mm — the needle entering the same hole
# twice. Enforcing costs 3.0 points of mean interior coverage and 3.5 of edge
# band across the satin corpus; the floor sweep and the rejected alternatives are
# in the Part 6 audit. `set_penetration_floor(None)` disables it, which is how
# the audit reproduces the before/after.
_PENETRATION_FLOOR_MM: float | None = MIN_PENETRATION_MM


# ── v2 Part 2: skeleton-guided satin lettering ───────────────────────────────
# A glyph is a STROKE, not an arbitrary blob. Filling its silhouette with
# horizontal tatami rows is what makes machine lettering read as blocky; real
# digitizing runs satin columns ACROSS the stroke, stepping ALONG its centreline,
# with the column width tracking the stroke's local width. These helpers build
# that: thin the glyph to its medial axis, walk each branch, and emit a zigzag
# whose half-width comes from the distance transform at each step.
SPUR_MIN_MM = 0.8         # skeleton branches shorter than this are thinning noise


SPUR_PRUNE_MULT = 0.6     # spur length threshold as a multiple of local half-width


# v2 Part 3: satin/tatami is decided by measured medial-axis width for EVERY
# shape. A region whose typical width is this multiple over the satin cap is a
# broad fill — skip thinning entirely and go straight to tatami (pure speed).
SATIN_PREGATE_SLACK = 1.5


# Share of a region the satin columns may fail to reach before the shape is
# judged not stroke-like. A ring or spoke is almost fully covered by columns
# swept along its axis; a disc is not, because columns are capped at the satin
# width. This is what keeps broad fills as tatami.
SATIN_MAX_UNCOVERED = 0.35


TANGENT_WINDOW = 3        # samples each side used to estimate stroke direction


# ── Edge-bounded satin (v2 Part 4) ────────────────────────────────────────────
# Parts 2/2.5/3 placed each column end by measuring outward from the medial axis
# — first the distance transform, then a ray-cast along the column's own
# direction. Both are per-sample APPROXIMATIONS of the boundary: the ray is
# aimed by a tangent estimated from a stair-stepped 1px skeleton, so wherever
# that estimate tilts, the end lands off the outline. Measured consequence:
# edge-band coverage stayed below tatami on every fixture satin took over.
#
# Part 4 stops approximating. The two boundary arcs of a stroke are extracted
# from the region's own contour and columns are laid between CORRESPONDING
# points on them, so a column end is a boundary point by construction and cannot
# fall short of, or past, the outline.
CLOSED_LOOP_TOL_PX = 2.5   # axis start/end within this = a ring, no terminals


MIN_ARC_SAMPLES = 4        # a boundary arc needs this many points to be usable


CAP_EXTRA_COLUMNS = 2      # columns added past each terminal to close the cap


PROJECT_CHUNK = 256        # contour points per distance-matrix chunk (memory)


# Consecutive stalled stations on one boundary before a mitre engages (v2 Part 8).
# A sharp vertex stalls its inner boundary for many columns in a row; a straight
# stroke only ever throws isolated short steps, and mitring those is pure damage.
MITRE_MIN_STALLED = 3


# A same-side penetration pair only counts when the triple actually ZIGZAGS: the
# same-side gap must be shorter than either crossing. True of a satin column pair,
# false of any stitch sequence advancing along a line.
#
# THIS MODULE OWNS THE VALUE. `scripts/measure_stitch_quality.py` imports it as
# `ZIGZAG_RATIO` rather than keeping its own copy (v2 Part 10 §6 item 1 flagged the
# duplicate). The pipeline owns it because `scripts/` is not a package — it is a
# dev CLI that inserts the backend root on `sys.path` — so a shipped service
# importing from it would invert the dependency. The direction here is the one
# already in use: `run_quality_bench.py` imports MIN_PENETRATION_MM and
# SATIN_SPACING_MM from this module.
ZIGZAG_RATIO = 0.9


COALESCE_REPAIR_PASSES = 200   # bound; each pass restores at most one point


UNDERLAY_REPAIR_PASSES = 200   # bound; each pass drops at most one point
# NO outward bias is applied to column ends. One was tried — a contour point is
# the centre of the outermost pixel still inside the shape, so half a pixel of
# reach is arguably owed — and while the coalescing defect below was still in
# place it did buy coverage. Once that was fixed it buys nothing (fixture 03 edge
# band 97.2 -> 97.2, fixture 05 98.3 -> 98.4 at +0.5px) and costs spill
# (03 8.0 -> 9.7, 05 12.2 -> 15.6, 04 47.3 -> 55.3). Removed. Sweep in the audit.


# Zhang-Suen's clockwise ring P2..P9 starting north, as (dy, dx) steps. Order is
# load-bearing: A counts 0→1 transitions ROUND this cycle.
THIN_RING = ((-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1))


# Candidate neighbour offsets as (dx, dy), orthogonals first then diagonals.
# THE ORDER IS LOAD-BEARING: `walk` follows nxt[0], so any reordering re-routes
# branches and changes stitches. The unrolled loop in `_skeleton_adjacency` must
# stay in step with these tuples.
SKEL_ORTHO = ((1, 0), (-1, 0), (0, 1), (0, -1))


SKEL_DIAG = ((1, 1), (1, -1), (-1, 1), (-1, -1))


def set_penetration_floor(mm: float | None) -> None:
    """Enable (or disable, with ``None``) the same-side penetration floor."""
    global _PENETRATION_FLOOR_MM
    _PENETRATION_FLOOR_MM = mm


# Below this gap between two regions of the SAME colour, the machine carries the
# thread across instead of trimming (v2 Part 48). A trim plus the re-thread costs
# roughly 2.5 s; at 844 trims on the reference panel that is about 35 minutes of
# machine time per run, which is a real production cost.
#
# 6.0mm is the conservative end of the range commercial machines auto-trim at
# (5-10mm). It is chosen against the measured gap distribution rather than in the
# abstract: after nearest-neighbour ordering, 28.6% of inter-object gaps on the
# panel fall under 6mm against 9.2% before, so the ordering is what makes this
# threshold worth having at all.
TRIM_MIN_GAP_MM = 6.0
