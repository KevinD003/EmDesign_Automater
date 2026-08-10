"""The garment colour is an input, and its removal is reported (DET3).

The substrate rule leaves regions matching the cloth colour unstitched so the
fabric shows through. That is right for embroidery. What was wrong is everything
around it:

  * the colour was only ever inferred from the image border — a number the
    customer is never asked for and cannot correct, yet it decides which of
    their artwork gets deleted;
  * the deletion was subtracted from BOTH coverage bases, so a design could lose
    a fifth of its foreground with every quality metric still reading as if it
    had sewn everything, and nothing was said to anyone;
  * and a transparent PNG — the most common real digitizing input there is — has
    its alpha composited onto white, so WHITE ARTWORK ON TRANSPARENT becomes
    white artwork on a white page, matches a white border, and is deleted
    entirely. Measured before this fix: 0 stitches, 0 objects, no warning about
    it.

An SVG was already exempt because its mask is declared rather than guessed. An
alpha channel is the same kind of declaration and now earns the same exemption.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.services.digitizer import _bgr_to_hex, _decode_raster, _parse_bgr, digitize_image


def _png(img) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _white_art_on_transparent(h: int = 500, w: int = 500) -> bytes:
    """A white ring and bar on a fully transparent field.

    Composited onto white — which is what the decoder must do to get a colour
    for every pixel — this is indistinguishable from a blank page. The alpha
    channel is the only thing that says otherwise.
    """
    rgba = np.zeros((h, w, 4), np.uint8)
    cv2.circle(rgba, (250, 250), 170, (255, 255, 255, 255), 26)
    cv2.rectangle(rgba, (200, 230), (300, 270), (255, 255, 255, 255), -1)
    return _png(rgba)


def _art_on_navy(h: int = 500, w: int = 500) -> bytes:
    """Gold ring + red bar on a navy field, opaque — so the rule DOES run."""
    img = np.full((h, w, 3), (80, 40, 20), np.uint8)
    cv2.circle(img, (250, 250), 170, (40, 170, 220), 30)
    cv2.rectangle(img, (200, 235), (300, 265), (40, 40, 200), -1)
    return _png(img)


# ── (d) input that declares its own foreground is exempt from the rule ───────


def test_white_artwork_on_transparent_is_not_deleted_as_the_garment():
    """The headline case. Before DET3 this produced 0 stitches and 0 objects."""
    d = digitize_image(_white_art_on_transparent(), "cotton", "100x100", 4)
    assert d.stitch_count > 0, (
        "white artwork on a transparent background was deleted as the garment — "
        "the alpha channel declares it is artwork and must exempt it"
    )
    assert d.objects, "no objects survived"
    assert d.substrate_removed_mm2 == 0.0, (
        "the substrate rule ran on input that declares its own foreground"
    )


def test_a_fully_opaque_alpha_channel_is_not_a_declaration():
    """Guard the guard, and the more dangerous direction.

    Plenty of exporters attach an all-255 alpha to artwork with no transparency.
    That says nothing about what is background, so treating it as a declaration
    would silently exempt a huge share of ordinary uploads from a rule they
    still need. `_decode_raster` must report no declaration for it.
    """
    opaque = np.dstack([_art_on_navy_img(), np.full((500, 500), 255, np.uint8)])
    _img, declared = _decode_raster(_png(opaque))
    assert declared is None, (
        "an all-opaque alpha channel was treated as a declaration of foreground"
    )

    _img2, declared2 = _decode_raster(_white_art_on_transparent())
    assert declared2 is not None, "real transparency was not recognised"
    assert declared2.max() == 255 and declared2.min() == 0


def test_a_fully_transparent_alpha_channel_is_not_a_declaration_either():
    """The same degeneracy from the other end, and it was missed the first time.

    An all-zero alpha declares nothing to be artwork, which says no more about
    WHICH pixels are design than an all-opaque one does. Treating it as a
    declaration skipped the substrate rule on a blank canvas and sent the whole
    image into a full-canvas distance transform — caught as a new numpy overflow
    warning under `test_fully_transparent_rgba`, which only asserts "no 5xx" and
    so would never have failed on it.
    """
    blank = np.zeros((300, 300, 4), np.uint8)
    _img, declared = _decode_raster(_png(blank))
    assert declared is None, (
        "a fully transparent image was treated as declaring its foreground"
    )


def _art_on_navy_img():
    img = np.full((500, 500, 3), (80, 40, 20), np.uint8)
    cv2.circle(img, (250, 250), 170, (40, 170, 220), 30)
    cv2.rectangle(img, (200, 235), (300, 265), (40, 40, 200), -1)
    return img


# ── (a) the garment colour is an input ──────────────────────────────────────


def test_declaring_the_substrate_changes_what_is_removed():
    """The parameter has to actually decide the removal, not merely be accepted.

    Declaring the GOLD instead of the navy must protect the navy and sacrifice
    the ring — a change no amount of border-reading could produce.
    """
    data = _art_on_navy()
    guessed = digitize_image(data, "cotton", "100x100", 4)
    as_navy = digitize_image(data, "cotton", "100x100", 4, substrate_color="#142850")
    as_gold = digitize_image(data, "cotton", "100x100", 4, substrate_color="#dcaa28")

    # Declaring what the border guess already found must change nothing at all.
    assert as_navy.stitch_count == guessed.stitch_count
    assert as_navy.substrate_removed_mm2 == guessed.substrate_removed_mm2

    assert as_gold.substrate_removed_mm2 != guessed.substrate_removed_mm2, (
        "substrate_color was accepted and then ignored"
    )
    assert as_gold.substrate_color_used == "#dcaa28"
    assert as_gold.substrate_color_declared is True
    assert guessed.substrate_color_declared is False


def test_a_substrate_that_cannot_be_parsed_is_refused_not_guessed():
    """Falling back to the border guess would delete different artwork than
    either party intended, silently — the exact defect the parameter closes."""
    for bad in ("#12345", "not-a-colour", (1, 2), "#gggggg"):
        with pytest.raises(ValueError):
            _parse_bgr(bad)


def test_hex_round_trips_through_bgr():
    assert _bgr_to_hex(_parse_bgr("#142850")) == "#142850"
    assert _bgr_to_hex(_parse_bgr("dcaa28")) == "#dcaa28"


# ── (b) and (c) the removal is reported, in prose and as a number ───────────


def test_removal_is_reported_as_its_own_channel():
    d = digitize_image(_art_on_navy(), "cotton", "100x100", 4)
    assert d.substrate_removed_mm2 > 0, "this fixture exists to exercise the rule"
    assert d.substrate_color_used == "#142850"

    said = [w for w in d.warnings if "garment colour" in w]
    assert said, f"artwork was removed and nothing was said: {d.warnings}"
    note = said[0]
    assert "mm²" in note, "the warning does not say how much was removed"
    assert d.substrate_color_used in note, "the warning does not name the colour"
    assert "not supplied" in note, (
        "a GUESSED substrate must say it was guessed and can be corrected — "
        "that is the difference between a report and an excuse"
    )


def test_a_declared_substrate_does_not_ask_to_be_corrected():
    d = digitize_image(_art_on_navy(), "cotton", "100x100", 4,
                       substrate_color="#142850")
    note = next(w for w in d.warnings if "garment colour" in w)
    assert "not supplied" not in note, (
        "the caller supplied the colour and is still being told to supply it"
    )
