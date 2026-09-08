"""Shape OpenType text with HarfBuzz and rasterize the resulting glyphs with FreeType."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import freetype
import uharfbuzz as hb
from PIL import Image, ImageChops

SUPERSAMPLE = 4


@dataclass(frozen=True)
class PositionedGlyph:
    glyph_id: int
    x_advance: int
    y_advance: int
    x_offset: int
    y_offset: int


class FontRenderer:
    def __init__(self, path: Path):
        self.hb_font = hb.Font(hb.Face(path.read_bytes()))
        self.upem = self.hb_font.face.upem
        self.hb_font.scale = (self.upem, self.upem)
        hb.ot_font_set_funcs(self.hb_font)
        self.face = freetype.Face(str(path))

    def shape(self, text: str, features: dict | None = None) -> list[PositionedGlyph]:
        buffer = hb.Buffer()
        buffer.add_str(text)
        buffer.guess_segment_properties()
        # Disable automatic ligatures so the selected feature is isolated.
        hb.shape(
            self.hb_font, buffer, {"kern": True, "liga": False, **(features or {})}
        )
        return [
            PositionedGlyph(
                info.codepoint, pos.x_advance, pos.y_advance, pos.x_offset, pos.y_offset
            )
            for info, pos in zip(buffer.glyph_infos, buffer.glyph_positions)
        ]

    def advance(self, text: str, features: dict | None = None) -> int:
        return sum(glyph.x_advance for glyph in self.shape(text, features))

    def draw(
        self,
        mask: Image.Image,
        text: str,
        origin: tuple[float, float],
        size: float,
        features: dict | None = None,
        x_scale: float = 1.0,
    ) -> float:
        """Draw into a supersampled mask and return the advance in display pixels."""
        self.face.set_char_size(round(size * SUPERSAMPLE * 64))
        self.face.set_transform(
            freetype.Matrix(round(x_scale * 65536), 0, 0, 65536), freetype.Vector(0, 0)
        )
        scale = size * SUPERSAMPLE / self.upem
        x, baseline = (coord * SUPERSAMPLE for coord in origin)
        start_x = x
        for glyph in self.shape(text, features):
            if glyph.glyph_id == 0:
                raise ValueError(f"Missing glyph in comparison sample: {text!r}")
            self.face.load_glyph(
                glyph.glyph_id,
                freetype.FT_LOAD_RENDER
                | freetype.FT_LOAD_NO_HINTING
                | freetype.FT_LOAD_NO_BITMAP,
            )
            slot = self.face.glyph
            bitmap = slot.bitmap
            if bitmap.width and bitmap.rows:
                raster = Image.frombytes(
                    "L",
                    (bitmap.width, bitmap.rows),
                    bytes(bitmap.buffer),
                    "raw",
                    "L",
                    abs(bitmap.pitch),
                    1 if bitmap.pitch >= 0 else -1,
                )
                left = round(x + glyph.x_offset * scale * x_scale) + slot.bitmap_left
                top = round(baseline - glyph.y_offset * scale) - slot.bitmap_top
                box = (left, top, left + raster.width, top + raster.height)
                if left < 0 or top < 0 or box[2] > mask.width or box[3] > mask.height:
                    raise ValueError(f"Comparison sample exceeds its panel: {text!r}")
                mask.paste(ImageChops.lighter(mask.crop(box), raster), box)
            x += glyph.x_advance * scale * x_scale
            baseline -= glyph.y_advance * scale
        return (x - start_x) / SUPERSAMPLE


def new_mask(size: tuple[int, int]) -> Image.Image:
    return Image.new("L", tuple(value * SUPERSAMPLE for value in size))


def finish_mask(mask: Image.Image) -> Image.Image:
    return mask.resize(
        tuple(value // SUPERSAMPLE for value in mask.size), Image.Resampling.LANCZOS
    )
