# The fixture-08 density peak — closed, with two new items opened

Opened by the CTO ruling of 2026-08-10 §1, which accepted the parity fix and directed:

> Land the parity fix; open the lock-site question as its own item with a probe built around the
> lock geometry rather than a fixed box. If that probe later shows a real general density rise, it
> is a separate fix on a stable base.

This is that probe and its result. **Every number below was produced by running the shipped code**
— `digitize_image` on `08_mascot_detail.png` at `run_quality_bench.RNG_SEED`, once on the parity
tree and once on a `git worktree` at the pre-parity commit `1431383`. Nothing is re-derived by hand
and nothing comes from a reimplementation.

## Verdict: not a density rise

| metric | before (`1431383`) | after (parity) |
| --- | --- | --- |
| `max_per_cell` | 13 | **14** |
| `p99_per_cell` | 5 | 5 |
| `flagged_cells` | 0 | **1** |
| `max_per_disc` (grid-free) | 23 | **26** |
| cells at the max | 1 | 1 |
| tail, top 12 | 13, 12, 9, 8, 8, 8, 8, 7, 7, 7, 7, 7 | 14, 12, 9, 8, 8, 8, 8, 7, 7, 7, 7, 7 |
| penetrations | 8,080 | 8,091 |
| objects | 20 | 20 |

Only the top entry moves. `p99` and the entire remainder of the tail are identical.

## What the site actually is

The peak is a **coincidence of two satin objects**, not a fill defect. Measured with
`cv2.pointPolygonTest` against each object's stored contour, two objects reach the point
(35.93, 65.03):

| object | type | stitches | signed distance |
| --- | --- | --- | --- |
| `Satin 1 (#de6c26)` | SATIN | 3,905 | −0.15 mm |
| `Satin 19 (#30221e)` | SATIN | 53 | −0.05 mm |

Their contributions are different in kind:

- **`Satin 1` supplies ~17 of the 26**, at penetration indices 1767–1881, arriving as *alternate*
  ends of a column zigzag — successive penetrations are 2.6–4.7 mm apart while every other one lands
  inside the same 0.5 mm disc. That is a satin column sweep pivoting about one point. It is
  **identical before and after the parity fix** and is the larger half of the density here.
- **`Satin 19` supplies the +3**, and it is a **tie-off**. After the fix: five consecutive
  penetrations entered by `JUMP@8071`, steps 0.617 / 0.342 / 0.700 / 0.610 / 0.610, the last
  returning to exactly `(36.006, 64.803)` — the coordinate of the second. Before the fix the same
  signature appears with three members, revisiting `(35.869, 64.717)`. Returning to an
  already-stitched coordinate immediately after a jump is what a lock *is*; it matches the design's
  final tie-off at stream 8155–8157 (steps 1.0 / 0.707 / 0.707, returning to its anchor).

So the ruling's third bullet — "the site is a lock" — is correct **about the delta**. It is not a
complete description of the site: most of the density there predates the fix and comes from
`Satin 1`.

## Two fixed-box mistakes, both now pinned as tests

The CTO's instruction was to build the probe around the lock geometry "rather than a fixed box". The
first two attempts used a box anyway, and both gave the wrong answer:

1. **The density probe judged run structure per cell.** A tie-off oscillates about one anchor, so
   when the anchor sits near a cell boundary its penetrations alternate between two cells and the
   run structure *within* either cell degenerates to singletons. The probe reported
   `looks_like_lock: false` — 14 penetrations in 13 runs — for a genuine lock. Re-run over a disc,
   the same site shows one consecutive run of five.
2. **The test helper repeated it verbatim.** `_has_tieoff_signature` looked inside the flagged cell
   alone and reported "not a tie-off". The revisited coordinate `(36.006, 64.803)` bins to cell
   (72, 129) while the flagged cell is (71, 130) — the lock straddles the grid line, which is
   *precisely why that cell reached the flag*. A cell-shaped test can never see it.

`tests/test_stitch_quality_metrics.py::test_the_tieoff_discriminator_sees_a_lock_that_straddles_the_grid`
pins the second one so the neighbourhood cannot quietly shrink back to a box.

## What changed in the gate, and what did not

`test_density_corpus_health_is_pinned` previously asserted `max_per_cell <= 13` and
`flagged_cells == 0`. Because `DENSITY_FLAG_PER_CELL` **is** 14, a max of 14 forces
`flagged_cells >= 1`; the two assertions cannot both survive a peak of 14. Rather than move the
bound, the gate now discriminates cause:

- `p99_per_cell <= 6` — **kept verbatim**. This is the actual density-shift detector and it did not
  move.
- `max_per_disc <= 26` — **new**. Translation-invariant, so unlike `max_per_cell` it cannot be a
  grid artefact.
- `flagged_cells <= 1` — relaxed by one, **and** every flagged cell must now prove it is a tie-off
  by containing a coordinate revisit in its neighbourhood.

The count bound is weaker. The gate is stronger where it matters: a change that piles *fill* into a
cell has no coordinate revisit and now fails, where the old form would have passed it at 13. Two
tests assert the discriminator answers **no** to dense stitching with no revisit and **yes** across a
grid straddle — a check that cannot say no is worse than no check, because it reads in the diff as a
safety assertion.

## Opened by this investigation

1. **`Satin 1`'s column-end pivot puts ~17 penetrations in one 0.5 mm disc.** Pre-existing,
   untouched by the parity fix, and the larger half of the corpus's worst density site. This is the
   real fabric-perforation question at this location and it has never been examined. It is a satin
   column geometry question (the inner side of a tight turn re-using its pivot), not a flag-level
   question.
2. **`sum(object.stitch_count)` is 8,001 against 8,091 actual penetrations — 90 unattributed**, on
   both trees. Found incidentally; it did not affect anything above, because the probe checked the
   totals and fell back to whole-stream attribution rather than inventing object boundaries. It
   matters on its own: the CTO's real-artwork comparison harness is specified to measure
   **per-object stitch-type agreement** against an expert machine file, and that reconciliation
   depends on per-object counts being right.
