#!/usr/bin/env python3
"""
Generate comparison image for Nimbus Match font family vs Times New Roman reference.
Includes overlapped rendering for checking layout metrics and glyph outlines.

Covers:
  - Styles: Regular, Bold, Italic, Bold Italic
  - Scripts: Latin (A-Z, a-z, 0-9), Greek, Cyrillic, Wide Punctuation & Symbols
  - Reference: Times New Roman (system font on Windows/macOS) with Liberation Serif fallback
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

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
        ["times.ttf", "LiberationSerif-Regular.ttf"],
    ),
    (
        "Bold",
        "NimbusMatch-Bold.otf",
        ["timesbd.ttf", "LiberationSerif-Bold.ttf"],
    ),
    (
        "Italic",
        "NimbusMatch-Italic.otf",
        ["timesi.ttf", "LiberationSerif-Italic.ttf"],
    ),
    (
        "Bold Italic",
        "NimbusMatch-BoldItalic.otf",
        ["timesbi.ttf", "LiberationSerif-BoldItalic.ttf"],
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
            return ImageFont.load_default()


def find_ref_font_path(candidates: list[str], fonts_dir: Path) -> tuple[Path, str]:
    """Locate reference font (Times New Roman on Windows/macOS or Liberation Serif fallback)."""
    search_dirs = [
        Path(r"C:\Windows\Fonts"),
        Path("/System/Library/Fonts/Supplemental"),
        Path("/System/Library/Fonts"),
        Path("/Library/Fonts"),
    ]

    for sdir in search_dirs:
        if sdir.exists():
            for cand in candidates:
                if (sdir / cand).exists():
                    return sdir / cand, "Times New Roman"
                if "times.ttf" in cand and (sdir / "Times New Roman.ttf").exists():
                    return sdir / "Times New Roman.ttf", "Times New Roman"
                if (
                    "timesbd.ttf" in cand
                    and (sdir / "Times New Roman Bold.ttf").exists()
                ):
                    return sdir / "Times New Roman Bold.ttf", "Times New Roman"
                if (
                    "timesi.ttf" in cand
                    and (sdir / "Times New Roman Italic.ttf").exists()
                ):
                    return sdir / "Times New Roman Italic.ttf", "Times New Roman"
                if (
                    "timesbi.ttf" in cand
                    and (sdir / "Times New Roman Bold Italic.ttf").exists()
                ):
                    return sdir / "Times New Roman Bold Italic.ttf", "Times New Roman"

    for cand in candidates:
        if (fonts_dir / cand).exists():
            return fonts_dir / cand, "Liberation Serif"

    raise FileNotFoundError(
        f"Could not find reference font from candidates {candidates}"
    )


def generate_comparison_image(
    fonts_dir: str | Path,
    out_file: str | Path,
    style_filter: str | None = None,
) -> None:
    fonts_dir = Path(fonts_dir)
    out_file = Path(out_file)

    width = 1750
    padding = 30
    line_gap = 32
    sample_font_size = 23

    label_font_title = load_ui_font(28)
    label_font_style = load_ui_font(22)
    label_font_script = load_ui_font(16)
    label_font_tag = load_ui_font(13)

    target_styles = STYLES
    if style_filter:
        target_styles = [s for s in STYLES if s[0].lower() == style_filter.lower()]
        if not target_styles:
            raise ValueError(f"Style '{style_filter}' not found in {STYLES}")

    height = 140 + len(target_styles) * (60 + len(TEST_SAMPLES) * 160) + 200

    img = Image.new("RGB", (width, height), color=(248, 249, 250))
    draw = ImageDraw.Draw(img)

    draw.rectangle([(0, 0), (width, 100)], fill=(20, 26, 38))
    draw.text(
        (padding, 20),
        "Nimbus Match vs Times New Roman — Visual Overlap Comparison",
        fill=(255, 255, 255),
        font=label_font_title,
    )
    draw.text(
        (padding, 60),
        "Red = Reference Font (Times New Roman / Liberation Serif) | Blue = Nimbus Match",
        fill=(175, 190, 210),
        font=label_font_script,
    )

    y = 120

    for style_title, nimbus_filename, ref_candidates in target_styles:
        nimbus_path = fonts_dir / nimbus_filename
        if not nimbus_path.exists():
            print(f"Warning: Skipping {style_title} (missing {nimbus_filename})")
            continue

        try:
            ref_path, ref_name = find_ref_font_path(ref_candidates, fonts_dir)
        except FileNotFoundError as e:
            print(f"Warning: Skipping {style_title} ({e})")
            continue

        font_nimbus = ImageFont.truetype(str(nimbus_path), sample_font_size)
        font_ref = ImageFont.truetype(str(ref_path), sample_font_size)

        draw.rectangle([(padding, y), (width - padding, y + 36)], fill=(225, 232, 242))
        draw.text(
            (padding + 15, y + 6),
            f"Style: {style_title} (Reference: {ref_name})",
            fill=(15, 30, 55),
            font=label_font_style,
        )
        y += 48

        for script_name, sample_text in TEST_SAMPLES:
            draw.text(
                (padding + 15, y),
                f"• {script_name}",
                fill=(70, 80, 95),
                font=label_font_script,
            )
            y += 24

            x_text = padding + 260

            bbox_ref = draw.textbbox((x_text, y), sample_text, font=font_ref)
            bbox_nim = draw.textbbox((x_text, y), sample_text, font=font_nimbus)

            draw.text(
                (padding + 15, y + 2),
                f"Overlap (Red: {ref_name}, Blue: Nimbus)",
                fill=(110, 30, 140),
                font=label_font_tag,
            )

            rgba_layer = Image.new("RGBA", (width, height), color=(0, 0, 0, 0))
            rgba_draw = ImageDraw.Draw(rgba_layer)

            rgba_draw.text(
                (x_text, y), sample_text, fill=(220, 20, 20, 140), font=font_ref
            )
            rgba_draw.text(
                (x_text, y), sample_text, fill=(10, 100, 230, 140), font=font_nimbus
            )

            img.paste(rgba_layer, (0, 0), rgba_layer)
            y += line_gap

            ref_w = bbox_ref[2] - bbox_ref[0]
            nim_w = bbox_nim[2] - bbox_nim[0]
            diff_w = abs(ref_w - nim_w)

            indicator_text = f"Metric Match: Ref Width = {ref_w}px | Nimbus Match Width = {nim_w}px (Δ = {diff_w}px)"
            draw.text(
                (x_text, y), indicator_text, fill=(90, 105, 120), font=label_font_tag
            )

            draw.line(
                [(padding + 15, y + 18), (width - padding - 15, y + 18)],
                fill=(230, 235, 240),
                width=1,
            )
            y += 26

        y += 20

    final_height = y + 30
    img_cropped = img.crop((0, 0, width, final_height))
    out_file.parent.mkdir(parents=True, exist_ok=True)
    img_cropped.save(out_file)
    print(
        f"Successfully generated comparison image ({width}x{final_height}px): {out_file}"
    )


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
    args = ap.parse_args()

    generate_comparison_image(args.fonts_dir, args.out, style_filter=args.style)


if __name__ == "__main__":
    main()
