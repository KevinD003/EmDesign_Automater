"""CTO A12/C10: OFL fonts ship IN the repo; lettering no longer depends on
which OS the server runs.

The review: unsupported glyphs digitized as tofu boxes on Linux, output
depended on server-installed fonts, and the hardcoded Arial/Helvetica paths
could not legally be bundled. Four OFL families now live in
apps/backend/fonts/ (a clean sans, a semibold sans for small text, a serif,
and a script — the set an embroidery shop actually uses), each with its OFL
license text alongside. `_font_files` already prefers the repo dir, so every
deployment resolves the same fonts first.
"""

from __future__ import annotations

import glob
import os

import cv2
import pytest
from PIL import ImageFont

from app.services.lettering import _font_files, generate_lettering, list_fonts

FONTS_DIR = os.path.join(os.path.dirname(__file__), "..", "fonts")
BUNDLED_FAMILIES = {"Montserrat", "Open Sans", "Playfair Display", "Dancing Script"}


def test_repo_carries_at_least_three_ofl_families():
    files = glob.glob(os.path.join(FONTS_DIR, "*.ttf"))
    families = {ImageFont.truetype(p, 32).getname()[0] for p in files}
    assert BUNDLED_FAMILIES <= families, f"bundled: {families}"
    assert len(files) >= 3  # the backlog's floor


def test_every_bundled_font_has_its_license_alongside():
    # OFL requires the license to accompany the font software; keeping the
    # check in the suite keeps future font additions honest.
    licenses = {os.path.basename(p).lower() for p in glob.glob(os.path.join(FONTS_DIR, "OFL-*.txt"))}
    for fam in ("montserrat", "opensans", "playfairdisplay", "dancingscript"):
        assert f"ofl-{fam}.txt" in licenses, f"missing OFL text for {fam}"


def test_bundled_fonts_outrank_system_fonts():
    files = _font_files()
    assert files, "no fonts found at all"
    repo = os.path.abspath(FONTS_DIR)
    head = [os.path.abspath(p) for p in files[: len(BUNDLED_FAMILIES)]]
    assert all(p.startswith(repo) for p in head), (
        f"repo fonts must be first so every deployment resolves the same faces: {head}"
    )


def test_lettering_renders_with_a_bundled_font():
    # End-to-end through the digitizer with an explicit bundled face — the
    # deterministic path every OS now shares. Montserrat SemiBold is the
    # instanced static (the variable default was Thin — undigitizable).
    path = os.path.join(FONTS_DIR, "Montserrat-SemiBold.ttf")
    cv2.setRNGSeed(1234)
    d = generate_lettering("Peak", height_mm=12.0, font_path=path)
    assert d.stitch_count > 200
    assert d.objects


def test_list_fonts_reports_the_bundled_families():
    # Non-Regular styles carry their suffix ("Montserrat SemiBold"), so match
    # on the family prefix rather than exact names.
    names = {f["name"] for f in list_fonts()}
    for fam in BUNDLED_FAMILIES:
        assert any(n == fam or n.startswith(fam + " ") for n in names), (
            f"{fam} not listed; got {sorted(names)[:10]}..."
        )


@pytest.mark.parametrize("fname", ["OpenSans[wdth,wght].ttf", "PlayfairDisplay[wght].ttf",
                                   "DancingScript[wght].ttf", "Montserrat-SemiBold.ttf"])
def test_each_bundled_face_loads_and_draws(fname):
    f = ImageFont.truetype(os.path.join(FONTS_DIR, fname), 64)
    box = f.getbbox("Peak")
    assert box[2] - box[0] > 50 and box[3] - box[1] > 20, f"{fname}: degenerate glyphs"
