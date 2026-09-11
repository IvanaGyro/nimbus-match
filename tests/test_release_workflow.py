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
    import shutil
    from pathlib import Path

    shutil.copytree(Path.cwd() / "families", tmp_path / "families")
    inputs = {
        "tinos": {"version": "1.340", "revision": "same"},
        "nimbus": {"version": "20200910"},
        "termes": {"version": "2.004"},
    }
    changed_code = {fid: False for fid in release.FAMILIES}
    releases = [
        {
            "tag_name": f"tinos-1.340-{provider}-{inputs[provider]['version']}-1",
            "draft": False,
            "prerelease": False,
            "published_at": "2026-09-11T01:00:00Z",
            "body": "Numeric OpenType revision: **1.004**.",
        }
        for provider in ("nimbus", "termes")
    ]
    monkeypatch.setattr(release, "resolve_inputs", lambda p: {"inputs": inputs})
    monkeypatch.setattr(release, "fingerprint", lambda p, i: "hash")
    monkeypatch.setattr(release, "git", lambda *a: "commit")
    monkeypatch.setattr(
        release,
        "code_changed",
        lambda p, tag: changed_code[
            "nimbus-match" if "-nimbus-" in tag else "termes-match"
        ],
    )
    monkeypatch.setattr(release, "fetch_json", lambda u: releases)
    return inputs, changed_code, releases


@pytest.mark.parametrize(
    "changed", [(), ("nimbus",), ("termes",), ("nimbus", "termes")]
)
def test_only_changed_upstream_versions_release(
    tmp_path, capsys, release_state, changed
):
    inputs, _, _ = release_state
    for provider in changed:
        inputs[provider]["version"] = "9.999"
    release.prepare(tmp_path)
    result = json.loads(capsys.readouterr().out)
    assert json.loads(result["families"]) == [p + "-match" for p in changed]
    for provider in changed:
        plan = json.loads(
            (tmp_path / "build_temp" / f"{provider}-match-inputs.json").read_text()
        )
        assert plan["publish"] is True
        assert plan["tag"] == f"tinos-1.340-{provider}-9.999-1"
        assert plan["font_revision"] == "1.005"


@pytest.mark.parametrize("dependency", ["tinos", "code"])
def test_shared_changes_release_both(tmp_path, capsys, release_state, dependency):
    inputs, changed_code, _ = release_state
    if dependency == "tinos":
        inputs["tinos"]["version"] = "1.350"
    else:
        changed_code.update({fid: True for fid in release.FAMILIES})
    release.prepare(tmp_path)
    assert json.loads(json.loads(capsys.readouterr().out)["families"]) == list(
        release.FAMILIES
    )


def test_pending_code_change_is_per_family(tmp_path, capsys, release_state):
    _, changed_code, _ = release_state
    changed_code["termes-match"] = True
    release.prepare(tmp_path)
    assert json.loads(json.loads(capsys.readouterr().out)["families"]) == [
        "termes-match"
    ]


def test_force_unchanged_is_development_only(
    tmp_path, capsys, release_state, monkeypatch
):
    release.prepare(tmp_path, force=True)
    assert json.loads(json.loads(capsys.readouterr().out)["families"]) == list(
        release.FAMILIES
    )
    monkeypatch.setattr(release, "gh", lambda *a: pytest.fail("No remote writes"))
    for fid in release.FAMILIES:
        release.publish(tmp_path, fid)


def test_matching_draft_reuses_increment(tmp_path, capsys, release_state):
    _, changed_code, releases = release_state
    changed_code["termes-match"] = True
    releases.append(
        {
            "tag_name": "tinos-1.340-termes-2.004-7",
            "draft": True,
            "body": "Build identity: termes-match / commit / hash",
        }
    )
    release.prepare(tmp_path)
    plan = json.loads((tmp_path / "build_temp/termes-match-inputs.json").read_text())
    assert plan["version"] == "1.340-2.004-7"


def test_versions_ignore_archive_only_changes(tmp_path, capsys, release_state):
    inputs, _, _ = release_state
    for definition in inputs.values():
        definition["sha256"] = "changed-archive"
    release.prepare(tmp_path)
    assert json.loads(capsys.readouterr().out)["should_build"] == "false"


def test_newest_publication_is_baseline(tmp_path, release_state):
    _, _, releases = release_state
    releases.append(
        {
            **releases[0],
            "tag_name": "tinos-1.340-nimbus-20200910-4",
            "published_at": "2026-09-12T01:00:00Z",
            "body": "Numeric OpenType revision: **1.007**.",
        }
    )
    previous = release.latest_version(
        releases, release.load_family(tmp_path, "nimbus-match")
    )
    assert previous["font_revision"] == "1.007"
    assert previous["tag"].endswith("-4")


def test_release_history_is_paginated(monkeypatch):
    urls = []

    def fetch(url):
        urls.append(url)
        return [{}] * 100 if len(urls) == 1 else []

    monkeypatch.setattr(release, "fetch_json", fetch)
    assert len(release.list_releases("example/fonts")) == 100
    assert urls[-1].endswith("page=2")


def test_api_failure_is_not_missing_release(tmp_path, monkeypatch):
    def failed(url):
        raise OSError("network failure")

    monkeypatch.setattr(release, "fetch_json", failed)
    with pytest.raises(OSError):
        release.prepare(tmp_path)


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

    _, changed_code, _ = release_state
    changed_code[family_id] = True
    release.prepare(tmp_path, family=family_id)
    plan = json.loads(
        (tmp_path / "build_temp" / f"{family_id}-inputs.json").read_text()
    )
    family = release.load_family(tmp_path, family_id)
    output = tmp_path / "dist" / family_id
    output.mkdir(parents=True)
    for name in asset_names(family):
        (output / name).write_bytes(name.encode())
    validated = []

    def validate(config, folder, version=None, revision=None):
        if version is not None:
            assert version == plan["version"] and revision == plan["font_revision"]
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
    assert len(remote) == 8
    assert not any(name.endswith(".json") for name in remote)
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
