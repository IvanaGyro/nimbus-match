"""Resolve once, download exact inputs, and verify every cached byte."""

from __future__ import annotations

import hashlib
import io
import json
import os
import urllib.request
import zipfile
from pathlib import Path

from fontTools.ttLib import TTFont

NIMBUS_REPO = "ArtifexSoftware/urw-base35-fonts"
TINOS_REPO = "googlefonts/tinos"
TERMES_URL = "https://ctan.math.illinois.edu/fonts/tex-gyre.zip"


def download(url):
    request = urllib.request.Request(url, headers={"User-Agent": "font-match"})
    if url.startswith("https://api.github.com/") and os.environ.get("GITHUB_TOKEN"):
        request.add_header("Authorization", "Bearer " + os.environ["GITHUB_TOKEN"])
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def fetch_json(url):
    return json.loads(download(url))


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def resolve_inputs(project):
    tinos = fetch_json(f"https://api.github.com/repos/{TINOS_REPO}/commits/main")["sha"]
    release = fetch_json(f"https://api.github.com/repos/{NIMBUS_REPO}/releases/latest")
    nimbus = fetch_json(
        f"https://api.github.com/repos/{NIMBUS_REPO}/commits/{release['tag_name']}"
    )["sha"]
    definitions = {
        "tinos": {
            "revision": tinos,
            "url": f"https://codeload.github.com/{TINOS_REPO}/zip/{tinos}",
        },
        "nimbus": {
            "revision": nimbus,
            "description": release["tag_name"],
            "url": f"https://codeload.github.com/{NIMBUS_REPO}/zip/{nimbus}",
        },
        "termes": {"revision": "2.004", "url": TERMES_URL},
    }
    for provider, definition in definitions.items():
        content = download(definition["url"])
        if provider == "termes":
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                versions = set()
                for style in ("regular", "bold", "italic", "bolditalic"):
                    member = f"tex-gyre/opentype/texgyretermes-{style}.otf"
                    with TTFont(io.BytesIO(archive.read(member))) as font:
                        versions.add(font["CFF "].cff.topDictIndex[0].version)
                if len(versions) != 1:
                    raise ValueError(
                        "Termes styles have inconsistent upstream versions"
                    )
                definition["revision"] = versions.pop()
        definition["sha256"] = sha256(content)
        cache = project / "build_temp" / "archives" / (definition["sha256"] + ".zip")
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(content)
    return {"schema": 1, "inputs": definitions}


def extract(project: Path, definition: dict, filenames: list[str], provider: str):
    digest = definition["sha256"]
    cache = project / "build_temp" / "archives" / (digest + ".zip")
    content = cache.read_bytes() if cache.exists() else download(definition["url"])
    if sha256(content) != digest:
        raise ValueError(
            f"Pinned {provider} input checksum changed: {definition['url']}"
        )
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(content)
    output = project / "build_temp" / provider / digest
    output.mkdir(parents=True, exist_ok=True)
    result = {}
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for filename in filenames:
            matches = [n for n in archive.namelist() if Path(n).name == filename]
            if len(matches) != 1:
                raise ValueError(f"Expected exactly one {filename}, found {matches}")
            path = output / filename
            path.write_bytes(archive.read(matches[0]))
            result[filename] = path
    return result
