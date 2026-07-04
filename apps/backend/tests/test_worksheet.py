"""Tests for worksheet PDF rendering and the thread catalog (Phase 1 tail + Phase 2)."""

from __future__ import annotations

from app.models.design import ColorStop, Design
from app.services import threads as threads_svc
from app.services.worksheet_pdf import build_worksheet, render_pdf


def _design() -> Design:
    return Design(
        name="t",
        width_mm=40,
        height_mm=40,
        stitch_count=100,
        color_stops=[
            ColorStop(stop_number=1, thread_brand="Madeira", catalog_number="1147", thread_name="Red", hex="#c8181e", stitch_count=60),
            ColorStop(stop_number=2, thread_brand="Madeira", catalog_number="1733", thread_name="Blue", hex="#1e3cc8", stitch_count=40),
        ],
    )


def test_render_pdf_returns_pdf_bytes():
    data = render_pdf(build_worksheet(_design()))
    assert data[:5] == b"%PDF-"
    assert len(data) > 500


def test_build_worksheet_totals():
    ws = build_worksheet(_design())
    assert ws.estimated_stitch_count == 100
    assert len(ws.color_sequence) == 2


def test_worksheet_thread_length_per_color():
    from app.models.design import ColorStop, Design, Stitch

    # two stops; color 1 stitches span 0→10→20mm (10+10=20mm), color 2 spans 0→5 (5mm)
    d = Design(
        name="t",
        stitch_count=5,
        color_stops=[
            ColorStop(stop_number=1, thread_brand="M", catalog_number="1", thread_name="A", hex="#111111", stitch_count=3),
            ColorStop(stop_number=2, thread_brand="M", catalog_number="2", thread_name="B", hex="#222222", stitch_count=2),
        ],
        stitches=[
            Stitch(x=0, y=0, command="STITCH"),
            Stitch(x=10, y=0, command="STITCH"),
            Stitch(x=20, y=0, command="STITCH"),
            Stitch(x=20, y=0, command="COLOR_CHANGE"),
            Stitch(x=0, y=0, command="JUMP"),  # jump does not count as thread
            Stitch(x=0, y=0, command="STITCH"),
            Stitch(x=5, y=0, command="STITCH"),
            Stitch(x=5, y=0, command="END"),
        ],
    )
    ws = build_worksheet(d)
    assert ws.color_sequence[0].thread_length_mm == 20.0
    assert ws.color_sequence[1].thread_length_mm == 5.0


def test_list_threads_loads_catalog():
    all_threads = threads_svc.list_threads()
    assert len(all_threads) >= 1
    assert all(t.hex.startswith("#") for t in all_threads)
    assert threads_svc.list_threads("Madeira")
    assert threads_svc.list_threads("no-such-brand") == []
