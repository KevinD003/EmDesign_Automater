"""File-backed design persistence — the fallback when Supabase isn't configured.

One JSON file per design at ``<root>/<sanitized_user>/<design_id>.json`` so users on
a keyless localhost/LAN deployment never lose work across restarts. Backend choice
is made per call (env read at call time, never at import):

- ``STITCHIQ_DESIGNS_DIR`` set  -> disk at that path.
- running under pytest (no env) -> in-memory ``_MEMORY`` (keeps the legacy offline
  suite hermetic; tests opt into disk via the env var + tmp_path).
- otherwise                     -> disk at ``data/designs`` (backend runs from
  apps/backend).

All writes are atomic (tmp file + ``os.replace``) so a crash never corrupts a design.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.models.design import Design

# Default on-disk root, relative to CWD (the backend runs from apps/backend).
_DEFAULT_ROOT = Path("data/designs")

# Design ids must be filename-safe and bounded: alnum + hyphen only (uuid4().hex
# and typical client ids fit). Anything else is treated as not-found — never a path.
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9-]{1,64}$")

# Characters allowed in a user's directory name; everything else becomes "_".
_UNSAFE_USER_CHARS_RE = re.compile(r"[^A-Za-z0-9@._-]")

# Dashboard "recent" list cap — mirrors supabase_store.design_stats.
_RECENT_LIMIT = 8

# In-memory backend, keyed (user_id, design_id). The NAME is load-bearing: the
# designs router aliases it for legacy-test compatibility — mutate, never rebind.
_MEMORY: dict[tuple[str, str], Design] = {}


def _use_disk() -> bool:
    """Disk when explicitly pointed at a dir; memory under pytest; else disk."""
    if os.environ.get("STITCHIQ_DESIGNS_DIR"):
        return True
    return "PYTEST_CURRENT_TEST" not in os.environ


def _root() -> Path:
    env = os.environ.get("STITCHIQ_DESIGNS_DIR")
    return Path(env) if env else _DEFAULT_ROOT


def _safe_user(user_id: str) -> str:
    """Sanitize a user id into a single directory name (path-traversal safe)."""
    cleaned = _UNSAFE_USER_CHARS_RE.sub("_", user_id or "")
    # "." / ".." survive the character filter but are path components, not names.
    if not cleaned or set(cleaned) == {"."}:
        return "anonymous"
    return cleaned


def _safe_id(design_id: str) -> bool:
    return bool(_SAFE_ID_RE.fullmatch(design_id or ""))


def _user_dir(user_id: str) -> Path:
    return _root() / _safe_user(user_id)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _atomic_write(path: Path, payload: dict) -> None:
    """Write via <name>.json.tmp + os.replace so a crash never leaves a torn file."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(tmp, path)


def _load(path: Path) -> Design | None:
    """Parse one design file; None on missing/corrupt (corrupt tolerance for list)."""
    try:
        return Design.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):  # ValueError covers JSONDecodeError + ValidationError
        return None


def create_design(design: Design, user_id: str) -> Design:
    """Store a design for a user; returns the stored copy with id/createdAt set."""
    design_id = design.id if design.id and _safe_id(design.id) else uuid.uuid4().hex
    stored = design.model_copy(
        update={"id": design_id, "created_at": design.created_at or _now_iso()}
    )
    if not _use_disk():
        _MEMORY[(user_id, design_id)] = stored
        return stored
    user_dir = _user_dir(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write(user_dir / f"{design_id}.json", stored.model_dump(by_alias=True))
    return stored


def get_design(design_id: str, user_id: str) -> Design | None:
    """Full-fidelity fetch scoped to the user; None if absent or the id is unsafe."""
    if not _safe_id(design_id):
        return None
    if not _use_disk():
        return _MEMORY.get((user_id, design_id))
    return _load(_user_dir(user_id) / f"{design_id}.json")


def _all_designs(user_id: str) -> list[Design]:
    """Every parseable design for a user (full fidelity), unsorted."""
    if not _use_disk():
        return [d for (uid, _), d in _MEMORY.items() if uid == user_id]
    designs: list[Design] = []
    for path in _user_dir(user_id).glob("*.json"):
        design = _load(path)
        if design is None:
            continue  # corrupt/foreign file: skip, never fail the whole listing
        if not design.created_at:  # legacy file without a stamp: fall back to mtime
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            design = design.model_copy(update={"created_at": mtime.isoformat()})
        designs.append(design)
    return designs


def list_designs(user_id: str) -> list[Design]:
    """Newest-first listing with ``stitches`` stripped (kept light for the library)."""
    designs = _all_designs(user_id)
    designs.sort(key=lambda d: d.created_at or "", reverse=True)
    return [d.model_copy(update={"stitches": []}) for d in designs]


def delete_design(design_id: str, user_id: str) -> None:
    """Idempotent delete; unsafe ids are a no-op (they can never exist)."""
    if not _safe_id(design_id):
        return
    if not _use_disk():
        _MEMORY.pop((user_id, design_id), None)
        return
    (_user_dir(user_id) / f"{design_id}.json").unlink(missing_ok=True)


def design_stats(user_id: str) -> dict:
    """Dashboard aggregates — same camelCase shape as supabase_store.design_stats."""
    designs = list_designs(user_id)
    return {
        "designCount": len(designs),
        "totalStitches": sum(d.stitch_count for d in designs),
        "totalColors": sum(len(d.color_stops) for d in designs),
        "recent": [
            {
                "id": d.id or "",
                "name": d.name or "Untitled",
                "stitchCount": d.stitch_count,
                "savedAt": d.created_at or "",
            }
            for d in designs[:_RECENT_LIMIT]
        ],
    }
