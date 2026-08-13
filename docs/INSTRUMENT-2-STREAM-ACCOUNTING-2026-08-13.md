# INSTRUMENT-2 — the stream accounts for itself, and the "90" was not a count

**Status: landed.** The identity holds on all fourteen fixtures and is pinned as four tests.

The headline correction first, because it changes what the task was:

> **The 90 unattributed penetrations were never a number of penetrations.** They came from
> `sum(object.stitch_count) − design.stitch_count`, and that subtraction is malformed: the two
> operands are counted in different spaces. Both readings were exact. The difference had no
> referent, and the explanation attached to it — "they are lock stitches" — was never testable.

---

## 1. Why the subtraction was malformed

| quantity | what it counts | when it is fixed |
| --- | --- | --- |
| `object.stitch_count` | `len(stitches) - obj_start` — a **stream span**, including the JUMPs and TRIMs emitted inside that object | at emission, **before** `_lock_stream` runs |
| `design.stitch_count` | STITCH entries alone — a **penetration count** | after locking |

Subtracting a penetration count from a sum of stream spans mixes three separate discrepancies
into one number and then names it after only one of them:

* object spans contain non-penetrating entries (their own lead-in TRIM and JUMP, plus every
  internal travel jump), which pushes the sum **up** relative to penetrations;
* object spans exclude every tie-off, which pushes it **down**;
* entries belonging to no object at all — colour-stop separators, the END marker — are in
  neither operand.

On the current tree the same malformed subtraction gives **94** on fixture 08. The actual
lock-penetration count is **162**. The old figure was not a bad estimate of the lock count; it
was not an estimate of it at all.

## 2. The identity, in one space at a time

The census is taken at the three points where the stream is rewritten — before the same-hex
merge, before locking, after locking — and recorded in `pipeline._LAST_STREAM_ACCOUNTING`.

**Stream space.** Every entry belongs to exactly one of six named categories:

```
stream_length == object_spans        # entries inside an object's own recorded span
               + stop_separators     # one per colour-stop boundary
               + linework_lead_in    # the TRIM and JUMP before each dark-linework run
               + end_markers         # the terminating END
               + merge_inserted      # JUMPs added when two same-thread stops merged
               + lock_inserted       # tie-offs and the TRIMs they force
```

**Penetration space.** Every needle penetration has one of two sources, and there is no third:

```
penetrations == penetrations_in_object_spans + lock_penetrations
```

### Fixture 08_mascot_detail [cotton @ 130×180], measured at `480b6c6`

```
stream_length            8106  =  object_spans          7930
                                + stop_separators          3
                                + linework_lead_in         0
                                + end_markers              1
                                + merge_inserted           0
                                + lock_inserted          172

penetrations             8024  =  in_object_spans       7862
                                + lock_penetrations      162      (54 ties x 3)

lock also inserted         10  TRIMs
difference from named       0
```

`162 = 54 × 3` is `_tie_triangle`'s construction exactly. That is the check that the category
is what it claims to be, rather than a residual with a label on it.

## 3. Why the census is recorded and not reconstructed

A lock stitch is an ordinary `STITCH` entry. Once it is in the stream it is indistinguishable
from real stitching by anything except its geometry, and recognising it by geometric signature
is precisely the inference that already located one tie-off at the wrong stream index — two
different tie-offs in one jump-delimited run shared a sub-signature. Recording the count at the
moment the entries are created is the only version of this that cannot be wrong.

## 4. Two things that had no name before

Both were found by writing the identity and watching it fail to close.

* **`_merge_adjacent_same_hex` inserts entries.** When it rewrites a `COLOR_CHANGE` into a
  `TRIM`, it inserts a `JUMP` if the next entry is a `STITCH` — a repositioning the TRIM no
  longer implies. It is 0 on fixture 08, but it is not structurally zero, and nothing counted
  it.
* **The dark-linework pass sets `obj_start` after its lead-in.** The main loop sets `obj_start`
  *before* its own TRIM and JUMP, so those land inside the object's span; the linework pass sets
  it *after*, so they land outside every span. Two entries per linework run, uncounted.

## 5. A defect the identity caught immediately

`_LAST_STREAM_ACCOUNTING` is module state, and the photographic-texture rescue calls
`digitize_image` recursively. The inner call overwrote the census, so when the retry was
**rejected** the module held the smoothed attempt's numbers while the caller received the
original design.

It surfaced the same day only because DET2 pushed fixture 04 over the 0.19 retry gate: the
census read **1,179 penetrations** while the returned design had **1,855**. Fixed by snapshotting
and restoring across the retry, the way `_LAST_UNCOVERED_PX`, `_DROP_LOG` and
`_CLASSIFICATION_LOG` already are. The rule is general: **every module-level diagnostic must
survive the retry branch or it describes a design nobody receives.**

## 6. Tests

`tests/test_stream_accounting.py`, four identities × fourteen fixtures = 56 assertions:

1. every stream entry belongs to exactly one named category;
2. every penetration is either in an object span or a lock, and the lock count is a whole
   number of three-point ties;
3. the merge pass adds no penetrations;
4. stream length minus penetrations equals the number of non-STITCH entries — *exactly*, which
   is what makes the two index spaces convertible rather than merely different.

Test 4 asserts the gap is **explained**, not that it is small. On `01_flat_2color_logo` it is 11
and on `08_mascot_detail` it is 82; both are correct, and neither is an anomaly.

## 7. Reproducing

```
cd apps/backend
.venv/bin/python -m pytest -q tests/test_stream_accounting.py
.venv/bin/python scripts/trace.py 08_mascot_detail --key accounting
```

`trace.py`'s `accounting` block still carries `"unreconciled": true` — it reports the raw spans
without the census. Wiring it to `_LAST_STREAM_ACCOUNTING` is a one-line follow-up and is
deliberately not in this change, so the identity lands and is verified before the reporting
surface starts depending on it.

## 8. Fixture limits

Fourteen synthetic images, cotton, two hoop sizes. The identity is structural — it is arithmetic
over the pipeline's own emission sites, not a measurement of artwork — so it should hold on any
input. It is unverified on real artwork, on the rebuild path (`rebuild.py` calls `_lock_stream`
too and has no census), and on designs that emit nothing, which the tests skip rather than
assert about.
