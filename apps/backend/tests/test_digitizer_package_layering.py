"""The digitizer package's shape is load-bearing — pin it (R001).

Splitting the 4,731-line module bought a layering: `constants` at the bottom,
`pipeline` at the top, and imports only ever pointing downward. Nothing enforces
that at runtime — Python is perfectly happy with a cycle until the day an import
order changes and it is not. These tests are the enforcement.

They also pin the two things the split could have quietly broken: the facade's
public surface (every caller imports `app.services.digitizer`, not a submodule)
and `_PENETRATION_FLOOR_MM`, the one name that is rebound at runtime rather than
mutated in place.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.services import digitizer
from app.services.digitizer import constants

PKG_DIR = Path(digitizer.__file__).parent

# Bottom to top. A module may import from those before it and never after.
LAYERS = [
    "constants",
    # Below everything: pure colour arithmetic, importing only `math`. It is a
    # layer rather than a helper inside geometry because the substrate gate
    # (pipeline) and any future thread-matching consumer both read it, and a
    # function two layers apart from both of its callers is how the pull-comp
    # expression came to exist twice.
    "colordiff",
    "accounting",
    "geometry",
    "provenance",
    "skeleton",
    "columns",
    "fills",
    "satin",
    "underlay",
    "generation",
    "routing",
    "planning",
    "staging",
    "pipeline",
    "rebuild",
]
RANK = {name: i for i, name in enumerate(LAYERS)}


def _imports_within_package(module: str) -> set[str]:
    """Sibling modules `module` imports, by name."""
    tree = ast.parse((PKG_DIR / f"{module}.py").read_text(encoding="utf-8"))
    siblings = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "app.services.digitizer":
                # `from app.services.digitizer import constants`
                siblings.update(a.name for a in node.names if a.name in RANK)
            elif node.module.startswith("app.services.digitizer."):
                siblings.add(node.module.rsplit(".", 1)[1])
    return siblings & set(RANK)


@pytest.mark.parametrize("module", LAYERS)
def test_module_only_imports_from_lower_layers(module: str) -> None:
    for dep in sorted(_imports_within_package(module)):
        assert RANK[dep] < RANK[module], (
            f"{module}.py imports {dep}.py, which sits at or above it. "
            f"Move the shared helper down a layer instead of importing upward."
        )


def test_every_layer_exists_as_a_module() -> None:
    on_disk = {p.stem for p in PKG_DIR.glob("*.py")} - {"__init__"}
    assert on_disk == set(LAYERS), (
        "the package gained or lost a module without updating LAYERS; "
        "a module outside the layering is a module with no rules"
    )


def test_facade_reexports_every_definition() -> None:
    """A caller importing `app.services.digitizer` must see the whole surface."""
    missing = []
    for layer in LAYERS:
        tree = ast.parse((PKG_DIR / f"{layer}.py").read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                if not hasattr(digitizer, node.name):
                    missing.append(f"{layer}.{node.name}")
    assert not missing, f"defined but not re-exported by the facade: {missing}"


def test_the_public_entry_points_are_importable_from_the_facade() -> None:
    for name in ("digitize_image", "rebuild_design", "set_penetration_floor",
                 "MIN_PENETRATION_MM", "FABRIC_PROFILES"):
        assert hasattr(digitizer, name), f"{name} vanished from the facade"


def test_penetration_floor_stays_live_through_the_facade() -> None:
    """The one rebound global: a plain re-export would freeze it at import time.

    `set_penetration_floor` rebinds the name inside `constants`, so both the
    facade and the modules that read it have to go through the module object. If
    this ever regresses, the setter appears to work and silently does nothing.
    """
    original = constants._PENETRATION_FLOOR_MM
    try:
        digitizer.set_penetration_floor(None)
        assert digitizer._PENETRATION_FLOOR_MM is None
        assert constants._PENETRATION_FLOOR_MM is None

        digitizer.set_penetration_floor(0.42)
        assert digitizer._PENETRATION_FLOOR_MM == 0.42
    finally:
        digitizer.set_penetration_floor(original)
    assert digitizer._PENETRATION_FLOOR_MM == original


def test_the_shared_logs_are_one_object_across_modules() -> None:
    """`_CLASSIFICATION_LOG`/`_DROP_LOG` are mutated in place, never rebound.

    That is what makes a plain re-export safe for them — but only while every
    module holds the same list. A stray reassignment anywhere would split them
    into per-module copies and the classification log would silently go empty.
    """
    from app.services.digitizer import pipeline

    assert pipeline._CLASSIFICATION_LOG is constants._CLASSIFICATION_LOG
    assert pipeline._DROP_LOG is constants._DROP_LOG
    assert digitizer._CLASSIFICATION_LOG is constants._CLASSIFICATION_LOG


def test_no_module_is_back_to_monolith_size() -> None:
    """The point of the split was that no one file holds everything again."""
    oversize = {p.name: len(p.read_text(encoding="utf-8").splitlines())
                for p in PKG_DIR.glob("*.py")
                if len(p.read_text(encoding="utf-8").splitlines()) > 1500}
    assert not oversize, (
        f"{oversize} — the pre-split module was 4,731 lines; keep the pieces small "
        f"enough to hold in your head. `pipeline.py` is the one to watch: it is "
        f"large because `digitize_image` is still a single ~800-line function."
    )
