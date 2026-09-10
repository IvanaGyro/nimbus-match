import io
import zipfile
import pytest
from font_match import upstream


def test_exact_revision_url_is_used_and_cached(tmp_path, monkeypatch):
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w") as archive:
        archive.writestr("root/font.otf", b"font bytes")
    data = content.getvalue()
    urls = []

    def download(url):
        urls.append(url)
        return data

    monkeypatch.setattr(upstream, "download", download)
    definition = {
        "revision": "a" * 40,
        "url": "https://example.invalid/archive/" + "a" * 40,
        "sha256": upstream.sha256(data),
    }
    result = upstream.extract(tmp_path, definition, ["font.otf"], "test")
    assert result["font.otf"].read_bytes() == b"font bytes"
    assert urls == [definition["url"]]
    upstream.extract(tmp_path, definition, ["font.otf"], "test")
    assert len(urls) == 1


def test_changed_archive_is_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(upstream, "download", lambda u: b"changed")
    with pytest.raises(ValueError, match="checksum changed"):
        upstream.extract(
            tmp_path,
            {"url": "https://example.invalid", "sha256": "0" * 64},
            ["font.otf"],
            "test",
        )


def test_missing_pinned_input_does_not_fall_back(tmp_path, monkeypatch):
    def failed(url):
        raise OSError("Pinned revision unavailable")

    monkeypatch.setattr(upstream, "download", failed)
    with pytest.raises(OSError, match="Pinned revision"):
        upstream.extract(
            tmp_path,
            {"url": "https://example.invalid", "sha256": "0" * 64},
            ["font.otf"],
            "test",
        )
