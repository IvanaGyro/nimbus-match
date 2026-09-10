"""Unicode-keyed advance policy; unknown glyphs retain scaled source metrics."""

import unicodedata

from fontTools.misc.roundTools import otRound

FF_ADVANCES = {"Regular": 1237, "Bold": 1200, "Italic": 1137, "BoldItalic": 1225}
ADVANCE_OVERRIDES = {0xFB00: FF_ADVANCES}


def apply_advance_corrections(font, style_name):
    cmap = font.getBestCmap() or {}
    for codepoint, styles in ADVANCE_OVERRIDES.items():
        glyph = cmap.get(codepoint)
        if glyph is not None:
            _, lsb = font["hmtx"][glyph]
            font["hmtx"][glyph] = (
                otRound(
                    styles[style_name.replace(" ", "")] * font["head"].unitsPerEm / 2048
                ),
                lsb,
            )


def predict_missing_advances(font, reference):
    """Predict canonical accented characters from a single encoded reference base.

    Only canonical decompositions with one base and combining marks qualify.
    Unknown symbols, compatibility forms and feature alternates retain source widths.
    Shared glyph aliases are never modified by prediction.
    """
    cmap, refmap = font.getBestCmap(), reference.getBestCmap()
    shared_glyphs = {cmap[cp] for cp in cmap.keys() & refmap.keys()}
    predicted = {}
    for cp in sorted(cmap.keys() - refmap.keys()):
        glyph = cmap[cp]
        decomposition = unicodedata.normalize("NFD", chr(cp))
        if glyph in shared_glyphs or len(decomposition) < 2:
            continue
        base, marks = decomposition[0], decomposition[1:]
        if ord(base) not in refmap or not all(unicodedata.combining(c) for c in marks):
            continue
        width = reference["hmtx"][refmap[ord(base)]][0]
        font["hmtx"][glyph] = (width, font["hmtx"][glyph][1])
        predicted[cp] = width
    return predicted
