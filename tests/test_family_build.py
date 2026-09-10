import json
import os
from pathlib import Path

import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.misc.roundTools import otRound
from fontTools.ttLib import TTFont

from font_match.artifacts import validate
from font_match.build import build_single_style, extract_reference_kerning_pairs
from font_match.config import STYLES, load_family
from font_match.metric_overrides import FF_ADVANCES, predict_missing_advances
from font_match.previews.render import FontRenderer
from font_match.upstream import extract

PROJECT = Path.cwd()
FAMILIES = (
    [os.environ["FONT_MATCH_FAMILY"]]
    if os.environ.get("FONT_MATCH_FAMILY")
    else ["nimbus-match", "termes-match"]
)


@pytest.fixture(params=FAMILIES)
def family(request):
    return load_family(PROJECT, request.param)


@pytest.fixture
def inputs():
    path = PROJECT / "build_temp/inputs.json"
    assert path.is_file(), (
        "Resolve and build fonts before running the required compatibility suite"
    )
    return json.loads(path.read_text())["inputs"]


def paths(family, inputs, style):
    source = (
        PROJECT
        / "build_temp"
        / family.id
        / inputs[family.provider]["sha256"]
        / family.sources[style]
    )
    reference = (
        PROJECT
        / "build_temp/references/tinos"
        / inputs["tinos"]["sha256"]
        / f"Tinos-{style}.ttf"
    )
    output = PROJECT / "dist" / family.id / f"{family.prefix}-{style}.otf"
    assert all(p.is_file() for p in (source, reference, output)), (
        "Required font inputs/output missing"
    )
    return source, reference, output


@pytest.mark.parametrize("style", STYLES)
def test_metrics_and_coverage(family, inputs, style):
    source, reference, output = paths(family, inputs, style)
    with TTFont(source) as original, TTFont(reference) as ref, TTFont(output) as font:
        cmap, rmap = font.getBestCmap(), ref.getBestCmap()
        assert cmap == original.getBestCmap()
        assert font.getGlyphOrder() == original.getGlyphOrder()
        for cp in cmap.keys() & rmap.keys():
            assert font["hmtx"][cmap[cp]][0] == ref["hmtx"][rmap[cp]][0], f"U+{cp:04X}"
        assert font["hmtx"][cmap[0xFB00]][0] == FF_ADVANCES[style]
        for attr in ("ascent", "descent", "lineGap"):
            assert getattr(font["hhea"], attr) == getattr(ref["hhea"], attr)
        for attr in (
            "sTypoAscender",
            "sTypoDescender",
            "sTypoLineGap",
            "usWinAscent",
            "usWinDescent",
        ):
            assert getattr(font["OS/2"], attr) == getattr(ref["OS/2"], attr)
        predicted = (
            predict_missing_advances(original, ref) if family.predict_missing else {}
        )
        for cp in cmap.keys() - rmap.keys() - {0xFB00} - predicted.keys():
            assert font["hmtx"][cmap[cp]][0] == otRound(
                original["hmtx"][cmap[cp]][0] * 2048 / original["head"].unitsPerEm
            )
        for cp, width in predicted.items():
            assert font["hmtx"][cmap[cp]][0] == width
        assert (
            font["head"].macStyle & 3
            == {"Regular": 0, "Bold": 1, "Italic": 2, "BoldItalic": 3}[style]
        )
        assert font["name"].getBestSubFamilyName() == style.replace(
            "BoldItalic", "Bold Italic"
        )


@pytest.mark.parametrize("style", STYLES)
def test_shaping_preserves_positioning_and_substitution(family, inputs, style):
    source, reference, output = paths(family, inputs, style)
    before, after, ref = [FontRenderer(p) for p in (source, output, reference)]
    for sample in ("AVATAR", "To Wa", "office final fluff"):
        assert after.advance(sample) == ref.advance(sample)
        assert after.shape(sample, {"liga": True}) == after.shape(
            sample, {"liga": False}
        )
    if family.id == "termes-match":
        for feature, sample in [
            ("smcp", "Roman"),
            ("onum", "1234567890"),
            ("c2sc", "ROMAN"),
        ]:
            expected = [g.glyph_id for g in before.shape(sample, {feature: True})]
            actual = [g.glyph_id for g in after.shape(sample, {feature: True})]
            assert actual == expected
            assert actual != [g.glyph_id for g in after.shape(sample, {feature: False})]
        delta = after.advance("CAPITALS", {"cpsp": True}) - after.advance(
            "CAPITALS", {"cpsp": False}
        )
        original = before.advance("CAPITALS", {"cpsp": True}) - before.advance(
            "CAPITALS", {"cpsp": False}
        )
        assert (
            original > 0
            and abs(delta - original * 2048 / before.upem) <= len("CAPITALS") / 2
        )


def test_release_packages(family):
    validate(family, PROJECT / "dist" / family.id)


def test_build_reads_only_explicit_inputs(family, inputs, tmp_path, monkeypatch):
    from font_match import build

    source, reference, output = paths(family, inputs, "Regular")
    real = build.TTFont
    destination = tmp_path / "font.otf"
    allowed = {source.resolve(), reference.resolve(), destination.resolve()}

    def guarded(path, *args, **kwargs):
        assert Path(path).resolve() in allowed, f"Unexpected font read: {path}"
        return real(path, *args, **kwargs)

    monkeypatch.setattr(build, "TTFont", guarded)
    build_single_style(
        source,
        reference,
        destination,
        "Regular",
        version="1.001",
        family=family.name,
        prefix=family.prefix,
        remove_liga=family.remove_liga,
        predict_missing=family.predict_missing,
        legacy_kerning_names=family.legacy_kerning_names,
    )
    with real(output) as expected, real(destination) as actual:
        assert actual["hmtx"].metrics == expected["hmtx"].metrics
        assert extract_reference_kerning_pairs(
            actual
        ) == extract_reference_kerning_pairs(expected)


def test_predicts_new_canonical_accents_without_guessing_symbols():
    def font(cmap, metrics):
        builder = FontBuilder(2048, isTTF=True)
        builder.setupGlyphOrder([".notdef", *metrics])
        builder.setupCharacterMap(cmap)
        builder.setupHorizontalMetrics({".notdef": (500, 0), **metrics})
        return builder.font

    source = font(
        {0x1EAD: "new_accent", 0x2603: "new_symbol"},
        {"new_accent": (1100, 12), "new_symbol": (1700, 20)},
    )
    reference = font({ord("a"): "a"}, {"a": (909, 0)})
    assert predict_missing_advances(source, reference) == {0x1EAD: 909}
    assert source["hmtx"]["new_accent"] == (909, 12)
    assert source["hmtx"]["new_symbol"] == (1700, 20)


def test_pinned_inputs_reject_hash_mismatch(tmp_path):
    archive = tmp_path / "build_temp/archives" / ("0" * 64 + ".zip")
    archive.parent.mkdir(parents=True)
    archive.write_bytes(b"changed upstream bytes")
    with pytest.raises(ValueError, match="checksum changed"):
        extract(
            tmp_path,
            {"sha256": "0" * 64, "url": "https://example.invalid/input.zip"},
            ["font.otf"],
            "test",
        )


def test_release_validation_fails_when_artifacts_missing(tmp_path):
    with pytest.raises(ValueError, match="Missing required"):
        validate(load_family(PROJECT, "termes-match"), tmp_path)
