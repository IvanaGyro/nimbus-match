# Multi-family implementation and verification

Implemented on 2026-09-10; public release verified on 2026-09-11. The chosen second-family identity is **Termes Match** (`termes-match`, `TermesMatch`). The repository remains `IvanaGyro/nimbus-match`.

## Non-negotiable build rules

1. Font construction uses only the selected outline source and Tinos. It does not locate, open, download or require Times New Roman. TNR belongs only to explicitly requested local preview/validation commands.
2. Preserve all input glyphs, including future additions and unencoded feature alternates. Discover cmap coverage at build time.
3. Copy shared advances by Unicode identity. For Termes-only canonical accented characters, predict widths from a single Tinos base plus combining marks. Apply explicit Unicode advance policy where available; otherwise retain scaled source advances. Unencoded alternates remain outside the strict metric compatibility guarantee.
4. Difference images focus on features TNR has that each Match family lacks, and on measured metric differences. Use real TNR, clearly label native versus synthetic small caps, and compare supported samples only.

## Implemented architecture

- Installed `src/font_match/` package with a console entry point and `python -m font_match`. Pixi installs the local project as an editable dependency; ordinary wheels contain only package code and metadata.
- Small typed family configurations in `families/<family>/family.toml`, including style mappings, names, source provider, feature/metric policies and relative notice paths.
- An explicit `--project-dir` resolves repository data independently of the installed package location. Root scripts remain compatibility entry points.
- `font-match resolve` records exact input URLs, full Git revisions and archive SHA-256 hashes. Downloads and extraction reject changed or unavailable pinned inputs. A release BUILD-INFO manifest can be reused with `build --inputs`.
- `font-match build --family all|nimbus-match|termes-match` builds four styles per family in separate output directories. The public build path never imports preview commands.
- `font-match verify --family all` reopens loose fonts, ZIPs and OTCs and writes the combined asset checksums.
- Optional `font-match preview` requires explicit TNR and Tinos paths and generates 640-pixel comparison images plus measured JSON reports.

## Source audit and policy decisions

Audited inputs:

| Input | Revision/version | Archive SHA-256 |
| --- | --- | --- |
| Nimbus Roman | `c15105598aa7eb256b1ebfcecd3d078801521e73` | `42b75a029bd03c77a351f05985b775502574390e72c665d58a40fa3ef94a6b4a` |
| Tinos | `3b4482a99b80ea5fc75f187b1be3120a3f5905b3` | `c5a585593b2ea497fdf11e22a5ecaf5bdd1026039724057916bb05aab2e8dbf3` |
| TeX Gyre Termes | `2.004` | `1773c470f9e388e087b68e3426e115af2cd236845a7e05ceb25b2a503409a7a3` |

All four Termes inputs are 1000-UPEM CFF text OTFs with 1,090 glyphs and 1,053 encoded characters. Each shares 653 encoded characters with Tinos and has 400 additional characters. Nimbus has 854 encoded characters, of which 732 are shared and 122 additional. Manifests list actual unencoded glyphs separately because cmap aliases make subtraction of glyph/codepoint counts unreliable.

Termes has native small caps, figure variants, stylistic alternates and `cpsp` positioning, plus `size` metadata. Preserve its non-kern GPOS lookups, script/language associations, GDEF and native GSUB features. Replace only kerning. Remap and sort feature indexes during serialization.

Disable automatic `liga` for both families. Shaping measurements showed that Termes's ligature substitutions substantially change constituent-character widths. Preserve Nimbus's established glyph-alias kerning behavior for baseline compatibility; new-family kerning uses Unicode mappings. Retain the U+FB00 style advances 1237, 1200, 1137 and 1225 at 2048 UPEM when that character exists.

Keep authentic source attribution and replace derivative product names in name/CFF records. Termes uses GFL/LPPL notices from its actual archive. Nimbus retains the applicable URW/Artifex notices. The audited Tinos revision uses OFL-1.1, replacing the old documentation's Apache-license claim. Reference fonts are not distributed in font packages.

## Release contract (corrected 2026-09-11)

Each family releases independently, only when its own upstream source font files change. Compare the SHA-256 hashes of all four Nimbus Roman or TeX Gyre Termes OTFs with that family's latest public BUILD-INFO style records. Changes to Tinos, build code, configuration, notices, or unrelated files in upstream archives do not by themselves publish a release. Preserve archive hashes and build fingerprints for reproducibility and verification, not as release triggers.

Use independent numeric counters and tags: `nimbus-match-v1.003`, `termes-match-v1.003`, and subsequent family-specific increments. Existing combined v1.002 manifests seed each counter and source baseline, so migration alone does not republish fonts. Search paginated public release history separately for each family's manifest, ignoring drafts and prereleases.

Each family release publishes:

- Four individually named OTF styles.
- An OTC containing exactly those four styles.
- A ZIP containing the four OTFs, INSTALL.txt, notices and BUILD-INFO.
- Separate `*-NOTICES.txt` and `*-BUILD-INFO.json` assets.
- SHA256SUMS covering those eight family assets.

Resolve inputs once, select changed families, and build them in read-only matrix jobs. Separate write-scoped publisher jobs validate and upload only their selected family's assets. Reuse only matching family drafts; reject public-release overwrites and unrelated drafts. Validate downloaded draft packages and verify public downloads, checksums and tag targets after publication. Workflow concurrency serializes release runs.

Manual runs can select one family or both. Forced builds of unchanged sources produce development artifacts only. A changed selected family may publish independently. If no sources changed, skip builds and publication. Existing public tags remain unchanged. GitHub's global latest-release alias cannot represent both families; documentation uses explicit versioned downloads and release history instead.

## Verification evidence

Completed locally:

- Fresh Pixi installation of an isolated staged checkout; imports and tests work without PYTHONPATH or source-directory injection.
- Ordinary wheel installation and CLI invocation outside the checkout; explicit project root successfully verifies both families. Wheel contents exclude fonts, family data and repository-only files.
- Independent and combined builds of both families. Both build orders produce byte-identical OTFs. A guarded test permits only explicitly supplied font inputs/output during construction.
- All four Nimbus styles exactly match the original builder's normalized outlines, advances, kern, GSUB and GPOS, apart from deliberate naming/version/timestamp handling.
- Required tests cover Unicode advances, vertical metrics, coverage preservation, future accented-character prediction, feature-enabled shaping, capital positioning, style identities, serialized CFF matrices and actual ZIP/OTC contents. Missing release artifacts fail rather than skip.
- 56 required tests pass after the independent-release correction. The 54 optional local TNR tests pass separately; they are explicitly skipped in public build testing.
- LibreOffice opened a temporary document embedding all eight OTF styles. Its PDF export contains all eight distinct PostScript identities and correctly renders ordinary text, native Termes small caps and synthetic Nimbus small caps. No permanent font installation was needed.
- Comparison PNGs were visually inspected for clipping and readability. The measured reference is local Times New Roman 7.12.
- Mandatory `pixi run pre-commit run --all-files` and `pixi run pytest` checks pass before each logical commit.

Historical combined-release verification (before the independent-release correction):

- [Combined Actions run 34495243028](https://github.com/IvanaGyro/nimbus-match/actions/runs/34495243028) passed preparation, both isolated family builds/tests, and publication.
- [Font Match v1.002](https://github.com/IvanaGyro/nimbus-match/releases/tag/v1.002) targets `0b889274dbf47cbf7fd42860cc8b96f77332fe04`. All 17 public assets were independently downloaded; their checksums, GitHub asset digests, tag target, manifests, ZIPs and OTCs passed verification.
- The initial v1.001 assets also passed independent verification. Its workflow exposed a Windows legacy-encoding failure while decoding GitHub's UTF-8 response after publication. A separate fix and regression test preceded v1.002; v1.001 was not overwritten.
- The initial project README linked each family through GitHub's global latest alias; the independent-release correction replaces these with explicit v1.002 links and release history.
- A subsequent non-forced preparation returned `should_build=false`, confirming unchanged inputs and build code do not create a duplicate release.

## Commit boundaries

Keep the shared-engine extraction, input pinning, two-family build/packages, release workflow, and comparison work as separate logical commits. The independent-release correction is one logical change spanning detection, publication, regression tests and documentation. Preserve Ivana as author and the executing model as committer/co-author. Existing published tags remain unchanged.

