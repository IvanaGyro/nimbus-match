"""Combined release preparation and verified draft publication."""

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from .artifacts import validate
from .cli import FAMILIES
from .config import load_family
from .upstream import fetch_json, resolve_inputs, sha256


def git(project, *args):
    return subprocess.check_output(["git", *args], cwd=project, text=True).strip()


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
    return subprocess.check_output(["gh", *args], cwd=project, text=True).strip()


def prepare(project, force=False, family="all"):
    repo = os.environ.get("GITHUB_REPOSITORY", "IvanaGyro/nimbus-match")
    # A successful empty list means no releases. API/auth/network errors propagate.
    releases = fetch_json(f"https://api.github.com/repos/{repo}/releases?per_page=100")
    resolved = resolve_inputs(project)
    digest = fingerprint(project, resolved["inputs"])
    public = next((r for r in releases if not r["draft"] and not r["prerelease"]), None)
    previous = None
    if public:
        asset = next(
            (a for a in public["assets"] if a["name"] == "NimbusMatch-BUILD-INFO.json"),
            None,
        )
        if asset:
            previous = fetch_json(asset["browser_download_url"]).get(
                "build_fingerprint"
            )
    versions = [
        int(m[1])
        for r in releases
        if (m := re.fullmatch(r"v1\.(\d{3})", r["tag_name"]))
    ]
    version = f"1.{max(versions, default=0) + 1:03d}"
    commit = git(project, "rev-parse", "HEAD")
    marker = f"Build identity: {commit} / {digest}"
    matching_draft = next(
        (
            r
            for r in releases
            if r["draft"]
            and marker in (r["body"] or "")
            and re.fullmatch(r"v1\.\d{3}", r["tag_name"])
        ),
        None,
    )
    if matching_draft:
        version = matching_draft["tag_name"][1:]
    should_build = force or family != "all" or previous != digest
    result = {
        **resolved,
        "version": version,
        "commit": commit,
        "build_fingerprint": digest,
        "publish": family == "all",
    }
    path = project / "build_temp/inputs.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n")
    values = {
        "should_build": str(should_build).lower(),
        "version": version,
        "families": json.dumps(list(FAMILIES) if family == "all" else [family]),
        "publish": str(family == "all").lower(),
    }
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.writelines(f"{k}={v}\n" for k, v in values.items())
    print(json.dumps(values))


def publish(project):
    repo = os.environ.get("GITHUB_REPOSITORY", "IvanaGyro/nimbus-match")
    inputs = json.loads((project / "build_temp/inputs.json").read_text())
    if not inputs.get("publish"):
        raise ValueError("A public release requires both families")
    if git(project, "rev-parse", "HEAD") != inputs["commit"]:
        raise ValueError("Checkout differs from tested release commit")
    if fingerprint(project, inputs["inputs"]) != inputs["build_fingerprint"]:
        raise ValueError("Build code/configuration changed after preparation")
    assets = []
    for family_id in FAMILIES:
        family = load_family(project, family_id)
        assets.extend(validate(family, project / "dist" / family_id))
        info = json.loads(
            (
                project / "dist" / family_id / f"{family.prefix}-BUILD-INFO.json"
            ).read_text()
        )
        for key in ("version", "commit", "build_fingerprint"):
            if info[key] != inputs[key]:
                raise ValueError(f"Mismatched {key} in {family_id}")
    sums = project / "dist/SHA256SUMS"
    sums.write_text("".join(f"{sha256(p.read_bytes())}  {p.name}\n" for p in assets))
    assets.append(sums)
    tag = "v" + inputs["version"]
    releases = json.loads(gh(project, "api", f"repos/{repo}/releases?per_page=100"))
    existing = next((r for r in releases if r["tag_name"] == tag), None)
    marker = f"Build identity: {inputs['commit']} / {inputs['build_fingerprint']}"
    if existing and (not existing["draft"] or marker not in (existing["body"] or "")):
        raise ValueError("Refusing to overwrite a published release or unrelated draft")
    if existing and existing["target_commitish"] != inputs["commit"]:
        raise ValueError("Matching draft targets a different commit")
    notes = project / "build_temp/release-notes.md"
    notes.write_text(
        f"""Nimbus Match and Termes Match {inputs["version"]}

Each family contains Regular, Bold, Italic and Bold Italic.
Install its ZIP's four OTFs OR its OTC; choose one format.
Individual OTF/OTC downloads require the corresponding NOTICES asset.
The BUILD-INFO assets record source identities, policies and coverage limits.
Native feature-alternate metrics are not guaranteed to match Times New Roman.

[Nimbus Match notices](https://github.com/{repo}/releases/download/{tag}/NimbusMatch-NOTICES.txt)
[Termes Match notices](https://github.com/{repo}/releases/download/{tag}/TermesMatch-NOTICES.txt)

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
            f"Font Match {inputs['version']}",
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
        for family_id in FAMILIES:
            validate(load_family(project, family_id), remote)
    gh(project, "release", "edit", tag, "--draft=false", "--latest")
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
        for family_id in FAMILIES:
            validate(load_family(project, family_id), remote)
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
        publish(Path.cwd())


if __name__ == "__main__":
    main()
