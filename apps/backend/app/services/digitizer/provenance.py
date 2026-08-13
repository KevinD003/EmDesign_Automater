"""Object provenance: did the user edit THIS object, and where are its stitches?

The B1.5 pass-through rests on two questions, and both are answered here so the
answers cannot drift apart:

* ``object_params_hash`` — a fingerprint of everything that determines an
  object's stitches. Equal hash means "regenerating would produce the same
  stream", so the stored stream can be reused instead.
* ``is_unedited`` — whether an object still matches its own fingerprint.

WHY THERE IS NO PER-OBJECT SLICE HELPER HERE. Splicing one object's stitches
out of a stored stream needs reliable boundaries, and there are none to record:
digitize emits object bodies and THEN rewrites the whole stream (`_lock_stream`
inserts tie stitches inside every block, `_merge_adjacent_same_hex` collapses
colour stops), so any index captured at emission is stale by the time the
design is returned. Measured while attempting exactly that: the recorded range
for fixture 01's first object ended 2.88mm away from its own stored exit point.
Per-object pass-through therefore needs boundary tracking THROUGH those passes
— real work, deliberately not faked with indices that look right and are not.
"""

from __future__ import annotations


def object_params_hash(obj) -> str:
    """Fingerprint of everything that determines an object's stitches (B1.5).

    Two objects with the same hash MUST generate the same stream, so the hash
    covers the geometry (contour, holes, flow lines) and every generator
    parameter — and deliberately NOT `name`, `id`, `sequence_order`,
    `color_stop`, `entry_point`, `exit_point`, `penetration_count` or
    `stream_span`: renaming an
    object, recolouring it or moving it in the sew order changes none of its
    stitches, and treating those as edits would throw away the pass-through for
    exactly the operations (recolour, reorder, Optimize) that need it most.

    Coordinates are rounded to 1e-4 mm before hashing — far below the 0.1mm
    fidelity criterion and below a thread width — so a JSON round trip that
    perturbs the last float digit cannot masquerade as an edit.
    """
    import hashlib
    import json

    def pts(seq):
        return [[round(float(p.x), 4), round(float(p.y), 4)] for p in (seq or [])]

    payload = {
        "stitch_type": str(getattr(obj.stitch_type, "value", obj.stitch_type)),
        "density": round(float(obj.density or 0.0), 6),
        "stitch_angle": round(float(obj.stitch_angle or 0.0), 4),
        "underlay_type": str(getattr(obj.underlay_type, "value", obj.underlay_type)),
        "pull_compensation": round(float(obj.pull_compensation or 0.0), 6),
        "contour": pts(obj.contour),
        "holes": [pts(h) for h in (obj.holes or [])],
        "flow_line": pts(obj.flow_line),
        "flow_line_b": pts(obj.flow_line_b),
        "flow_divide": pts(obj.flow_divide),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()[:32]


def is_unedited(obj) -> bool:
    """True when the object's parameters still match the ones that made it."""
    return bool(obj.params_hash) and obj.params_hash == object_params_hash(obj)


# How far an object's recorded entry point may sit from the stitch it claims
# to be, before the stream is judged inconsistent with the objects. 0.01mm is a
# tenth of the fidelity criterion and far below a thread width.
_ENTRY_TOLERANCE_MM = 0.01


def objects_match_stream(design, objs) -> bool:
    """True when `objs` are in the order their stitches actually appear.

    `object_params_hash` ignores `sequence_order` on purpose — reordering
    changes no stitch OF an object — so "every object is unedited" is NOT
    enough to conclude a rebuild has nothing to do: Optimize reorders objects
    and edits none of them, and treating that as a no-op would make Optimize
    silently do nothing.

    Object bodies cannot be sliced out of the stream by index (see the module
    docstring), but each object records its own entry point, so the ORDER can
    still be checked: walk the stream once and require each entry point to
    appear after the previous one. A design whose objects were reordered fails
    here and regenerates. So does one whose stream was rewritten underneath the
    objects — by the stitch editor, say — which is the safe answer too.
    """
    import math

    cursor = 0
    for obj in objs:
        point = obj.entry_point
        if point is None:
            return False
        for i in range(cursor, len(design.stitches)):
            s = design.stitches[i]
            if math.hypot(s.x - point.x, s.y - point.y) <= _ENTRY_TOLERANCE_MM:
                cursor = i + 1
                break
        else:
            return False
    return True


def rebuild_is_a_noop(design, objs) -> bool:
    """True when a rebuild could not change anything, so it must not try.

    Re-rastering an unedited design only degrades it: rebuild works on a 0.1mm
    grid (A8) while the stored stream came off the digitizer's finer geometry,
    so every Apply and every Optimize used to roughen every edge in the design
    and repeated edits accumulated the damage (C6). It is also the only way the
    fidelity criterion ("no coordinate moves >0.1mm") can hold at all —
    regenerating from a contour approximates coordinates, it cannot reproduce
    them.

    Three conditions, and all three are load-bearing:

    * there IS a stored stream to keep;
    * every object still matches its own fingerprint — no parameter that feeds
      a generator has changed;
    * the objects are still in the order their stitches appear, which
      `objects_match_stream` checks against the stream itself rather than
      against `sequence_order`. Without this a pure Optimize reorder would be
      reported as "nothing to do" and Optimize would silently do nothing.

    An object with no fingerprint — every design saved before B1.5, every
    imported machine file — fails the second condition, so those regenerate
    exactly as they always did.
    """
    return bool(
        design.stitches
        and all(is_unedited(o) for o in objs)
        and objects_match_stream(design, objs)
    )
