import json

import pytest

from font_match import release


def test_readme_only_change_does_not_change_build_identity(tmp_path):
    for name in (
        "pyproject.toml",
        "pixi.lock",
        ".github/workflows/weekly_font_release.yml",
    ):
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("build configuration")
    source = tmp_path / "src/font_match/build.py"
    source.parent.mkdir(parents=True)
    source.write_text("build code")
    first = release.fingerprint(tmp_path, {"revision": "one"})
    (tmp_path / "README.md").write_text("documentation only")
    assert release.fingerprint(tmp_path, {"revision": "one"}) == first
    source.write_text("corrected build code")
    assert release.fingerprint(tmp_path, {"revision": "one"}) != first


@pytest.fixture
def release_state(tmp_path, monkeypatch):
    from pathlib import Path
    import shutil

    shutil.copytree(Path.cwd() / "families", tmp_path / "families")
    hashes = {fid: {s: fid + s for s in release.STYLES} for fid in release.FAMILIES}
    manifests = {
        fid: {
            "family": fid,
            "version": "1.002",
            "inputs": {
                "tinos": {"revision": "same", "version": "1.340"},
                "nimbus": {"version": "20200910"},
                "termes": {"version": "2.004"},
            },
            "build_code_fingerprint": "changed-code",
            "styles": {s: {"source_sha256": h} for s, h in values.items()},
        }
        for fid, values in hashes.items()
    }
    releases = [
        {
            "tag_name": "v1.002",
            "draft": False,
            "prerelease": False,
            "assets": [
                {
                    "name": f"{release.load_family(tmp_path, fid).prefix}-BUILD-INFO.json",
                    "browser_download_url": fid,
                }
                for fid in release.FAMILIES
            ],
        }
    ]
    monkeypatch.setattr(
        release,
        "resolve_inputs",
        lambda p: {
            "inputs": {
                "tinos": {"revision": "same", "version": "1.340"},
                "nimbus": {"version": "20200910"},
                "termes": {"version": "2.004"},
            }
        },
    )
    monkeypatch.setattr(release, "fingerprint", lambda p, i: "changed-code")
    monkeypatch.setattr(release, "git", lambda *a: "commit")
    monkeypatch.setattr(release, "source_hashes", lambda p, f, i: hashes[f.id])
    monkeypatch.setattr(
        release, "fetch_json", lambda u: manifests[u] if u in manifests else releases
    )
    return hashes, manifests, releases


@pytest.mark.parametrize(
    "changed", [(), ("nimbus-match",), ("termes-match",), release.FAMILIES]
)
def test_only_changed_outline_families_release(
    tmp_path, capsys, release_state, changed
):
    hashes, _, _ = release_state
    for fid in changed:
        hashes[fid]["Regular"] = "new-source"
    release.prepare(tmp_path)
    result = json.loads(capsys.readouterr().out)
    assert json.loads(result["families"]) == list(changed)
    assert result["should_build"] == str(bool(changed)).lower()
    for fid in changed:
        plan = json.loads((tmp_path / "build_temp" / f"{fid}-inputs.json").read_text())
        assert plan["publish"] is True
        assert plan["tag"] == (
            "tinos-1.340-nimbus-20200910-1"
            if fid == "nimbus-match"
            else "tinos-1.340-termes-2.004-1"
        )
        assert plan["font_revision"] == "1.003"


def test_force_unchanged_is_development_only(
    tmp_path, capsys, release_state, monkeypatch
):
    release.prepare(tmp_path, force=True)
    assert json.loads(json.loads(capsys.readouterr().out)["families"]) == list(
        release.FAMILIES
    )
    monkeypatch.setattr(
        release, "gh", lambda *a: pytest.fail("No remote writes allowed")
    )
    for fid in release.FAMILIES:
        plan = json.loads((tmp_path / "build_temp" / f"{fid}-inputs.json").read_text())
        assert plan["publish"] is False
        release.publish(tmp_path, fid)


def test_selected_family_does_not_release_other_changed_family(
    tmp_path, capsys, release_state
):
    hashes, _, _ = release_state
    hashes["nimbus-match"]["Regular"] = "new"
    hashes["termes-match"]["Regular"] = "new"
    release.prepare(tmp_path, family="termes-match")
    assert json.loads(json.loads(capsys.readouterr().out)["families"]) == [
        "termes-match"
    ]


def test_independent_history_and_draft_version(tmp_path, capsys, release_state):
    hashes, manifests, releases = release_state
    hashes["nimbus-match"]["Regular"] = "new"
    hashes["termes-match"]["Regular"] = "new"
    manifests["nimbus-match"]["version"] = "1.009"
    releases.insert(
        0,
        {
            "tag_name": "tinos-1.340-nimbus-20200910-9",
            "draft": False,
            "prerelease": False,
            "assets": [releases[0]["assets"][0]],
        },
    )
    releases.insert(
        0,
        {
            "tag_name": "tinos-1.340-termes-2.004-7",
            "draft": True,
            "body": "Build identity: termes-match / commit / changed-code",
        },
    )
    release.prepare(tmp_path)
    capsys.readouterr()
    for fid, version in (
        ("nimbus-match", "1.340-20200910-10"),
        ("termes-match", "1.340-2.004-7"),
    ):
        plan = json.loads((tmp_path / "build_temp" / f"{fid}-inputs.json").read_text())
        assert plan["version"] == version


def test_release_history_is_paginated(monkeypatch):
    urls = []

    def fetch(url):
        urls.append(url)
        return [{}] * 100 if len(urls) == 1 else [{"older": True}]

    monkeypatch.setattr(release, "fetch_json", fetch)
    assert len(release.list_releases("example/fonts")) == 101
    assert urls[-1].endswith("page=2")


def test_api_failure_is_not_a_missing_release(tmp_path, monkeypatch):
    def failed(url):
        raise OSError("authentication/network failure")

    monkeypatch.setattr(release, "fetch_json", failed)
    with pytest.raises(OSError):
        release.prepare(tmp_path)


def test_source_identity_ignores_archive_only_changes(tmp_path):
    import io
    import zipfile
    from types import SimpleNamespace

    family = SimpleNamespace(
        provider="termes", id="termes-match", sources={"Regular": "termes.otf"}
    )
    identities = []
    for unrelated in (b"old other font", b"new other font"):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("termes.otf", b"unchanged Termes font")
            archive.writestr("other.otf", unrelated)
        data = stream.getvalue()
        digest = release.sha256(data)
        path = tmp_path / "build_temp/archives" / (digest + ".zip")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        identities.append(
            release.source_hashes(tmp_path, family, {"termes": {"sha256": digest}})
        )
    assert identities[0] == identities[1]


def test_github_json_preserves_utf8_on_legacy_windows_locale(tmp_path, monkeypatch):
    payload = json.dumps(
        {"sha": "commit", "message": "Release č"}, ensure_ascii=False
    ).encode("utf-8")

    def windows_output(command, **options):
        # Model the real failure: gh emits UTF-8 while Windows defaults to cp1252.
        return payload.decode(options.get("encoding", "cp1252"))

    monkeypatch.setattr(release.subprocess, "check_output", windows_output)
    result = json.loads(
        release.gh(tmp_path, "api", "repos/example/fonts/commits/v1.001")
    )
    assert result == {"sha": "commit", "message": "Release č"}


@pytest.mark.parametrize("family_id", release.FAMILIES)
def test_publisher_uploads_only_selected_family(
    tmp_path, monkeypatch, release_state, family_id
):
    from font_match import upstream
    from font_match.artifacts import asset_names

    hashes, _, _ = release_state
    hashes[family_id]["Regular"] = "new"
    release.prepare(tmp_path, family=family_id)
    plan = json.loads(
        (tmp_path / "build_temp" / f"{family_id}-inputs.json").read_text()
    )
    family = release.load_family(tmp_path, family_id)
    output = tmp_path / "dist" / family_id
    output.mkdir(parents=True)
    for name in asset_names(family):
        (output / name).write_bytes(name.encode())
    (output / f"{family.prefix}-BUILD-INFO.json").write_text(
        json.dumps(
            {
                **plan,
                "styles": {
                    s: {"source_sha256": h} for s, h in hashes[family_id].items()
                },
            }
        )
    )
    validated = []

    def validate(config, folder):
        assert config.id == family_id
        paths = [folder / name for name in asset_names(config)]
        assert all(p.is_file() for p in paths)
        validated.append(folder)
        return paths

    monkeypatch.setattr(release, "validate", validate)
    remote = {}
    calls = []

    def gh(project, *args):
        calls.append(args)
        if args[:2] == ("release", "upload"):
            assert args[2] == plan["tag"]
            for path in args[3:-1]:
                p = __import__("pathlib").Path(path)
                remote[p.name] = p.read_bytes()
        elif args[:2] == ("release", "download"):
            folder = __import__("pathlib").Path(args[-1])
            for name, data in remote.items():
                (folder / name).write_bytes(data)
        elif args[:2] == ("release", "view"):
            return json.dumps(
                {
                    "assets": [{"name": name} for name in remote],
                    "isDraft": False,
                    "url": "public",
                }
            )
        elif args[0] == "api":
            return json.dumps({"sha": "commit"})
        return ""

    monkeypatch.setattr(release, "gh", gh)
    monkeypatch.setattr(upstream, "download", lambda url: remote[url.rsplit("/", 1)[1]])
    release.publish(tmp_path, family_id)
    assert set(remote) == set(asset_names(family)) | {"SHA256SUMS"}
    notes = (tmp_path / "build_temp/release-notes.md").read_text(encoding="utf-8")
    assert "Times New Roman metric-compatible" in notes
    assert f"Tinos: **{plan['inputs']['tinos']['version']}**" in notes
    assert f"**{plan['inputs'][family.provider]['version']}**" in notes
    assert plan["tag"] in notes and plan["version"] in notes
    assert f"{family.prefix}-LICENSE.txt" in notes
    assert len(validated) == 3
    assert ("release", "edit", plan["tag"], "--draft=false", "--latest=false") in calls
    checks = {
        name: digest
        for digest, name in (
            line.split("  ") for line in remote["SHA256SUMS"].decode().splitlines()
        )
    }
    assert checks == {
        name: release.sha256(data)
        for name, data in remote.items()
        if name != "SHA256SUMS"
    }


@pytest.mark.parametrize("dependency", ["tinos", "code", "legacy-manifest"])
def test_shared_dependency_change_releases_both(
    tmp_path, capsys, release_state, dependency
):
    _, manifests, _ = release_state
    for manifest in manifests.values():
        if dependency == "tinos":
            manifest["inputs"]["tinos"]["revision"] = "old"
        elif dependency == "code":
            manifest["build_code_fingerprint"] = "old-code"
        else:
            del manifest["build_code_fingerprint"]
    release.prepare(tmp_path)
    assert json.loads(json.loads(capsys.readouterr().out)["families"]) == list(
        release.FAMILIES
    )
    for fid in release.FAMILIES:
        plan = json.loads((tmp_path / "build_temp" / f"{fid}-inputs.json").read_text())
        assert plan["publish"] is True
        assert plan["build_code_fingerprint"] == "changed-code"


def test_shared_change_remains_pending_for_unreleased_family(
    tmp_path, capsys, release_state
):
    _, manifests, _ = release_state
    manifests["termes-match"]["build_code_fingerprint"] = "old-code"
    release.prepare(tmp_path)
    assert json.loads(json.loads(capsys.readouterr().out)["families"]) == [
        "termes-match"
    ]


@pytest.mark.parametrize("changed_provider", ["tinos", "nimbus"])
def test_increment_resets_for_new_upstream_pair(
    tmp_path, capsys, release_state, monkeypatch, changed_provider
):
    hashes, manifests, releases = release_state
    import copy

    current = copy.deepcopy(manifests["nimbus-match"]["inputs"])
    current[changed_provider]["version"] = "9.999"
    monkeypatch.setattr(release, "resolve_inputs", lambda p: {"inputs": current})
    hashes["nimbus-match"]["Regular"] = "new"
    releases.insert(
        0,
        {
            "tag_name": "tinos-1.340-nimbus-20200910-12",
            "draft": True,
            "body": "unrelated",
        },
    )
    release.prepare(tmp_path, family="nimbus-match")
    plan = json.loads((tmp_path / "build_temp/nimbus-match-inputs.json").read_text())
    assert plan["version"].endswith("-1")
    assert "9.999" in plan["tag"]
    assert plan["font_revision"] == "1.003"


def test_newer_family_release_wins_over_global_latest(tmp_path, release_state):
    import copy

    _, manifests, releases = release_state
    releases[0]["published_at"] = "2026-09-10T15:25:18Z"
    later = copy.deepcopy(manifests["nimbus-match"])
    later["version"] = "1.003"
    manifests["later"] = later
    releases.append(
        {
            "tag_name": "nimbus-match-v1.003",
            "draft": False,
            "prerelease": False,
            "published_at": "2026-09-10T18:58:47Z",
            "assets": [
                {"name": "NimbusMatch-BUILD-INFO.json", "browser_download_url": "later"}
            ],
        }
    )
    assert (
        release.latest_manifest(
            releases, release.load_family(tmp_path, "nimbus-match")
        )["version"]
        == "1.003"
    )
