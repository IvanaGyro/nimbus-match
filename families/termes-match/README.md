# Termes Match

An independently installable derivative of the four TeX Gyre Termes text styles, using Tinos advances and kerning at 2048 units per em. It uses the family name **Termes Match** and PostScript prefix **TermesMatch**. TeX Gyre Termes Math is not an input.

## Coverage and native features

The audited Termes 2.004 OTFs each contain 1,090 glyphs and 1,053 encoded characters: 653 shared with Tinos and 400 additional characters. Multiple codepoints can share a glyph; the manifest separately lists unencoded glyphs. Each build calculates coverage anew and preserves the entire input glyph order and cmap.

Shared-character advances follow Tinos. For source-only canonically decomposable accented characters, the build predicts the advance from the reference base character. Explicit Unicode policy takes precedence; otherwise scaled source advances remain. Unknown future symbols and unencoded feature alternates are preserved, with no arbitrary name-based metric mapping. These predictions and native alternate widths are outside the strict shared-character compatibility guarantee.

Native `smcp`, `c2sc`, oldstyle figures, stylistic sets and other source substitutions remain available. Source `cpsp` positioning and `size` metadata retain their script/language associations and necessary GDEF data. Only source kerning is replaced. Automatic `liga` is disabled: the audited ligature substitutions materially changed text widths; ordinary `ffi`, for example, follows the reference's constituent-character layout instead.

## Differences from Times New Roman

Termes Match has native small caps, but their widths and outlines differ from TNR. Capital spacing also exists in both fonts but adds different amounts. The figure explicitly shows those differences alongside missing features and OS/2 metric differences.

Red is local Times New Roman 7.12; blue is Termes Match Regular; gray is overlap. Values are font units at 2048 units per em. Samples are supported by both fonts; the complete feature-tag gap includes script-specific features that may fall outside shared coverage. Application rendering may differ from these HarfBuzz/FreeType illustrations.

![Missing features and metric differences](previews/differences.png)

[Full measured differences](previews/differences.json).

## Build and install

Resolve inputs using the [project instructions](../../README.md), then:

```sh
pixi run font-match build --family termes-match
```

Install the four OTFs in `dist/termes-match/TermesMatch.zip` or the separate `TermesMatch.otc`. This family can coexist with Nimbus Match.

For optional comparison generation:

```sh
pixi run font-match preview --family termes-match --reference C:/Windows/Fonts/times.ttf --tinos path/to/Tinos-Regular.ttf --out families/termes-match/previews/differences.png
```

For native small caps in LibreOffice, use `Termes Match:smcp=1`.

## Credits and notices

TeX Gyre Termes was extended by B. Jackowski and J. M. Nowacki on behalf of TeX users groups, with Vietnamese contributions by Han The Thanh. Its source README identifies the underlying Nimbus Roman release as separately provided under the GUST Font License. See [CTAN](https://ctan.org/pkg/tex-gyre-termes) and the [complete upstream notices, source manifest and derivative notice](licenses/NOTICES.txt).

This derivative follows GFL/LPPL terms and uses a changed family name. It does not inherit the separately distributed Nimbus Match font's AGPL license. Ivana maintains the derivative. The pinned Tinos metric reference is OFL-1.1 and is not bundled. Exact source versions, URLs, archive and per-font hashes are recorded in BUILD-INFO.

