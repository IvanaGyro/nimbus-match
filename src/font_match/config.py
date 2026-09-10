"""Repository-owned family configuration."""

import tomllib
from dataclasses import dataclass
from pathlib import Path

STYLES = ("Regular", "Bold", "Italic", "BoldItalic")


@dataclass(frozen=True)
class Family:
    id: str
    name: str
    prefix: str
    provider: str
    sources: dict[str, str]
    remove_liga: bool
    predict_missing: bool
    legacy_kerning_names: bool
    notices: tuple[Path, ...]


def load_family(project: Path, family_id: str) -> Family:
    path = project / "families" / family_id / "family.toml"
    if not path.is_file():
        raise ValueError(f"Missing family configuration: {path}; use --project-dir")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    if data["id"] != family_id or set(data["sources"]) != set(STYLES):
        raise ValueError(f"Invalid family identity or styles in {path}")
    return Family(
        data["id"],
        data["name"],
        data["prefix"],
        data["provider"],
        data["sources"],
        data["remove_liga"],
        data["predict_missing"],
        data["legacy_kerning_names"],
        tuple(path.parent / name for name in data["notices"]),
    )
