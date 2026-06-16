from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.request import urlretrieve

from digimon_pet.data.sprite_pipeline import (
    DEFAULT_MANIFEST_PATH,
    DEFAULT_REPORT_PATH,
    DEFAULT_ROSTER_PATH,
    DEFAULT_SOURCE_CONFIG_PATH,
    build_sprite_manifest,
)
from digimon_pet.domain.models import PetState, Species
from digimon_pet.paths import PROJECT_ROOT


DEFAULT_DOWNLOAD_MANIFEST_PATH = PROJECT_ROOT / "data" / "sprite_downloads.json"


@dataclass(frozen=True)
class SpriteAnimation:
    path: str
    frame_width: int | None = None
    frame_height: int | None = None
    frame_count: int = 1
    fps: int = 6
    frame_indices: tuple[int, ...] = (0,)


def load_runtime_manifest(path: Path = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"entries": {}}
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        return {"entries": {}}
    entries = raw.get("entries")
    if not isinstance(entries, dict):
        raw["entries"] = {}
    return raw


def load_or_build_runtime_manifest(
    project_root: Path = PROJECT_ROOT,
    *,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    roster_path: Path = DEFAULT_ROSTER_PATH,
    source_config_path: Path = DEFAULT_SOURCE_CONFIG_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
    download_manifest_path: Path = DEFAULT_DOWNLOAD_MANIFEST_PATH,
) -> dict[str, Any]:
    manifest = build_sprite_manifest(project_root, roster_path, source_config_path, manifest_path, report_path)
    download_missing_sprites(project_root, manifest, download_manifest_path)
    manifest = build_sprite_manifest(project_root, roster_path, source_config_path, manifest_path, report_path)
    if manifest.get("entries") or manifest_path.exists():
        return manifest
    manifest = load_runtime_manifest(manifest_path)
    if not roster_path.exists() or not source_config_path.exists():
        return manifest
    return manifest


def download_missing_sprites(
    project_root: Path,
    manifest: dict[str, Any],
    download_manifest_path: Path = DEFAULT_DOWNLOAD_MANIFEST_PATH,
) -> int:
    if not download_manifest_path.exists():
        return 0
    downloads = _load_download_entries(download_manifest_path)
    missing_ids = {str(item["species_id"]) for item in manifest.get("missing", []) if isinstance(item, dict)}
    count = 0
    downloaded_entries: list[dict[str, Any]] = []
    for entry in downloads:
        species_id = str(entry.get("species_id", ""))
        target_path = _project_relative_path(project_root, entry.get("path"))
        if target_path.exists():
            downloaded_entries.append(_source_manifest_entry(project_root, target_path, entry))
            continue
        if species_id not in missing_ids:
            continue
        url = str(entry.get("url", "")).strip()
        if not url:
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        urlretrieve(url, target_path)
        downloaded_entries.append(_source_manifest_entry(project_root, target_path, entry))
        count += 1
    _write_downloaded_source_manifests(downloaded_entries)
    return count


def resolve_sprite_animation(
    state: PetState,
    species: Species,
    manifest: dict[str, Any],
) -> SpriteAnimation | None:
    entry = _manifest_entry(state.species_id, manifest)
    if entry is not None:
        animation = _manifest_animation(state.current_action, entry)
        if animation is not None:
            return animation

    slot = species.sprite_slots.get(state.current_action) or species.sprite_slots.get("idle")
    if not slot:
        return None
    return SpriteAnimation(path=slot)


def _manifest_entry(species_id: str, manifest: dict[str, Any]) -> dict[str, Any] | None:
    entries = manifest.get("entries")
    if not isinstance(entries, dict):
        return None
    entry = entries.get(species_id)
    if not isinstance(entry, dict):
        return None
    return entry


def _manifest_animation(action: str, entry: dict[str, Any]) -> SpriteAnimation | None:
    asset_path = str(entry.get("asset_path") or "").strip()
    metadata = entry.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    animations = metadata.get("animations")
    if isinstance(animations, dict):
        selected = animations.get(action) or animations.get("idle")
        if isinstance(selected, dict):
            path = str(selected.get("path") or asset_path).strip()
            return _animation_from_metadata(path, {**metadata, **selected}, "idle")

    if asset_path:
        return _animation_from_metadata(asset_path, metadata, action)
    return None


def _animation_from_metadata(path: str, metadata: dict[str, Any], action: str) -> SpriteAnimation:
    frame_count = max(1, int(metadata.get("frame_count", 1)))
    return SpriteAnimation(
        path=path,
        frame_width=_optional_int(metadata.get("frame_width")),
        frame_height=_optional_int(metadata.get("frame_height")),
        frame_count=frame_count,
        fps=max(1, int(metadata.get("fps", 6))),
        frame_indices=_frame_indices_for_action(action, frame_count),
    )


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _frame_indices_for_action(action: str, frame_count: int) -> tuple[int, ...]:
    sequences = {
        "idle": (0, 1),
        "sleep": (6,),
        "eat": (5, 10),
        "train": (12,),
        "angry": (2,),
        "scold": (2,),
        "happy": (4,),
        "clean": (4,),
        "walk": (13, 14),
        "move": (13, 14),
    }
    candidates = sequences.get(action, sequences["idle"])
    valid = tuple(index for index in candidates if index < frame_count)
    if valid:
        return valid
    idle = tuple(index for index in sequences["idle"] if index < frame_count)
    return idle or (0,)


def _load_download_entries(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _project_relative_path(project_root: Path, raw_path: Any) -> Path:
    path = Path(str(raw_path))
    if path.is_absolute():
        raise ValueError(f"Expected a project-relative download path, got {path}")
    return project_root / path


def _source_manifest_entry(project_root: Path, target_path: Path, entry: dict[str, Any]) -> dict[str, Any]:
    metadata = {
        key: value
        for key, value in entry.items()
        if key not in {"species_id", "source_id", "url", "path"} and value is not None
    }
    return {
        "manifest_path": target_path.parent / "manifest.json",
        "item": {
            "name": str(entry.get("name") or entry.get("species_id") or target_path.stem),
            "path": target_path.relative_to(project_root).as_posix(),
            **metadata,
        },
    }


def _write_downloaded_source_manifests(entries: list[dict[str, Any]]) -> None:
    grouped: dict[Path, list[dict[str, Any]]] = {}
    for entry in entries:
        manifest_path = entry["manifest_path"]
        grouped.setdefault(manifest_path, []).append(entry["item"])

    for manifest_path, new_items in grouped.items():
        existing = _load_existing_source_manifest(manifest_path)
        by_name = {str(item.get("name", "")): item for item in existing}
        for item in new_items:
            by_name[str(item["name"])] = item
        manifest_path.write_text(
            json.dumps({"sprites": list(by_name.values())}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _load_existing_source_manifest(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if isinstance(raw, dict) and isinstance(raw.get("sprites"), list):
        return [item for item in raw["sprites"] if isinstance(item, dict)]
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []
