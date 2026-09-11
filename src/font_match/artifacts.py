"""Per-family release packaging with strict content validation."""

import io
import zipfile
import re

from fontTools.ttLib import TTCollection, TTFont

from .config import STYLES


def asset_names(family):
    return [f"{family.prefix}-{s}.otf" for s in STYLES] + [
        f"{family.prefix}.otc",
        f"{family.prefix}.zip",
        f"{family.prefix}-LICENSE.txt",
    ]


def package(family, output):
    fonts = [output / f"{family.prefix}-{s}.otf" for s in STYLES]
    # Remove the retired sidecar when rebuilding in an existing output directory.
    (output / f"{family.prefix}-BUILD-INFO.json").unlink(missing_ok=True)
    notice = output / f"{family.prefix}-LICENSE.txt"
    notice.write_text(
        "\n\n".join(p.read_text(encoding="utf-8") for p in family.notices),
        encoding="utf-8",
    )
    collection = TTCollection()
    collection.fonts = [TTFont(p, recalcTimestamp=False) for p in fonts]
    collection.save(output / f"{family.prefix}.otc")
    collection.close()
    with zipfile.ZipFile(
        output / f"{family.prefix}.zip", "w", zipfile.ZIP_DEFLATED
    ) as archive:
        for path in [*fonts, notice]:
            # Fixed ZIP metadata makes repeated packages reproducible.
            entry = zipfile.ZipInfo(path.name, (2000, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, path.read_bytes())
        archive.writestr(
            zipfile.ZipInfo("INSTALL.txt", (2000, 1, 1, 0, 0, 0)),
            f"Install the four {family.name} OTF files, or the separately supplied OTC.\nChoose one format to avoid duplicate installation.\nSee the included LICENSE file.\n",
        )
    validate(family, output)


def validate(family, output, expected_version=None, expected_revision=None):
    for name in asset_names(family):
        if not (output / name).is_file():
            raise ValueError(f"Missing required release artifact: {output / name}")
    with TTFont(output / f"{family.prefix}-Regular.otf") as regular:
        label = regular["name"].getDebugName(5)
    match = re.fullmatch(r"Version (\d+\.\d{3})(?:; (.+))?", label or "")
    if not match:
        raise ValueError("Invalid embedded font version")
    revision, version = match[1], match[2] or match[1]
    if expected_version is not None and version != expected_version:
        raise ValueError("Font version differs from prepared release")
    if expected_revision is not None and revision != expected_revision:
        raise ValueError("Font revision differs from prepared release")
    expected = {f"{family.prefix}-{s}.otf" for s in STYLES}

    def check(font, style):
        assert font["name"].getBestFamilyName() == family.name
        assert font["name"].getDebugName(6) == f"{family.prefix}-{style}"
        assert font["name"].getDebugName(5) == label
        assert abs(font["head"].fontRevision - float(revision)) < 1 / 65536
        assert font["CFF "].cff.topDictIndex[0].version == revision
        assert font["head"].unitsPerEm == 2048
        assert abs(font["CFF "].cff.topDictIndex[0].FontMatrix[0] - 1 / 2048) < 1e-9

    for style in STYLES:
        name = f"{family.prefix}-{style}.otf"
        with TTFont(output / name) as font:
            check(font, style)
    with zipfile.ZipFile(output / f"{family.prefix}.zip") as archive:
        assert set(archive.namelist()) == expected | {
            "INSTALL.txt",
            f"{family.prefix}-LICENSE.txt",
        }
        for name in expected | {
            f"{family.prefix}-LICENSE.txt",
        }:
            assert archive.read(name) == (output / name).read_bytes()
        for style in STYLES:
            with TTFont(
                io.BytesIO(archive.read(f"{family.prefix}-{style}.otf"))
            ) as font:
                check(font, style)
    with TTCollection(output / f"{family.prefix}.otc") as collection:
        assert len(collection.fonts) == 4
        for style, font in zip(STYLES, collection.fonts):
            check(font, style)
            with TTFont(output / f"{family.prefix}-{style}.otf") as loose:
                check(loose, style)
                for tag in ("hmtx", "CFF ", "GSUB", "GPOS", "name"):
                    if tag in loose:
                        assert font.getTableData(tag) == loose.getTableData(tag)
    return [output / name for name in asset_names(family)]
