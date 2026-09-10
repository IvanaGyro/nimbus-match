# Nimbus Match and Termes Match

Two separately installable font families with Tinos text metrics at 2048 units per em. **Nimbus Match** uses Nimbus Roman outlines; **Termes Match** uses the extended TeX Gyre Termes text fonts. Each includes Regular, Bold, Italic and Bold Italic.

Font builds read only the selected outline source and Tinos. Local Times New Roman is used only for optional comparisons. Matching shared character widths does not guarantee identical native feature metrics or application rendering.

| Family | Downloads | Details |
| --- | --- | --- |
| Nimbus Match | [ZIP](https://github.com/IvanaGyro/nimbus-match/releases/latest/download/NimbusMatch.zip) · [OTC](https://github.com/IvanaGyro/nimbus-match/releases/latest/download/NimbusMatch.otc) | [Features and comparisons](families/nimbus-match/README.md) |
| Termes Match | [ZIP](https://github.com/IvanaGyro/nimbus-match/releases/latest/download/TermesMatch.zip) · [OTC](https://github.com/IvanaGyro/nimbus-match/releases/latest/download/TermesMatch.otc) | [Features and comparisons](families/termes-match/README.md) |

Install a family's four OTFs **or** its OTC. Choose one format to avoid duplicate installation. Each ZIP includes installation instructions, notices and a build manifest; individual OTF/OTC users should also download that family's NOTICES file.

## Build

```sh
pixi install
pixi run font-match resolve
pixi run font-match build --family all
pixi run font-match verify --family all
pixi run pytest
pixi run pre-commit run --all-files
```

Use `--family nimbus-match` or `--family termes-match` to build independently. Outputs go to `dist/<family>/`. `resolve` records full revisions, archive hashes and URLs in `build_temp/inputs.json`; subsequent builds verify those exact inputs. A saved `*-BUILD-INFO.json` also works as `--inputs`. Unknown glyphs are retained, with conservative metric prediction for Termes and scaled source metrics as the fallback.

`pixi run python -m font_match` is equivalent to `pixi run font-match`. Outside this checkout, pass `--project-dir /path/to/nimbus-match` **before** the subcommand. Root Python scripts remain compatibility entry points; `check_and_build.py --force` builds Nimbus Match locally.

## Comparisons and releases

The [Nimbus Match](families/nimbus-match/README.md) and [Termes Match](families/termes-match/README.md) pages show features that Times New Roman provides but each family lacks, plus measured metric differences. Comparisons explicitly identify their reference and never substitute Tinos for TNR.

Weekly and manual CI resolve inputs once, build each family in an isolated matrix job, validate both packages, and publish one combined release. A family-only manual run produces development artifacts. Numeric release versions are independent of upstream versions. Published assets are checked by checksum and reopened after download.

Source credits and applicable font notices are maintained per family. Repository code is [AGPL-3.0-or-later](LICENSE).
