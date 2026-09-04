#!/usr/bin/env python3
"""
Generate comparison image for Nimbus Match font family vs Times New Roman reference.
Includes overlapped rendering for checking layout metrics and glyph outlines.

Covers:
  - Styles: Regular, Bold, Italic, Bold Italic
  - Scripts: Latin (A-Z, a-z, 0-9), Greek, Cyrillic, Wide Punctuation & Symbols
  - Reference: Times New Roman (system font on Windows) with Liberation Serif fallback
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
    ("Latin Text", "The quick brown fox jumps over the lazy dog."),
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
    ("Bold", "NimbusMatch-Bold.otf", ["timesbd.ttf", "LiberationSerif-Bold.ttf"]),
    ("Italic", "NimbusMatch-Italic.otf", ["timesi.ttf", "LiberationSerif-Italic.ttf"]),
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
    except Exception:
        try:
            return ImageFont.truetype("DejaVuSans.ttf", size)
        except Exception:
            return ImageFont.load_default()


def find_ref_font_path(candidates: list[str], fonts_dir: Path) -> tuple[Path, str]:
    """Locate reference font (Times New Roman on Windows/macOS or Liberation Serif fallback)."""
    search_dirs = [
        Path(r"C:\Windows\Fonts"),
        Path("/System/Library/Fonts/Supplemental"),
        Path("/System/Library/Fonts"),
        Path("/Library/Fonts"),
    ]

    # Check for Times New Roman font files across OS font directories
    for sdir in search_dirs:
        if sdir.exists():
            for cand in candidates:
                if (sdir / cand).exists():
                    return sdir / cand, "Times New Roman"
                # Handle macOS font naming variations like "Times New Roman.ttf"
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

    # Fallback to Liberation Serif reference fonts in fonts_dir
    for cand in candidates:
        if (fonts_dir / cand).exists():
            return fonts_dir / cand, "Liberation Serif"

    raise FileNotFoundError(
        f"Could not find reference font from candidates {candidates}"
    )


def generate_comparison_image(fonts_dir: str | Path, out_file: str | Path) -> None:
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

    # Ample initial height canvas so bottom is never clipped before cropping
    height = 140 + len(STYLES) * (60 + len(TEST_SAMPLES) * 160) + 200

    img = Image.new("RGB", (width, height), color=(248, 249, 250))
    draw = ImageDraw.Draw(img)

    # Header Card
    draw.rectangle([(0, 0), (width, 100)], fill=(20, 26, 38))
    draw.text(
        (padding, 20),
        "Nimbus Match vs Times New Roman — Overlapped Visual Comparison",
        fill=(255, 255, 255),
        font=label_font_title,
    )
    draw.text(
        (padding, 60),
        "Direct overlap inspection (Times New Roman in Red, Nimbus Match in Blue) across Regular, Bold, Italic & Bold Italic",
        fill=(175, 190, 210),
        font=label_font_script,
    )

    y = 120

    for style_title, nimbus_filename, ref_candidates in STYLES:
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

        # Style Section Header Card
        draw.rectangle([(padding, y), (width - padding, y + 36)], fill=(225, 232, 242))
        draw.text(
            (padding + 15, y + 6),
            f"Style: {style_title} (Reference: {ref_name})",
            fill=(15, 30, 55),
            font=label_font_style,
        )
        y += 48

        for script_name, sample_text in TEST_SAMPLES:
            # Script section title
            draw.text(
                (padding + 15, y),
                f"• {script_name}",
                fill=(70, 80, 95),
                font=label_font_script,
            )
            y += 24

            x_text = padding + 180

            # 1. Times New Roman Line (Red)
            bbox_ref = draw.textbbox((x_text, y), sample_text, font=font_ref)
            draw.text(
                (padding + 15, y + 2),
                f"{ref_name} (Ref)",
                fill=(200, 30, 30),
                font=label_font_tag,
            )
            draw.text((x_text, y), sample_text, fill=(200, 30, 30), font=font_ref)
            y += line_gap

            # 2. Nimbus Match Line (Blue)
            bbox_nim = draw.textbbox((x_text, y), sample_text, font=font_nimbus)
            draw.text(
                (padding + 15, y + 2),
                "Nimbus Match",
                fill=(10, 90, 200),
                font=label_font_tag,
            )
            draw.text((x_text, y), sample_text, fill=(10, 90, 200), font=font_nimbus)
            y += line_gap

            # 3. OVERLAPPED LINE (TNR + Nimbus Match drawn at identical position)
            draw.text(
                (padding + 15, y + 2),
                "Overlapped View",
                fill=(110, 30, 140),
                font=label_font_tag,
            )

            # Create transparent RGBA overlay for semi-transparent blending
            rgba_layer = Image.new("RGBA", (width, height), color=(0, 0, 0, 0))
            rgba_draw = ImageDraw.Draw(rgba_layer)

            # Draw TNR layer in semi-transparent Red (220, 20, 20, 140)
            rgba_draw.text(
                (x_text, y), sample_text, fill=(220, 20, 20, 140), font=font_ref
            )
            # Draw Nimbus Match layer in semi-transparent Blue (10, 100, 230, 140)
            rgba_draw.text(
                (x_text, y), sample_text, fill=(10, 100, 230, 140), font=font_nimbus
            )

            img.paste(rgba_layer, (0, 0), rgba_layer)
            y += line_gap

            # Metric width indicator line
            ref_w = bbox_ref[2] - bbox_ref[0]
            nim_w = bbox_nim[2] - bbox_nim[0]
            diff_w = abs(ref_w - nim_w)

            indicator_text = f"Metric Match: Ref Width = {ref_w}px | Nimbus Match Width = {nim_w}px (Δ = {diff_w}px)"
            draw.text(
                (x_text, y), indicator_text, fill=(90, 105, 120), font=label_font_tag
            )

            # Separator line
            draw.line(
                [(padding + 15, y + 18), (width - padding - 15, y + 18)],
                fill=(230, 235, 240),
                width=1,
            )
            y += 30

        y += 20

    # Crop canvas cleanly to actual rendered height
    final_height = y + 30
    img_cropped = img.crop((0, 0, width, final_height))
    out_file.parent.mkdir(parents=True, exist_ok=True)
    img_cropped.save(out_file)
    print(
        f"Successfully generated full comparison image ({width}x{final_height}px): {out_file}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate Nimbus Match comparison image")
    ap.add_argument(
        "--fonts-dir", required=True, help="Directory containing OTF/TTF fonts"
    )
    ap.add_argument(
        "--out", default="nimbus_match_comparison.png", help="Output PNG path"
    )
    args = ap.parse_args()

    generate_comparison_image(args.fonts_dir, args.out)


if __name__ == "__main__":
    main()
