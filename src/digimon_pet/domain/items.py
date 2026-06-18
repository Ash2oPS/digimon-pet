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
    catalog: ItemCatalog | None = None,
) -> ItemUseResult:
    item = _find_item(item_id, catalog)
    if item is None:
        return ItemUseResult(used=False, reason="unknown_item")
    return use_evolution_item(state, item, species, rng)


def can_use_item(
    state: PetState,
    item_id: str,
    species: dict[str, Species],
    catalog: ItemCatalog | None = None,
) -> ItemUseResult:
    item = _find_item(item_id, catalog)
    if item is None:
        return ItemUseResult(used=False, reason="unknown_item")
    reason = _evolution_item_blocking_reason(state, item, species)
    if reason is not None:
        return ItemUseResult(used=False, reason=reason)
    return ItemUseResult(used=True)


def choose_weighted_item(
    catalog: ItemCatalog,
    pool_name: str,
    rng: random.Random,
) -> str | None:
    normal_entries, evolution_entries = _eligible_pool_entries_by_type(catalog, pool_name)
    if normal_entries and evolution_entries:
        if rng.randint(1, 100) <= 10:
            return evolution_entries[rng.randint(1, len(evolution_entries)) - 1].item_id
        return _choose_weighted_entry(normal_entries, rng)

    entries = normal_entries or evolution_entries
    if evolution_entries and not normal_entries:
        return evolution_entries[rng.randint(1, len(evolution_entries)) - 1].item_id
    return _choose_weighted_entry(entries, rng)


def item_drop_chance_percent(
    catalog: ItemCatalog,
    pool_name: str,
    item_id: str,
    *,
    edited_weight: int | None = None,
) -> int:
    normal_entries, evolution_entries = _eligible_pool_entries_by_type(
        catalog,
        pool_name,
        item_id=item_id,
        edited_weight=edited_weight,
    )
    item = catalog.items.get(item_id)
    if item is None:
        return 0

    if item.type == ItemType.EVOLUTION:
        if not any(entry.item_id == item_id for entry in evolution_entries):
            return 0
        category_percent = 10 if normal_entries else 100
        return round(category_percent / len(evolution_entries))

    selected_weight = next(
        (entry.weight for entry in normal_entries if entry.item_id == item_id),
        0,
    )
    total_normal_weight = sum(entry.weight for entry in normal_entries)
    if selected_weight <= 0 or total_normal_weight <= 0:
        return 0
    category_percent = 90 if evolution_entries else 100
    return max(0, min(100, round(category_percent * selected_weight / total_normal_weight)))


def _eligible_pool_entries_by_type(
    catalog: ItemCatalog,
    pool_name: str,
    *,
    item_id: str | None = None,
    edited_weight: int | None = None,
) -> tuple[tuple[ItemPoolEntry, ...], tuple[ItemPoolEntry, ...]]:
    normal_entries: list[ItemPoolEntry] = []
    evolution_entries: list[ItemPoolEntry] = []
    selected_entry_found = False
    selected_item = catalog.items.get(item_id or "")

    for entry in catalog.pools.get(pool_name, ()):
        definition = catalog.items.get(entry.item_id)
        if definition is None:
            continue

        weight = (
            edited_weight
            if entry.item_id == item_id and edited_weight is not None
            else entry.weight
        )
        if entry.item_id == item_id:
            selected_entry_found = True
        if weight <= 0:
            continue

        edited_entry = ItemPoolEntry(item_id=entry.item_id, weight=weight)
        if definition.type == ItemType.EVOLUTION:
            evolution_entries.append(edited_entry)
        else:
            normal_entries.append(edited_entry)

    if (
        item_id
        and edited_weight is not None
        and edited_weight > 0
        and not selected_entry_found
        and selected_item is not None
    ):
        edited_entry = ItemPoolEntry(item_id=item_id, weight=edited_weight)
        if selected_item.type == ItemType.EVOLUTION:
            evolution_entries.append(edited_entry)
        else:
            normal_entries.append(edited_entry)

    return tuple(normal_entries), tuple(evolution_entries)


def _choose_weighted_entry(
    entries: tuple[ItemPoolEntry, ...],
    rng: random.Random,
) -> str | None:
    total = sum(entry.weight for entry in entries)
    if total <= 0:
        return None

    choice = rng.randint(1, total)
    current = 0
    for entry in entries:
        current += entry.weight
        if choice <= current:
            return entry.item_id
    return None


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


def _find_item(item_id: str, catalog: ItemCatalog | None = None) -> ItemDefinition | None:
    if catalog is not None:
        return catalog.items.get(item_id)
    return EVOLUTION_ITEMS.get(item_id)


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
