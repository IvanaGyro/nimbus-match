from pathlib import Path

import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.misc.roundTools import otRound
from fontTools.ttLib import TTFont

from build_nimbus_match import apply_tnr_advance_corrections


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


@pytest.mark.parametrize(
    "style, expected",
    [("Regular", 1237), ("Bold", 1200), ("Italic", 1137), ("BoldItalic", 1225)],
)
def test_built_ff_correction_and_preserved_extra_advances(style, expected):
    paths = [
        Path("build_temp") / f"NimbusRoman-{style}.otf",
        Path("build_temp") / f"Tinos-{style}.ttf",
        Path("dist") / f"NimbusMatch-{style}.otf",
    ]
    if not all(path.exists() for path in paths):
        pytest.skip("Build the fonts to verify source and output advances")
    with (
        TTFont(paths[0]) as source,
        TTFont(paths[1]) as reference,
        TTFont(paths[2]) as output,
    ):
        source_cmap, ref_cmap, out_cmap = (
            font.getBestCmap() for font in (source, reference, output)
        )
        assert output["hmtx"][out_cmap[0xFB00]][0] == expected
        extras = source_cmap.keys() - ref_cmap.keys() - {0xFB00}
        assert extras
        for cp in extras:
            assert cp in out_cmap
            scaled = otRound(
                source["hmtx"][source_cmap[cp]][0]
                * output["head"].unitsPerEm
                / source["head"].unitsPerEm
            )
            assert output["hmtx"][out_cmap[cp]][0] == scaled, f"U+{cp:04X} changed"
