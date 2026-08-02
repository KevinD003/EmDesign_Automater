"""v2 Part 36 — image editor, thread editor, stitch (DST) editor.

Each editor is tested through the behaviour a user would notice, not through
its internals: an edit that changes the pixels, a thread chart that survives a
reload, and a stream edit whose result a machine would still accept.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.design import Stitch, StitchCommand
from app.services import stitch_edit, thread_store
from app.services.image_edit import EditParams, apply_edits, suggest


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("STITCHIQ_THREAD_STORE", str(tmp_path / "threads.json"))
    monkeypatch.setenv("STITCHIQ_USER_STORE", str(tmp_path / "users.json"))
    thread_store.reset_store_cache()
    yield TestClient(app)
    thread_store.reset_store_cache()


def _photo(w=200, h=160):
    img = np.full((h, w, 3), 120, np.uint8)
    cv2.circle(img, (w // 2, h // 2), 40, (30, 30, 200), -1)
    cv2.rectangle(img, (10, 10), (50, 40), (20, 180, 20), -1)
    return img


# ── image editor ────────────────────────────────────────────────────────────


def test_rotation_never_crops_the_artwork_away():
    """A 'straighten' that silently eats a corner is worse than none: the
    canvas must grow to fit the rotated bounds."""
    img = _photo()
    out = apply_edits(img, EditParams(rotate_deg=30))
    assert out.shape[0] > img.shape[0] and out.shape[1] > img.shape[1]


def test_auto_levels_expands_a_flat_tonal_range():
    flat = np.full((60, 60, 3), 128, np.uint8)
    cv2.circle(flat, (30, 30), 20, (140, 140, 140), -1)  # 12 levels of span
    out = apply_edits(flat, EditParams(auto_levels=True))
    assert int(out.max()) - int(out.min()) > int(flat.max()) - int(flat.min())


def test_posterize_reduces_distinct_colours():
    rng = np.random.default_rng(3)
    noisy = rng.integers(0, 255, (80, 80, 3), dtype=np.uint8)
    before = len(np.unique(noisy.reshape(-1, 3), axis=0))
    out = apply_edits(noisy, EditParams(posterize=4))
    after = len(np.unique(out.reshape(-1, 3), axis=0))
    assert after < before and after <= 4**3


def test_crop_and_scale_compose_in_a_fixed_order():
    """Geometry runs crop -> flip -> rotate -> scale, so the same sliders always
    give the same pixels regardless of the order the user touched them."""
    img = _photo(200, 200)
    out = apply_edits(img, EditParams(crop=(0.0, 0.0, 0.5, 0.5), scale=2.0))
    assert out.shape[0] == 200 and out.shape[1] == 200


def test_suggestions_quote_the_measurement_behind_them():
    flat = np.full((80, 80, 3), 128, np.uint8)
    s = suggest(flat)
    assert s["measurements"]["contrastSpan"] < 160
    assert s["suggested"]["autoLevels"] is True
    assert any("tonal span" in t for t in s["tips"])


def test_image_edit_endpoint_returns_a_decodable_png(client):
    ok, buf = cv2.imencode(".png", _photo())
    assert ok
    r = client.post(
        "/api/image/edit",
        files={"file": ("t.png", buf.tobytes(), "image/png")},
        data={"auto_levels": "true", "posterize": "6"},
    )
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    out = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)
    assert out is not None and out.shape[2] == 3


# ── thread editor ───────────────────────────────────────────────────────────


def test_custom_threads_round_trip_and_validate(client):
    r = client.post(
        "/api/threads/custom",
        json={"brand": "House", "name": "Signature Red", "code": "H-101", "hex": "#C0392B"},
    )
    assert r.status_code == 201
    tid = r.json()["id"]
    assert r.json()["hex"] == "#c0392b", "hex is normalised for stable comparison"

    assert client.get("/api/threads/custom").json()[0]["name"] == "Signature Red"

    r = client.patch(f"/api/threads/custom/{tid}", json={"hex": "#00ff00"})
    assert r.status_code == 200 and r.json()["hex"] == "#00ff00"

    bad = client.post(
        "/api/threads/custom", json={"brand": "X", "name": "Y", "hex": "not-a-colour"}
    )
    assert bad.status_code == 422 and "hex" in bad.json()["detail"]

    assert client.delete(f"/api/threads/custom/{tid}").status_code == 204
    assert client.get("/api/threads/custom").json() == []


def test_palettes_save_and_delete(client):
    r = client.post(
        "/api/threads/palettes",
        json={
            "name": "Autumn",
            "colors": [{"hex": "#8b4513", "name": "Bark"}, {"hex": "#ff8c00", "name": "Amber"}],
        },
    )
    assert r.status_code == 201 and len(r.json()["colors"]) == 2
    pid = r.json()["id"]
    assert client.delete(f"/api/threads/palettes/{pid}").status_code == 204
    assert client.get("/api/threads/palettes").json() == []


def test_empty_palette_is_refused(client):
    r = client.post("/api/threads/palettes", json={"name": "Nothing", "colors": []})
    assert r.status_code == 422


# ── stitch (DST) editor ─────────────────────────────────────────────────────


def _stream():
    return [
        Stitch(x=0, y=0, command=StitchCommand.STITCH),
        Stitch(x=2, y=0, command=StitchCommand.STITCH),
        Stitch(x=4, y=0, command=StitchCommand.STITCH),
        Stitch(x=6, y=0, command=StitchCommand.STITCH),
        Stitch(x=6, y=0, command=StitchCommand.TRIM),
        Stitch(x=20, y=0, command=StitchCommand.JUMP),
        Stitch(x=22, y=0, command=StitchCommand.STITCH),
        Stitch(x=22, y=0, command=StitchCommand.END),
    ]


def test_scaling_a_block_never_leaves_an_over_limit_stitch():
    """The defect this guards: scaling up silently stretches moves past the
    machine's 12.7mm reach, and the file fails at the machine, not here."""
    out, notes = stitch_edit.apply_ops(_stream(), [
        {"op": "transform", "start": 0, "end": 3, "scale": 8.0}
    ])
    assert stitch_edit.stream_stats(out)["overLimit"] == 0
    assert any("12.7mm" in n for n in notes), "an automatic repair must be reported"


def test_delete_range_and_refuse_deleting_everything():
    out, _ = stitch_edit.apply_ops(_stream(), [{"op": "delete", "start": 1, "end": 2}])
    assert stitch_edit.stream_stats(out)["stitches"] == 3

    with pytest.raises(stitch_edit.EditError):
        stitch_edit.apply_ops(_stream(), [{"op": "delete", "start": 0, "end": 99}])


def test_jump_to_stitch_conversion_and_trim_removal():
    out, _ = stitch_edit.apply_ops(_stream(), [
        {"op": "setCommand", "start": 5, "end": 5, "command": "STITCH"},
        {"op": "removeTrims", "start": 0, "end": 99},
    ])
    stats = stitch_edit.stream_stats(out)
    assert stats["jumps"] == 0 and stats["trims"] == 0
    # Converting a 14mm jump into a stitch must also respect the machine limit.
    assert stats["overLimit"] == 0


def test_stream_always_ends_with_exactly_one_end():
    out, _ = stitch_edit.apply_ops(_stream(), [{"op": "splitColor", "index": 3}])
    ends = [s for s in out if stitch_edit._cmd(s) is StitchCommand.END]
    assert len(ends) == 1 and stitch_edit._cmd(out[-1]) is StitchCommand.END


def test_consecutive_duplicate_controls_collapse():
    st = [
        Stitch(x=0, y=0, command=StitchCommand.STITCH),
        Stitch(x=1, y=0, command=StitchCommand.STITCH),
    ]
    out, notes = stitch_edit.apply_ops(st, [
        {"op": "splitColor", "index": 1},
        {"op": "splitColor", "index": 1},
    ])
    changes = [s for s in out if stitch_edit._cmd(s) is StitchCommand.COLOR_CHANGE]
    assert len(changes) == 1, "a doubled colour change is a no-op on the machine"
    assert any("redundant" in n for n in notes)


def test_edit_endpoint_updates_the_design_header(client):
    design = {
        "name": "d",
        "widthMm": 6,
        "heightMm": 0,
        "stitches": [
            {"x": 0, "y": 0, "command": "STITCH"},
            {"x": 6, "y": 0, "command": "STITCH"},
            {"x": 6, "y": 0, "command": "END"},
        ],
        "colorStops": [],
        "objects": [],
    }
    r = client.post(
        "/api/stitches/edit",
        json={"design": design, "ops": [{"op": "transform", "start": 0, "end": 1, "scale": 2.0}]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["design"]["widthMm"] == 12.0, "the header must follow the edit"
    assert body["stats"]["overLimit"] == 0


def test_unknown_operation_is_a_clear_422(client):
    design = {
        "name": "d", "widthMm": 1, "heightMm": 1,
        "stitches": [{"x": 0, "y": 0, "command": "STITCH"}],
        "colorStops": [], "objects": [],
    }
    r = client.post("/api/stitches/edit", json={"design": design, "ops": [{"op": "nope"}]})
    assert r.status_code == 422 and "nope" in r.json()["detail"]
