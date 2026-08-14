"""Which tree a measurement came from. One implementation, both instruments.

Every number this repository reports is supposed to carry its conditions. TRACE
established the block — `code.head`, `code.dirty`, the toolchain versions — and
`coverage_audit.py` did not have it. That gap produced a real error: C11's
coverage was quoted at 6.74 % from a PRE-boundary audit JSON beside an object
count from the POST-boundary one. Both numbers were correct measurements of
their own trees; the row was two trees spliced together, and nothing in either
file said so.

The lesson recorded at the time was "route the coverage table through TRACE".
The CTO's ruling of 2026-08-21 sharpened it, and the sharpening is the reason
this module exists rather than a copied function:

    Emitting the field still requires a human to look at it. Refusing the
    comparison does not. The failure mode was memory compensating for a
    missing field; a field you can still ignore does not close it.

So this module supplies the field, and its consumers are expected to REFUSE to
compare across trees rather than merely record which tree they were on.

Why a module and not an import from `trace.py`: `trace.py` already imports the
fixture table from `coverage_audit.py`, so having `coverage_audit` import
`trace` would close a cycle. A shared bottom layer is the same shape as
`accounting.py` serving both emitters — one implementation cannot drift into
two that disagree.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def code_provenance() -> dict:
    """`{"head": <sha or "">, "dirty": bool}` for the tree this ran on.

    `dirty` true means the working tree had uncommitted changes, so the
    measurement cannot be attributed to `head` — the same statement TRACE
    makes. An empty `head` means git could not answer (a tarball, a stripped
    checkout); that is also unattributable, and `attributable()` says so.
    """
    def _run(*args: str) -> str:
        try:
            return subprocess.run(("git", *args), cwd=BACKEND, capture_output=True,
                                  text=True, timeout=10).stdout.strip()
        except Exception:  # noqa: BLE001 — a measurement from a tarball is still a measurement
            return ""

    return {"head": _run("rev-parse", "HEAD"), "dirty": bool(_run("status", "--porcelain"))}


def toolchain() -> dict:
    import cv2
    import numpy as np

    return {"python": sys.version.split()[0], "opencv": cv2.__version__,
            "numpy": np.__version__}


def attributable(code: dict | None) -> bool:
    """Can this measurement be pinned to a specific commit?

    False for a dirty tree, an unknown head, or a document written before the
    provenance block existed. All three are the same condition for a reader:
    you cannot tell which code produced the number.
    """
    if not code:
        return False
    return bool(code.get("head")) and not code.get("dirty")


def describe(code: dict | None) -> str:
    """One line naming the tree, for refusal messages and headers."""
    if not code:
        return "UNATTRIBUTABLE (no provenance block — written before it existed)"
    head = code.get("head") or "unknown"
    if not code.get("head"):
        return "UNATTRIBUTABLE (git could not name the head)"
    return f"{head[:7]}{' + UNCOMMITTED CHANGES (unattributable)' if code.get('dirty') else ''}"
