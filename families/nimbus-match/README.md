# Nimbus Match

A Times New Roman metric-compatible font family built from Nimbus Roman outlines and Tinos text metrics. It includes Regular, Bold, Italic and Bold Italic and can coexist with the other Match family.

## Build policy

Builds use only the selected outline source and Tinos. All source glyphs are preserved, including future additions and unencoded alternates. Shared-character advances are matched by Unicode identity. Exact coverage, source versions and available features are recorded in each release's BUILD-INFO, rather than committed as snapshots.

Additional glyphs keep their scaled source widths except for explicit Unicode metric policy. Automatic ligatures are disabled to preserve ordinary text layout. Nimbus retains its established kerning-alias behavior.

Shared text metrics do not guarantee identical native feature widths or rendering in every application.

## Build and install

Resolve inputs as described in the [project README](../../README.md), then run:

```sh
pixi run font-match build --family nimbus-match
```

Install the four OTFs from the family's ZIP or its separate OTC, choosing one format. Download the corresponding LICENSE asset when using individual OTF/OTC files. Find published fonts and exact versions in the [release history](https://github.com/IvanaGyro/nimbus-match/releases).

## Local comparisons

Generate a current difference image and metric report with explicitly supplied local fonts:

```sh
pixi run font-match preview --family nimbus-match --reference C:/Windows/Fonts/times.ttf --tinos path/to/Tinos-Regular.ttf --out build_temp/previews/nimbus-match/differences.png
```

The image focuses on features Times New Roman has that the Match family lacks, and measured metric differences. Red is TNR, blue is Match, and gray is overlap. Native and synthetic effects are labeled separately. The PNG and accompanying JSON depend on the actual fonts supplied and must stay in ignored output directories; they are not source files.

## Font license

Nimbus Roman comes from [URW/Artifex](https://github.com/ArtifexSoftware/urw-base35-fonts). Nimbus Match retains its applicable AGPL font terms. See [LICENSE](LICENSE) for the complete font license and attribution, including the Tinos reference terms. Ivana maintains the derivative; upstream maintainers are not responsible for these modifications. Tinos fonts are not packaged. The repository code has a separate [MIT license](../../LICENSE).
