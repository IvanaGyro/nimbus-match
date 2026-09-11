"""Independent upstream-triggered family releases and verified publication."""

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from .artifacts import validate
from .cli import FAMILIES
from .config import STYLES, load_family
from .upstream import extract, fetch_json, resolve_inputs, sha256


def git(project, *args):
    return subprocess.check_output(
        ["git", *args], cwd=project, text=True, encoding="utf-8"
    ).strip()


def fingerprint(project, inputs):
    paths = sorted(
        [
            *(project / "src").rglob("*.py"),
            *(project / "families").rglob("family.toml"),
            *(project / "families").rglob("licenses/*.txt"),
            project / "pyproject.toml",
            project / "pixi.lock",
            project / ".github/workflows/weekly_font_release.yml",
        ]
    )
    return sha256(
        json.dumps(inputs, sort_keys=True).encode()
        + b"".join(
            p.relative_to(project).as_posix().encode()
            + p.read_bytes().replace(b"\r\n", b"\n")
            for p in paths
        )
    )


def gh(project, *args):
    return subprocess.check_output(
        ["gh", *args], cwd=project, text=True, encoding="utf-8"
    ).strip()


def list_releases(repo):
    releases = []
    page = 1
    while True:
        batch = fetch_json(
            f"https://api.github.com/repos/{repo}/releases?per_page=100&page={page}"
        )
        releases.extend(batch)
        if len(batch) < 100:
            return releases
        page += 1


def source_hashes(project, family, inputs):
    sources = extract(
        project, inputs[family.provider], list(family.sources.values()), family.id
    )
    return {
        style: sha256(sources[name].read_bytes())
        for style, name in family.sources.items()
    }


def latest_manifest(releases, family):
    # GitHub may return its designated latest release ahead of newer family
    # releases. Baselines follow publication time, not API list position.
    for release in sorted(
        releases, key=lambda r: r.get("published_at") or "", reverse=True
    ):
        if release["draft"] or release["prerelease"]:
            continue
        for asset in release["assets"]:
            if asset["name"] == f"{family.prefix}-BUILD-INFO.json":
                info = fetch_json(asset["browser_download_url"])
                if info["family"] != family.id or set(info["styles"]) != set(STYLES):
                    raise ValueError("Invalid published family manifest")
                return info
    return None


def prepare(project, force=False, family="all"):
    repo = os.environ.get("GITHUB_REPOSITORY", "IvanaGyro/nimbus-match")
    releases = list_releases(repo)
    resolved = resolve_inputs(project)
    shared = project / "build_temp/inputs.json"
    shared.parent.mkdir(parents=True, exist_ok=True)
    shared.write_text(json.dumps(resolved, indent=2) + "\n", encoding="utf-8")
    digest = fingerprint(project, resolved["inputs"])
    code_digest = fingerprint(project, {})
    commit = git(project, "rev-parse", "HEAD")
    selected = []
    for family_id in FAMILIES if family == "all" else [family]:
        config = load_family(project, family_id)
        current = source_hashes(project, config, resolved["inputs"])
        previous = latest_manifest(releases, config)
        changed = previous is None or current != {
            style: report["source_sha256"]
            for style, report in previous["styles"].items()
        }
        # Compare shared dependencies against each family's own last release so a
        # successful release of one family cannot consume the other's update.
        if previous is not None:
            changed |= previous.get("build_code_fingerprint") != code_digest or any(
                previous["inputs"]["tinos"].get(key)
                != resolved["inputs"]["tinos"].get(key)
                for key in ("revision", "sha256")
            )
        if not changed and not force:
            continue
        tinos_version = resolved["inputs"]["tinos"]["version"]
        source_version = resolved["inputs"][config.provider]["version"]
        for token in (tinos_version, source_version):
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*", token):
                raise ValueError(f"Unsafe upstream version: {token}")
        stem = f"tinos-{tinos_version}-{config.provider}-{source_version}"
        pattern = re.compile(rf"{re.escape(stem)}-(\d+)")
        increments = [
            int(m[1]) for r in releases if (m := pattern.fullmatch(r["tag_name"]))
        ]
        increment = max(increments, default=0) + 1
        # Numeric OpenType revisions stay monotonic across upstream version pairs.
        old_revision = (
            previous.get("font_revision", previous["version"]) if previous else "1.000"
        )
        number = int(old_revision.replace(".", "")) + 1
        font_revision = f"{number // 1000}.{number % 1000:03d}"
        marker = f"Build identity: {family_id} / {commit} / {digest}"
        draft = next(
            (
                r
                for r in releases
                if r["draft"]
                and marker in (r["body"] or "")
                and pattern.fullmatch(r["tag_name"])
            ),
            None,
        )
        if draft:
            increment = int(pattern.fullmatch(draft["tag_name"])[1])
        version = f"{tinos_version}-{source_version}-{increment}"
        result = {
            **resolved,
            "family": family_id,
            "version": version,
            "tag": f"{stem}-{increment}",
            "font_revision": font_revision,
            "commit": commit,
            "build_fingerprint": digest,
            "build_code_fingerprint": code_digest,
            "source_hashes": current,
            "publish": changed,
        }
        path = project / "build_temp" / f"{family_id}-inputs.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        selected.append(family_id)
    values = {
        "should_build": str(bool(selected)).lower(),
        "families": json.dumps(selected),
    }
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.writelines(f"{k}={v}\n" for k, v in values.items())
    print(json.dumps(values))


def publish(project, family_id):
    repo = os.environ.get("GITHUB_REPOSITORY", "IvanaGyro/nimbus-match")
    inputs = json.loads(
        (project / "build_temp" / f"{family_id}-inputs.json").read_text()
    )
    if inputs["family"] != family_id:
        raise ValueError("Prepared family differs from requested family")
    if not inputs.get("publish"):
        print("Sources and build code unchanged; development artifacts only.")
        return
    if git(project, "rev-parse", "HEAD") != inputs["commit"]:
        raise ValueError("Checkout differs from tested release commit")
    if fingerprint(project, inputs["inputs"]) != inputs["build_fingerprint"]:
        raise ValueError("Build code/configuration changed after preparation")
    assets = []
    family = load_family(project, family_id)
    assets.extend(validate(family, project / "dist" / family_id))
    info = json.loads(
        (project / "dist" / family_id / f"{family.prefix}-BUILD-INFO.json").read_text()
    )
    for key in (
        "version",
        "font_revision",
        "commit",
        "build_fingerprint",
        "build_code_fingerprint",
    ):
        if info[key] != inputs[key]:
            raise ValueError(f"Mismatched {key} in {family_id}")
    if {s: r["source_sha256"] for s, r in info["styles"].items()} != inputs[
        "source_hashes"
    ]:
        raise ValueError("Built sources differ from prepared sources")
    sums = project / "dist" / family_id / "SHA256SUMS"
    sums.write_text("".join(f"{sha256(p.read_bytes())}  {p.name}\n" for p in assets))
    assets.append(sums)
    tag = inputs["tag"]
    tinos_version = inputs["inputs"]["tinos"]["version"]
    source_version = inputs["inputs"][family.provider]["version"]
    increment = inputs["version"].rsplit("-", 1)[1]
    if tag != f"tinos-{tinos_version}-{family.provider}-{source_version}-{increment}":
        raise ValueError("Invalid prepared family tag")
    releases = list_releases(repo)
    existing = next((r for r in releases if r["tag_name"] == tag), None)
    marker = f"Build identity: {family_id} / {inputs['commit']} / {inputs['build_fingerprint']}"
    if existing and (not existing["draft"] or marker not in (existing["body"] or "")):
        raise ValueError("Refusing to overwrite a published release or unrelated draft")
    if existing and existing["target_commitish"] != inputs["commit"]:
        raise ValueError("Matching draft targets a different commit")
    notes = project / "build_temp/release-notes.md"
    notes.write_text(
        f"""{family.name} {inputs["version"]}

This family contains Regular, Bold, Italic and Bold Italic.
Install its ZIP's four OTFs OR its OTC; choose one format.
Individual OTF/OTC downloads require the corresponding NOTICES asset.
The BUILD-INFO assets record source identities, policies and coverage limits.
Native feature-alternate metrics are not guaranteed to match Times New Roman.

[{family.name} notices](https://github.com/{repo}/releases/download/{tag}/{family.prefix}-NOTICES.txt)

{marker}
""",
        encoding="utf-8",
    )
    if not existing:
        gh(
            project,
            "release",
            "create",
            tag,
            "--draft",
            "--target",
            inputs["commit"],
            "--title",
            f"{family.name} {inputs['version']}",
            "--notes-file",
            str(notes),
        )
    gh(project, "release", "upload", tag, *map(str, assets), "--clobber")
    release = json.loads(
        gh(project, "release", "view", tag, "--json", "assets,isDraft,url")
    )
    if {a["name"] for a in release["assets"]} != {p.name for p in assets}:
        raise ValueError("Uploaded assets differ from explicit allowlist")
    # Download and validate the actual remote files before making the draft public.
    with tempfile.TemporaryDirectory(dir=project / "build_temp") as temporary:
        remote = Path(temporary)
        gh(project, "release", "download", tag, "--dir", str(remote))
        for path in assets:
            if (remote / path.name).read_bytes() != path.read_bytes():
                raise ValueError(f"Remote checksum mismatch: {path.name}")
        validate(family, remote)
    gh(project, "release", "edit", tag, "--draft=false", "--latest=false")
    release = json.loads(gh(project, "release", "view", tag, "--json", "isDraft,url"))
    if release["isDraft"]:
        raise ValueError("Release is still a draft")
    target = json.loads(gh(project, "api", f"repos/{repo}/commits/{tag}"))["sha"]
    if target != inputs["commit"]:
        raise ValueError("Published tag points to unexpected commit")
    from .upstream import download

    with tempfile.TemporaryDirectory(dir=project / "build_temp") as temporary:
        remote = Path(temporary)
        for path in assets:
            content = download(
                f"https://github.com/{repo}/releases/download/{tag}/{path.name}"
            )
            if sha256(content) != sha256(path.read_bytes()):
                raise ValueError(f"Public download checksum mismatch: {path.name}")
            (remote / path.name).write_bytes(content)
        validate(family, remote)
    print(release["url"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "publish"])
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--family", choices=[*FAMILIES, "all"], default="all")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(Path.cwd(), args.force, args.family)
    else:
        if args.family == "all":
            parser.error("publish requires a single --family")
        publish(Path.cwd(), args.family)


if __name__ == "__main__":
    main()
