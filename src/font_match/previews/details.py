#!/usr/bin/env python3
"""Render Nimbus Match / Times New Roman overlays for supported comparison samples."""

from __future__ import annotations

import argparse
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw

from .comparison import (
    BLUE,
    IMAGE_WIDTH,
    INK,
    PADDING,
    RED,
    STYLES,
    composite_overlay,
    find_ref_font_path,
    load_ui_font,
)
from .render import SUPERSAMPLE, FontRenderer, finish_mask, new_mask

PANEL_SIZE = (IMAGE_WIDTH - 2 * PADDING, 150)
# LibreOffice Writer uses 80% unless its legacy SmallCapsPercentage66 option is set.
# https://github.com/LibreOffice/core/blob/bce0998afefdbc355585ca324285661a2170ba77/sw/source/core/txtnode/fntcap.cxx#L517-L523
SMALL_CAPS_SCALE = 0.8


def validate_font_pair(nimbus: TTFont, reference: TTFont) -> None:
    for font, expected in ((nimbus, "Nimbus Match"), (reference, "Times New Roman")):
        actual = font["name"].getBestFamilyName()
        if actual != expected:
            raise ValueError(f"Expected {expected}, got {actual}")
        if font["name"].getBestSubFamilyName() != "Regular":
            raise ValueError("The detail comparison requires Regular fonts")
    if nimbus["head"].unitsPerEm != reference["head"].unitsPerEm:
        raise ValueError("Comparison metrics require matching units per em")


def glyph_advance(font: TTFont, codepoint: int) -> int | None:
    glyph = (font.getBestCmap() or {}).get(codepoint)
    return None if glyph is None else font["hmtx"][glyph][0]


def strike_mask(renderer: FontRenderer, font: TTFont) -> Image.Image:
    mask = new_mask(PANEL_SIZE)
    size, baseline, start = 96, 108, 10
    width = renderer.draw(mask, "Canceled", (start, baseline), size)
    os2 = font["OS/2"]
    y = baseline - size * os2.yStrikeoutPosition / renderer.upem
    ImageDraw.Draw(mask).line(
        tuple(round(coord * SUPERSAMPLE) for coord in (start, y, start + width, y)),
        fill=255,
        width=max(1, round(size * os2.yStrikeoutSize / renderer.upem * SUPERSAMPLE)),
    )
    return finish_mask(mask)


def script_mask(renderer: FontRenderer, font: TTFont, superscript: bool) -> Image.Image:
    """Apply the font's OS/2 sub/superscript sizes and offsets to ordinary digits."""
    mask = new_mask(PANEL_SIZE)
    size, baseline = 86, 105
    prefix = "ySuperscript" if superscript else "ySubscript"
    os2 = font["OS/2"]
    y_scale = getattr(os2, prefix + "YSize") / renderer.upem
    x_scale = getattr(os2, prefix + "XSize") / renderer.upem
    dx = size * getattr(os2, prefix + "XOffset") / renderer.upem
    dy = size * getattr(os2, prefix + "YOffset") / renderer.upem
    dy = -dy if superscript else dy
    parts = (
        [("x", False), ("2", True), (" + y", False), ("2", True)]
        if superscript
        else [("H", False), ("2", True), ("O + CO", False), ("2", True)]
    )
    x = 10.0
    for text, is_script in parts:
        if is_script:
            x += renderer.draw(
                mask,
                text,
                (x + dx, baseline + dy),
                size * y_scale,
                x_scale=x_scale / y_scale,
            )
        else:
            x += renderer.draw(mask, text, (x, baseline), size)
    return finish_mask(mask)


def feature_mask(renderer: FontRenderer, text: str, tag: str) -> Image.Image:
    mask = new_mask(PANEL_SIZE)
    size = 84 if tag == "cpsp" else 104
    renderer.draw(mask, text, (10, 112), size, {tag: True})
    return finish_mask(mask)


def synthetic_smallcaps_mask(renderer: FontRenderer) -> Image.Image:
    """Mimic LibreOffice's synthetic small caps for the fixed 'Roman' specimen."""
    mask = new_mask(PANEL_SIZE)
    size, baseline = 104, 112
    features = {"smcp": False, "c2sc": False}
    advance = renderer.draw(mask, "R", (10, baseline), size, features)
    renderer.draw(
        mask, "OMAN", (10 + advance, baseline), size * SMALL_CAPS_SCALE, features
    )
    return finish_mask(mask)


def smallcaps_masks(reference: FontRenderer, nimbus: FontRenderer) -> list[Image.Image]:
    """Compare TNR's real small caps with Nimbus Match's configured synthetic fallback."""
    glyphs = [
        [glyph.glyph_id for glyph in reference.shape("Roman", {"smcp": enabled})]
        for enabled in (False, True)
    ]
    if glyphs[0] == glyphs[1]:
        raise ValueError(
            "The TNR reference must provide native smcp glyphs for 'Roman'"
        )
    return [
        feature_mask(reference, "Roman", "smcp"),
        synthetic_smallcaps_mask(nimbus),
    ]


def generate_font_details(fonts_dir: Path, out_file: Path) -> None:
    nimbus_path = fonts_dir / "NimbusMatch-Regular.otf"
    reference_path, _ = find_ref_font_path(
        STYLES[0][2], fonts_dir, require_times_new_roman=True
    )
    with TTFont(nimbus_path) as nimbus, TTFont(reference_path) as reference:
        validate_font_pair(nimbus, reference)
        fonts = [reference, nimbus]
        renderers = [FontRenderer(path) for path in (reference_path, nimbus_path)]
        panels = []
        panels.append(
            (
                "1. Strikethrough",
                [
                    strike_mask(renderer, font)
                    for renderer, font in zip(renderers, fonts)
                ],
                f"Position: TNR {reference['OS/2'].yStrikeoutPosition} · Nimbus Match {nimbus['OS/2'].yStrikeoutPosition}",
            )
        )
        for title, superscript, attr, label in (
            ("2. Subscripts", False, "ySubscriptYOffset", "Drop"),
            ("3. Superscripts", True, "ySuperscriptYOffset", "Rise"),
        ):
            panels.append(
                (
                    title,
                    [
                        script_mask(renderer, font, superscript)
                        for renderer, font in zip(renderers, fonts)
                    ],
                    f"{label}: TNR {getattr(reference['OS/2'], attr)} · Nimbus Match {getattr(nimbus['OS/2'], attr)}",
                )
            )

        added = [
            renderer.advance("CAPITALS", {"cpsp": True})
            - renderer.advance("CAPITALS", {"cpsp": False})
            for renderer in renderers
        ]
        panels.append(
            (
                "4. Capital spacing · cpsp",
                [feature_mask(renderer, "CAPITALS", "cpsp") for renderer in renderers],
                f"Added: TNR {added[0]:+d} · Nimbus Match {added[1]:+d}",
            )
        )
        panels.append(
            (
                "5. Small caps · LibreOffice",
                smallcaps_masks(*renderers),
                "TNR: smcp · Nimbus Match: scaled (80%)",
            )
        )

        height = 240 + len(panels) * 280
        image = Image.new("RGB", (IMAGE_WIDTH, height), "white")
        draw = ImageDraw.Draw(image)
        draw.text(
            (PADDING, 24), "Regular · feature overlays", fill=INK, font=load_ui_font(34)
        )
        draw.text(
            (PADDING, 74), "Times New Roman (TNR)", fill=RED, font=load_ui_font(32)
        )
        draw.text((PADDING, 116), "Nimbus Match", fill=BLUE, font=load_ui_font(32))
        draw.text((PADDING, 164), "Gray = overlap", fill=INK, font=load_ui_font(30))
        for index, (title, masks, caption) in enumerate(panels):
            y = 220 + index * 280
            draw.rectangle((0, y, IMAGE_WIDTH, y + 48), fill=(235, 240, 247))
            draw.text((PADDING, y + 5), title, fill=INK, font=load_ui_font(32))
            image.paste(composite_overlay(*masks), (PADDING, y + 54))
            caption_font = load_ui_font(30)
            if caption_font.getlength(caption) > PANEL_SIZE[0]:
                raise ValueError(f"Comparison caption exceeds its panel: {caption!r}")
            draw.text((PADDING, y + 218), caption, fill=INK, font=caption_font)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        image.save(out_file)
        print(f"Generated font details ({IMAGE_WIDTH}x{height}px): {out_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fonts-dir", type=Path, default=Path("dist"))
    parser.add_argument(
        "--out", type=Path, default=Path("nimbus_match_tnr_details.png")
    )
    args = parser.parse_args()
    generate_font_details(args.fonts_dir, args.out)


if __name__ == "__main__":
    main()
