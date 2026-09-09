import pytest
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

from generate_font_details import smallcaps_masks
from render_font_sample import FontRenderer, finish_mask, new_mask


@pytest.fixture
def renderer_factory(tmp_path):
    def make_renderer(with_features):
        builder = FontBuilder(1000, isTTF=True)
        names = [".notdef", "A", "a", "a.sc"]
        builder.setupGlyphOrder(names)
        builder.setupCharacterMap(
            {**{ord(c): "A" for c in "AROMN"}, **{ord(c): "a" for c in "aomn"}}
        )
        glyphs = {}
        for name, height in zip(names, (700, 700, 400, 500)):
            pen = TTGlyphPen(None)
            pen.moveTo((0, 0))
            pen.lineTo((300, 0))
            pen.lineTo((300, height))
            pen.lineTo((0, height))
            pen.closePath()
            glyphs[name] = pen.glyph()
        builder.setupGlyf(glyphs)
        builder.setupHorizontalMetrics({name: (600, 0) for name in names})
        builder.setupHorizontalHeader(ascent=800, descent=-200)
        builder.setupNameTable({"familyName": "Renderer test", "styleName": "Regular"})
        builder.setupOS2(
            sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200
        )
        builder.setupPost()
        if with_features:
            addOpenTypeFeaturesFromString(
                builder.font,
                """
                languagesystem DFLT dflt;
                languagesystem latn dflt;
                feature cpsp { pos A 80; } cpsp;
                feature smcp { sub a by a.sc; } smcp;
            """,
            )
        path = tmp_path / f"sample-{with_features}.ttf"
        builder.save(path)
        return FontRenderer(path)

    return make_renderer


def test_cpsp_positions_reach_the_rendered_mask(renderer_factory):
    renderer = renderer_factory(True)
    assert renderer.advance("AA", {"cpsp": True}) == 1360
    assert renderer.advance("AA", {"cpsp": False}) == 1200
    masks = []
    for enabled in (False, True):
        mask = new_mask((150, 100))
        advance = renderer.draw(mask, "AA", (10, 80), 60, {"cpsp": enabled})
        assert advance == pytest.approx((1360 if enabled else 1200) * 60 / 1000)
        masks.append(finish_mask(mask))
    assert masks[1].getbbox()[2] > masks[0].getbbox()[2]


def test_smcp_uses_substituted_glyph_outlines(renderer_factory):
    renderer = renderer_factory(True)
    assert renderer.shape("a", {"smcp": False})[0].glyph_id == 2
    assert renderer.shape("a", {"smcp": True})[0].glyph_id == 3
    masks = []
    for enabled in (False, True):
        mask = new_mask((100, 100))
        renderer.draw(mask, "a", (10, 80), 60, {"smcp": enabled})
        masks.append(finish_mask(mask))
    assert masks[1].getbbox()[1] < masks[0].getbbox()[1]


def test_absent_features_do_not_invent_spacing_or_small_caps(renderer_factory):
    renderer = renderer_factory(False)
    assert renderer.shape("AAa", {"cpsp": True, "smcp": True}) == renderer.shape("AAa")


def test_comparison_uses_native_and_synthetic_small_caps(renderer_factory):
    native, synthetic = smallcaps_masks(renderer_factory(True), renderer_factory(False))
    # The initial capital stays identical. The suffix uses 500-unit native
    # outlines versus 700-unit uppercase outlines scaled to 80% (560 units).
    assert (
        native.crop((0, 0, 70, 150)).tobytes()
        == synthetic.crop((0, 0, 70, 150)).tobytes()
    )
    native_suffix = native.crop((72, 0, 584, 150)).getbbox()
    synthetic_suffix = synthetic.crop((72, 0, 584, 150)).getbbox()
    assert synthetic_suffix[1] < native_suffix[1]
    assert synthetic_suffix[2] < native_suffix[2]


def test_comparison_requires_real_small_caps_in_reference(renderer_factory):
    renderer = renderer_factory(False)
    with pytest.raises(ValueError, match="native smcp"):
        smallcaps_masks(renderer, renderer)
