# Nimbus Match

[![Weekly Font Build](https://github.com/IvanaGyro/nimbus-match/actions/workflows/weekly_font_release.yml/badge.svg)](https://github.com/IvanaGyro/nimbus-match/actions/workflows/weekly_font_release.yml)
[![License: OFL-1.1](https://img.shields.io/badge/License-OFL_1.1-blue.svg)](https://scripts.sil.org/OFL)

**Nimbus Match** is a metric-compatible metric generator for **Times New Roman** and **Liberation Serif** across 4 primary styles (**Regular**, **Bold**, **Italic**, **Bold Italic**).

By recalibrating glyph advance widths, font metrics (`usWinAscent`, `usWinDescent`, `hhea.ascent`, `hhea.descent`), units per em (UPEM 2048), and GPOS kerning tables from upstream [URW Nimbus Roman](https://github.com/ArtifexSoftware/urw-base35-fonts) and [Liberation Serif](https://github.com/liberationfonts/liberation-fonts), **Nimbus Match** ensures exact document layout parity without reflowing text.

---

## ✨ Features

- **4 Core Font Styles**: Regular, Bold, Italic, Bold Italic.
- **Strict Metric Compatibility**: Matches horizontal advance widths for over 800 glyphs across all 4 styles to preserve document line breaks and page layout.
- **UPEM Rescaling**: Rescales 1000 UPEM PostScript fonts to standard 2048 UPEM TrueType grids for high-precision metric alignment.
- **Kerning & GPOS Support**: Preserves and scales 800+ kerning pairs per font style.
- **Automated Upstream Monitoring**: Weekly GitHub Actions workflow monitors URW Base35 & Liberation Fonts releases and automatically builds and publishes updated OTF font release binaries.
- **Visual Verification Tooling**: Includes `generate_comparison.py` to create direct side-by-side and overlapped rendering inspections against system reference fonts.

---

## 🚀 Quick Start

### Building Fonts Locally

Ensure you have [`pixi`](https://pixi.sh) installed.

```bash
# Clone the repository
git clone https://github.com/IvanaGyro/nimbus-match.git
cd nimbus-match

# Run the build orchestrator (fetches upstream dependencies & generates dist/*.otf)
pixi run python check_and_build.py --force
```

Generated OTF files and comparison PNG will be placed in the `dist/` directory:
- `dist/NimbusMatch-Regular.otf`
- `dist/NimbusMatch-Bold.otf`
- `dist/NimbusMatch-Italic.otf`
- `dist/NimbusMatch-BoldItalic.otf`
- `dist/nimbus_match_comparison.png`

---

## 🧪 Testing & Code Quality

Run tests and pre-commit checks using `pixi`:

```bash
# Run pytest metric-compatibility test suite
pixi run pytest

# Run code formatters and linters (ruff, pyproject-fmt)
pixi run pre-commit run --all-files
```

---

## 📜 License & Credits

- **Nimbus Roman**: Developed by URW / Artifex Software ([urw-base35-fonts](https://github.com/ArtifexSoftware/urw-base35-fonts)).
- **Liberation Serif**: Developed by Red Hat / Liberation Fonts project ([liberation-fonts](https://github.com/liberationfonts/liberation-fonts)).
- **Nimbus Match**: Released under the SIL Open Font License (OFL-1.1).
