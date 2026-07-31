"""Tests for the environment checks in scripts/preflight.py.

Covers ports, fonts, disk space, frontend deps, and the optional .env file
(swarm ops team, launch preflight). Framework tests live in
test_swarm_ops_preflight.py.
"""

from __future__ import annotations

import importlib.util
import socket
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


def test_check_port_free_passes_on_free_port():
    # Bind to port 0 to have the OS pick a free ephemeral port, then close
    # it so the check sees it free. Never assumes 8000/5173 state.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    result = preflight.check_port_free(port)
    assert result.status == preflight.PASS
    assert result.name == f"port-{port}"


def test_check_port_free_warns_when_port_is_bound():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        result = preflight.check_port_free(port)
    assert result.status == preflight.WARN
    assert "already running" in result.detail


def test_registered_port_checks_use_expected_ports():
    assert preflight.check_port_backend().name == "port-8000"
    assert preflight.check_port_frontend().name == "port-5173"


def test_environment_checks_are_registered():
    # A check that exists but is never appended to CHECKS is dead code:
    # preflight would silently skip it on launch day.
    expected = {
        preflight.check_port_backend,
        preflight.check_port_frontend,
        preflight.check_fonts,
        preflight.check_disk_space,
        preflight.check_frontend_deps,
        preflight.check_env_file,
    }
    assert expected <= set(preflight.CHECKS)


def test_check_fonts_passes_in_container():
    # Container ships DejaVu TTFs, so the app's resolver must find one.
    result = preflight.check_fonts()
    assert result.status == preflight.PASS
    assert result.detail.lower().endswith((".ttf", ".otf", ".ttc"))


def test_check_disk_space_passes_here():
    result = preflight.check_disk_space()
    assert result.status == preflight.PASS


def test_check_disk_space_fails_when_min_threshold_exceeds_free():
    # An absurdly high minimum guarantees the FAIL branch on any machine.
    result = preflight.check_disk_space(min_gb=10**9, low_gb=2 * 10**9)
    assert result.status == preflight.FAIL
    assert "minimum" in result.detail


def test_check_disk_space_warns_between_thresholds():
    result = preflight.check_disk_space(min_gb=0, low_gb=10**9)
    assert result.status == preflight.WARN
    assert "recommended" in result.detail


def test_check_frontend_deps_passes_here():
    # Both repo-root and apps/frontend node_modules exist in this checkout.
    result = preflight.check_frontend_deps()
    assert result.status == preflight.PASS


def test_check_frontend_deps_warns_on_missing_dir(tmp_path):
    missing = tmp_path / "node_modules"
    result = preflight.check_frontend_deps(dep_dirs=(missing,))
    assert result.status == preflight.WARN
    assert "npm install" in result.detail


def test_check_env_file_passes_when_present(tmp_path):
    env = tmp_path / ".env"
    env.write_text("SUPABASE_URL=http://example.invalid\n")
    result = preflight.check_env_file(env_path=env)
    assert result.status == preflight.PASS
    assert result.detail == "found"


def test_check_env_file_warns_when_absent(tmp_path):
    result = preflight.check_env_file(env_path=tmp_path / ".env")
    assert result.status == preflight.WARN
    assert "no apps/backend/.env" in result.detail
