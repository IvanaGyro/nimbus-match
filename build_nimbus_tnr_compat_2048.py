#!/usr/bin/env python3
"""
Build a Nimbus Roman prototype with Times New Roman-compatible Latin text
metrics using only free fonts as input.

Inputs:
  - NimbusRoman-Regular.otf (URW Base35)
  - LiberationSerif-Regular.ttf (metric reference)

The script does NOT read or copy anything from Times New Roman.

Key steps:
  1. Rescale Nimbus from 1000 UPEM to Liberation's 2048 UPEM.
  2. Rebuild Nimbus CFF charstrings with exact 2.048 scaling using Type 2
     fixed-point operands, avoiding the outline rounding introduced by the
     stock fontTools scaleUpem helper.
  3. Copy Liberation-compatible advances for shared U+0020..U+024F glyphs.
  4. Replace Nimbus kerning with Liberation's kerning, emitting both a modern
     OpenType GPOS kern feature and a legacy kern table.
  5. Remove Nimbus's default liga feature because its fi/fl/ff ligatures alter
     advances relative to Liberation/TNR-compatible shaping.
  6. Match Liberation vertical metrics.

Requires:
  pip install fonttools
"""

from __future__ import annotations

import argparse
from pathlib import Path

from fontTools.cffLib import specializer as cffSpecializer
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.scaleUpem import scale_upem
from fontTools.ttLib.tables import _k_e_r_n


def _scale_cff_args_exact(args, factor: float) -> None:
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

    # Nimbus Roman Regular currently uses one private dict. Scale the CFF hint
    # data with fixed-point precision as well.
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
    if "kern" not in ref or not ref["kern"].kernTables:
        raise RuntimeError("Reference font has no legacy kern table")

    ref_rev = reverse_cmap(ref)
    dst_cmap = dst.getBestCmap() or {}
    dst_glyphs = set(dst.getGlyphOrder())

    pairs: dict[tuple[str, str], int] = {}
    skipped = 0
    for (left, right), value in ref["kern"].kernTables[0].kernTable.items():
        dl = map_reference_glyph(left, ref_rev, dst_cmap, dst_glyphs)
        dr = map_reference_glyph(right, ref_rev, dst_cmap, dst_glyphs)
        if not dl or not dr:
            skipped += 1
            continue
        pairs[(dl, dr)] = int(value)

    # Legacy kern table.
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

    # Modern GPOS kern feature. Nimbus's original GPOS is kern-only, so it is
    # safe for this targeted prototype to replace it.
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


def copy_latin_advances(dst: TTFont, ref: TTFont) -> int:
    dst_cmap = dst.getBestCmap() or {}
    ref_cmap = ref.getBestCmap() or {}
    changed = 0
    seen: set[str] = set()

    for cp in range(0x20, 0x250):
        if cp not in dst_cmap or cp not in ref_cmap:
            continue
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

    return changed


def copy_vertical_metrics(dst: TTFont, ref: TTFont) -> None:
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


def set_name(font: TTFont, name_id: int, text: str) -> None:
    font["name"].setName(text, name_id, 3, 1, 0x409)
    try:
        font["name"].setName(text, name_id, 1, 0, 0)
    except Exception:
        pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nimbus", required=True)
    ap.add_argument("--reference", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    nimbus = TTFont(args.nimbus)
    reference = TTFont(args.reference)

    old_upem = nimbus["head"].unitsPerEm
    target_upem = reference["head"].unitsPerEm
    if old_upem == target_upem:
        raise RuntimeError(
            "Nimbus is already at the reference UPEM; this prototype expects a rescale"
        )

    scale_upem(nimbus, target_upem)
    replace_rounded_cff_with_exact_scaled_cff(
        nimbus, args.nimbus, old_upem, target_upem
    )

    pairs, skipped = build_kerning(nimbus, reference)
    liga_removed = remove_feature(nimbus, "GSUB", "liga")
    advances_changed = copy_latin_advances(nimbus, reference)
    copy_vertical_metrics(nimbus, reference)

    family = "Nimbus Roman TNR Compat 2048 Prototype"
    for nid, text in (
        (1, family),
        (2, "Regular"),
        (4, family),
        (6, "NimbusRomanTNRCompat2048Prototype-Regular"),
        (16, family),
        (17, "Regular"),
        (5, "Version 0.3; 2048-UPM TNR-compatible metric prototype"),
        (3, "Version 0.3; NimbusRomanTNRCompat2048Prototype-Regular"),
    ):
        set_name(nimbus, nid, text)

    out = Path(args.out)
    nimbus.save(out)
    TTFont(out).close()  # structural sanity check

    print(f"saved: {out}")
    print(f"UPEM: {old_upem} -> {target_upem}")
    print(f"kerning pairs installed: {len(pairs)}")
    print(f"kerning pairs skipped: {skipped}")
    print(f"GSUB liga feature records removed: {liga_removed}")
    print(f"Latin advances changed after rescaling: {advances_changed}")


if __name__ == "__main__":
    main()
