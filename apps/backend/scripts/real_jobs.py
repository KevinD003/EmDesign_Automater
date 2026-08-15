"""Real job pairs: customer artwork beside the machine file an expert produced.

A SEPARATE CORPUS TIER, deliberately. `corpus100` is 13 real images, 40 crops and
recolours of three photographs, and 47 generated designs — and its own docstring
warns that a tier-C average must never be read as a real-world score. Real job
pairs are the only material that can answer "is our output competitive", so they
get their own root, their own tier label, and no path by which they can be
averaged into A/B/C. `TIER` below is asserted distinct from the corpus100 tiers
by `tests/test_real_job_harness.py`.

WHAT A JOB IS

    tests/fixtures/corpus_real/
        <job-name>/
            artwork.png          the customer's file, as supplied
            expert.dst           what a professional digitizer produced from it
            job.json             optional; fabric, hoop, colours, provenance

One artwork and one machine file per directory. Both are required — a job with
only one half cannot be compared and is an error, not a skip, for the same reason
`build_corpus100.py` now refuses a missing tier-A source: a corpus that silently
shrinks is worse than one that fails.

NOTHING IS TUNED AGAINST THIS. The instrument exists before the material, on
purpose. When real pairs arrive the first question is what the comparison says,
not what it can be made to say.

WHAT TO ASK FOR is kept beside the (empty) directory, in
`tests/fixtures/corpus_real/README.md`, so whoever is about to send material
reads it rather than this module. One line of it is load-bearing enough to
repeat here: **at least one FLAT-LIT SCAN, not only photographs.** The A01/A02
promotion measured that a photograph takes the textured path and therefore
cannot reach `hairline_runs` AT ALL — its close/open at 0.4/0.3 mm removes
everything the 0.25 mm sub-thread census could see, and both promoted
photographs contributed zero regions with their narrowest at 0.34 and 0.38 mm.
So more photographs will never exercise the hairline machinery, and the noise
criterion deferred on 2026-08-18 is deferred on a class that cannot reach the
code. Artwork scoring under `TEXTURE_SMOOTH_MIN` (6.0) is what reaches it.

    python scripts/real_jobs.py            # list what is present, validate it
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND / "tests" / "fixtures" / "corpus_real"

# Kept out of `corpus100`'s A/B/C namespace on purpose — see the module docstring.
TIER = "R-real-job"

# What the digitizer is asked for when `job.json` does not say. These are the
# bench's own defaults rather than new numbers, so a job with no metadata is
# digitized exactly as the bench digitizes an unspecified fixture.
DEFAULT_PARAMS = {"fabric": "cotton", "hoop": "100x100", "colors": 6, "text": False}

META_FILENAME = "job.json"

ARTWORK_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".svg"}
# Read support is pyembroidery's, not a list invented here; `_supported_read_exts`
# is consulted at load time so this stays a hint rather than a second source of
# truth that can drift from what the reader actually accepts.
EXPERT_EXTS_HINT = {".dst", ".pes", ".exp", ".jef", ".vp3", ".xxx", ".pec", ".sew"}


class RealJobError(RuntimeError):
    """A job directory that cannot be used. Never downgraded to a warning."""


@dataclass(frozen=True)
class RealJob:
    name: str
    artwork: Path
    expert: Path
    params: dict = field(default_factory=lambda: dict(DEFAULT_PARAMS))
    notes: str = ""

    @property
    def tier(self) -> str:
        return TIER


def _one(paths: list[Path], kind: str, job: str) -> Path:
    if not paths:
        raise RealJobError(
            f"{job}: no {kind} file. A job is a PAIR — the customer's artwork and "
            f"the machine file an expert produced from it. Half a pair cannot be "
            f"compared."
        )
    if len(paths) > 1:
        raise RealJobError(
            f"{job}: {len(paths)} {kind} files ({[p.name for p in paths]}). One "
            f"per job, so there is no question which one the numbers came from."
        )
    return paths[0]


def _expert_exts() -> set[str]:
    """Extensions the embroidery reader actually accepts, asked at load time."""
    try:
        sys.path.insert(0, str(BACKEND))
        from app.services.embroidery_io import _supported_read_exts

        return {e if e.startswith(".") else f".{e}" for e in _supported_read_exts()}
    except Exception:  # noqa: BLE001 - fall back to the hint, still validate
        return set(EXPERT_EXTS_HINT)


def load_jobs(root: Path | None = None) -> list[RealJob]:
    """Every job pair under ``root``, validated. Empty list when none exist yet.

    An EMPTY root is a normal state — the instrument ships before the material —
    and returns []. A malformed job is not: it raises.
    """
    root = ROOT if root is None else root
    if not root.exists():
        return []

    expert_exts = _expert_exts()
    jobs: list[RealJob] = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        # `job.json` is EXCLUDED BY NAME before anything is classified.
        # `_expert_exts()` asks pyembroidery what it can read, and pyembroidery
        # reads a `.json` stitch format — so the job's own metadata file matched
        # as a machine file and every job carrying one failed with "2 machine
        # files". Reserving the name is the fix; inferring the metadata file from
        # what is left over would break again the moment the reader gains another
        # extension.
        files = [f for f in sorted(d.iterdir())
                 if f.is_file() and f.name != META_FILENAME]
        artwork = _one([f for f in files if f.suffix.lower() in ARTWORK_EXTS],
                       "artwork", d.name)
        expert = _one([f for f in files if f.suffix.lower() in expert_exts],
                      "machine", d.name)

        params = dict(DEFAULT_PARAMS)
        notes = ""
        meta_path = d / META_FILENAME
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise RealJobError(f"{d.name}: job.json is not valid JSON: {exc}") from exc
            unknown = set(meta) - set(DEFAULT_PARAMS) - {"notes"}
            if unknown:
                # Silently ignoring a key means a job digitized at settings the
                # metadata says it was not.
                raise RealJobError(
                    f"{d.name}: job.json has unknown keys {sorted(unknown)}; "
                    f"known keys are {sorted(set(DEFAULT_PARAMS) | {'notes'})}"
                )
            notes = str(meta.pop("notes", ""))
            params.update(meta)
        jobs.append(RealJob(name=d.name, artwork=artwork, expert=expert,
                            params=params, notes=notes))
    return jobs


def main() -> int:
    try:
        jobs = load_jobs()
    except RealJobError as exc:
        print(f"invalid job: {exc}")
        return 1

    if not jobs:
        print(f"no real job pairs yet — expected under {ROOT}")
        print("  <job-name>/artwork.png + <job-name>/expert.dst  (+ optional job.json)")
        print("\nThis is the expected state until real artwork arrives. The "
              "comparison harness (scripts/compare_expert.py) is built and tested "
              "against synthetic pairs so it is ready when they do.")
        return 0

    print(f"tier {TIER} — {len(jobs)} job pair(s) under {ROOT}\n")
    print(f"{'job':28s} {'artwork':22s} {'expert':18s} fabric    hoop      colours")
    for j in jobs:
        print(f"{j.name:28s} {j.artwork.name:22s} {j.expert.name:18s} "
              f"{j.params['fabric']:9s} {j.params['hoop']:9s} {j.params['colors']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
