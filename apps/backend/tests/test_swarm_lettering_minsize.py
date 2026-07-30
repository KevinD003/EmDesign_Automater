"""Swarm tests: 4mm minimum lettering height guard (legibility floor)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.lettering import find_font, generate_lettering

try:
    find_font()
    HAVE_FONT = True
except ValueError:
    HAVE_FONT = False


def test_below_minimum_raises_value_error():
    with pytest.raises(ValueError, match="below 4mm"):
        generate_lettering("A", height_mm=3.9)


def test_far_below_minimum_raises_value_error():
    with pytest.raises(ValueError, match="below 4mm"):
        generate_lettering("A", height_mm=0.5)


def test_api_rejects_sub_4mm_height_with_422():
    resp = TestClient(app).post("/api/lettering", json={"text": "A", "heightMm": 3})
    assert resp.status_code == 422
    assert "below 4mm cannot be embroidered legibly" in str(resp.json()["detail"])


@pytest.mark.skipif(not HAVE_FONT, reason="no TrueType font found on this system")
def test_exactly_4mm_is_allowed():
    # Boundary: 4.0 is the smallest legal height and must digitize.
    d = generate_lettering("I", height_mm=4.0)
    assert d.stitch_count > 0
