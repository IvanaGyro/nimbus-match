import pytest
from fontTools.fontBuilder import FontBuilder

from font_match.build import apply_tnr_advance_corrections


@pytest.mark.parametrize(
    "style, expected",
    [("Regular", 1237), ("Bold", 1200), ("Italic", 1137), ("BoldItalic", 1225)],
)
def test_ff_correction_needs_no_reference_font_and_preserves_other_metrics(
    style, expected
):
    builder = FontBuilder(2048, isTTF=True)
    builder.setupGlyphOrder([".notdef", "ff", "extra"])
    builder.setupCharacterMap({0xFB00: "ff", 0x2200: "extra"})
    builder.setupHorizontalMetrics(
        {".notdef": (500, 0), "ff": (1500, 37), "extra": (1700, 24)}
    )
    apply_tnr_advance_corrections(builder.font, style)
    assert builder.font["hmtx"].metrics == {
        ".notdef": (500, 0),
        "ff": (expected, 37),
        "extra": (1700, 24),
    }
