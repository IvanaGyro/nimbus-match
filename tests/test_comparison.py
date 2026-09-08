import pytest
from fontTools.fontBuilder import FontBuilder
from PIL import Image, ImageFont

from generate_comparison import BLUE, OVERLAP, RED, composite_overlay, wrap_sample
from generate_font_details import glyph_advance, validate_font_pair


def make_font(family):
    builder = FontBuilder(2048, isTTF=True)
    builder.setupGlyphOrder([".notdef", "A"])
    builder.setupCharacterMap({ord("A"): "A"})
    builder.setupHorizontalMetrics({".notdef": (500, 0), "A": (640, 0)})
    builder.setupNameTable({"familyName": family, "styleName": "Regular"})
    return builder.font


@pytest.mark.parametrize("wrong_side", ["nimbus", "reference"])
def test_detail_comparison_rejects_tinos(wrong_side):
    nimbus = make_font("Tinos" if wrong_side == "nimbus" else "Nimbus Match")
    reference = make_font("Tinos" if wrong_side == "reference" else "Times New Roman")
    with pytest.raises(ValueError, match="got Tinos"):
        validate_font_pair(nimbus, reference)


def test_missing_glyph_is_not_reported_as_notdef_width():
    font = make_font("Nimbus Match")
    assert glyph_advance(font, ord("A")) == 640
    assert glyph_advance(font, 0x2E3A) is None


def test_comparison_wraps_to_fit_both_fonts_without_losing_characters():
    fonts = [ImageFont.load_default(size=size) for size in (48, 60)]
    sample = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    lines = wrap_sample(sample, fonts, 200)
    assert "".join(lines) == sample
    assert len(lines) > 1
    for line in lines:
        for font in fonts:
            assert max(font.getlength(line), font.getbbox(line)[2]) <= 200


def test_overlay_keeps_shared_ink_light_and_exclusive_ink_saturated():
    reference = Image.new("L", (4, 1))
    reference.putdata([255, 255, 0, 0])
    nimbus = Image.new("L", (4, 1))
    nimbus.putdata([255, 0, 255, 0])
    result = composite_overlay(reference, nimbus)
    assert [result.getpixel((x, 0)) for x in range(4)] == [
        OVERLAP,
        RED,
        BLUE,
        (255, 255, 255),
    ]
    assert min(result.getpixel((0, 0))) >= 180
