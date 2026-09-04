from pathlib import Path

import pytest
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

DIST_DIR = Path("dist")
WIN_FONTS = Path(r"C:\Windows\Fonts")

STYLES = [
    (
        "Regular",
        "NimbusMatch-Regular.otf",
        ["times.ttf", "LiberationSerif-Regular.ttf"],
    ),
    ("Bold", "NimbusMatch-Bold.otf", ["timesbd.ttf", "LiberationSerif-Bold.ttf"]),
    ("Italic", "NimbusMatch-Italic.otf", ["timesi.ttf", "LiberationSerif-Italic.ttf"]),
    (
        "BoldItalic",
        "NimbusMatch-BoldItalic.otf",
        ["timesbi.ttf", "LiberationSerif-BoldItalic.ttf"],
    ),
]


def get_ref_font_path(candidates: list[str]) -> Path:
    """Find system Times New Roman or fallback reference font."""
    search_dirs = [
        WIN_FONTS,
        Path("/System/Library/Fonts/Supplemental"),
        Path("/System/Library/Fonts"),
        Path("/Library/Fonts"),
        Path("dist"),
        Path("scratch_fonts"),
    ]
    for sdir in search_dirs:
        if not sdir.exists():
            continue
        for cand in candidates:
            if (sdir / cand).exists():
                return sdir / cand
            if "times.ttf" in cand and (sdir / "Times New Roman.ttf").exists():
                return sdir / "Times New Roman.ttf"
            if "timesbd.ttf" in cand and (sdir / "Times New Roman Bold.ttf").exists():
                return sdir / "Times New Roman Bold.ttf"
            if "timesi.ttf" in cand and (sdir / "Times New Roman Italic.ttf").exists():
                return sdir / "Times New Roman Italic.ttf"
            if (
                "timesbi.ttf" in cand
                and (sdir / "Times New Roman Bold Italic.ttf").exists()
            ):
                return sdir / "Times New Roman Bold Italic.ttf"
    pytest.skip(f"Reference font candidates {candidates} not found")


@pytest.fixture(scope="module", autouse=True)
def ensure_fonts_built():
    """Ensure fonts are built in dist/ before running tests."""
    missing = [
        filename for _, filename, _ in STYLES if not (DIST_DIR / filename).exists()
    ]
    if missing:
        from check_and_build import main as build_main

        print(f"Building missing test fonts: {missing}")
        build_main()


@pytest.mark.parametrize("style_name, font_file, ref_candidates", STYLES)
def test_upem_is_2048(style_name, font_file, ref_candidates):
    font_path = DIST_DIR / font_file
    assert font_path.exists(), f"Font file {font_file} does not exist"

    font = TTFont(font_path)
    assert font["head"].unitsPerEm == 2048, (
        f"{style_name} UPEM is {font['head'].unitsPerEm}, expected 2048"
    )


@pytest.mark.parametrize("style_name, font_file, ref_candidates", STYLES)
def test_font_naming(style_name, font_file, ref_candidates):
    font_path = DIST_DIR / font_file
    font = TTFont(font_path)

    name_table = font["name"]
    family_names = [
        record.toUnicode() for record in name_table.names if record.nameID in (1, 16)
    ]
    assert any("Nimbus Match" in name for name in family_names), (
        f"Family name 'Nimbus Match' not found in {font_file}"
    )


@pytest.mark.parametrize("style_name, font_file, ref_candidates", STYLES)
def test_basic_latin_advance_widths_exact_match(style_name, font_file, ref_candidates):
    """Test that standard ASCII Printable Latin characters (0x20..0x7E) match 100% identically."""
    font_path = DIST_DIR / font_file
    ref_path = get_ref_font_path(ref_candidates)

    font = TTFont(font_path)
    ref_font = TTFont(ref_path)

    font_cmap = font.getBestCmap() or {}
    ref_cmap = ref_font.getBestCmap() or {}

    mismatches = []
    for cp in range(0x20, 0x7F):
        if cp not in font_cmap or cp not in ref_cmap:
            continue
        g_nim = font_cmap[cp]
        g_ref = ref_cmap[cp]

        adv_nim = font["hmtx"][g_nim][0]
        adv_ref = ref_font["hmtx"][g_ref][0]

        diff = abs(adv_nim - adv_ref)
        if diff > 1:
            mismatches.append((cp, chr(cp), adv_nim, adv_ref))

    assert len(mismatches) == 0, (
        f"[{style_name}] Found Basic Latin advance mismatches: {mismatches}"
    )


@pytest.mark.parametrize("style_name, font_file, ref_candidates", STYLES)
def test_overall_character_advance_compatibility(style_name, font_file, ref_candidates):
    """
    Test overall character advance width compatibility across all shared codepoints
    (Latin, Greek, Cyrillic, Punctuation, Symbols).
    """
    font_path = DIST_DIR / font_file
    ref_path = get_ref_font_path(ref_candidates)

    font = TTFont(font_path)
    ref_font = TTFont(ref_path)

    font_cmap = font.getBestCmap() or {}
    ref_cmap = ref_font.getBestCmap() or {}

    shared_cps = set(font_cmap.keys()).intersection(ref_cmap.keys())
    assert len(shared_cps) > 200, (
        f"Expected >200 shared codepoints, got {len(shared_cps)}"
    )

    exact_matches = 0
    diffs = []

    for cp in sorted(shared_cps):
        if cp < 0x20 or (0x7F <= cp < 0xA0):
            continue

        g_nim = font_cmap[cp]
        g_ref = ref_cmap[cp]

        adv_nim = font["hmtx"][g_nim][0]
        adv_ref = ref_font["hmtx"][g_ref][0]

        diff = abs(adv_nim - adv_ref)
        diffs.append(diff)
        if diff <= 1:
            exact_matches += 1

    total_valid = len(diffs)
    match_ratio = exact_matches / total_valid if total_valid else 0
    avg_diff = sum(diffs) / total_valid if total_valid else 0

    assert match_ratio >= 0.96, (
        f"[{style_name}] Only {match_ratio * 100:.1f}% of codepoints matched metrics (expected >=96%)"
    )
    assert avg_diff < 10.0, (
        f"[{style_name}] Average advance width difference is {avg_diff:.3f} UPM (expected <10.0 UPM)"
    )


@pytest.mark.parametrize("style_name, font_file, ref_candidates", STYLES)
def test_vertical_metrics_match_reference(style_name, font_file, ref_candidates):
    font_path = DIST_DIR / font_file
    ref_path = get_ref_font_path(ref_candidates)

    font = TTFont(font_path)
    ref_font = TTFont(ref_path)

    for attr in ("ascent", "descent", "lineGap"):
        val_nim = getattr(font["hhea"], attr)
        val_ref = getattr(ref_font["hhea"], attr)
        assert val_nim == val_ref, (
            f"[{style_name}] hhea.{attr} mismatch: {val_nim} vs {val_ref}"
        )

    for attr in (
        "sTypoAscender",
        "sTypoDescender",
        "sTypoLineGap",
        "usWinAscent",
        "usWinDescent",
    ):
        val_nim = getattr(font["OS/2"], attr)
        val_ref = getattr(ref_font["OS/2"], attr)
        assert val_nim == val_ref, (
            f"[{style_name}] OS/2.{attr} mismatch: {val_nim} vs {val_ref}"
        )


@pytest.mark.parametrize("style_name, font_file, ref_candidates", STYLES)
def test_kerning_present(style_name, font_file, ref_candidates):
    font_path = DIST_DIR / font_file
    font = TTFont(font_path)

    has_kern_table = "kern" in font and len(font["kern"].kernTables) > 0
    has_gpos_kern = "GPOS" in font and any(
        rec.FeatureTag == "kern" for rec in font["GPOS"].table.FeatureList.FeatureRecord
    )

    assert has_kern_table or has_gpos_kern, (
        f"[{style_name}] No legacy kern table or GPOS kern feature found"
    )


@pytest.mark.parametrize("style_name, font_file, ref_candidates", STYLES)
def test_rendered_sentence_width_matches_times_new_roman(
    style_name, font_file, ref_candidates
):
    """Test rendered paragraph/sentence width difference between Nimbus Match and Times New Roman."""
    font_path = DIST_DIR / font_file
    ref_path = get_ref_font_path(ref_candidates)

    test_sentences = [
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ  abcdefghijklmnopqrstuvwxyz  0123456789",
        "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ αβγδεζηθικλμνξοπρστυφχψω",
        "Съешь же ещё этих мягких французских булок, да выпей чаю.",
        r"!”#$%&'()*+,-./:;<=>?@[\]^_`{|}~ ¡¢£¤¥§©«®°±²³µ¶·¹º»¼½¾¿–—‘’“”„†‡•…‰′″‹›€№™",
    ]

    img = Image.new("RGB", (2500, 100))
    draw = ImageDraw.Draw(img)

    for size in (24, 36):
        pil_nim = ImageFont.truetype(str(font_path), size)
        pil_ref = ImageFont.truetype(str(ref_path), size)

        for text in test_sentences:
            bbox_nim = draw.textbbox((0, 0), text, font=pil_nim)
            bbox_ref = draw.textbbox((0, 0), text, font=pil_ref)

            width_nim = bbox_nim[2] - bbox_nim[0]
            width_ref = bbox_ref[2] - bbox_ref[0]

            diff = abs(width_nim - width_ref)
            relative_diff = diff / max(width_ref, 1)

            # Assert rendered line width difference is <= 3px or <= 0.5% relative difference
            assert diff <= 3 or relative_diff < 0.005, (
                f"[{style_name} @ {size}pt] Rendered line width mismatch for '{text[:20]}...': "
                f"Nimbus Match = {width_nim}px, Reference = {width_ref}px (diff = {diff}px, {relative_diff * 100:.2f}%)"
            )


@pytest.mark.parametrize("style_name, font_file, ref_candidates", STYLES)
def test_opentype_table_completeness(style_name, font_file, ref_candidates):
    """Verify all mandatory OpenType font tables exist and are non-empty."""
    font_path = DIST_DIR / font_file
    font = TTFont(font_path)

    required_tables = [
        "head",
        "hhea",
        "maxp",
        "OS/2",
        "hmtx",
        "cmap",
        "name",
        "post",
        "CFF ",
    ]
    for table_tag in required_tables:
        assert table_tag in font, (
            f"[{style_name}] Missing required OpenType table: '{table_tag}'"
        )


@pytest.mark.parametrize("style_name, font_file, ref_candidates", STYLES)
def test_whitespace_and_special_space_boundary(style_name, font_file, ref_candidates):
    """Boundary test for whitespace, non-breaking space, and zero-width spaces."""
    font_path = DIST_DIR / font_file
    ref_path = get_ref_font_path(ref_candidates)

    font = TTFont(font_path)
    ref_font = TTFont(ref_path)

    font_cmap = font.getBestCmap() or {}
    ref_cmap = ref_font.getBestCmap() or {}

    space_cps = [0x0020, 0x00A0]  # Standard space, Non-breaking space
    for cp in space_cps:
        if cp in font_cmap and cp in ref_cmap:
            adv_nim = font["hmtx"][font_cmap[cp]][0]
            adv_ref = ref_font["hmtx"][ref_cmap[cp]][0]
            assert abs(adv_nim - adv_ref) <= 1, (
                f"[{style_name}] Space codepoint U+{cp:04X} advance width mismatch: {adv_nim} vs {adv_ref}"
            )


@pytest.mark.parametrize("style_name, font_file, ref_candidates", STYLES)
def test_notdef_and_unmapped_glyph_boundary(style_name, font_file, ref_candidates):
    """Boundary test for .notdef presence and unmapped codepoint handling."""
    font_path = DIST_DIR / font_file
    font = TTFont(font_path)

    glyph_order = font.getGlyphOrder()
    assert ".notdef" in glyph_order, f"[{style_name}] Missing mandatory '.notdef' glyph"

    font_cmap = font.getBestCmap() or {}
    unmapped_cp = 0xE0000  # Private use / unmapped
    assert unmapped_cp not in font_cmap, (
        f"[{style_name}] Unexpected mapping for unmapped codepoint U+{unmapped_cp:05X}"
    )


def test_otc_collection_integrity():
    """Verify that NimbusMatch.otc exists and contains all 4 font faces with 2048 UPEM."""
    otc_path = DIST_DIR / "NimbusMatch.otc"
    if not otc_path.exists():
        pytest.skip("NimbusMatch.otc not found in dist/")

    from fontTools.ttLib import TTCollection

    ttc = TTCollection(otc_path)
    assert len(ttc.fonts) == 4, (
        f"Expected 4 fonts inside NimbusMatch.otc, found {len(ttc.fonts)}"
    )

    for font in ttc.fonts:
        assert font["head"].unitsPerEm == 2048
        name_table = font["name"]
        family_names = [r.toUnicode() for r in name_table.names if r.nameID in (1, 16)]
        assert any("Nimbus Match" in n for n in family_names)
