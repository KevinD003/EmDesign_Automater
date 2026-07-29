"""Verify that audit documents' lint claims match what ruff actually reports.

v2 Part 12, Part A item 6. Parts 7-10 each printed "ruff: 14 findings over every
touched file" when 14 was ``digitizer.py`` alone — the substantive claim ("all
pre-existing") happened to be true, but the scope wording was wrong four audits
running and nothing could catch it. This makes the claim machine-checkable.

An audit that wants its lint count verified embeds one line:

    LINT-VERIFY: findings=14 files=apps/backend/app/services/digitizer.py apps/backend/scripts/foo.py

Paths are relative to the REPO ROOT (unambiguous wherever the checker runs).
The checker re-runs ruff over exactly those files and fails on any mismatch, so
a claimed count that drifts from reality fails CI instead of surviving four
parts. Audits without the marker (everything before Part 12) are skipped —
history is not retroactively gated.

    python scripts/verify_lint_claim.py ../../docs/benchmarks
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[1]
MARKER = re.compile(r"^LINT-VERIFY:\s+findings=(\d+)\s+files=(.+?)\s*$", re.MULTILINE)
FINDING = re.compile(r"^\S+:\d+:\d+:", re.MULTILINE)


def ruff_findings(files: list[Path]) -> int:
    """Count of ruff findings over `files`, parsed from concise output."""
    proc = subprocess.run(  # noqa: PLW1510 - findings make ruff exit nonzero by design
        [sys.executable, "-m", "ruff", "check", "--output-format=concise",
         *[str(f) for f in files]],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    return len(FINDING.findall(proc.stdout))


def check_audit(path: Path) -> list[str]:
    """Returns a list of failure messages for one audit file (empty = pass/skip)."""
    failures = []
    for m in MARKER.finditer(path.read_text()):
        claimed = int(m.group(1))
        files = [REPO_ROOT / f for f in m.group(2).split()]
        missing = [f for f in files if not f.exists()]
        if missing:
            failures.append(f"{path.name}: files not found: {[str(f) for f in missing]}")
            continue
        actual = ruff_findings(files)
        if actual != claimed:
            failures.append(f"{path.name}: claims {claimed} findings, ruff reports {actual}")
        else:
            print(f"  ok  {path.name}: {claimed} findings, verified")
    return failures


def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    root = Path(args[0]) if args else REPO_ROOT / "docs" / "benchmarks"
    audits = sorted(root.glob("*-audit.md"))
    if not audits:
        print(f"no *-audit.md under {root}", file=sys.stderr)
        return 2
    failures: list[str] = []
    marked = 0
    for a in audits:
        if MARKER.search(a.read_text()):
            marked += 1
            failures += check_audit(a)
    print(f"{len(audits)} audits scanned, {marked} carry LINT-VERIFY markers")
    for f in failures:
        print(f"  FAIL {f}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
