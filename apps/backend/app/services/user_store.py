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

# Session-token cap per user: bounds file growth for ~100 LAN users; oldest
# tokens (by issued_at) are evicted when a user exceeds this.
MAX_SESSIONS_PER_USER = 20

# Password-reset tokens (v2 Part 35): single-use, short-lived. 30 minutes is
# long enough to open an email and short enough that a leaked link goes stale
# within the same sitting.
RESET_TTL_MINUTES = 30

# Account roles and plans (v2 Part 35). The FIRST profile created on a fresh
# store becomes the admin — on a self-hosted install the person who sets the
# server up is the operator; every later signup is a plain user until an admin
# promotes them.
ROLES = ("user", "admin")
PLANS = ("free", "pro", "studio")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Session lifetime. A supervised LAN launch runs for a day at most, so a token
# older than this is far likelier to be stale or captured than in active use.
# Verified as the gap that let a token committed to git 22 hours earlier still
# authenticate against a fresh server (v2 Part 21 review).
SESSION_TTL_HOURS = 12


class DuplicateUsernameError(Exception):
    """Raised when a username (case-insensitive) is already taken."""


def _empty_data() -> dict:
    # "sessions" is reserved for the session-management layer; "resets" holds
    # single-use password-reset tokens. Keep the keys in the schema so all
    # layers share one file shape.
    return {"profiles": {}, "sessions": {}, "resets": {}}


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
        raw.setdefault("resets", {})
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
        # role/plan/email default via .get() so records written before v2
        # Part 35 keep working without a migration step.
        return {
            "userId": record["user_id"],
            "username": record["username"],
            "hasPin": record["pin_hash"] is not None,
            "createdAt": record["created_at"],
            "email": record.get("email"),
            "role": record.get("role", "user"),
            "plan": record.get("plan", "free"),
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

    def create_profile(
        self, username: str, pin: str | None, email: str | None = None
    ) -> dict:
        name = self._validate_username(username)
        if pin is not None and not PIN_MIN_LEN <= len(pin) <= PIN_MAX_LEN:
            raise ValueError(
                f"PIN must be {PIN_MIN_LEN}-{PIN_MAX_LEN} characters long."
            )
        if email is not None:
            email = self._validate_email(email)
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
                "email": email,
                # First profile on a fresh store is the operator.
                "role": "admin" if not self._data["profiles"] else "user",
                "plan": "free",
            }
            self._data["profiles"][record["user_id"]] = record
            self._save()
            return self._public(record)

    @staticmethod
    def _validate_email(email: str) -> str:
        addr = email.strip().lower()
        if not _EMAIL_RE.match(addr) or len(addr) > 254:
            raise ValueError("That does not look like a valid email address.")
        return addr

    def set_email(self, user_id: str, email: str) -> dict:
        addr = self._validate_email(email)
        with self._lock:
            record = self._data["profiles"].get(user_id)
            if record is None:
                raise KeyError(f"Unknown user_id: {user_id}")
            record["email"] = addr
            self._save()
            return self._public(record)

    def set_plan(self, user_id: str, plan: str) -> dict:
        if plan not in PLANS:
            raise ValueError(f"Plan must be one of {', '.join(PLANS)}.")
        with self._lock:
            record = self._data["profiles"].get(user_id)
            if record is None:
                raise KeyError(f"Unknown user_id: {user_id}")
            record["plan"] = plan
            self._save()
            return self._public(record)

    def set_role(self, user_id: str, role: str) -> dict:
        if role not in ROLES:
            raise ValueError(f"Role must be one of {', '.join(ROLES)}.")
        with self._lock:
            record = self._data["profiles"].get(user_id)
            if record is None:
                raise KeyError(f"Unknown user_id: {user_id}")
            if role != "admin":
                # Never demote the last admin — the install would be locked
                # out of its own admin panel with no recovery path.
                admins = [
                    r
                    for r in self._data["profiles"].values()
                    if r.get("role", "user") == "admin"
                ]
                if len(admins) == 1 and admins[0]["user_id"] == user_id:
                    raise ValueError("Cannot demote the only admin.")
            record["role"] = role
            self._save()
            return self._public(record)

    def get_by_email(self, email: str) -> dict | None:
        addr = email.strip().lower()
        with self._lock:
            for record in self._data["profiles"].values():
                if record.get("email") == addr:
                    return dict(record)
        return None

    # ---- password (PIN) reset — single-use, short-lived tokens ----

    def issue_reset_token(self, email: str) -> tuple[str, dict] | None:
        """Mint a reset token for the account with this email, or None.

        Returning None (instead of raising) lets the HTTP layer answer 202
        for every address, so the RESPONSE never reveals whether an account
        exists. Honest limit: a known address does more work (mint token,
        rewrite the store, write the mail), so a determined attacker could
        still distinguish the two by timing. Closing that needs a queued
        send; at this scale the response-identity is the guarantee made.
        """
        with self._lock:
            target = None
            addr = email.strip().lower()
            for record in self._data["profiles"].values():
                if record.get("email") == addr:
                    target = record
                    break
            if target is None:
                return None
            token = secrets.token_urlsafe(32)
            # One live token per user: a newer request invalidates older ones.
            self._data["resets"] = {
                t: r
                for t, r in self._data["resets"].items()
                if r["user_id"] != target["user_id"]
            }
            self._data["resets"][token] = {
                "user_id": target["user_id"],
                "issued_at": datetime.now(UTC).isoformat(),
            }
            self._save()
            return token, dict(target)

    def redeem_reset_token(self, token: str, new_pin: str) -> dict | None:
        """Set a new PIN for the token's account; None for bad/expired tokens.

        The token is consumed on every attempt that reaches it — a reset link
        works exactly once. All live sessions are revoked: whoever held the
        old PIN (or a stolen token) is signed out everywhere.
        """
        if not PIN_MIN_LEN <= len(new_pin) <= PIN_MAX_LEN:
            raise ValueError(
                f"PIN must be {PIN_MIN_LEN}-{PIN_MAX_LEN} characters long."
            )
        with self._lock:
            entry = self._data["resets"].pop(token, None)
            if entry is None:
                return None
            issued = entry.get("issued_at")
            try:
                age_ok = (
                    datetime.now(UTC)
                    - datetime.fromisoformat(str(issued)).replace(tzinfo=UTC)
                ).total_seconds() <= RESET_TTL_MINUTES * 60
            except ValueError:
                age_ok = False
            record = self._data["profiles"].get(entry["user_id"])
            if not age_ok or record is None:
                self._save()  # the token is consumed even on failure
                return None
            salt = secrets.token_bytes(SALT_BYTES)
            record["pin_salt"] = salt.hex()
            record["pin_hash"] = self._hash_pin(new_pin, salt).hex()
            self._data["sessions"] = {
                t: s
                for t, s in self._data["sessions"].items()
                if s["user_id"] != record["user_id"]
            }
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

    def issue_token(self, user_id: str) -> str:
        """Mint a new session token for user_id; evict oldest past the cap."""
        with self._lock:
            if user_id not in self._data["profiles"]:
                raise KeyError(f"Unknown user_id: {user_id}")
            token = secrets.token_urlsafe(32)
            sessions = self._data["sessions"]
            sessions[token] = {
                "user_id": user_id,
                "issued_at": datetime.now(UTC).isoformat(),
            }
            owned = sorted(
                (t for t, s in sessions.items() if s["user_id"] == user_id),
                key=lambda t: sessions[t]["issued_at"],
            )
            for stale in owned[: max(0, len(owned) - MAX_SESSIONS_PER_USER)]:
                del sessions[stale]
            self._save()
            return token

    def verify_token(self, token: str) -> dict | None:
        """Public profile for a live, UNEXPIRED token, or None.

        Also returns None for a token whose profile was deleted. Expiry is
        checked here rather than only at issue time because tokens are
        persisted to disk and survive restarts: before v2 Part 21 a token was
        valid forever, so one captured (or committed to git) stayed usable
        indefinitely.
        """
        with self._lock:
            session = self._data["sessions"].get(token)
            if session is None:
                return None
            if self._expired(session):
                del self._data["sessions"][token]
                self._save()
                return None
            record = self._data["profiles"].get(session["user_id"])
            if record is None:
                return None
            return self._public(record)

    @staticmethod
    def _expired(session: dict) -> bool:
        """True when the session is older than SESSION_TTL_HOURS.

        An unparseable or missing issued_at counts as expired: a session we
        cannot age is one we cannot trust.
        """
        stamp = session.get("issued_at")
        if not stamp:
            return True
        try:
            issued = datetime.fromisoformat(str(stamp))
        except ValueError:
            return True
        if issued.tzinfo is None:
            issued = issued.replace(tzinfo=UTC)
        return (datetime.now(UTC) - issued).total_seconds() > SESSION_TTL_HOURS * 3600

    def login(self, username: str, pin: str | None) -> tuple[dict, str] | None:
        """Case-insensitive login; PIN required only when the profile has one.

        The identifier may be a username or, when it contains an "@", the
        account's email address — one field on the login form serves both.
        """
        record = self.get_by_username(username)
        if record is None and "@" in username:
            record = self.get_by_email(username)
        if record is None:
            return None
        # A profile without a PIN accepts any (ignored) pin argument.
        has_pin = record["pin_hash"] is not None
        if has_pin and (pin is None or not self.verify_pin(record["user_id"], pin)):
            return None
        return self._public(record), self.issue_token(record["user_id"])

    def revoke_token(self, token: str) -> bool:
        with self._lock:
            if self._data["sessions"].pop(token, None) is None:
                return False
            self._save()
            return True


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


def resolve_bearer(authorization: str | None) -> str | None:
    """Map an Authorization header to a user_id via the process-wide store.

    Accepts only `Bearer <token>` (scheme case-insensitive); anything else,
    or a token that does not verify, yields None. This is the single hook
    intended for HTTP-layer auth integration.
    """
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    profile = get_store().verify_token(parts[1].strip())
    return profile["userId"] if profile else None
