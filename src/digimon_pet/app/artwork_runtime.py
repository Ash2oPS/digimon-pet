from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.request import urlretrieve

from digimon_pet.paths import PROJECT_ROOT

DEFAULT_ARTWORK_DOWNLOAD_MANIFEST_PATH = PROJECT_ROOT / "data" / "artwork_downloads.json"


def download_missing_artworks(
    project_root: Path = PROJECT_ROOT,
    manifest_path: Path = DEFAULT_ARTWORK_DOWNLOAD_MANIFEST_PATH,
) -> int:
    if not manifest_path.exists():
        return 0
    count = 0
    for entry in _load_artwork_entries(manifest_path):
        target_path = _project_relative_path(project_root, entry.get("path"))
        if target_path.exists():
            continue
        url = str(entry.get("url", "")).strip()
        if not url:
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            urlretrieve(url, target_path)
        except OSError:
            continue
        count += 1
    return count


def resolve_artwork_path(
    species_id: str,
    project_root: Path = PROJECT_ROOT,
    manifest_path: Path = DEFAULT_ARTWORK_DOWNLOAD_MANIFEST_PATH,
) -> Path | None:
    if not manifest_path.exists():
        return None
    for entry in _load_artwork_entries(manifest_path):
        if str(entry.get("species_id", "")) != species_id:
            continue
        target_path = _project_relative_path(project_root, entry.get("path"))
        return target_path if target_path.exists() else None
    return None


def _load_artwork_entries(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _project_relative_path(project_root: Path, raw_path: Any) -> Path:
    path = Path(str(raw_path))
    if path.is_absolute():
        raise ValueError(f"Expected a project-relative artwork path, got {path}")
    return project_root / path
