#!/usr/bin/env python3
"""
Generate comparison image for Nimbus Match font family vs Times New Roman reference.
Includes overlapped rendering for checking layout metrics and glyph outlines.

Covers:
  - Styles: Regular, Bold, Italic, Bold Italic
  - Scripts: Latin (A-Z, a-z, 0-9), Greek, Cyrillic, Wide Punctuation & Symbols
  - Reference: Times New Roman (system font on Windows/macOS) with Tinos / Liberation Serif fallback
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image, ImageChops, ImageDraw, ImageFont

IMAGE_WIDTH = 640
PADDING = 28
SAMPLE_SIZE = 48
RED = (220, 45, 55)
BLUE = (15, 110, 220)
OVERLAP = (188, 194, 202)
INK = (30, 40, 55)


def font_family(path: Path) -> str:
    with TTFont(path) as font:
        return font["name"].getBestFamilyName() or path.stem


TEST_SAMPLES = [
    (
        "Latin Alphabet & Digits",
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ  abcdefghijklmnopqrstuvwxyz  0123456789",
    ),
    (
        "Greek Alphabet",
        "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ  αβγδεζηθικλμνξοπρστυφχψω  0123456789",
    ),
    (
        "Cyrillic Alphabet",
        "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ  абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
    ),
    (
        "Punctuation / Symbols",
        r"!”#$%&'()*+,-./:;<=>?@[\]^_`{|}~ ¡¢£¤¥§©«®°±²³µ¶·¹º»¼½¾¿–—‘’“”„†‡•…‰′″‹›€№™",
    ),
]

STYLES = [
    (
        "Regular",
        "NimbusMatch-Regular.otf",
        ["times.ttf", "Tinos-Regular.ttf", "LiberationSerif-Regular.ttf"],
    ),
    (
        "Bold",
        "NimbusMatch-Bold.otf",
        ["timesbd.ttf", "Tinos-Bold.ttf", "LiberationSerif-Bold.ttf"],
    ),
    (
        "Italic",
        "NimbusMatch-Italic.otf",
        ["timesi.ttf", "Tinos-Italic.ttf", "LiberationSerif-Italic.ttf"],
    ),
    (
        "Bold Italic",
        "NimbusMatch-BoldItalic.otf",
        ["timesbi.ttf", "Tinos-BoldItalic.ttf", "LiberationSerif-BoldItalic.ttf"],
    ),
]


def load_ui_font(size: int = 16) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    """Load default or system sans font for UI labels."""
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        try:
            return ImageFont.truetype("DejaVuSans.ttf", size)
        except OSError:
            return ImageFont.load_default(size=size)


def find_ref_font_path(
    candidates: list[str], fonts_dir: Path, *, require_times_new_roman: bool = True
) -> tuple[Path, str]:
    """Locate reference font (Times New Roman on Windows/macOS or Tinos / Liberation fallback)."""
    search_dirs = [
        Path(r"C:\Windows\Fonts"),
        Path("/System/Library/Fonts/Supplemental"),
        Path("/System/Library/Fonts"),
        Path("/Library/Fonts"),
    ]

    aliases = {
        "times.ttf": "Times New Roman.ttf",
        "timesbd.ttf": "Times New Roman Bold.ttf",
        "timesi.ttf": "Times New Roman Italic.ttf",
        "timesbi.ttf": "Times New Roman Bold Italic.ttf",
    }
    for sdir in [*search_dirs, fonts_dir]:
        for cand in candidates:
            for filename in dict.fromkeys([cand, aliases.get(cand, cand)]):
                path = sdir / filename
                if not path.is_file():
                    continue
                family = font_family(path)
                if require_times_new_roman and family != "Times New Roman":
                    continue
                return path, family

    raise FileNotFoundError(
        "Times New Roman is required for README comparisons; install it locally."
        if require_times_new_roman
        else f"Could not find reference font from candidates {candidates}"
    )


def wrap_sample(text: str, fonts: list, max_width: int) -> list[str]:
    """Use identical line breaks and allow room for both fonts' ink and advances."""
    lines = []
    line = ""
    for char in text:
        candidate = line + char
        if line and any(
            max(font.getlength(candidate), font.getbbox(candidate)[2]) > max_width
            for font in fonts
        ):
            lines.append(line.rstrip())
            line = char.lstrip()
        else:
            line = candidate
    if line:
        lines.append(line.rstrip())
    return lines


def composite_overlay(
    reference: Image.Image, nimbus: Image.Image, background: Image.Image | None = None
) -> Image.Image:
    """Color shared coverage light gray and exclusive coverage red/blue, symmetrically."""
    shared = ImageChops.darker(reference, nimbus)
    masks = (
        shared,
        ImageChops.subtract(reference, nimbus),
        ImageChops.subtract(nimbus, reference),
    )
    clear = ImageChops.invert(ImageChops.lighter(reference, nimbus))
    background = (
        background
        if background is not None
        else Image.new("RGB", reference.size, "white")
    )
    channels = []
    for channel, base in enumerate(background.split()):
        result = ImageChops.multiply(base, clear)
        for mask, color in zip(masks, (OVERLAP, RED, BLUE)):
            contribution = mask.point(
                [round(value * color[channel] / 255) for value in range(256)]
            )
            result = ImageChops.add(result, contribution)
        channels.append(result)
    return Image.merge("RGB", channels)


def draw_overlay(image: Image.Image, xy: tuple, text: str, fonts: list) -> None:
    bounds = [font.getbbox(text, anchor="ls") for font in fonts]
    top = max(0, math.floor(xy[1] + min(box[1] for box in bounds)))
    bottom = min(image.height, math.ceil(xy[1] + max(box[3] for box in bounds)))
    if top >= bottom:
        return
    region = (0, top, image.width, bottom)
    masks = []
    for font in fonts:
        mask = Image.new("L", (image.width, bottom - top))
        ImageDraw.Draw(mask).text(
            (xy[0], xy[1] - top), text, font=font, fill=255, anchor="ls"
        )
        masks.append(mask)
    image.paste(composite_overlay(*masks, image.crop(region)), (0, top))


def generate_comparison_image(
    fonts_dir: str | Path,
    out_file: str | Path,
    style_filter: str | None = None,
    *,
    require_times_new_roman: bool = True,
) -> None:
    fonts_dir = Path(fonts_dir)
    out_file = Path(out_file)

    target_styles = STYLES
    if style_filter:
        target_styles = [s for s in STYLES if s[0].lower() == style_filter.lower()]
        if not target_styles:
            raise ValueError(f"Style '{style_filter}' not found in {STYLES}")

    panels = []
    for style_title, nimbus_filename, ref_candidates in target_styles:
        nimbus_path = fonts_dir / nimbus_filename
        if not nimbus_path.exists():
            raise FileNotFoundError(nimbus_path)
        if font_family(nimbus_path) != "Nimbus Match":
            raise ValueError(f"Expected a Nimbus Match font: {nimbus_path}")
        ref_path, ref_name = find_ref_font_path(
            ref_candidates, fonts_dir, require_times_new_roman=require_times_new_roman
        )
        fonts = [
            ImageFont.truetype(str(path), SAMPLE_SIZE)
            for path in (ref_path, nimbus_path)
        ]
        with TTFont(nimbus_path) as left, TTFont(ref_path) as right:
            shared = set(left.getBestCmap()) & set(right.getBestCmap())
        samples = []
        for script_name, sample_text in TEST_SAMPLES:
            sample_text = "".join(c for c in sample_text if ord(c) in shared)
            if not sample_text.strip():
                continue
            lines = wrap_sample(sample_text, fonts, IMAGE_WIDTH - 2 * PADDING)
            samples.append((script_name, lines))
        panels.append((style_title, ref_name, fonts, samples))

    height = PADDING + sum(
        200 + sum(66 + 64 * len(lines) for _, lines in samples)
        for _, _, _, samples in panels
    )
    img = Image.new("RGB", (IMAGE_WIDTH, height), "white")
    draw = ImageDraw.Draw(img)
    y = PADDING
    for style_title, ref_name, fonts, samples in panels:
        draw.text((PADDING, y), style_title, fill=INK, font=load_ui_font(36))
        draw.text((PADDING, y + 48), ref_name, fill=RED, font=load_ui_font(32))
        draw.text((PADDING, y + 88), "Nimbus Match", fill=BLUE, font=load_ui_font(32))
        draw.text((PADDING, y + 132), "Gray = overlap", fill=INK, font=load_ui_font(30))
        y += 200
        for script_name, lines in samples:
            draw.rectangle((0, y, IMAGE_WIDTH, y + 46), fill=(235, 240, 247))
            draw.text((PADDING, y + 4), script_name, fill=INK, font=load_ui_font(32))
            y += 66
            for line in lines:
                draw_overlay(img, (PADDING, y + 44), line, fonts)
                y += 64

    out_file.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_file)
    print(f"Generated comparison ({IMAGE_WIDTH}x{height}px): {out_file}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate Nimbus Match comparison image")
    ap.add_argument(
        "--fonts-dir", required=True, help="Directory containing OTF/TTF fonts"
    )
    ap.add_argument(
        "--out", default="nimbus_match_comparison.png", help="Output PNG path"
    )
    ap.add_argument(
        "--style", default=None, help="Specific style to render (e.g. Regular)"
    )
    ap.add_argument(
        "--require-times-new-roman",
        action="store_true",
        default=True,
        help="Require a real local Times New Roman font (always enabled)",
    )
    args = ap.parse_args()

    generate_comparison_image(
        args.fonts_dir,
        args.out,
        style_filter=args.style,
        require_times_new_roman=args.require_times_new_roman,
    )


if __name__ == "__main__":
    main()
