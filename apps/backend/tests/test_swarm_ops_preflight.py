"""Tests for scripts/preflight.py (swarm ops team, launch preflight)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# scripts/ has no package __init__, so load preflight.py by file path.
_PREFLIGHT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "preflight.py"
)
_spec = importlib.util.spec_from_file_location("preflight", _PREFLIGHT_PATH)
assert _spec is not None and _spec.loader is not None
preflight = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("preflight", preflight)
_spec.loader.exec_module(preflight)


def test_run_checks_converts_exception_to_fail():
    def boom():
        raise RuntimeError("kaboom")

    results = preflight.run_checks([boom])
    assert len(results) == 1
    assert results[0].status == preflight.FAIL
    assert results[0].name == "boom"
    assert "kaboom" in results[0].detail


def test_run_checks_keeps_passing_results():
    def ok():
        return preflight.CheckResult("ok", preflight.PASS, "fine")

    results = preflight.run_checks([ok])
    assert results[0].status == preflight.PASS


def test_check_python_version_passes_on_current_interpreter():
    # Tests run under the repo venv (Python 3.11+), so this must PASS.
    result = preflight.check_python_version()
    assert result.status == preflight.PASS
    assert result.name == "python-version"


def test_check_backend_imports_passes_in_venv():
    result = preflight.check_backend_imports()
    assert result.status == preflight.PASS


def test_check_backend_imports_fails_on_missing_module():
    result = preflight.check_backend_imports(
        modules=("numpy", "definitely_not_a_real_module_xyz")
    )
    assert result.status == preflight.FAIL
    assert "definitely_not_a_real_module_xyz" in result.detail
    # Present modules must not be listed as missing.
    assert "numpy" not in result.detail


def test_check_venv_never_worse_than_warn_here():
    # .venv exists in this repo, so the worst allowed outcome is WARN.
    result = preflight.check_venv()
    assert result.status in (preflight.PASS, preflight.WARN)


def test_check_node_passes_here():
    # Container has node v22; engines require >=20.
    result = preflight.check_node()
    assert result.status == preflight.PASS


def test_main_exits_1_on_fail(monkeypatch, capsys):
    def failing():
        return preflight.CheckResult("doomed", preflight.FAIL, "nope")

    monkeypatch.setattr(preflight, "CHECKS", [failing])
    assert preflight.main() == 1
    out = capsys.readouterr().out
    assert "FAIL" in out and "doomed" in out


def test_main_exits_0_on_pass_and_warn(monkeypatch, capsys):
    def ok():
        return preflight.CheckResult("fine", preflight.PASS, "all good")

    def warn():
        return preflight.CheckResult("meh", preflight.WARN, "heads up")

    monkeypatch.setattr(preflight, "CHECKS", [ok, warn])
    assert preflight.main() == 0
    out = capsys.readouterr().out
    assert "PASS" in out and "WARN" in out
