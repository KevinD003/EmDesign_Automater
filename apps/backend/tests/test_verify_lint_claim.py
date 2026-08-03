"""Tests for scripts/verify_lint_claim.py (v2 Part 12, Part A item 6)."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT / "scripts"))

import verify_lint_claim as V


def _audit(tmp_path, body: str) -> Path:
    p = tmp_path / "v9-test-audit.md"
    p.write_text(body)
    return p


def test_a_correct_claim_passes(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(V, "ruff_findings", lambda files: 14)
    a = _audit(tmp_path, "prose\nLINT-VERIFY: findings=14 files=apps/backend/app/services/digitizer/pipeline.py\n")
    assert V.check_audit(a) == []
    assert "verified" in capsys.readouterr().out


def test_a_wrong_claim_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(V, "ruff_findings", lambda files: 15)
    a = _audit(tmp_path, "LINT-VERIFY: findings=14 files=apps/backend/app/services/digitizer/pipeline.py\n")
    fails = V.check_audit(a)
    assert len(fails) == 1 and "claims 14" in fails[0] and "reports 15" in fails[0]


def test_a_claim_naming_a_missing_file_fails(tmp_path):
    a = _audit(tmp_path, "LINT-VERIFY: findings=0 files=apps/backend/no/such/file.py\n")
    fails = V.check_audit(a)
    assert len(fails) == 1 and "not found" in fails[0]


def test_audits_without_the_marker_are_skipped(tmp_path):
    _audit(tmp_path, "an old audit, no marker\n")
    assert V.main([str(tmp_path)]) == 0


def test_ruff_findings_counts_a_real_finding(tmp_path):
    """End-to-end against real ruff: one unused import = one finding."""
    bad = tmp_path / "one_finding.py"
    bad.write_text("import os\n")
    assert V.ruff_findings([bad]) == 1


def test_main_fails_on_a_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(V, "ruff_findings", lambda files: 3)
    _audit(tmp_path, "LINT-VERIFY: findings=2 files=apps/backend/app/services/digitizer/pipeline.py\n")
    assert V.main([str(tmp_path)]) == 1
