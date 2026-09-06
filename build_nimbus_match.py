#!/usr/bin/env python3
"""
Build Nimbus Match font family (Regular, Bold, Italic, Bold Italic)
with Times New Roman / Tinos layout metrics.

Inputs:
  - Nimbus Roman OTF font files (URW Base35)
  - Tinos / reference TTF font files (metric reference)

The script does NOT read or copy anything from proprietary Times New Roman.
All font binaries are processed dynamically.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from fontTools.cffLib import TopDict
from fontTools.cffLib import specializer as cffSpecializer
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.scaleUpem import scale_upem
from fontTools.ttLib.tables import _k_e_r_n


def _scale_cff_args_exact(args: list, factor: float) -> None:
    """Recursively scale CFF operands with exact float precision."""
    for i, arg in enumerate(args):
        if isinstance(arg, list):
            _scale_cff_args_exact(arg, factor)
        elif not isinstance(arg, bytes):
            args[i] = arg * factor


def replace_rounded_cff_with_exact_scaled_cff(
    scaled: TTFont, original_path: str, old_upem: int, new_upem: int
) -> None:
    """Replace scaleUpem-rounded CFF programs with fixed-point exact scaling."""
    factor = new_upem / old_upem
    original = TTFont(original_path)

    ocff = original["CFF "].cff
    scff = scaled["CFF "].cff
    ocff.desubroutinize()
    scff.desubroutinize()

    otop = ocff.topDictIndex[0]
    stop = scff.topDictIndex[0]

    for glyph_name in otop.charset:
        och, _ = otop.CharStrings.getItemAndSelector(glyph_name)
        sch, _ = stop.CharStrings.getItemAndSelector(glyph_name)

        commands = cffSpecializer.programToCommands(och.program)
        for _op, args in commands:
            _scale_cff_args_exact(args, factor)
        sch.program[:] = cffSpecializer.commandsToProgram(commands)

    for attr in ("UnderlinePosition", "UnderlineThickness", "FontBBox", "StrokeWidth"):
        value = getattr(otop, attr, None)
        if value is None:
            continue
        if isinstance(value, list):
            setattr(stop, attr, [x * factor for x in value])
        else:
            setattr(stop, attr, value * factor)

    stop.FontMatrix = [1.0 / new_upem, 0.0, 0.0, 1.0 / new_upem, 0.0, 0.0]

    op = otop.Private
    sp = stop.Private
    for attr in (
        "BlueValues",
        "OtherBlues",
        "FamilyBlues",
        "FamilyOtherBlues",
        "StdHW",
        "StdVW",
        "StemSnapH",
        "StemSnapV",
        "defaultWidthX",
        "nominalWidthX",
    ):
        value = getattr(op, attr, None)
        if value is None:
            continue
        if isinstance(value, list):
            setattr(sp, attr, [x * factor for x in value])
        else:
            setattr(sp, attr, value * factor)


def reverse_cmap(font: TTFont) -> dict[str, list[int]]:
    rev: dict[str, list[int]] = {}
    for cp, glyph in (font.getBestCmap() or {}).items():
        rev.setdefault(glyph, []).append(cp)
    return rev


def map_reference_glyph(
    src_glyph: str,
    src_reverse: dict[str, list[int]],
    dst_cmap: dict[int, str],
    dst_glyphs: set[str],
) -> str | None:
    if src_glyph in dst_glyphs:
        return src_glyph
    for cp in src_reverse.get(src_glyph, []):
        if cp in dst_cmap:
            return dst_cmap[cp]
    return None


def extract_reference_kerning_pairs(ref: TTFont) -> dict[tuple[str, str], int]:
    """Extract pair kerning values from reference font via legacy kern table or GPOS PairPos."""
    pairs: dict[tuple[str, str], int] = {}
    if "kern" in ref and ref["kern"].kernTables:
        for (left, right), val in ref["kern"].kernTables[0].kernTable.items():
            if val != 0:
                pairs[(left, right)] = int(val)
        return pairs

    if "GPOS" in ref and ref["GPOS"].table:
        gpos = ref["GPOS"].table
        kern_lookups = set()
        if gpos.FeatureList:
            for r in gpos.FeatureList.FeatureRecord:
                if r.FeatureTag == "kern":
                    for idx in r.Feature.LookupListIndex:
                        kern_lookups.add(idx)

        glyph_order = ref.getGlyphOrder()
        for idx in sorted(kern_lookups):
            lookup = gpos.LookupList.Lookup[idx]
            if lookup.LookupType == 2:  # PairPos
                for subtable in lookup.SubTable:
                    if subtable.Format == 1:
                        for g_name, pair_set in zip(
                            subtable.Coverage.glyphs, subtable.PairSet
                        ):
                            for pvr in pair_set.PairValueRecord:
                                val = getattr(pvr.Value1, "XAdvance", 0) or 0
                                if val != 0:
                                    pairs[(g_name, pvr.SecondGlyph)] = int(val)
                    elif subtable.Format == 2:
                        class1_glyphs: dict[int, list[str]] = {}
                        class2_glyphs: dict[int, list[str]] = {}
                        for g in subtable.Coverage.glyphs:
                            c1 = subtable.ClassDef1.classDefs.get(g, 0)
                            class1_glyphs.setdefault(c1, []).append(g)
                        for g in glyph_order:
                            c2 = subtable.ClassDef2.classDefs.get(g, 0)
                            class2_glyphs.setdefault(c2, []).append(g)

                        for c1_idx, c1_rec in enumerate(subtable.Class1Record):
                            if c1_idx not in class1_glyphs:
                                continue
                            for c2_idx, c2_rec in enumerate(c1_rec.Class2Record):
                                if c2_idx not in class2_glyphs:
                                    continue
                                val = getattr(c2_rec.Value1, "XAdvance", 0) or 0
                                if val != 0:
                                    for g1 in class1_glyphs[c1_idx]:
                                        for g2 in class2_glyphs[c2_idx]:
                                            pairs[(g1, g2)] = int(val)
    return pairs


def build_kerning(dst: TTFont, ref: TTFont) -> tuple[dict[tuple[str, str], int], int]:
    """Transfer kerning pairs from reference font (kern or GPOS) to destination font."""
    ref_pairs = extract_reference_kerning_pairs(ref)
    if not ref_pairs:
        raise RuntimeError("Reference font has no kerning pairs in kern or GPOS tables")

    ref_rev = reverse_cmap(ref)
    dst_cmap = dst.getBestCmap() or {}
    dst_glyphs = set(dst.getGlyphOrder())

    pairs: dict[tuple[str, str], int] = {}
    skipped = 0
    for (left, right), val in ref_pairs.items():
        dl = map_reference_glyph(left, ref_rev, dst_cmap, dst_glyphs)
        dr = map_reference_glyph(right, ref_rev, dst_cmap, dst_glyphs)
        if not dl or not dr:
            skipped += 1
            continue
        pairs[(dl, dr)] = int(val)

    if "kern" in dst:
        del dst["kern"]
    kern = newTable("kern")
    kern.version = 0
    sub = _k_e_r_n.KernTable_format_0(apple=False)
    sub.version = 0
    sub.coverage = 1
    sub.tupleIndex = None
    sub.kernTable = pairs
    kern.kernTables = [sub]
    dst["kern"] = kern

    if "GPOS" in dst:
        feature_list = dst["GPOS"].table.FeatureList
        tags = (
            []
            if not feature_list
            else [r.FeatureTag for r in feature_list.FeatureRecord]
        )
        extra = set(tags) - {"kern"}
        if extra:
            raise RuntimeError(
                f"Refusing to discard non-kern Nimbus GPOS features: {sorted(extra)}"
            )
        del dst["GPOS"]

    lines = [
        "languagesystem DFLT dflt;",
        "languagesystem latn dflt;",
        "feature kern {",
    ]
    lines.extend(f"  pos {left} {right} {val};" for (left, right), val in pairs.items())
    lines.append("} kern;")
    addOpenTypeFeaturesFromString(dst, "\n".join(lines), tables=["GPOS"])

    return pairs, skipped


def remove_feature(font: TTFont, table_tag: str, feature_tag: str) -> int:
    """Remove a specific OpenType feature from GSUB or GPOS."""
    if table_tag not in font:
        return 0
    table = font[table_tag].table
    if not table.FeatureList:
        return 0

    old = table.FeatureList.FeatureRecord
    removed = {i for i, rec in enumerate(old) if rec.FeatureTag == feature_tag}
    if not removed:
        return 0

    remap: dict[int, int] = {}
    new_records = []
    for i, rec in enumerate(old):
        if i not in removed:
            remap[i] = len(new_records)
            new_records.append(rec)

    table.FeatureList.FeatureRecord = new_records
    table.FeatureList.FeatureCount = len(new_records)

    if table.ScriptList:
        for script_rec in table.ScriptList.ScriptRecord:
            langsyses = []
            if script_rec.Script.DefaultLangSys is not None:
                langsyses.append(script_rec.Script.DefaultLangSys)
            langsyses.extend(x.LangSys for x in script_rec.Script.LangSysRecord)
            for langsys in langsyses:
                langsys.FeatureIndex = [
                    remap[i] for i in langsys.FeatureIndex if i in remap
                ]
                langsys.FeatureCount = len(langsys.FeatureIndex)
                if langsys.ReqFeatureIndex != 0xFFFF:
                    langsys.ReqFeatureIndex = remap.get(langsys.ReqFeatureIndex, 0xFFFF)

    return len(removed)


def copy_all_shared_advances(dst: TTFont, ref: TTFont) -> tuple[int, int]:
    """
    Copy reference advances for all shared codepoints (Latin, Greek, Cyrillic, Symbols).
    Returns (advances_changed, total_shared_codepoints).
    """
    dst_cmap = dst.getBestCmap() or {}
    ref_cmap = ref.getBestCmap() or {}
    changed = 0
    seen: set[str] = set()

    shared_cps = set(dst_cmap.keys()).intersection(ref_cmap.keys())

    for cp in sorted(shared_cps):
        dg = dst_cmap[cp]
        if dg in seen:
            continue
        seen.add(dg)
        rg = ref_cmap[cp]
        advance, lsb = dst["hmtx"][dg]
        target = ref["hmtx"][rg][0]
        if advance != target:
            dst["hmtx"][dg] = (target, lsb)
            changed += 1

    return changed, len(shared_cps)


def copy_metrics_and_os2_metadata(
    dst: TTFont, ref: TTFont, style_name: str = "Regular"
) -> None:
    """
    Copy vertical metrics, layout metrics (sub/superscript, strikeout), PANOSE,
    and family classification from reference font. Also recalculates OS/2 ranges
    and cleans up obsolete tables.
    """
    # 1. Vertical metrics
    for attr in ("ascent", "descent", "lineGap"):
        setattr(dst["hhea"], attr, getattr(ref["hhea"], attr))
    for attr in (
        "sTypoAscender",
        "sTypoDescender",
        "sTypoLineGap",
        "usWinAscent",
        "usWinDescent",
    ):
        setattr(dst["OS/2"], attr, getattr(ref["OS/2"], attr))

    # 2. Subscript, superscript, and strikeout metrics
    for attr in (
        "ySubscriptXSize",
        "ySubscriptYSize",
        "ySubscriptXOffset",
        "ySubscriptYOffset",
        "ySuperscriptXSize",
        "ySuperscriptYSize",
        "ySuperscriptXOffset",
        "ySuperscriptYOffset",
        "yStrikeoutSize",
        "yStrikeoutPosition",
    ):
        if hasattr(ref["OS/2"], attr):
            setattr(dst["OS/2"], attr, getattr(ref["OS/2"], attr))

    # 3. PANOSE and sFamilyClass
    if getattr(ref["OS/2"], "sFamilyClass", 0) != 0:
        dst["OS/2"].sFamilyClass = ref["OS/2"].sFamilyClass
    else:
        dst["OS/2"].sFamilyClass = 261  # Oldstyle Serifs (Times New Roman standard)

    panose_defaults = {
        "Regular": (2, 2, 6, 3, 5, 4, 5, 2, 3, 4),
        "Bold": (2, 2, 8, 3, 7, 5, 5, 2, 3, 4),
        "Italic": (2, 2, 5, 3, 5, 4, 5, 9, 3, 4),
        "BoldItalic": (2, 2, 7, 3, 6, 5, 5, 9, 3, 4),
    }

    panose_attrs = (
        "bFamilyType",
        "bSerifStyle",
        "bWeight",
        "bProportion",
        "bContrast",
        "bStrokeVariation",
        "bArmStyle",
        "bLetterForm",
        "bMidline",
        "bXHeight",
    )
    ref_panose = [getattr(ref["OS/2"].panose, a, 0) for a in panose_attrs]
    if any(ref_panose):
        for attr in panose_attrs:
            setattr(dst["OS/2"].panose, attr, getattr(ref["OS/2"].panose, attr))
    else:
        defaults = panose_defaults.get(style_name, panose_defaults["Regular"])
        for attr, val in zip(panose_attrs, defaults):
            setattr(dst["OS/2"].panose, attr, val)

    # 4. Code page ranges
    dst["OS/2"].ulCodePageRange1 = ref["OS/2"].ulCodePageRange1
    dst["OS/2"].ulCodePageRange2 = ref["OS/2"].ulCodePageRange2

    # 5. Maintain fsType = 0x0004 (Preview & Print embedding)
    dst["OS/2"].fsType = 0x0004

    # 6. Remove obsolete HP printer table PCLT if present
    if "PCLT" in dst:
        del dst["PCLT"]

    # 7. Recalculate Unicode ranges and explicitly clear Bit 48 (CJK Symbols and Punctuation)
    dst["OS/2"].recalcUnicodeRanges(dst)
    dst["OS/2"].ulUnicodeRange2 &= ~(1 << 16)

    # 8. Recalculate average character width
    dst["OS/2"].recalcAvgCharWidth(dst)


def set_font_names(font: TTFont, style_name: str, version: str = "1.000") -> None:
    """Set font naming metadata to 'Nimbus Match' with specified version."""
    family = "Nimbus Match"

    style_str_map = {
        "Regular": ("Regular", "Regular"),
        "Bold": ("Bold", "Bold"),
        "Italic": ("Italic", "Italic"),
        "BoldItalic": ("Bold Italic", "BoldItalic"),
    }

    subfamily_user, ps_suffix = style_str_map.get(style_name, (style_name, style_name))
    full_name = f"{family} {subfamily_user}"
    ps_name = f"NimbusMatch-{ps_suffix}"

    target_nids = {1, 2, 3, 4, 5, 6, 16, 17}

    if "name" in font:
        font["name"].names = [
            rec for rec in font["name"].names if rec.nameID not in target_nids
        ]

    # Parse numeric version for head.fontRevision
    rev = 1.0
    try:
        clean_v = version.split("-")[0].strip().lstrip("v")
        parts = clean_v.split(".")
        if len(parts) >= 2:
            rev = float(f"{parts[0]}.{parts[1]}")
        else:
            rev = float(parts[0])
    except (ValueError, IndexError):
        rev = 1.0
    font["head"].fontRevision = rev

    for nid, text in (
        (1, family),  # Font Family
        (2, subfamily_user),  # Font Subfamily
        (3, f"{version};{ps_name}"),  # Unique ID
        (4, full_name),  # Full Name
        (
            5,
            f"Version {version}; Nimbus Match Times New Roman metric compatible font",
        ),  # Version
        (6, ps_name),  # PostScript Name
        (16, family),  # Preferred Family
        (17, subfamily_user),  # Preferred Subfamily
    ):
        font["name"].setName(text, nid, 3, 1, 0x409)
        try:
            font["name"].setName(text, nid, 1, 0, 0)
        except (KeyError, ValueError, AttributeError):
            pass

    if "CFF " in font:
        try:
            font["CFF "].cff.topDictIndex[0].version = str(version)
        except Exception:
            pass


def build_single_style(
    nimbus_path: str | Path,
    ref_path: str | Path,
    out_path: str | Path,
    style_name: str,
    version: str = "1.000",
) -> None:
    """Process a single font style (Regular, Bold, Italic, BoldItalic)."""
    nimbus_path = Path(nimbus_path)
    ref_path = Path(ref_path)
    out_path = Path(out_path)

    nimbus = TTFont(nimbus_path)
    reference = TTFont(ref_path)

    old_upem = nimbus["head"].unitsPerEm
    target_upem = reference["head"].unitsPerEm
    # Reset TopDict.defaults to standard 1000 UPEM default [0.001, 0, 0, 0.001, 0, 0]
    # to avoid state leakage from scale_upem in-place mutation across iterations
    TopDict.defaults["FontMatrix"] = [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]

    if "CFF " in nimbus:
        # Explicitly assign a fresh instance list so scale_upem does not mutate TopDict.defaults
        nimbus["CFF "].cff.topDictIndex[0].FontMatrix = [
            1.0 / old_upem,
            0.0,
            0.0,
            1.0 / old_upem,
            0.0,
            0.0,
        ]

    scale_upem(nimbus, target_upem)
    replace_rounded_cff_with_exact_scaled_cff(
        nimbus, str(nimbus_path), old_upem, target_upem
    )

    pairs, skipped = build_kerning(nimbus, reference)
    liga_removed = remove_feature(nimbus, "GSUB", "liga")
    advances_changed, total_shared = copy_all_shared_advances(nimbus, reference)
    copy_metrics_and_os2_metadata(nimbus, reference, style_name=style_name)
    set_font_names(nimbus, style_name, version=version)

    # Ensure TopDict.defaults is [0.001, 0, 0, 0.001, 0, 0] before saving so DictCompiler
    # serializes FontMatrix [1/2048, 0, 0, 1/2048, 0, 0] into the binary CFF table
    TopDict.defaults["FontMatrix"] = [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    nimbus.save(out_path)
    TTFont(out_path).close()

    print(f"[{style_name}] Successfully built {out_path.name}")
    print(f"  UPEM: {old_upem} -> {target_upem}")
    print(f"  Version: {version} (fontRevision: {nimbus['head'].fontRevision:.2f})")
    print(f"  Shared codepoints: {total_shared}, advances updated: {advances_changed}")
    print(f"  Kerning pairs: {len(pairs)} installed, {skipped} skipped")
    print(f"  GSUB liga features removed: {liga_removed}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build Nimbus Match fonts")
    ap.add_argument("--nimbus", required=True, help="Input Nimbus OTF path")
    ap.add_argument(
        "--reference",
        required=True,
        help="Input Tinos or reference TTF font path",
    )
    ap.add_argument(
        "--style",
        required=True,
        choices=["Regular", "Bold", "Italic", "BoldItalic"],
        help="Style name",
    )
    ap.add_argument("--out", required=True, help="Output OTF file path")
    ap.add_argument("--version", default="1.000", help="Font version string")
    args = ap.parse_args()

    build_single_style(
        args.nimbus, args.reference, args.out, args.style, version=args.version
    )


if __name__ == "__main__":
    main()
