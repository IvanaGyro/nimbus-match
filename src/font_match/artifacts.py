"""Per-family release packaging with strict content validation."""

import io
import json
import platform
import zipfile
from importlib.metadata import version

from fontTools.ttLib import TTCollection, TTFont

from .config import STYLES
from .upstream import sha256


def asset_names(family):
    return [f"{family.prefix}-{s}.otf" for s in STYLES] + [
        f"{family.prefix}.otc",
        f"{family.prefix}.zip",
        f"{family.prefix}-BUILD-INFO.json",
        f"{family.prefix}-NOTICES.txt",
    ]


def package(family, output, manifest):
    fonts = [output / f"{family.prefix}-{s}.otf" for s in STYLES]
    manifest["font_sha256"] = {p.name: sha256(p.read_bytes()) for p in fonts}
    manifest["tools"] = {
        "python": platform.python_version(),
        "fonttools": version("fonttools"),
    }
    info = output / f"{family.prefix}-BUILD-INFO.json"
    info.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    notice = output / f"{family.prefix}-NOTICES.txt"
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
        for path in [*fonts, info, notice]:
            # Fixed ZIP metadata makes repeated packages reproducible.
            entry = zipfile.ZipInfo(path.name, (2000, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, path.read_bytes())
        archive.writestr(
            zipfile.ZipInfo("INSTALL.txt", (2000, 1, 1, 0, 0, 0)),
            f"Install the four {family.name} OTF files, or the separately supplied OTC.\nChoose one format to avoid duplicate installation.\nSee the included NOTICES and BUILD-INFO files.\n",
        )
    validate(family, output)


def validate(family, output):
    for name in asset_names(family):
        if not (output / name).is_file():
            raise ValueError(f"Missing required release artifact: {output / name}")
    info = json.loads((output / f"{family.prefix}-BUILD-INFO.json").read_text())
    expected = {f"{family.prefix}-{s}.otf" for s in STYLES}

    def check(font, style):
        assert font["name"].getBestFamilyName() == family.name
        assert font["name"].getDebugName(6) == f"{family.prefix}-{style}"
        assert font["name"].getDebugName(5) == f"Version {info['version']}"
        assert font["head"].unitsPerEm == 2048
        assert abs(font["CFF "].cff.topDictIndex[0].FontMatrix[0] - 1 / 2048) < 1e-9

    for style in STYLES:
        name = f"{family.prefix}-{style}.otf"
        assert sha256((output / name).read_bytes()) == info["font_sha256"][name]
        with TTFont(output / name) as font:
            check(font, style)
    with zipfile.ZipFile(output / f"{family.prefix}.zip") as archive:
        assert set(archive.namelist()) == expected | {
            "INSTALL.txt",
            f"{family.prefix}-BUILD-INFO.json",
            f"{family.prefix}-NOTICES.txt",
        }
        for name in expected | {
            f"{family.prefix}-BUILD-INFO.json",
            f"{family.prefix}-NOTICES.txt",
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
