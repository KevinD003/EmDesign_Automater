"""Guard tests for the root .env.example (ops annotations for the LAN launch).

Keeps the tracked example file well-formed, free of real secrets, and in sync
with the env vars app/config.py actually reads (CORS_ORIGINS).
"""

from __future__ import annotations

import re
from pathlib import Path

from app.config import Settings

# tests/ -> apps/backend -> apps -> repo root
ENV_EXAMPLE = Path(__file__).resolve().parents[3] / ".env.example"

# Placeholder keys the setup docs rely on; removing one breaks copy-and-fill.
REQUIRED_KEYS = (
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_KEY",
    "DATABASE_URL",
)

# Real-credential fingerprints: Supabase/JWT tokens start with "eyJ" (base64
# of '{"'), OpenAI-style keys with "sk-". Neither belongs in a tracked file.
SECRET_PATTERN = re.compile(r"eyJ|sk-")

# KEY=value shape for active (non-comment) lines: env-style upper-snake key.
KEY_VALUE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*=\S")


def _active_lines() -> list[str]:
    """Non-comment, non-blank lines of .env.example."""
    lines = ENV_EXAMPLE.read_text().splitlines()
    return [ln for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]


def test_env_example_exists() -> None:
    assert ENV_EXAMPLE.is_file(), f"missing {ENV_EXAMPLE}"


def test_active_lines_are_key_value_shaped() -> None:
    bad = [ln for ln in _active_lines() if not KEY_VALUE_PATTERN.match(ln)]
    assert not bad, f"non KEY=value lines: {bad}"


def test_required_placeholder_keys_present() -> None:
    keys = {ln.split("=", 1)[0] for ln in _active_lines()}
    missing = [k for k in REQUIRED_KEYS if k not in keys]
    assert not missing, f"placeholder keys missing: {missing}"


def test_no_real_secrets_outside_comments() -> None:
    leaks = [ln for ln in _active_lines() if SECRET_PATTERN.search(ln)]
    assert not leaks, f"possible real secret in .env.example: {leaks}"


def test_cors_origins_documented() -> None:
    # Commented-out example is fine — it only needs to be discoverable.
    assert "CORS_ORIGINS" in ENV_EXAMPLE.read_text()


def test_settings_parses_json_list_cors_origins(monkeypatch) -> None:
    monkeypatch.setenv(
        "CORS_ORIGINS", '["http://localhost:5173","http://192.168.1.50:5173"]'
    )
    settings = Settings(_env_file=None)
    assert settings.cors_origins == [
        "http://localhost:5173",
        "http://192.168.1.50:5173",
    ]
