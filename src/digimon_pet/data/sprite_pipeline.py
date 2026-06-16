from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from digimon_pet.paths import DATA_DIR, PROJECT_ROOT


DEFAULT_ROSTER_PATH = DATA_DIR / "dw1_roster.json"
DEFAULT_SOURCE_CONFIG_PATH = DATA_DIR / "sprite_sources.json"
DEFAULT_MANIFEST_PATH = DATA_DIR / "dw1_sprite_manifest.json"
DEFAULT_REPORT_PATH = DATA_DIR / "dw1_sprite_report.md"

DEFAULT_ALIAS_MAP: dict[str, list[str]] = {
    "Penguinmon": ["Penmon"],
    "Biyomon": ["Piyomon"],
    "Centarumon": ["Centalmon"],
    "Phoenixmon": ["Hououmon"],
    "HerculesKabuterimon": ["Herakle Kabuterimon"],
    "Ninjamon": ["Igamon"],
    "Piximon": ["Piccolomon"],
    "Frigimon": ["Yukidarumon"],
    "Kokatorimon": ["Cockatrimon"],
    "Vegiemon": ["Vegimon"],
    "Machinedramon": ["Mugendramon"],
    "Ogremon": ["Orgemon"],
    "Sukamon": ["Scumon"],
    "Tsunomon": ["Tunomon"],
    "Tyrannomon": ["Tyranomon"],
    "MegaSeadramon": ["Mega Seadramon"],
    "MetalGreymon": ["Metal Greymon", "Metal Greymon (Virus)"],
}


@dataclass(frozen=True)
class RosterEntry:
    id: str
    name: str
    aliases: tuple[str, ...] = ()
    promo_japan: bool = False


@dataclass(frozen=True)
class SpriteSource:
    id: str
    name: str
    priority: int
    root: Path | None = None
    manifest: Path | None = None


@dataclass(frozen=True)
class SpriteAsset:
    source_id: str
    source_name: str
    name: str
    path: str
    metadata: dict[str, Any] = field(default_factory=dict)


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.casefold())


def load_roster(path: Path | None = None, *, include_japanese_promos: bool = False) -> list[RosterEntry]:
    raw_items = _read_json(path or DEFAULT_ROSTER_PATH)
    roster = [_roster_entry_from_dict(item) for item in raw_items]
    if include_japanese_promos:
        return roster
    return [entry for entry in roster if not entry.promo_japan]


def load_sprite_sources(project_root: Path = PROJECT_ROOT, path: Path | None = None) -> list[SpriteSource]:
    raw_items = _read_json(path or DEFAULT_SOURCE_CONFIG_PATH)
    sources = [_sprite_source_from_dict(project_root, item) for item in raw_items]
    return sorted(sources, key=lambda source: source.priority)


def load_available_sprites(sources: list[SpriteSource], project_root: Path = PROJECT_ROOT) -> dict[str, dict[str, SpriteAsset]]:
    by_source: dict[str, dict[str, SpriteAsset]] = {}
    for source in sources:
        assets = _load_source_assets(source, project_root)
        by_source[source.id] = {normalize_name(asset.name): asset for asset in assets}
    return by_source


def resolve_roster_sprites(
    roster: list[RosterEntry],
    sources: list[SpriteSource],
    available_sprites: dict[str, dict[str, SpriteAsset]],
) -> dict[str, Any]:
    entries: dict[str, dict[str, Any]] = {}
    missing: list[dict[str, str]] = []
    conflicts: list[dict[str, Any]] = []

    for species in roster:
        candidates = _candidate_names(species)
        matches = _matches_for_species(candidates, sources, available_sprites)
        if not matches:
            missing.append({"species_id": species.id, "name": species.name})
            continue

        chosen_source, chosen_asset, matched_name = matches[0]
        alias_used = [] if normalize_name(matched_name) == normalize_name(species.name) else [matched_name]
        entries[species.id] = {
            "species_id": species.id,
            "name": species.name,
            "source_id": chosen_source.id,
            "source_name": chosen_source.name,
            "asset_path": chosen_asset.path,
            "matched_name": chosen_asset.name,
            "aliases_used": alias_used,
            "metadata": chosen_asset.metadata,
        }

        if len(matches) > 1:
            conflicts.append(
                {
                    "species_id": species.id,
                    "name": species.name,
                    "chosen_source_id": chosen_source.id,
                    "available_source_ids": [source.id for source, _, _ in matches],
                }
            )

    return {
        "entries": entries,
        "missing": missing,
        "conflicts": conflicts,
        "source_priority": [{"id": source.id, "name": source.name, "priority": source.priority} for source in sources],
    }


def build_sprite_manifest(
    project_root: Path = PROJECT_ROOT,
    roster_path: Path | None = None,
    source_config_path: Path | None = None,
    output_path: Path | None = None,
    report_path: Path | None = None,
) -> dict[str, Any]:
    roster = load_roster(roster_path)
    sources = load_sprite_sources(project_root, source_config_path)
    available = load_available_sprites(sources, project_root)
    result = resolve_roster_sprites(roster, sources, available)

    _write_json(output_path or DEFAULT_MANIFEST_PATH, result)
    _write_report(report_path or DEFAULT_REPORT_PATH, result)
    return result


def _candidate_names(species: RosterEntry) -> list[str]:
    candidates = [species.name, *species.aliases, *DEFAULT_ALIAS_MAP.get(species.name, [])]
    seen: set[str] = set()
    unique: list[str] = []
    for candidate in candidates:
        key = normalize_name(candidate)
        if key not in seen:
            unique.append(candidate)
            seen.add(key)
    return unique


def _matches_for_species(
    candidates: list[str],
    sources: list[SpriteSource],
    available_sprites: dict[str, dict[str, SpriteAsset]],
) -> list[tuple[SpriteSource, SpriteAsset, str]]:
    normalized_candidates = [(candidate, normalize_name(candidate)) for candidate in candidates]
    matches: list[tuple[SpriteSource, SpriteAsset, str]] = []
    for source in sources:
        assets = available_sprites.get(source.id, {})
        for candidate, normalized in normalized_candidates:
            asset = assets.get(normalized)
            if asset is not None:
                matches.append((source, asset, candidate))
                break
    return matches


def _load_source_assets(source: SpriteSource, project_root: Path) -> list[SpriteAsset]:
    if source.manifest and source.manifest.exists():
        return _load_manifest_assets(source, project_root)
    if source.root and source.root.exists():
        return _scan_png_assets(source, project_root)
    return []


def _load_manifest_assets(source: SpriteSource, project_root: Path) -> list[SpriteAsset]:
    raw = _read_json(source.manifest)
    items = _manifest_items(raw)
    assets: list[SpriteAsset] = []
    for item in items:
        name = str(item.get("name") or item.get("digimon") or item.get("species") or "").strip()
        raw_path = str(item.get("path") or item.get("file") or item.get("spritesheet") or "").strip()
        if not name or not raw_path:
            continue
        asset_path = _manifest_asset_path(project_root, source.manifest, raw_path)
        metadata = {key: value for key, value in item.items() if key not in {"name", "digimon", "species", "path", "file", "spritesheet"}}
        assets.append(
            SpriteAsset(
                source_id=source.id,
                source_name=source.name,
                name=name,
                path=_relative_posix(project_root, asset_path),
                metadata=metadata,
            )
        )
    return assets


def _scan_png_assets(source: SpriteSource, project_root: Path) -> list[SpriteAsset]:
    if source.root is None:
        return []
    assets: list[SpriteAsset] = []
    for path in sorted(source.root.rglob("*.png")):
        name = path.parent.name if path.parent != source.root else path.stem
        assets.append(
            SpriteAsset(
                source_id=source.id,
                source_name=source.name,
                name=name,
                path=_relative_posix(project_root, path),
            )
        )
    return assets


def _manifest_items(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        if isinstance(raw.get("sprites"), list):
            return [item for item in raw["sprites"] if isinstance(item, dict)]
        items: list[dict[str, Any]] = []
        for key, value in raw.items():
            if isinstance(value, str):
                items.append({"name": key, "path": value})
            elif isinstance(value, dict):
                items.append({"name": value.get("name", key), **value})
        return items
    return []


def _roster_entry_from_dict(raw: dict[str, Any]) -> RosterEntry:
    return RosterEntry(
        id=str(raw["id"]),
        name=str(raw["name"]),
        aliases=tuple(str(alias) for alias in raw.get("aliases", [])),
        promo_japan=bool(raw.get("promo_japan", False)),
    )


def _sprite_source_from_dict(project_root: Path, raw: dict[str, Any]) -> SpriteSource:
    return SpriteSource(
        id=str(raw["id"]),
        name=str(raw["name"]),
        priority=int(raw["priority"]),
        root=_optional_project_path(project_root, raw.get("root")),
        manifest=_optional_project_path(project_root, raw.get("manifest")),
    )


def _optional_project_path(project_root: Path, value: Any) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    if path.is_absolute():
        raise ValueError(f"Expected a project-relative path, got {path}")
    return project_root / path


def _manifest_asset_path(project_root: Path, manifest_path: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        raise ValueError(f"Expected a project-relative asset path, got {path}")
    project_relative = project_root / path
    if project_relative.exists():
        return project_relative
    return manifest_path.parent / path


def _relative_posix(project_root: Path, path: Path) -> str:
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _write_report(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# Digimon World 1 Sprite Resolution Report",
        "",
        "## Resolved",
    ]
    for entry in result["entries"].values():
        aliases = ", ".join(entry["aliases_used"]) if entry["aliases_used"] else "-"
        lines.append(f"- {entry['name']}: {entry['source_name']} ({entry['asset_path']}); aliases: {aliases}")

    lines.extend(["", "## Missing"])
    if result["missing"]:
        lines.extend(f"- {item['name']}" for item in result["missing"])
    else:
        lines.append("- None")

    lines.extend(["", "## Conflicts"])
    if result["conflicts"]:
        for conflict in result["conflicts"]:
            sources = ", ".join(conflict["available_source_ids"])
            lines.append(f"- {conflict['name']}: chose {conflict['chosen_source_id']} from {sources}")
    else:
        lines.append("- None")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the offline Digimon World 1 sprite manifest.")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--roster", type=Path, default=DEFAULT_ROSTER_PATH)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCE_CONFIG_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    args = parser.parse_args()

    result = build_sprite_manifest(args.project_root, args.roster, args.sources, args.output, args.report)
    print(f"Resolved {len(result['entries'])}; missing {len(result['missing'])}; conflicts {len(result['conflicts'])}")


if __name__ == "__main__":
    main()
