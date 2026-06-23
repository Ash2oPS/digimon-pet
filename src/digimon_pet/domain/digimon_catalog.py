from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from digimon_pet.domain.items import ItemCatalog
from digimon_pet.domain.models import GrowthStage


SPECIES_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
NATURAL_EVOLUTION_ID_PATTERN = re.compile(r"^[a-z0-9_]+__to__[a-z0-9_]+$")
SPRITE_SLOT_NAMES = ("idle", "walk", "sleep", "eat", "train")
VALID_STAT_NAMES = {"hp", "mp", "offense", "defense", "speed", "brains"}
VALID_STAGE_VALUES = {stage.value for stage in GrowthStage}
DW1_STAGE_BY_APP_STAGE = {
    GrowthStage.BABY.value: "fresh",
    GrowthStage.BABY_2.value: "in_training",
}


@dataclass
class DigimonCatalog:
    species_rows: list[dict[str, Any]]
    digivolutions: dict[str, Any]
    natural_evolutions: list[dict[str, Any]]
    special_evolutions: list[dict[str, Any]]

    def species_by_id(self) -> dict[str, dict[str, Any]]:
        return {str(row.get("id", "")): row for row in self.species_rows}


@dataclass(frozen=True)
class DigimonDeleteImpact:
    species_id: str
    natural_as_source: list[str]
    natural_as_target: list[str]
    special_references: list[str]
    sprite_paths: list[str]


@dataclass(frozen=True)
class DigimonValidationResult:
    errors: list[str]
    warnings: list[str]

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)


def load_digimon_catalog(species_path: Path, digivolutions_path: Path) -> DigimonCatalog:
    species_rows = json.loads(species_path.read_text(encoding="utf-8"))
    digivolutions = json.loads(digivolutions_path.read_text(encoding="utf-8"))
    return DigimonCatalog(
        species_rows=copy.deepcopy(species_rows),
        digivolutions=copy.deepcopy(digivolutions),
        natural_evolutions=copy.deepcopy(digivolutions.get("natural_evolutions", [])),
        special_evolutions=copy.deepcopy(digivolutions.get("special_evolutions", [])),
    )


def digimon_catalog_to_species_rows(catalog: DigimonCatalog) -> list[dict[str, Any]]:
    return copy.deepcopy(catalog.species_rows)


def digimon_catalog_to_digivolutions(catalog: DigimonCatalog) -> dict[str, Any]:
    raw = copy.deepcopy(catalog.digivolutions)
    raw["natural_evolutions"] = [_normalized_natural_evolution(catalog, row) for row in catalog.natural_evolutions]
    raw["special_evolutions"] = [_normalized_special_evolution(catalog, row) for row in catalog.special_evolutions]
    indexes = copy.deepcopy(raw.get("indexes", {}))
    indexes["by_source"] = rebuild_indexes_by_source(catalog)
    raw["indexes"] = indexes
    return raw


def add_species(catalog: DigimonCatalog) -> str:
    species_id = _next_unique_id(catalog, "new_digimon")
    catalog.species_rows.append(
        {
            "id": species_id,
            "name": "New Digimon",
            "stage": GrowthStage.ROOKIE.value,
            "aliases": [],
            "sprite_slots": {},
        }
    )
    return species_id


def duplicate_species(catalog: DigimonCatalog, species_id: str) -> str:
    source = catalog.species_by_id().get(species_id)
    if source is None:
        return ""
    duplicate = copy.deepcopy(source)
    duplicate_id = _next_unique_id(catalog, _duplicate_base_id(species_id))
    duplicate["id"] = duplicate_id
    duplicate["name"] = _duplicate_name(str(source.get("name", species_id)), duplicate_id, species_id)
    source_index = catalog.species_rows.index(source)
    catalog.species_rows.insert(source_index + 1, duplicate)
    return duplicate_id


def delete_species(catalog: DigimonCatalog, species_id: str) -> DigimonDeleteImpact:
    species = catalog.species_by_id().get(species_id)
    sprite_paths = _sprite_paths(species) if species else []
    natural_as_source = [
        _row_id(row)
        for row in catalog.natural_evolutions
        if str(row.get("source_species_id", "")) == species_id
    ]
    natural_as_target = [
        _row_id(row)
        for row in catalog.natural_evolutions
        if str(row.get("target_species_id", "")) == species_id
    ]
    special_references = [
        _row_id(row)
        for row in catalog.special_evolutions
        if _special_references_species(row, species_id)
    ]
    catalog.species_rows = [row for row in catalog.species_rows if str(row.get("id", "")) != species_id]
    catalog.natural_evolutions = [
        row
        for row in catalog.natural_evolutions
        if str(row.get("source_species_id", "")) != species_id
        and str(row.get("target_species_id", "")) != species_id
    ]
    catalog.special_evolutions = [
        row for row in catalog.special_evolutions if not _special_references_species(row, species_id)
    ]
    return DigimonDeleteImpact(
        species_id=species_id,
        natural_as_source=natural_as_source,
        natural_as_target=natural_as_target,
        special_references=special_references,
        sprite_paths=sprite_paths,
    )


def rebuild_indexes_by_source(catalog: DigimonCatalog) -> dict[str, list[str]]:
    by_source: dict[str, list[str]] = {}
    for row in catalog.natural_evolutions:
        source_id = str(row.get("source_species_id", "")).strip()
        evolution_id = _row_id(row)
        if source_id and evolution_id:
            by_source.setdefault(source_id, []).append(evolution_id)
    return {source_id: sorted(ids) for source_id, ids in sorted(by_source.items())}


def validate_digimon_catalog(
    catalog: DigimonCatalog,
    project_root: Path,
    *,
    sprite_manifest_path: Path | None = None,
    item_catalog: ItemCatalog | None = None,
) -> DigimonValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()
    runtime_sprite_paths = _runtime_sprite_paths(project_root, sprite_manifest_path)

    for row in catalog.species_rows:
        species_id = str(row.get("id", "")).strip()
        name = str(row.get("name", "")).strip()
        stage = str(row.get("stage", "")).strip()
        if not species_id:
            errors.append("Digimon id is required")
        elif not SPECIES_ID_PATTERN.fullmatch(species_id):
            errors.append(f"Invalid Digimon id: {species_id}")
        if species_id in seen_ids:
            errors.append(f"Duplicate Digimon id: {species_id}")
        seen_ids.add(species_id)
        if not name:
            errors.append(f"{species_id} name is required")
        if not isinstance(row.get("aliases", []), list):
            errors.append(f"{species_id} aliases must be an array")
        if stage not in VALID_STAGE_VALUES:
            errors.append(f"{species_id} has invalid stage: {stage}")
        _validate_sprite_slots(row, project_root, warnings, runtime_sprite_paths)

    species_ids = {str(row.get("id", "")).strip() for row in catalog.species_rows}
    for row in catalog.natural_evolutions:
        _validate_natural_evolution(row, species_ids, errors)
    for row in catalog.special_evolutions:
        _validate_special_evolution(row, species_ids, errors, warnings)
    _validate_link_shape(catalog, species_ids, warnings, item_catalog)
    return DigimonValidationResult(errors=errors, warnings=warnings)


def _validate_sprite_slots(
    row: dict[str, Any],
    project_root: Path,
    warnings: list[str],
    runtime_sprite_paths: dict[str, str],
) -> None:
    species_id = str(row.get("id", "")).strip()
    if _runtime_sprite_exists(project_root, runtime_sprite_paths.get(species_id)):
        return
    sprite_slots = row.get("sprite_slots", {})
    if not isinstance(sprite_slots, dict):
        warnings.append(f"{species_id} sprite slots are invalid")
        return
    for slot_name, sprite_path in sprite_slots.items():
        if not str(sprite_path).strip():
            continue
        path = Path(str(sprite_path))
        if not path.is_absolute():
            path = project_root / path
        if not path.exists():
            warnings.append(f"{species_id} missing sprite file for {slot_name}: {sprite_path}")


def _runtime_sprite_paths(project_root: Path, sprite_manifest_path: Path | None) -> dict[str, str]:
    path = sprite_manifest_path or project_root / "data" / "dw1_sprite_manifest.json"
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    entries = raw.get("entries", {}) if isinstance(raw, dict) else {}
    if not isinstance(entries, dict):
        return {}
    paths: dict[str, str] = {}
    for species_id, entry in entries.items():
        if isinstance(entry, dict):
            asset_path = str(entry.get("asset_path", "")).strip()
            if asset_path:
                paths[str(species_id)] = asset_path
    return paths


def _runtime_sprite_exists(project_root: Path, raw_path: str | None) -> bool:
    if not raw_path:
        return False
    path = Path(raw_path)
    if not path.is_absolute():
        path = project_root / path
    return path.exists()


def _validate_natural_evolution(row: dict[str, Any], species_ids: set[str], errors: list[str]) -> None:
    evolution_id = _row_id(row)
    source_id = str(row.get("source_species_id", "")).strip()
    target_id = str(row.get("target_species_id", "")).strip()
    expected_id = f"{source_id}__to__{target_id}"
    if not NATURAL_EVOLUTION_ID_PATTERN.fullmatch(evolution_id) or evolution_id != expected_id:
        errors.append(f"{evolution_id} has malformed natural evolution id")
    if source_id not in species_ids:
        errors.append(f"{evolution_id} references unknown source species: {source_id}")
    if target_id not in species_ids:
        errors.append(f"{evolution_id} references unknown target species: {target_id}")
    groups = row.get("requirements", {}).get("groups", {})
    stats = groups.get("stats", {}) if isinstance(groups, dict) else {}
    if isinstance(stats, dict):
        for stat_name, value in stats.items():
            stat = str(stat_name)
            if stat not in VALID_STAT_NAMES:
                errors.append(f"{evolution_id} uses unknown requirement stat: {stat}")
            try:
                number = int(value)
            except (TypeError, ValueError):
                number = -1
            if number < 0:
                errors.append(f"{evolution_id} has invalid requirement value for {stat}: {value}")


def _validate_special_evolution(
    row: dict[str, Any],
    species_ids: set[str],
    errors: list[str],
    warnings: list[str],
) -> None:
    evolution_id = _row_id(row)
    target_id = str(row.get("target_species_id", "")).strip()
    if target_id not in species_ids:
        errors.append(f"{evolution_id} targets unknown species: {target_id}")
    selector = row.get("source_selector", {})
    if isinstance(selector, dict):
        for source_id in selector.get("species_ids", []):
            if str(source_id) not in species_ids:
                errors.append(f"{evolution_id} requires unknown source species: {source_id}")
    if not str(row.get("trigger", "")).strip():
        warnings.append(f"{evolution_id} trigger text is empty")


def _validate_link_shape(
    catalog: DigimonCatalog,
    species_ids: set[str],
    warnings: list[str],
    item_catalog: ItemCatalog | None,
) -> None:
    incoming = {str(row.get("target_species_id", "")) for row in catalog.natural_evolutions}
    outgoing = {str(row.get("source_species_id", "")) for row in catalog.natural_evolutions}
    incoming.update(str(row.get("target_species_id", "")) for row in catalog.special_evolutions)
    for row in catalog.special_evolutions:
        selector = row.get("source_selector", {})
        if not isinstance(selector, dict):
            continue
        outgoing.update(str(source_id) for source_id in selector.get("species_ids", ()))
        selected_stage = str(selector.get("stage", "")).strip()
        if selected_stage:
            outgoing.update(
                str(species.get("id", "")).strip()
                for species in catalog.species_rows
                if str(species.get("stage", "")).strip() == selected_stage
            )
    if item_catalog is not None:
        for item in item_catalog.items.values():
            if item.evolution is None:
                continue
            incoming.add(item.evolution.target_species_id)
            outgoing.update(item.evolution.required_species_ids)
    for row in catalog.species_rows:
        species_id = str(row.get("id", "")).strip()
        stage = str(row.get("stage", "")).strip()
        if species_id not in species_ids:
            continue
        if stage not in {GrowthStage.BABY.value, GrowthStage.BABY_2.value} and species_id not in incoming:
            warnings.append(f"{species_id} has no incoming natural evolution")
        if stage not in {GrowthStage.CHAMPION.value, GrowthStage.ULTIMATE.value} and species_id not in outgoing:
            warnings.append(f"{species_id} has no outgoing natural evolution")


def _normalized_natural_evolution(catalog: DigimonCatalog, row: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(row)
    source_id = str(normalized.get("source_species_id", ""))
    target_id = str(normalized.get("target_species_id", ""))
    species = catalog.species_by_id()
    if source_id in species:
        normalized["source_name"] = str(species[source_id].get("name", source_id))
    if target_id in species:
        target = species[target_id]
        normalized["target_name"] = str(target.get("name", target_id))
        normalized["target_stage"] = _dw1_stage_value(str(target.get("stage", "")))
    return normalized


def _normalized_special_evolution(catalog: DigimonCatalog, row: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(row)
    target_id = str(normalized.get("target_species_id", ""))
    target = catalog.species_by_id().get(target_id)
    if target:
        normalized["target_name"] = str(target.get("name", target_id))
        normalized["target_stage"] = _dw1_stage_value(str(target.get("stage", "")))
    return normalized


def _dw1_stage_value(stage: str) -> str:
    return DW1_STAGE_BY_APP_STAGE.get(stage, stage)


def _next_unique_id(catalog: DigimonCatalog, base_id: str) -> str:
    existing = set(catalog.species_by_id())
    if base_id not in existing:
        return base_id
    index = 2
    while f"{base_id}_{index}" in existing:
        index += 1
    return f"{base_id}_{index}"


def _duplicate_base_id(species_id: str) -> str:
    return re.sub(r"_\d+$", "", species_id)


def _duplicate_name(name: str, duplicate_id: str, source_id: str) -> str:
    suffix = duplicate_id.removeprefix(f"{_duplicate_base_id(source_id)}_")
    base_name = re.sub(r"\s+\d+$", "", name)
    return f"{base_name} {suffix}"


def _row_id(row: dict[str, Any]) -> str:
    return str(row.get("id", "")).strip()


def _special_references_species(row: dict[str, Any], species_id: str) -> bool:
    if str(row.get("target_species_id", "")) == species_id:
        return True
    selector = row.get("source_selector", {})
    return isinstance(selector, dict) and species_id in {str(value) for value in selector.get("species_ids", [])}


def _sprite_paths(row: dict[str, Any] | None) -> list[str]:
    if row is None:
        return []
    sprite_slots = row.get("sprite_slots", {})
    if not isinstance(sprite_slots, dict):
        return []
    return [str(value) for value in sprite_slots.values() if str(value).strip()]
