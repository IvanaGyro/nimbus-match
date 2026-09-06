#!/usr/bin/env python3
"""
Upstream release checker and build orchestrator for Nimbus Match fonts.

Dynamic fetcher: downloads upstream fonts without committing binaries to git.
Outputs GitHub Actions step parameters.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import tarfile
import urllib.request
import zipfile
from pathlib import Path

from fontTools.ttLib import TTCollection, TTFont

from build_nimbus_match import build_single_style
from generate_comparison import generate_comparison_image

NIMBUS_REPO = "ArtifexSoftware/urw-base35-fonts"
TINOS_REPO = "googlefonts/tinos"


def fetch_json(url: str) -> dict | list:
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0)"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_latest_upstream_versions() -> tuple[str, str]:
    """Fetch latest release tags for Nimbus Roman (urw-base35) and Tinos."""
    print("Fetching latest release info from GitHub API...")

    nimbus_data = fetch_json(f"https://api.github.com/repos/{NIMBUS_REPO}/releases")
    if not nimbus_data:
        raise RuntimeError("No releases found for URW Base35 fonts")
    nimbus_tag = nimbus_data[0]["tag_name"]

    try:
        tinos_data = fetch_json(f"https://api.github.com/repos/{TINOS_REPO}/releases")
        if tinos_data:
            tinos_tag = tinos_data[0]["tag_name"]
        else:
            commit_data = fetch_json(
                f"https://api.github.com/repos/{TINOS_REPO}/commits?per_page=1"
            )
            tinos_tag = commit_data[0]["sha"][:7] if commit_data else "main"
    except Exception as e:
        print(f"Warning: could not fetch Tinos release info ({e}), defaulting to main")
        tinos_tag = "main"

    return nimbus_tag, tinos_tag


def check_tag_exists_in_current_repo(tag_name: str) -> bool:
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        print("GITHUB_REPOSITORY not set; skipping repo tag check.")
        return False

    url = f"https://api.github.com/repos/{repo}/releases/tags/{tag_name}"
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0)"}
        )
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            req.add_header("Authorization", f"token {token}")
        with urllib.request.urlopen(req):
            return True
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        return False


def download_bytes(url: str) -> bytes:
    print(f"Downloading: {url}")
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0)"}
    )
    with urllib.request.urlopen(req) as resp:
        return resp.read()


def extract_nimbus_fonts(nimbus_tag: str, target_dir: Path) -> dict[str, Path]:
    """Download and extract Nimbus Roman OTF files."""
    url = f"https://github.com/{NIMBUS_REPO}/archive/refs/tags/{nimbus_tag}.tar.gz"
    content = download_bytes(url)

    extracted: dict[str, Path] = {}
    mapping = {
        "NimbusRoman-Regular.otf": "Regular",
        "NimbusRoman-Bold.otf": "Bold",
        "NimbusRoman-Italic.otf": "Italic",
        "NimbusRoman-BoldItalic.otf": "BoldItalic",
    }

    with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as tar:
        for m in tar.getmembers():
            base_name = Path(m.name).name
            if base_name in mapping:
                style_key = mapping[base_name]
                out_path = target_dir / base_name
                out_path.write_bytes(tar.extractfile(m).read())
                extracted[style_key] = out_path
                print(f" Extracted Nimbus [{style_key}]: {base_name}")

    if len(extracted) < 4:
        raise RuntimeError(
            f"Failed to extract all 4 Nimbus styles (found {len(extracted)}/4)"
        )
    return extracted


def extract_tinos_fonts(tinos_ver: str, target_dir: Path) -> dict[str, Path]:
    """Download Tinos TTF font files from upstream repository."""
    extracted: dict[str, Path] = {}
    mapping = {
        "Tinos-Regular.ttf": "Regular",
        "Tinos-Bold.ttf": "Bold",
        "Tinos-Italic.ttf": "Italic",
        "Tinos-BoldItalic.ttf": "BoldItalic",
    }

    base_raw = f"https://raw.githubusercontent.com/{TINOS_REPO}/main/fonts/ttf/"
    for filename, style_key in mapping.items():
        url = f"{base_raw}{filename}"
        content = download_bytes(url)
        out_path = target_dir / filename
        out_path.write_bytes(content)
        extracted[style_key] = out_path
        print(f" Downloaded Tinos [{style_key}]: {filename}")

    if len(extracted) < 4:
        raise RuntimeError(
            f"Failed to extract all 4 Tinos styles (found {len(extracted)}/4)"
        )
    return extracted


def set_github_output(name: str, value: str) -> None:
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")
    print(f"[GH OUTPUT] {name}={value}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Check upstream releases and build Nimbus Match fonts"
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Force build even if release tag exists",
    )
    ap.add_argument(
        "--work-dir",
        default="build_temp",
        help="Working directory for downloads and intermediate files",
    )
    ap.add_argument(
        "--out-dir", default="dist", help="Output directory for generated fonts"
    )
    args = ap.parse_args()

    work_dir = Path(args.work_dir)
    out_dir = Path(args.out_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    nimbus_tag, tinos_tag = get_latest_upstream_versions()
    release_tag = f"v{tinos_tag}-{nimbus_tag}"
    release_title = f"Nimbus Match v{tinos_tag}-{nimbus_tag}"

    print(f"Upstream versions: Tinos={tinos_tag}, Nimbus Roman={nimbus_tag}")
    print(f"Target Release Tag: {release_tag}")

    already_released = check_tag_exists_in_current_repo(release_tag)
    if already_released and not args.force:
        print(
            f"Release tag {release_tag} already exists in current repository. Skipping build."
        )
        set_github_output("should_release", "false")
        set_github_output("release_tag", release_tag)
        return

    set_github_output("should_release", "true")
    set_github_output("release_tag", release_tag)
    set_github_output("release_title", release_title)
    set_github_output("nimbus_version", nimbus_tag)
    set_github_output("tinos_version", tinos_tag)
    set_github_output("liberation_version", tinos_tag)

    print("\n1. Extracting upstream Nimbus Roman fonts...")
    nimbus_files = extract_nimbus_fonts(nimbus_tag, work_dir)

    print("\n2. Extracting upstream Tinos fonts...")
    tinos_files = extract_tinos_fonts(tinos_tag, work_dir)

    print("\n3. Building Nimbus Match fonts for 4 styles...")
    styles = ["Regular", "Bold", "Italic", "BoldItalic"]
    for style in styles:
        nim_otf = nimbus_files[style]
        tinos_ttf = tinos_files[style]
        out_otf = out_dir / f"NimbusMatch-{style}.otf"
        build_single_style(
            nim_otf, tinos_ttf, out_otf, style, version=f"{tinos_tag}-{nimbus_tag}"
        )

    print("\n4. Building OpenType Collection (NimbusMatch.otc)...")
    otc_path = out_dir / "NimbusMatch.otc"
    ttc = TTCollection()
    for style in styles:
        otf_file = out_dir / f"NimbusMatch-{style}.otf"
        if otf_file.exists():
            ttc.fonts.append(TTFont(otf_file))
    ttc.save(otc_path)
    for f in ttc.fonts:
        f.close()
    print(f" Successfully created {otc_path.name} ({otc_path.stat().st_size} bytes)")

    print("\n5. Generating visual comparison image...")
    ref_filenames = [
        "Tinos-Regular.ttf",
        "Tinos-Bold.ttf",
        "Tinos-Italic.ttf",
        "Tinos-BoldItalic.ttf",
    ]
    for filename in ref_filenames:
        if (work_dir / filename).exists():
            (out_dir / filename).write_bytes((work_dir / filename).read_bytes())

    comparison_img = out_dir / "nimbus_match_comparison.png"
    try:
        generate_comparison_image(out_dir, comparison_img)
    finally:
        for filename in ref_filenames:
            ref_file = out_dir / filename
            if ref_file.exists():
                ref_file.unlink()

    print("\n5. Packaging all font variants into NimbusMatch.zip...")
    zip_path = out_dir / "NimbusMatch.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for style in styles:
            otf_file = out_dir / f"NimbusMatch-{style}.otf"
            if otf_file.exists():
                zf.write(otf_file, arcname=otf_file.name)
    print(f" Successfully created {zip_path.name} ({zip_path.stat().st_size} bytes)")

    print("\nBuild complete! Output files:")
    for p in out_dir.iterdir():
        print(f" - {p.name} ({p.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
