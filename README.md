# Nimbus Match and Termes Match

Two separately installable font families with Tinos text metrics at 2048 units per em. **Nimbus Match** uses Nimbus Roman outlines; **Termes Match** uses the extended TeX Gyre Termes text fonts. Each includes Regular, Bold, Italic and Bold Italic.

Font builds read only the selected outline source and Tinos. Local Times New Roman is used only for optional comparisons. Matching shared character widths does not guarantee identical native feature metrics or application rendering.

| Family | Downloads | Details |
| --- | --- | --- |
| Nimbus Match | [Releases](https://github.com/IvanaGyro/nimbus-match/releases) | [Build and comparisons](families/nimbus-match/README.md) |
| Termes Match | [Releases](https://github.com/IvanaGyro/nimbus-match/releases) | [Build and comparisons](families/termes-match/README.md) |

Each family has separate releases. Use the source name in the tag to identify the family; GitHub's global latest-release alias cannot track both independently.

Install a family's four OTFs **or** its OTC. Choose one format to avoid duplicate installation. Each ZIP includes installation instructions and the font license; individual OTF/OTC users should also download that family's LICENSE file.

## Build

```sh
pixi install
pixi run font-match resolve
pixi run font-match build --family all
pixi run font-match verify --family all
pixi run pytest
pixi run pre-commit run --all-files
```

Use `--family nimbus-match` or `--family termes-match` to build independently. Outputs go to `dist/<family>/`. `resolve` records full revisions, archive hashes and URLs in `build_temp/inputs.json`; subsequent builds verify those exact inputs. Unknown glyphs are retained, with conservative metric prediction for Termes and scaled source metrics as the fallback.

`pixi run python -m font_match` is equivalent to `pixi run font-match`. Outside this checkout, pass `--project-dir /path/to/nimbus-match` **before** the subcommand. Root Python scripts remain compatibility entry points; `check_and_build.py --force` builds Nimbus Match locally.

## Comparisons and releases

The [Nimbus Match](families/nimbus-match/README.md) and [Termes Match](families/termes-match/README.md) pages explain how to generate local comparisons of features that Times New Roman provides but each family lacks, plus measured metric differences. Comparisons explicitly identify their reference and never substitute Tinos for TNR.

Weekly and manual CI compare each family's upstream versions against its latest public version tag. Nimbus Roman version changes release Nimbus Match; TeX Gyre Termes version changes release Termes Match. Tinos version or shared build-code changes trigger both families. Code changes are detected against each family's release tag in Git, including configuration, dependency locks and licenses. Documentation and archive changes without an upstream version change do not trigger publication.

Each changed family gets its own release, seven family assets and SHA256SUMS. Tags put the Tinos version first, the outline-source version second, and an increment last: `tinos-<version>-nimbus-<version>-<increment>` or `tinos-<version>-termes-<version>-<increment>`. Nimbus uses its upstream release identifier; Tinos and Termes use their embedded font versions. The increment advances independently for each family/version pair and starts at 1 for a new pair. The readable font version contains the same three values; a separate numeric OpenType revision remains monotonic for installation compatibility. Published assets are checked by checksum and reopened after download. Existing releases are preserved.

A manual run can check one family or both. `force_build` builds families with unchanged sources and build code as development artifacts only; it does not override release detection. Build jobs remain read-only, and a separate publisher uploads only the selected family's validated assets.

Source credits and applicable font notices are maintained per family. Repository code is [MIT](LICENSE); font terms are in each family's LICENSE.

## Generated data

Keep downloaded fonts, build manifests, source hashes, coverage reports, preview images and metric tables in ignored `build_temp/` or `dist/` directories. Do not commit generated font-dependent snapshots or bulk TNR metrics. Generate comparisons using the family instructions for the actual fonts being tested.

Release tags and embedded font versions identify each build. Packages contain fonts, installation instructions and the font license; SHA256SUMS verifies the release downloads.
