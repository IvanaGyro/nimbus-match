#!/usr/bin/env python3
"""
Build Nimbus Match font family (Regular, Bold, Italic, Bold Italic)
with Times New Roman / Liberation Serif layout metrics.

Inputs:
  - Nimbus Roman OTF font files (URW Base35)
  - Liberation Serif TTF font files (metric reference)

The script does NOT read or copy anything from proprietary Times New Roman.
All font binaries are processed dynamically.
"""

from __future__ import annotations

import argparse
from pathlib import Path

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

    stop.FontMatrix = [x / factor for x in otop.FontMatrix]

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


def build_kerning(dst: TTFont, ref: TTFont) -> tuple[dict[tuple[str, str], int], int]:
    """Transfer kerning pairs from reference to destination font."""
    if "kern" not in ref or not ref["kern"].kernTables:
        raise RuntimeError("Reference font has no legacy kern table")

    ref_rev = reverse_cmap(ref)
    dst_cmap = dst.getBestCmap() or {}
    dst_glyphs = set(dst.getGlyphOrder())

    pairs: dict[tuple[str, str], int] = {}
    skipped = 0
    for (left, right), val in ref["kern"].kernTables[0].kernTable.items():
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


def copy_vertical_metrics(dst: TTFont, ref: TTFont) -> None:
    """Copy vertical metrics from reference font to destination font."""
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


def set_font_names(font: TTFont, style_name: str) -> None:
    """Set font naming metadata to 'Nimbus Match'."""
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

    for nid, text in (
        (1, family),  # Font Family
        (2, subfamily_user),  # Font Subfamily
        (3, f"1.000;{ps_name}"),  # Unique ID
        (4, full_name),  # Full Name
        (
            5,
            "Version 1.000; Nimbus Match Times New Roman metric compatible font",
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


def build_single_style(
    nimbus_path: str | Path,
    ref_path: str | Path,
    out_path: str | Path,
    style_name: str,
) -> None:
    """Process a single font style (Regular, Bold, Italic, BoldItalic)."""
    nimbus_path = Path(nimbus_path)
    ref_path = Path(ref_path)
    out_path = Path(out_path)

    nimbus = TTFont(nimbus_path)
    reference = TTFont(ref_path)

    old_upem = nimbus["head"].unitsPerEm
    target_upem = reference["head"].unitsPerEm
    if old_upem == target_upem:
        raise RuntimeError("Nimbus is already at reference UPEM")

    scale_upem(nimbus, target_upem)
    replace_rounded_cff_with_exact_scaled_cff(
        nimbus, str(nimbus_path), old_upem, target_upem
    )

    pairs, skipped = build_kerning(nimbus, reference)
    liga_removed = remove_feature(nimbus, "GSUB", "liga")
    advances_changed, total_shared = copy_all_shared_advances(nimbus, reference)
    copy_vertical_metrics(nimbus, reference)
    set_font_names(nimbus, style_name)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    nimbus.save(out_path)
    TTFont(out_path).close()

    print(f"[{style_name}] Successfully built {out_path.name}")
    print(f"  UPEM: {old_upem} -> {target_upem}")
    print(f"  Shared codepoints: {total_shared}, advances updated: {advances_changed}")
    print(f"  Kerning pairs: {len(pairs)} installed, {skipped} skipped")
    print(f"  GSUB liga features removed: {liga_removed}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build Nimbus Match fonts")
    ap.add_argument("--nimbus", required=True, help="Input Nimbus OTF path")
    ap.add_argument(
        "--reference",
        required=True,
        help="Input Liberation Serif TTF reference path",
    )
    ap.add_argument(
        "--style",
        required=True,
        choices=["Regular", "Bold", "Italic", "BoldItalic"],
        help="Style name",
    )
    ap.add_argument("--out", required=True, help="Output OTF file path")
    args = ap.parse_args()

    build_single_style(args.nimbus, args.reference, args.out, args.style)


if __name__ == "__main__":
    main()
