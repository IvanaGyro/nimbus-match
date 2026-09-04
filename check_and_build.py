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
from pathlib import Path

from build_nimbus_match import build_single_style
from generate_comparison import generate_comparison_image

NIMBUS_REPO = "ArtifexSoftware/urw-base35-fonts"
LIBERATION_REPO = "liberationfonts/liberation-fonts"


def fetch_json(url: str) -> dict | list:
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0)"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_latest_upstream_versions() -> tuple[str, str]:
    """Fetch latest release tags for Nimbus Roman (urw-base35) and Liberation Fonts."""
    print("Fetching latest release info from GitHub API...")

    # 1. Nimbus Roman
    nimbus_data = fetch_json(f"https://api.github.com/repos/{NIMBUS_REPO}/releases")
    if not nimbus_data:
        raise RuntimeError("No releases found for URW Base35 fonts")
    nimbus_tag = nimbus_data[0]["tag_name"]

    # 2. Liberation Fonts
    lib_data = fetch_json(f"https://api.github.com/repos/{LIBERATION_REPO}/releases")
    if not lib_data:
        raise RuntimeError("No releases found for Liberation fonts")
    lib_tag = lib_data[0]["tag_name"]

    return nimbus_tag, lib_tag


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
    except Exception:
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


def extract_liberation_fonts(lib_tag: str, target_dir: Path) -> dict[str, Path]:
    """Download and extract Liberation Serif TTF files."""
    extracted: dict[str, Path] = {}
    mapping = {
        "LiberationSerif-Regular.ttf": "Regular",
        "LiberationSerif-Bold.ttf": "Bold",
        "LiberationSerif-Italic.ttf": "Italic",
        "LiberationSerif-BoldItalic.ttf": "BoldItalic",
    }

    # Attempt 1: Debian package feed
    deb_urls = [
        f"http://ftp.debian.org/debian/pool/main/f/fonts-liberation2/fonts-liberation2_{lib_tag}-1_all.deb",
        f"http://ftp.debian.org/debian/pool/main/f/fonts-liberation2/fonts-liberation2_{lib_tag}-2_all.deb",
        "https://archlinux.org/packages/extra/any/ttf-liberation/download/",
    ]

    for deb_url in deb_urls:
        try:
            content = download_bytes(deb_url)
            # Try tar or deb parsing
            if deb_url.endswith(".deb"):
                # Parse AR format deb
                offset = 8
                data_tar = None
                while offset < len(content):
                    header = content[offset : offset + 60]
                    if len(header) < 60:
                        break
                    name = header[:16].decode("ascii", errors="ignore").strip()
                    size = int(header[48:58].decode("ascii", errors="ignore").strip())
                    offset += 60
                    file_data = content[offset : offset + size]
                    if name.startswith("data.tar"):
                        data_tar = file_data
                        break
                    offset += size
                    if offset % 2 != 0:
                        offset += 1
                if data_tar:
                    with tarfile.open(fileobj=io.BytesIO(data_tar), mode="r:*") as tar:
                        for m in tar.getmembers():
                            base_name = Path(m.name).name
                            if base_name in mapping:
                                style_key = mapping[base_name]
                                out_path = target_dir / base_name
                                out_path.write_bytes(tar.extractfile(m).read())
                                extracted[style_key] = out_path
                                print(
                                    f" Extracted Liberation [{style_key}]: {base_name}"
                                )
            else:
                # Arch package tar.zst or tar.xz
                with tarfile.open(fileobj=io.BytesIO(content), mode="r:*") as tar:
                    for m in tar.getmembers():
                        base_name = Path(m.name).name
                        if base_name in mapping:
                            style_key = mapping[base_name]
                            out_path = target_dir / base_name
                            out_path.write_bytes(tar.extractfile(m).read())
                            extracted[style_key] = out_path
                            print(f" Extracted Liberation [{style_key}]: {base_name}")
            if len(extracted) == 4:
                break
        except Exception as e:
            print(f" Failed download from {deb_url}: {e}")

    # Fallback to direct raw github copies if package feed is unavailable
    if len(extracted) < 4:
        print("Falling back to GitHub raw download for Liberation Serif...")
        base_raw = "https://raw.githubusercontent.com/shantigilbert/liberation-fonts-ttf/master/"
        for filename, style_key in mapping.items():
            if style_key not in extracted:
                content = download_bytes(f"{base_raw}{filename}")
                out_path = target_dir / filename
                out_path.write_bytes(content)
                extracted[style_key] = out_path
                print(f" Downloaded Liberation raw [{style_key}]: {filename}")

    if len(extracted) < 4:
        raise RuntimeError(
            f"Failed to extract all 4 Liberation Serif styles (found {len(extracted)}/4)"
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
        "--force", action="store_true", help="Force build even if release tag exists"
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

    nimbus_tag, lib_tag = get_latest_upstream_versions()
    release_tag = f"v{lib_tag}-{nimbus_tag}"
    release_title = f"Nimbus Match v{lib_tag}-{nimbus_tag}"

    print(f"Upstream versions: Liberation Fonts={lib_tag}, Nimbus Roman={nimbus_tag}")
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
    set_github_output("liberation_version", lib_tag)

    print("\n1. Extracting upstream Nimbus Roman fonts...")
    nimbus_files = extract_nimbus_fonts(nimbus_tag, work_dir)

    print("\n2. Extracting upstream Liberation Serif fonts...")
    lib_files = extract_liberation_fonts(lib_tag, work_dir)

    print("\n3. Building Nimbus Match fonts for 4 styles...")
    styles = ["Regular", "Bold", "Italic", "BoldItalic"]
    for style in styles:
        nim_otf = nimbus_files[style]
        lib_ttf = lib_files[style]
        out_otf = out_dir / f"NimbusMatch-{style}.otf"
        build_single_style(nim_otf, lib_ttf, out_otf, style)

    print("\n4. Generating visual comparison image...")
    # Copy reference fonts to out_dir for comparison generator
    for filename in [
        "LiberationSerif-Regular.ttf",
        "LiberationSerif-Bold.ttf",
        "LiberationSerif-Italic.ttf",
        "LiberationSerif-BoldItalic.ttf",
    ]:
        if (work_dir / filename).exists():
            (out_dir / filename).write_bytes((work_dir / filename).read_bytes())

    comparison_img = out_dir / "nimbus_match_comparison.png"
    generate_comparison_image(out_dir, comparison_img)

    # Clean up intermediate reference files from dist directory so release contains only output OTF + PNG
    for filename in [
        "LiberationSerif-Regular.ttf",
        "LiberationSerif-Bold.ttf",
        "LiberationSerif-Italic.ttf",
        "LiberationSerif-BoldItalic.ttf",
    ]:
        ref_file = out_dir / filename
        if ref_file.exists():
            ref_file.unlink()

    print("\nBuild complete! Output files:")
    for p in out_dir.iterdir():
        print(f" - {p.name} ({p.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
