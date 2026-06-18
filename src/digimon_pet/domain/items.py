from __future__ import annotations

import random
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from digimon_pet.domain.lifecycle import force_evolve_to
from digimon_pet.domain.models import GrowthStage, PetState, Species


MONZAEMON_HEAD_ID = "monzaemon_head"


class ItemType(StrEnum):
    EVOLUTION = "evolution"
    CONSUMABLE = "consumable"
    KEY_ITEM = "key_item"
    MISC = "misc"


@dataclass(frozen=True)
class EvolutionItemEffect:
    target_species_id: str
    required_species_ids: tuple[str, ...] = ()
    required_stages: tuple[GrowthStage, ...] = ()


@dataclass(frozen=True)
class ItemDefinition:
    id: str
    name: str
    description: str
    type: ItemType
    icon_path: str | None = None
    evolution: EvolutionItemEffect | None = None


@dataclass(frozen=True)
class ItemPoolEntry:
    item_id: str
    weight: int


@dataclass(frozen=True)
class ItemCatalog:
    items: dict[str, ItemDefinition]
    pools: dict[str, tuple[ItemPoolEntry, ...]]


@dataclass(frozen=True)
class ItemUseResult:
    used: bool
    event: str | None = None
    reason: str | None = None


EVOLUTION_ITEMS: dict[str, ItemDefinition] = {
    MONZAEMON_HEAD_ID: ItemDefinition(
        id=MONZAEMON_HEAD_ID,
        name="Monzaemon's Head",
        description="Forces Numemon to evolve into Monzaemon.",
        type=ItemType.EVOLUTION,
        icon_path="assets/items/monzaemon_head.png",
        evolution=EvolutionItemEffect(
            target_species_id="monzaemon",
            required_species_ids=("numemon",),
        ),
    )
}


def item_catalog_from_dict(raw: dict[str, Any]) -> ItemCatalog:
    items = [_item_from_dict(item) for item in raw.get("items", [])]
    pools = {
        str(pool_id): tuple(_pool_entry_from_dict(entry) for entry in entries)
        for pool_id, entries in raw.get("pools", {}).items()
    }
    return ItemCatalog(items={item.id: item for item in items}, pools=pools)


def item_catalog_to_dict(catalog: ItemCatalog) -> dict[str, Any]:
    return {
        "items": [_item_to_dict(item) for item in catalog.items.values()],
        "pools": {
            pool_id: [_pool_entry_to_dict(entry) for entry in entries]
            for pool_id, entries in catalog.pools.items()
        },
    }


def use_item(
    state: PetState,
    item_id: str,
    species: dict[str, Species],
    rng: random.Random,
) -> ItemUseResult:
    item = EVOLUTION_ITEMS.get(item_id)
    if item is None:
        return ItemUseResult(used=False, reason="unknown_item")
    return use_evolution_item(state, item, species, rng)


def can_use_item(
    state: PetState,
    item_id: str,
    species: dict[str, Species],
) -> ItemUseResult:
    item = EVOLUTION_ITEMS.get(item_id)
    if item is None:
        return ItemUseResult(used=False, reason="unknown_item")
    reason = _evolution_item_blocking_reason(state, item, species)
    if reason is not None:
        return ItemUseResult(used=False, reason=reason)
    return ItemUseResult(used=True)


def use_evolution_item(
    state: PetState,
    item: ItemDefinition,
    species: dict[str, Species],
    rng: random.Random,
) -> ItemUseResult:
    reason = _evolution_item_blocking_reason(state, item, species)
    if reason is not None:
        return ItemUseResult(used=False, reason=reason)
    if item.evolution is None:
        return ItemUseResult(used=False, reason="not_usable")

    target = species.get(item.evolution.target_species_id)
    if target is None:  # Guarded above; keeps the type checker honest.
        return ItemUseResult(used=False, reason="unknown_target")

    _consume_item(state, item.id)
    event = force_evolve_to(state, target, rng)
    state.mark_discovered(target.id)
    return ItemUseResult(used=True, event=event)


def _evolution_item_blocking_reason(
    state: PetState,
    item: ItemDefinition,
    species: dict[str, Species],
) -> str | None:
    if item.type != ItemType.EVOLUTION or item.evolution is None:
        return "not_usable"
    if state.inventory.get(item.id, 0) <= 0:
        return "missing_item"
    if (
        item.evolution.required_species_ids
        and state.species_id not in item.evolution.required_species_ids
    ):
        return "wrong_species"
    if item.evolution.required_stages and state.stage not in item.evolution.required_stages:
        return "wrong_stage"
    if item.evolution.target_species_id not in species:
        return "unknown_target"
    return None


def _consume_item(state: PetState, item_id: str) -> None:
    quantity = state.inventory.get(item_id, 0) - 1
    if quantity <= 0:
        state.inventory.pop(item_id, None)
    else:
        state.inventory[item_id] = quantity


def _item_from_dict(raw: dict[str, Any]) -> ItemDefinition:
    evolution = raw.get("evolution")
    return ItemDefinition(
        id=str(raw["id"]),
        name=str(raw["name"]),
        description=str(raw["description"]),
        type=ItemType(str(raw["type"])),
        icon_path=_optional_str(raw.get("icon_path")),
        evolution=_evolution_effect_from_dict(evolution) if evolution else None,
    )


def _evolution_effect_from_dict(raw: dict[str, Any]) -> EvolutionItemEffect:
    return EvolutionItemEffect(
        target_species_id=str(raw["target_species_id"]),
        required_species_ids=tuple(str(item) for item in raw.get("required_species_ids", ())),
        required_stages=tuple(GrowthStage(str(item)) for item in raw.get("required_stages", ())),
    )


def _pool_entry_from_dict(raw: dict[str, Any]) -> ItemPoolEntry:
    return ItemPoolEntry(item_id=str(raw["item_id"]), weight=int(raw["weight"]))


def _item_to_dict(item: ItemDefinition) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "type": item.type.value,
    }
    if item.icon_path is not None:
        raw["icon_path"] = item.icon_path
    if item.evolution is not None:
        raw["evolution"] = _evolution_effect_to_dict(item.evolution)
    return raw


def _evolution_effect_to_dict(effect: EvolutionItemEffect) -> dict[str, Any]:
    return {
        "target_species_id": effect.target_species_id,
        "required_species_ids": list(effect.required_species_ids),
        "required_stages": [stage.value for stage in effect.required_stages],
    }


def _pool_entry_to_dict(entry: ItemPoolEntry) -> dict[str, Any]:
    return {"item_id": entry.item_id, "weight": entry.weight}


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
