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

## Source policy

Discover coverage, glyph aliases and native features from each build's inputs. Preserve the complete source glyph order and cmap. Preserve non-kerning positioning and native substitutions, replacing kerning and applying the configured default-ligature policy. Retain explicit Unicode metric policy and conservative prediction for additional characters.

Do not commit source hashes, glyph counts, generated previews or measured metric tables. Exact input versions and coverage belong in ignored build outputs and public release manifests. Optional TNR comparisons remain local. Family LICENSE files are maintained source documents, separate from generated audit data and the root MIT code license.

## Release contract (corrected 2026-09-11)

Each family releases independently when its own upstream source font files change, or when Tinos or shared build code changes. Shared changes trigger both families. Compare the SHA-256 hashes of all four Nimbus Roman or TeX Gyre Termes OTFs with that family's latest public BUILD-INFO style records. Compare Tinos input identity and a separate code fingerprint against each family’s own last manifest. The code fingerprint covers package code, family configurations/notices, dependency configuration/lockfile and release workflow, but excludes outline inputs and documentation. Preserve the full build fingerprint for publication verification. Legacy manifests without the separate code fingerprint trigger one release per family to establish this baseline. Unrelated files in upstream archives do not trigger a release.

Tags follow Tinos version, outline-source version, increment: `tinos-<version>-nimbus-<version>-<increment>` and `tinos-<version>-termes-<version>-<increment>`. Tinos and Termes versions are read from all four upstream fonts and must agree within each family; Nimbus uses its upstream release identifier. The increment advances within a family/version pair and resets to 1 for a new pair. Existing tags remain untouched. Matching drafts reuse their increment.

BUILD-INFO `version` holds the readable three-part version; `font_revision` holds a separately increasing numeric OpenType revision. Name ID 5 includes both, while head.fontRevision and CFF version retain valid numeric values. The numeric revision continues from the last family manifest, including older manifests that used a numeric `version`. Search paginated public release history separately for each family's manifest, ignoring drafts and prereleases.

Each family release publishes:

- Four individually named OTF styles.
- An OTC containing exactly those four styles.
- A ZIP containing the four OTFs, INSTALL.txt, notices and BUILD-INFO.
- Separate `*-LICENSE.txt` and `*-BUILD-INFO.json` assets.
- SHA256SUMS covering those eight family assets.

Resolve inputs once, select changed families, and build them in read-only matrix jobs. Separate write-scoped publisher jobs validate and upload only their selected family's assets. Reuse only matching family drafts; reject public-release overwrites and unrelated drafts. Validate downloaded draft packages and verify public downloads, checksums and tag targets after publication. Workflow concurrency serializes release runs.

Manual runs can select one family or both. Forced builds of unchanged sources and code produce development artifacts only. A changed selected family may publish independently. If neither sources nor shared dependencies changed, skip builds and publication. Existing public tags remain unchanged. GitHub's global latest-release alias cannot represent both families; documentation uses explicit versioned downloads and release history instead.

## Verification policy

Run formatting/lint and the required test suite before each logical commit. Required tests verify input integrity, Unicode metrics, glyph preservation, future-glyph prediction, naming, release detection/version allocation and serialized OTF/OTC/ZIP contents. Optional tests may read explicitly enabled local TNR; builds never do.

Verify ordinary wheel installation outside the checkout and independent family builds. Validate uploaded draft assets and public downloads against checksums and manifests. Keep font-dependent evidence in ignored local output or CI artifacts, not in repository snapshots.

## Commit boundaries

Keep versioning, code licensing, font-license filenames, generated-data cleanup and release-note improvements as focused logical commits. Preserve Ivana as author and the executing model as committer/co-author. Existing published tags remain unchanged.
