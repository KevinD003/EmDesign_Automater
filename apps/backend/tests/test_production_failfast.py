"""CTO A10/S1: APP_ENV=production refuses to boot on dev fallbacks.

The review's S1: with any SUPABASE_* var missing or typo'd, auth silently
falls back to the local-dev sentinel and per-process dicts — production would
run fully unauthenticated and lose data on restart. The validator makes that
configuration refuse to BOOT. These tests drive the validator directly with
patched settings, so no subprocess or real env mutation is needed.
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.main import _validate_production_config


@pytest.fixture()
def _production(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "supabase_url", "https://x.supabase.co")
    monkeypatch.setattr(settings, "supabase_anon_key", "anon")
    monkeypatch.setattr(settings, "supabase_service_key", "service")
    monkeypatch.delenv("STITCHIQ_OPEN_ACCESS", raising=False)


def test_development_boots_without_any_keys(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "supabase_url", "")
    _validate_production_config()  # no raise


def test_production_with_full_config_boots(_production):
    _validate_production_config()  # no raise


@pytest.mark.parametrize("key", ["supabase_url", "supabase_anon_key", "supabase_service_key"])
def test_production_refuses_to_boot_with_a_missing_key(_production, monkeypatch, key):
    monkeypatch.setattr(settings, key, "")
    with pytest.raises(RuntimeError, match=key.upper()):
        _validate_production_config()


def test_production_refuses_open_access(_production, monkeypatch):
    monkeypatch.setenv("STITCHIQ_OPEN_ACCESS", "1")
    with pytest.raises(RuntimeError, match="OPEN_ACCESS"):
        _validate_production_config()


def test_whitespace_only_key_counts_as_missing(_production, monkeypatch):
    # a quoted-but-empty .env value must not sneak past the gate
    monkeypatch.setattr(settings, "supabase_service_key", "   ")
    with pytest.raises(RuntimeError, match="SUPABASE_SERVICE_KEY"):
        _validate_production_config()
