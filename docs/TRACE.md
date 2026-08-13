# TRACE — every headline number gets a command and a key

**Rule for every StitchIQ report from now on:** a number in prose carries the command that
produces it and the key it is read from. If it cannot, it does not go in the report.

```
cd apps/backend
.venv/bin/python scripts/trace.py 08_mascot_detail --key design.penetrations
```

## Why this exists

Three errors in this repo are all the same error — a number that outlived the conditions it
was measured at:

* **"22.65 machine-minutes"** travelled through four reports before anyone checked. The
  corpus spans 18.78–22.64 minutes; the figure was one fixture near the top of the range,
  quoted as if it described the corpus.
* **A jersey number was reported as fleece.** The correction then gave the wrong hoop for two
  fixtures. Two labelling errors in two hours.
* **A tie-off was located at the wrong stream index.** Both readings were exact. Two
  different tie-offs in the same jump-delimited run shared a sub-signature, and the two index
  spaces were being read as one. *The error was a locator, not a number.*

`run_quality_bench.py` already refuses to print an unlabelled headline. This is the other
half: one JSON document per run, carrying the numbers, the conditions, the input's hash and
the tree they came from.

## Usage

```
scripts/trace.py 08_mascot_detail                    # one fixture, JSON to stdout
scripts/trace.py --all --json trace.json             # all fourteen
scripts/trace.py 08_mascot_detail --key machine.minutes_net_of_trim
scripts/trace.py 08_mascot_detail --stream-index 8071
scripts/trace.py 08_mascot_detail --penetration-index 7992
```

`--key` takes a dotted path and prints one value. With `--all` the document is a list, so the
first component is an index: `--key 7.design.penetrations`.

The fourteen are the ten bench fixtures plus `C24_many_colours`, `C11_many_colours`,
`C05_gradient_field`, `C18_gradient_field` at SH2's configuration. The fixture table, the RNG
seed and the machine model are **imported** from `run_quality_bench.py` and
`coverage_audit.py`, never retyped — a trace that used its own copy of any of them would
certify numbers no other harness produces.

## The two index spaces

A stitch position is meaningless without its space, and these differ by hundreds of entries
on a real design.

| space | counts | where it is used |
| --- | --- | --- |
| **stream index** | position in `design.stitches` — STITCH, JUMP, TRIM, COLOR_CHANGE | slicing the stitch list; `_lock_stream` inserts tie-offs here |
| **penetration index** | position among STITCH entries alone | `design.stitch_count`; the machine-time estimate; what the needle does |

Measured at `3e20a1f`: `01_flat_2color_logo` [cotton @ 100×100] has stream length 6,176 and
6,165 penetrations — the two spaces differ by 11. `08_mascot_detail` [cotton @ 130×180] has
8,106 and 8,024 — **82**.

That 82 is worth a note about this document's own rule. An earlier report put the gap on
fixture 08 at **79**, and that figure was correct *on the parity tree*, where 08 ran 8,091
penetrations. The parity fix moved the fixture to 8,024 and the gap with it. Neither number
was ever wrong; one of them was quoted without the tree it belonged to, which is precisely
the failure this script exists to make impossible. Hence `code.head` in every document.

`--stream-index` and `--penetration-index` convert between them and print the entry, so a
locator in a report can be checked rather than trusted. An entry that is not a STITCH has
**no** penetration index and the tool says so rather than inventing one.

**A third span, reported and deliberately not reconciled.** An object's own `stitch_count` is
`len(stitches) - obj_start`, computed before `_lock_stream` runs — a *stream span* including
the JUMPs and TRIMs inside that object, and excluding the lock stitches inserted afterwards.
Summing it and comparing against penetrations compares two different things. The
`accounting.*` block reports both sides, their difference, and `"unreconciled": true`.
Closing that identity with named categories is INSTRUMENT-2's job; until it lands, the trace
says it is open rather than implying it is closed.

## What one document contains

| block | key | note |
| --- | --- | --- |
| identity | `fixture`, `source.sha256`, `source.bytes` | the exact input bytes |
| conditions | `conditions.label`, `.fabric`, `.hoop`, `.max_colors`, `.rng_seed` | never optional |
| provenance | `code.head`, `code.dirty`, `toolchain.*` | `dirty: true` means the tree was not clean; treat the numbers as unattributable |
| design | `design.penetrations`, `.stream_length`, `.jumps`, `.trims`, `.objects`, `.object_types` | |
| machine | `machine.minutes_net_of_trim` | plus both halves, `sew_minutes` and `trim_minutes`, because quoting either alone is how a regression gets reported as a win |
| coverage | `coverage.uncovered_px` | the pipeline's own figure, read from the pipeline — see DET2 |
| accounting | `accounting.*` | open; see above |
| index spaces | `index_spaces.*` | |
| warnings | `warnings` | verbatim, as the user would see them |

## What it does not do

It runs the shipped `digitize_image` at a pinned seed and reports what came back. It does not
re-implement a metric, compare against a baseline, or judge anything. A trace is evidence,
not a verdict.
