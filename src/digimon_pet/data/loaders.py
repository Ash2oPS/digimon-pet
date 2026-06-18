from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from digimon_pet.domain.items import ItemCatalog, item_catalog_from_dict
from digimon_pet.domain.models import EvolutionRule, GrowthStage, Species
from digimon_pet.paths import DATA_DIR


def load_species(path: Path | None = None) -> dict[str, Species]:
    raw_items = _read_json(path or DATA_DIR / "species.json")
    species = [_species_from_dict(item) for item in raw_items]
    return {item.id: item for item in species}


def load_evolution_rules(path: Path | None = None) -> list[EvolutionRule]:
    raw_items = _read_json(path or DATA_DIR / "evolution_rules.json")
    return [_rule_from_dict(item) for item in raw_items]


def load_dw1_digivolutions(path: Path | None = None) -> dict[str, Any]:
    return dict(_read_json(path or DATA_DIR / "dw1_digivolutions.json"))


def load_item_catalog(path: Path | None = None) -> ItemCatalog:
    return item_catalog_from_dict(_read_json(path or DATA_DIR / "items.json"))


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _species_from_dict(raw: dict[str, Any]) -> Species:
    return Species(
        id=str(raw["id"]),
        name=str(raw["name"]),
        stage=GrowthStage(str(raw["stage"])),
        sprite_slots=dict(raw.get("sprite_slots", {})),
    )


def _rule_from_dict(raw: dict[str, Any]) -> EvolutionRule:
    return EvolutionRule(
        source_species_id=str(raw["source_species_id"]),
        target_species_id=str(raw["target_species_id"]),
        min_age_seconds=int(raw["min_age_seconds"]),
        max_care_mistakes=_optional_int(raw.get("max_care_mistakes")),
        min_discipline=_optional_int(raw.get("min_discipline")),
        min_training_count=_optional_int(raw.get("min_training_count")),
        priority=int(raw.get("priority", 0)),
    )


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)
