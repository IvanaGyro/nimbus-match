"""Measured feature gaps and metric differences against an explicit local TNR."""

import json
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw

from .comparison import BLUE, INK, RED, composite_overlay, load_ui_font
from .details import feature_mask, script_mask, strike_mask, synthetic_smallcaps_mask
from .render import FontRenderer, finish_mask, new_mask


def feature_tags(font):
    return {
        r.FeatureTag
        for tag in ("GSUB", "GPOS")
        if tag in font and font[tag].table.FeatureList
        for r in font[tag].table.FeatureList.FeatureRecord
    }


def generate(match_path: Path, reference_path: Path, tinos_path: Path, output: Path):
    with (
        TTFont(match_path) as match,
        TTFont(reference_path) as tnr,
        TTFont(tinos_path) as tinos,
    ):
        if tnr["name"].getBestFamilyName() != "Times New Roman":
            raise ValueError("An actual local Times New Roman font is required")
        if tinos["name"].getBestFamilyName() != "Tinos":
            raise ValueError("The diagnostic metrics reference must be Tinos")
        if any(f["head"].unitsPerEm != 2048 for f in (match, tnr, tinos)):
            raise ValueError("Comparison requires 2048 UPEM fonts")
        if any(
            f["name"].getBestSubFamilyName() != "Regular" for f in (match, tnr, tinos)
        ):
            raise ValueError("The difference comparison requires Regular fonts")
        name = match["name"].getBestFamilyName()
        renderers = [FontRenderer(p) for p in (reference_path, match_path)]
        missing = sorted(feature_tags(tnr) - feature_tags(match))
        common = set(match.getBestCmap()) & set(tnr.getBestCmap())
        panels = []

        def supported(text):
            return all(ord(c) in common for c in text)

        def values(attr):
            return [getattr(f["OS/2"], attr) for f in (tnr, tinos, match)]

        def caption(vals):
            return f"TNR {vals[0]}   Tinos {vals[1]}   Match {vals[2]}"

        metrics = {}
        for attr in (
            "yStrikeoutPosition",
            "yStrikeoutSize",
            "ySubscriptXSize",
            "ySubscriptYSize",
            "ySubscriptXOffset",
            "ySubscriptYOffset",
            "ySuperscriptXSize",
            "ySuperscriptYSize",
            "ySuperscriptXOffset",
            "ySuperscriptYOffset",
        ):
            v = values(attr)
            if len(set(v)) > 1:
                metrics[attr] = v
        if any(k.startswith("yStrikeout") for k in metrics) and supported("Canceled"):
            panels.append(
                (
                    "Strikethrough position",
                    [strike_mask(r, f) for r, f in zip(renderers, (tnr, match))],
                    caption(values("yStrikeoutPosition")),
                )
            )
        for title, is_super, attr, text in [
            ("Subscript drop", False, "ySubscriptYOffset", "H2O + CO2"),
            ("Superscript rise", True, "ySuperscriptYOffset", "x2 + y2"),
        ]:
            if supported(text) and any(
                k.startswith("ySuperscript" if is_super else "ySubscript")
                for k in metrics
            ):
                panels.append(
                    (
                        title,
                        [
                            script_mask(r, f, is_super)
                            for r, f in zip(renderers, (tnr, match))
                        ],
                        caption(values(attr)),
                    )
                )
        if supported("CAPITALS"):
            added = [
                r.advance("CAPITALS", {"cpsp": True})
                - r.advance("CAPITALS", {"cpsp": False})
                for r in renderers
            ]
            if added[0] != added[1]:
                panels.append(
                    (
                        "Capital spacing · cpsp",
                        [feature_mask(r, "CAPITALS", "cpsp") for r in renderers],
                        f"Added width: TNR {added[0]:+d}   Match {added[1]:+d}",
                    )
                )
        if supported("Roman"):
            native = []
            for r in renderers:
                native.append(
                    [g.glyph_id for g in r.shape("Roman", {"smcp": True})]
                    != [g.glyph_id for g in r.shape("Roman", {"smcp": False})]
                )
            if native[0]:
                masks = [
                    feature_mask(renderers[0], "Roman", "smcp"),
                    feature_mask(renderers[1], "Roman", "smcp")
                    if native[1]
                    else synthetic_smallcaps_mask(renderers[1]),
                ]
                panels.append(
                    (
                        "Small caps · native metrics"
                        if native[1]
                        else "Small caps · missing native smcp",
                        masks,
                        f"Native widths: TNR {renderers[0].advance('Roman', {'smcp': True})}   Match {renderers[1].advance('Roman', {'smcp': True})}"
                        if native[1]
                        else "TNR native · Match uppercase at 80%",
                    )
                )
        for tag, sample in [
            ("liga", "ffi"),
            ("onum", "0123"),
            ("numr", "123"),
            ("dnom", "123"),
        ]:
            if tag in missing and supported(sample):
                before = renderers[0].shape(sample, {tag: False})
                enabled = renderers[0].shape(sample, {tag: True})
                if before != enabled:
                    panels.append(
                        (
                            f"Missing feature · {tag}",
                            [feature_mask(r, sample, tag) for r in renderers],
                            f"{tag} enabled in both · only TNR responds",
                        )
                    )
        differences = []
        for cp in sorted(common):
            widths = []
            for font in (tnr, tinos, match):
                glyph = font.getBestCmap().get(cp)
                widths.append(font["hmtx"][glyph][0] if glyph else None)
            if widths[0] != widths[2]:
                differences.append({"codepoint": f"U+{cp:04X}", "widths": widths})
        for row in sorted(
            differences,
            key=lambda x: abs(x["widths"][0] - x["widths"][2]),
            reverse=True,
        )[:2]:
            text = chr(int(row["codepoint"][2:], 16))  # noqa: FURB166
            if text.isspace():
                continue
            masks = []
            for r in renderers:
                mask = new_mask((584, 150))
                r.draw(mask, text, (10, 112), 104)
                masks.append(finish_mask(mask))
            panels.append(
                (
                    f"Advance width · {row['codepoint']}",
                    masks,
                    caption([v if v is not None else "absent" for v in row["widths"]]),
                )
            )
        tags = "TNR-only features: " + (", ".join(missing) or "none")
        # Wrap by measured pixel width, keeping labels legible.
        lines = [""]
        for word in tags.split():
            if load_ui_font(20).getlength(lines[-1] + word) > 584:
                lines.append("")
            lines[-1] += word + " "
        header = max(245, 184 + len(lines) * 24 + 24)
        image = Image.new("RGB", (640, header + len(panels) * 240 + 30), "white")
        draw = ImageDraw.Draw(image)
        draw.text((28, 18), name + " · differences", font=load_ui_font(30), fill=INK)
        draw.text((28, 64), "Times New Roman", font=load_ui_font(27), fill=RED)
        draw.text((28, 104), name, font=load_ui_font(27), fill=BLUE)
        draw.text(
            (28, 145),
            "Gray = overlap · units = 1/2048 em",
            font=load_ui_font(22),
            fill=INK,
        )
        for i, line in enumerate(lines):
            draw.text((28, 184 + i * 24), line, font=load_ui_font(20), fill=INK)
        for i, (title, masks, note) in enumerate(panels):
            y = header + i * 240
            draw.rectangle((0, y, 640, y + 40), fill=(235, 240, 247))
            draw.text((28, y + 4), title, font=load_ui_font(26), fill=INK)
            image.paste(composite_overlay(*masks), (28, y + 44))
            draw.text((28, y + 202), note, font=load_ui_font(20), fill=INK)
        output.parent.mkdir(parents=True, exist_ok=True)
        image.save(output)
        report = {
            "family": name,
            "reference_version": tnr["name"].getDebugName(5),
            "missing_features": missing,
            "metric_order": ["TNR", "Tinos", name],
            "metrics": metrics,
            "advance_differences": differences,
        }
        output.with_suffix(".json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
