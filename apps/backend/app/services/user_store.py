"""Lightweight local user profile store backed by a JSON file (stdlib only)."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
from datetime import UTC, datetime
from pathlib import Path

# PBKDF2 iteration count: 100k keeps interactive login under ~100ms on modest
# hardware while making offline brute-force of a short PIN expensive.
PBKDF2_ITERATIONS = 100_000

# Salt length in bytes; 16 is the accepted minimum for PBKDF2 salts.
SALT_BYTES = 16

# Username constraints: 1-32 chars from letters, digits, space, underscore, dash.
USERNAME_MAX_LEN = 32
_USERNAME_RE = re.compile(r"^[A-Za-z0-9 _-]+$")

# PIN length bounds: 4 minimum for basic entropy, 64 cap to bound hashing cost.
PIN_MIN_LEN = 4
PIN_MAX_LEN = 64


class DuplicateUsernameError(Exception):
    """Raised when a username (case-insensitive) is already taken."""


def _empty_data() -> dict:
    # "sessions" is reserved for the session-management layer; keep the key
    # in the schema so both layers share one file shape.
    return {"profiles": {}, "sessions": {}}


class UserStore:
    """Thread-safe JSON-file-backed store of local user profiles."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self) -> dict:
        # A missing or corrupt file must never crash the store: recover to
        # the empty schema and let the next write repair the file.
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return _empty_data()
        if not isinstance(raw, dict) or not isinstance(raw.get("profiles"), dict):
            return _empty_data()
        raw.setdefault("sessions", {})
        return raw

    def _save(self) -> None:
        # Atomic write: tmp file + os.replace so readers never see a partial file.
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        os.replace(tmp, self._path)

    @staticmethod
    def _public(record: dict) -> dict:
        # Public view only — pin_salt/pin_hash must never leave the store.
        return {
            "userId": record["user_id"],
            "username": record["username"],
            "hasPin": record["pin_hash"] is not None,
            "createdAt": record["created_at"],
        }

    @staticmethod
    def _validate_username(username: str) -> str:
        name = username.strip()
        if not 1 <= len(name) <= USERNAME_MAX_LEN:
            raise ValueError(
                f"Username must be 1-{USERNAME_MAX_LEN} characters long."
            )
        if not _USERNAME_RE.match(name):
            raise ValueError(
                "Username may only contain letters, digits, spaces, "
                "underscores, and dashes."
            )
        return name

    @staticmethod
    def _hash_pin(pin: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, PBKDF2_ITERATIONS)

    def create_profile(self, username: str, pin: str | None) -> dict:
        name = self._validate_username(username)
        if pin is not None and not PIN_MIN_LEN <= len(pin) <= PIN_MAX_LEN:
            raise ValueError(
                f"PIN must be {PIN_MIN_LEN}-{PIN_MAX_LEN} characters long."
            )
        with self._lock:
            key = name.casefold()
            for record in self._data["profiles"].values():
                if record["username_key"] == key:
                    raise DuplicateUsernameError(
                        f"Username '{name}' is already taken."
                    )
            pin_salt = pin_hash = None
            if pin is not None:
                salt = secrets.token_bytes(SALT_BYTES)
                pin_salt = salt.hex()
                pin_hash = self._hash_pin(pin, salt).hex()
            record = {
                "user_id": "local-" + secrets.token_hex(8),
                "username": name,
                "username_key": key,
                "pin_salt": pin_salt,
                "pin_hash": pin_hash,
                "created_at": datetime.now(UTC).isoformat(),
            }
            self._data["profiles"][record["user_id"]] = record
            self._save()
            return self._public(record)

    def verify_pin(self, user_id: str, pin: str) -> bool:
        with self._lock:
            record = self._data["profiles"].get(user_id)
            if record is None or record["pin_hash"] is None:
                return False
            salt = bytes.fromhex(record["pin_salt"])
            expected = bytes.fromhex(record["pin_hash"])
            return hmac.compare_digest(self._hash_pin(pin, salt), expected)

    def get_by_username(self, username: str) -> dict | None:
        key = username.strip().casefold()
        with self._lock:
            for record in self._data["profiles"].values():
                if record["username_key"] == key:
                    return dict(record)
        return None

    def list_profiles(self) -> list[dict]:
        with self._lock:
            profiles = [self._public(r) for r in self._data["profiles"].values()]
        return sorted(profiles, key=lambda p: p["createdAt"])


# Default store location: apps/backend/data/local_users.json.
_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "local_users.json"

_store: UserStore | None = None


def get_store() -> UserStore:
    """Return the process-wide store, honoring STITCHIQ_USER_STORE if set."""
    global _store
    if _store is None:
        env_path = os.environ.get("STITCHIQ_USER_STORE")
        _store = UserStore(Path(env_path) if env_path else _DEFAULT_PATH)
    return _store


def reset_store_cache() -> None:
    """Drop the cached store so tests can repoint via STITCHIQ_USER_STORE."""
    global _store
    _store = None
