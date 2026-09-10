"""Build and inspect separately installable metric-matched font families."""

import argparse
import json
import subprocess
from pathlib import Path

from fontTools.ttLib import TTFont

from .artifacts import package, validate
from .build import build_single_style
from .config import STYLES, load_family
from .upstream import extract, resolve_inputs, sha256

FAMILIES = ("nimbus-match", "termes-match")


def build_family(project, family_id, resolved, version, out_dir=None):
    family = load_family(project, family_id)
    inputs = resolved["inputs"]
    sources = extract(
        project, inputs[family.provider], list(family.sources.values()), family.id
    )
    reference_names = [f"Tinos-{s}.ttf" for s in STYLES]
    references = extract(project, inputs["tinos"], reference_names, "references/tinos")
    output = (out_dir or project / "dist") / family.id
    output.mkdir(parents=True, exist_ok=True)
    reports = {}
    for style in STYLES:
        source = sources[family.sources[style]]
        reference = references[f"Tinos-{style}.ttf"]
        destination = output / f"{family.prefix}-{style}.otf"
        build_single_style(
            source,
            reference,
            destination,
            style,
            version,
            family=family.name,
            prefix=family.prefix,
            remove_liga=family.remove_liga,
            predict_missing=family.predict_missing,
            legacy_kerning_names=family.legacy_kerning_names,
        )
        with (
            TTFont(source) as original,
            TTFont(reference) as ref,
            TTFont(destination) as built,
        ):
            cmap, rmap = original.getBestCmap(), ref.getBestCmap()
            shared = set(cmap) & set(rmap)
            assert all(
                built["hmtx"][built.getBestCmap()[cp]][0] == ref["hmtx"][rmap[cp]][0]
                for cp in shared
            )
            reports[style] = {
                "source_sha256": sha256(source.read_bytes()),
                "reference_sha256": sha256(reference.read_bytes()),
                "encoded_count": len(cmap),
                "shared_count": len(shared),
                "source_only": [f"U+{cp:04X}" for cp in sorted(set(cmap) - set(rmap))],
                "unencoded": sorted(set(original.getGlyphOrder()) - set(cmap.values())),
                "features": {
                    tag: sorted(
                        {
                            r.FeatureTag
                            for r in built[tag].table.FeatureList.FeatureRecord
                        }
                    )
                    for tag in ("GSUB", "GPOS")
                    if tag in built
                },
            }
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=project, text=True
    ).strip()
    manifest = {
        "schema": 1,
        "family": family.id,
        "version": version,
        "commit": commit,
        "inputs": inputs,
        "styles": reports,
        "policies": {
            "remove_liga": family.remove_liga,
            "unknown_advances": "canonical-base-prediction-then-scaled-source"
            if family.predict_missing
            else "scaled-source",
            "reference": "Tinos",
            "metric_overrides": "Unicode-keyed",
            "non_kern_positioning": "preserved",
        },
    }
    manifest["build_fingerprint"] = resolved.get("build_fingerprint")
    package(family, output, manifest)
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    resolve = commands.add_parser("resolve")
    resolve.add_argument("--out", type=Path, default=Path("build_temp/inputs.json"))
    build = commands.add_parser("build")
    build.add_argument("--family", choices=(*FAMILIES, "all"), required=True)
    build.add_argument("--inputs", type=Path, default=Path("build_temp/inputs.json"))
    build.add_argument("--version")
    build.add_argument("--out-dir", type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("--family", choices=(*FAMILIES, "all"), required=True)
    args = parser.parse_args(argv)
    project = args.project_dir.resolve()
    if args.command == "resolve":
        result = resolve_inputs(project)
        path = project / args.out
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    elif args.command == "build":
        import re

        path = project / args.inputs
        if not path.exists():
            parser.error("Resolve inputs first: font-match resolve")
        resolved = json.loads(path.read_text())
        args.version = args.version or resolved.get("version", "1.001")
        if not re.fullmatch(r"\d+\.\d{3}", args.version):
            parser.error("Version must be numeric, for example 1.001")
        for family_id in FAMILIES if args.family == "all" else [args.family]:
            build_family(
                project,
                family_id,
                resolved,
                args.version,
                project / args.out_dir if args.out_dir else None,
            )
    elif args.command == "verify":
        assets = []
        for family_id in FAMILIES if args.family == "all" else [args.family]:
            family = load_family(project, family_id)
            assets.extend(validate(family, project / "dist" / family_id))
        (project / "dist" / "SHA256SUMS").write_text(
            "".join(f"{sha256(p.read_bytes())}  {p.name}\n" for p in assets),
            encoding="utf-8",
        )
