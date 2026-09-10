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


@pytest.mark.parametrize(
    "changed,force,expected",
    [(False, False, False), (False, True, True), (True, False, True)],
)
def test_release_detection_uses_inputs_and_code(
    tmp_path, monkeypatch, capsys, changed, force, expected
):
    monkeypatch.setattr(release, "resolve_inputs", lambda p: {"inputs": {}})
    monkeypatch.setattr(
        release, "fingerprint", lambda p, i: "new" if changed else "same"
    )
    monkeypatch.setattr(release, "git", lambda *a: "commit")

    def fetch(url):
        if url == "manifest":
            return {"build_fingerprint": "same"}
        return [
            {
                "tag_name": "v1.001",
                "draft": False,
                "prerelease": False,
                "assets": [
                    {
                        "name": "NimbusMatch-BUILD-INFO.json",
                        "browser_download_url": "manifest",
                    }
                ],
            }
        ]

    monkeypatch.setattr(release, "fetch_json", fetch)
    release.prepare(tmp_path, force)
    result = json.loads(capsys.readouterr().out)
    assert result["should_build"] == str(expected).lower()
    assert result["version"] == "1.002"


def test_matching_unfinished_draft_reuses_version(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(release, "resolve_inputs", lambda p: {"inputs": {}})
    monkeypatch.setattr(release, "fingerprint", lambda p, i: "hash")
    monkeypatch.setattr(release, "git", lambda *a: "commit")
    monkeypatch.setattr(
        release,
        "fetch_json",
        lambda u: [
            {
                "tag_name": "v1.007",
                "draft": True,
                "body": "Build identity: commit / hash",
            }
        ],
    )
    release.prepare(tmp_path)
    assert json.loads(capsys.readouterr().out)["version"] == "1.007"


def test_api_failure_is_not_a_missing_release(tmp_path, monkeypatch):
    def failed(url):
        raise OSError("authentication/network failure")

    monkeypatch.setattr(release, "fetch_json", failed)
    with pytest.raises(OSError):
        release.prepare(tmp_path)


def test_family_only_run_cannot_publish(tmp_path):
    path = tmp_path / "build_temp/inputs.json"
    path.parent.mkdir()
    path.write_text('{"publish":false}')
    with pytest.raises(ValueError, match="both families"):
        release.publish(tmp_path)


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
