"""Custom threads and saved palettes (v2 Part 36) — the "thread editor".

The shipped catalogue covers the big brands, but every real embroidery shop
runs cones the catalogue does not have: a house brand, a customer's PMS-matched
special, a metallic that only exists on one supplier's card. Competitors solve
this with a user thread chart plus saved palettes, and so does this: per-user
custom threads and named palettes, stored beside the local profiles.

Per-user by construction — a thread chart is shop data, not global data — and
persisted with the same atomic-write + lock discipline as ``user_store``.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import threading
from datetime import UTC, datetime
from pathlib import Path

HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")

MAX_NAME_LEN = 64
MAX_THREADS_PER_USER = 2000
MAX_PALETTES_PER_USER = 200
MAX_PALETTE_COLORS = 64


class ThreadStoreError(ValueError):
    """Rejected write — the message is user-facing."""


def normalise_hex(value: str) -> str:
    if not isinstance(value, str) or not HEX_RE.match(value.strip()):
        raise ThreadStoreError(f"'{value}' is not a 6-digit hex colour like #1a2b3c.")
    return "#" + value.strip().lstrip("#").lower()


def _text(value: str, field: str, *, required: bool = True) -> str:
    v = (value or "").strip()
    if required and not v:
        raise ThreadStoreError(f"{field} is required.")
    if len(v) > MAX_NAME_LEN:
        raise ThreadStoreError(f"{field} must be {MAX_NAME_LEN} characters or fewer.")
    return v


def _empty() -> dict:
    return {"threads": {}, "palettes": {}}


class ThreadStore:
    """Thread-safe JSON-file store of per-user custom threads and palettes."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self) -> dict:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return _empty()
        if not isinstance(raw, dict):
            return _empty()
        raw.setdefault("threads", {})
        raw.setdefault("palettes", {})
        return raw

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        os.replace(tmp, self._path)

    # ── custom threads ──
    def list_threads(self, user_id: str) -> list[dict]:
        with self._lock:
            return sorted(
                (dict(t) for t in self._data["threads"].get(user_id, {}).values()),
                key=lambda t: (t.get("brand", ""), t.get("name", "")),
            )

    def add_thread(self, user_id: str, brand: str, name: str, code: str, hex_color: str) -> dict:
        record = {
            "id": "thr-" + secrets.token_hex(6),
            "brand": _text(brand, "Brand"),
            "name": _text(name, "Thread name"),
            "code": _text(code, "Catalog number", required=False),
            "hex": normalise_hex(hex_color),
            "custom": True,
            "createdAt": datetime.now(UTC).isoformat(),
        }
        with self._lock:
            owned = self._data["threads"].setdefault(user_id, {})
            if len(owned) >= MAX_THREADS_PER_USER:
                raise ThreadStoreError(
                    f"You have reached the {MAX_THREADS_PER_USER}-thread limit."
                )
            owned[record["id"]] = record
            self._save()
            return dict(record)

    def update_thread(self, user_id: str, thread_id: str, **fields) -> dict:
        with self._lock:
            owned = self._data["threads"].get(user_id, {})
            record = owned.get(thread_id)
            if record is None:
                raise KeyError(thread_id)
            if "brand" in fields:
                record["brand"] = _text(fields["brand"], "Brand")
            if "name" in fields:
                record["name"] = _text(fields["name"], "Thread name")
            if "code" in fields:
                record["code"] = _text(fields["code"], "Catalog number", required=False)
            if "hex" in fields:
                record["hex"] = normalise_hex(fields["hex"])
            self._save()
            return dict(record)

    def delete_thread(self, user_id: str, thread_id: str) -> bool:
        with self._lock:
            removed = self._data["threads"].get(user_id, {}).pop(thread_id, None)
            if removed is not None:
                self._save()
            return removed is not None

    # ── palettes ──
    def list_palettes(self, user_id: str) -> list[dict]:
        with self._lock:
            return sorted(
                (dict(p) for p in self._data["palettes"].get(user_id, {}).values()),
                key=lambda p: p.get("createdAt", ""),
            )

    def save_palette(self, user_id: str, name: str, colors: list[dict]) -> dict:
        if not colors:
            raise ThreadStoreError("A palette needs at least one colour.")
        if len(colors) > MAX_PALETTE_COLORS:
            raise ThreadStoreError(
                f"A palette holds at most {MAX_PALETTE_COLORS} colours."
            )
        clean = [
            {
                "hex": normalise_hex(c.get("hex", "")),
                "name": _text(c.get("name", "Thread"), "Colour name", required=False)
                or "Thread",
                "brand": _text(c.get("brand", ""), "Brand", required=False),
                "code": _text(c.get("code", ""), "Catalog number", required=False),
            }
            for c in colors
        ]
        record = {
            "id": "pal-" + secrets.token_hex(6),
            "name": _text(name, "Palette name"),
            "colors": clean,
            "createdAt": datetime.now(UTC).isoformat(),
        }
        with self._lock:
            owned = self._data["palettes"].setdefault(user_id, {})
            if len(owned) >= MAX_PALETTES_PER_USER:
                raise ThreadStoreError(
                    f"You have reached the {MAX_PALETTES_PER_USER}-palette limit."
                )
            owned[record["id"]] = record
            self._save()
            return dict(record)

    def delete_palette(self, user_id: str, palette_id: str) -> bool:
        with self._lock:
            removed = self._data["palettes"].get(user_id, {}).pop(palette_id, None)
            if removed is not None:
                self._save()
            return removed is not None


_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "thread_store.json"
_store: ThreadStore | None = None


def get_store() -> ThreadStore:
    global _store
    if _store is None:
        env = os.environ.get("STITCHIQ_THREAD_STORE")
        _store = ThreadStore(Path(env) if env else _DEFAULT_PATH)
    return _store


def reset_store_cache() -> None:
    global _store
    _store = None
