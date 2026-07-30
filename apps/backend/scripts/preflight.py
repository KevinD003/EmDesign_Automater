"""Launch preflight checker for STITCHIQ localhost/LAN deployments.

Runs a series of environment checks (interpreter version, venv, backend
dependencies, node) and prints one aligned status line per check.

Invocation (from apps/backend):

    .venv/bin/python scripts/preflight.py

Exit code is 0 when no check FAILs, 1 otherwise. WARN never fails the run.

Later ops tasks append additional check functions to the CHECKS registry
near main() at the bottom of this module. Stdlib-only: the framework must
work even when backend dependencies are broken.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import socket
import subprocess
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

# apps/backend — resolved relative to this file so cwd never matters.
BACKEND_DIR = Path(__file__).resolve().parents[1]

# Repo root (scripts/ -> apps/backend -> apps -> root); disk + frontend
# checks operate on the whole monorepo, not just the backend.
REPO_ROOT = Path(__file__).resolve().parents[3]

# Minimum supported interpreter: repo targets Python 3.11–3.14.
MIN_PYTHON = (3, 11)

# Minimum node major version: package.json engines requires node >= 20.
MIN_NODE_MAJOR = 20

# Import names (not pip names) of backend runtime dependencies.
BACKEND_MODULES = (
    "fastapi",
    "uvicorn",
    "pydantic",
    "cv2",
    "numpy",
    "PIL",
    "reportlab",
    "pyembroidery",
    "httpx",
)

# Column width for the check-name field in printed output lines.
NAME_COLUMN_WIDTH = 18

# Cap on subprocess wait for `node --version`; a healthy node answers
# instantly, so anything longer means a hung binary.
NODE_VERSION_TIMEOUT_S = 10

# Ports the two dev servers bind: uvicorn (backend) and vite (frontend).
BACKEND_PORT = 8000
FRONTEND_PORT = 5173

# Disk thresholds in GiB. Uploads, .dst/.pes exports, and the frontend
# build output all write to this volume; under MIN_DISK_GB writes start
# failing mid-request, under LOW_DISK_GB a launch-day spike may fill it.
MIN_DISK_GB = 1
LOW_DISK_GB = 5

# GiB in bytes, for converting shutil.disk_usage figures.
BYTES_PER_GB = 1024**3

# Directories `npm install` must have populated before the frontend can
# build (workspace hoists most packages to the repo root; the frontend
# keeps its own for non-hoistable ones).
FRONTEND_DEP_DIRS = (
    REPO_ROOT / "node_modules",
    REPO_ROOT / "apps" / "frontend" / "node_modules",
)

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"


@dataclass
class CheckResult:
    """Outcome of one preflight check."""

    name: str
    status: str  # one of PASS, FAIL, WARN
    detail: str


def check_python_version() -> CheckResult:
    """Running interpreter must meet MIN_PYTHON."""
    current = sys.version_info[:3]
    version_str = ".".join(str(part) for part in current)
    required = ".".join(str(part) for part in MIN_PYTHON)
    if current >= MIN_PYTHON:
        return CheckResult(
            "python-version", PASS, f"{version_str} (>={required} required)"
        )
    return CheckResult(
        "python-version", FAIL, f"{version_str} found, >={required} required"
    )


def check_venv() -> CheckResult:
    """Detect the backend venv; WARN (not FAIL) if running outside it."""
    in_venv = sys.prefix != sys.base_prefix
    venv_dir = BACKEND_DIR / ".venv"
    if in_venv:
        return CheckResult("venv", PASS, f"running inside venv ({sys.prefix})")
    if venv_dir.is_dir():
        return CheckResult(
            "venv",
            WARN,
            f"not running inside a venv, but {venv_dir} exists — "
            "run via .venv/bin/python",
        )
    return CheckResult("venv", FAIL, f"no venv active and {venv_dir} is missing")


def check_backend_imports(
    modules: Sequence[str] = BACKEND_MODULES,
) -> CheckResult:
    """All backend runtime dependencies must be importable."""
    missing = [name for name in modules if importlib.util.find_spec(name) is None]
    if missing:
        return CheckResult(
            "backend-imports", FAIL, "missing modules: " + ", ".join(missing)
        )
    return CheckResult(
        "backend-imports", PASS, f"all {len(modules)} backend modules importable"
    )


def check_node() -> CheckResult:
    """node must exist and be >= MIN_NODE_MAJOR (frontend build needs it)."""
    node = shutil.which("node")
    if node is None:
        return CheckResult(
            "node", FAIL, f"node not found on PATH (>=v{MIN_NODE_MAJOR} required)"
        )
    try:
        proc = subprocess.run(
            [node, "--version"],
            capture_output=True,
            text=True,
            timeout=NODE_VERSION_TIMEOUT_S,
            check=False,  # returncode handled explicitly below
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CheckResult("node", FAIL, f"node --version failed: {exc}")
    version = proc.stdout.strip()
    match = re.match(r"v(\d+)", version)
    if proc.returncode != 0 or match is None:
        return CheckResult(
            "node", FAIL, f"could not parse node version output: {version!r}"
        )
    major = int(match.group(1))
    if major >= MIN_NODE_MAJOR:
        return CheckResult("node", PASS, f"{version} (>=v{MIN_NODE_MAJOR} required)")
    return CheckResult(
        "node", FAIL, f"{version} found, >=v{MIN_NODE_MAJOR} required"
    )


def check_port_free(port: int) -> CheckResult:
    """A bindable loopback port is PASS; a bound one is WARN (app running)."""
    # SO_REUSEADDR deliberately NOT set: with it, bind() can succeed on a
    # port that still has a live listener, hiding the very conflict this
    # check exists to surface.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError:
        return CheckResult(
            f"port-{port}", WARN, "port in use — is the app already running?"
        )
    finally:
        sock.close()
    return CheckResult(f"port-{port}", PASS, f"127.0.0.1:{port} is free")


def check_port_backend() -> CheckResult:
    """uvicorn binds BACKEND_PORT."""
    return check_port_free(BACKEND_PORT)


def check_port_frontend() -> CheckResult:
    """vite binds FRONTEND_PORT."""
    return check_port_free(FRONTEND_PORT)


def check_fonts() -> CheckResult:
    """Lettering needs a TrueType font; reuse the app's own resolver."""
    # The resolver lives in the app package, so make apps/backend importable.
    # An ImportError here propagates and run_checks reports it as FAIL.
    backend = str(BACKEND_DIR)
    if backend not in sys.path:
        sys.path.insert(0, backend)
    from app.services.lettering import find_font

    try:
        return CheckResult("fonts", PASS, find_font())
    except ValueError as exc:  # find_font raises ValueError when none exist
        return CheckResult("fonts", FAIL, str(exc))


def check_disk_space(
    root: Path = REPO_ROOT,
    min_gb: float = MIN_DISK_GB,
    low_gb: float = LOW_DISK_GB,
) -> CheckResult:
    """Free space on the repo volume must clear the launch thresholds."""
    free_gb = shutil.disk_usage(root).free / BYTES_PER_GB
    detail = f"{free_gb:.1f} GB free at {root}"
    if free_gb < min_gb:
        return CheckResult(
            "disk-space", FAIL, f"{detail} (<{min_gb} GB minimum)"
        )
    if free_gb < low_gb:
        return CheckResult(
            "disk-space", WARN, f"{detail} (<{low_gb} GB recommended)"
        )
    return CheckResult("disk-space", PASS, detail)


def check_frontend_deps(
    dep_dirs: Sequence[Path] = FRONTEND_DEP_DIRS,
) -> CheckResult:
    """WARN when any node_modules dir is missing (npm install needed)."""
    missing = [str(path) for path in dep_dirs if not path.is_dir()]
    if missing:
        return CheckResult(
            "frontend-deps",
            WARN,
            "missing " + ", ".join(missing) + " — run npm install before build",
        )
    return CheckResult(
        "frontend-deps", PASS, f"all {len(dep_dirs)} node_modules dirs present"
    )


def check_env_file(env_path: Path = BACKEND_DIR / ".env") -> CheckResult:
    """apps/backend/.env (Supabase persistence) is optional; absence is WARN.

    Mirrors the fallback documented in app/routers/designs.py: without
    Supabase config, designs go to local JSON files (in-memory under pytest)
    — not shared across machines, and a single worker owns the data dir.
    """
    if env_path.is_file():
        return CheckResult("env-file", PASS, "found")
    return CheckResult(
        "env-file",
        WARN,
        "no apps/backend/.env — Supabase off; designs fall back to local "
        "JSON files under data/designs/, single machine/worker only",
    )


def run_checks(
    checks: Iterable[Callable[[], CheckResult]],
) -> list[CheckResult]:
    """Run every check; a raising check becomes a FAIL, never a crash."""
    results: list[CheckResult] = []
    for check in checks:
        try:
            results.append(check())
        except Exception as exc:  # noqa: BLE001 — preflight must never crash
            results.append(
                CheckResult(check.__name__, FAIL, f"check raised {exc!r}")
            )
    return results


# Registry of all preflight checks. Later ops tasks append here.
CHECKS: list[Callable[[], CheckResult]] = [
    check_python_version,
    check_venv,
    check_backend_imports,
    check_node,
    check_port_backend,
    check_port_frontend,
    check_fonts,
    check_disk_space,
    check_frontend_deps,
    check_env_file,
]


def main() -> int:
    """Print one aligned line per check; exit 1 if any check FAILs."""
    results = run_checks(CHECKS)
    for result in results:
        print(f"{result.status}  {result.name:<{NAME_COLUMN_WIDTH}} {result.detail}")
    return 1 if any(result.status == FAIL for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
