from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from enum import StrEnum
from collections.abc import Callable
from typing import Any

from digimon_pet.domain.lifecycle import EvolutionSchedule, force_death, force_evolve_to
from digimon_pet.domain.models import FilledIncubatorState, GrowthStage, PetState, Species


MONZAEMON_HEAD_ID = "monzaemon_head"
INCUBATOR_ID = "incubator"
EVOLUTION_ITEM_POOL_PERCENT = 15
NORMAL_ITEM_POOL_PERCENT_WITH_EVOLUTIONS = 100 - EVOLUTION_ITEM_POOL_PERCENT
INCUBATOR_ALLOWED_STAGES = {GrowthStage.ROOKIE, GrowthStage.CHAMPION, GrowthStage.ULTIMATE}
RANDOM_STAT_DELTA_STATS = ("hp", "mp", "offense", "defense", "speed", "brains")


class ItemType(StrEnum):
    EVOLUTION = "evolution"
    CONSUMABLE = "consumable"
    KEY_ITEM = "key_item"
    MISC = "misc"


class InventoryCategory(StrEnum):
    STATS = "consumable"
    EVOLUTION = "evolution"
    SPECIAL = "special"


class ItemEffectType(StrEnum):
    STAT_DELTA = "stat_delta"
    STAT_PERCENT = "stat_percent"
    RANDOM_STAT_DELTA = "random_stat_delta"
    RANDOM_STAT_PERCENT = "random_stat_percent"
    INSTANT_DEATH = "instant_death"
    HALVE_LIFECYCLE_REMAINING = "halve_lifecycle_remaining"


@dataclass(frozen=True)
class ItemEffect:
    type: ItemEffectType
    stat: str | None = None
    amount: int = 0


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
    inventory_category: InventoryCategory | None = None
    icon_path: str | None = None
    evolution: EvolutionItemEffect | None = None
    effects: tuple[ItemEffect, ...] = ()


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
    stat_gains: dict[str, int] | None = None


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
    lifecycle_schedule: EvolutionSchedule | None = None,
) -> ItemUseResult:
    item = _find_item(item_id, catalog)
    if item is None:
        return ItemUseResult(used=False, reason="unknown_item")
    if item.type == ItemType.EVOLUTION:
        return use_evolution_item(state, item, species, rng)
    if item.type == ItemType.CONSUMABLE:
        return use_consumable_item(state, item, rng, lifecycle_schedule)
    if item.id == INCUBATOR_ID:
        return incubate_current_digimon(state, item, rng)
    return ItemUseResult(used=False, reason="not_usable")


def can_use_item(
    state: PetState,
    item_id: str,
    species: dict[str, Species],
    catalog: ItemCatalog | None = None,
    lifecycle_schedule: EvolutionSchedule | None = None,
) -> ItemUseResult:
    item = _find_item(item_id, catalog)
    if item is None:
        return ItemUseResult(used=False, reason="unknown_item")
    if item.type == ItemType.CONSUMABLE:
        reason = _consumable_item_blocking_reason(state, item, lifecycle_schedule)
        if reason is not None:
            return ItemUseResult(used=False, reason=reason)
        return ItemUseResult(used=True)
    if item.id == INCUBATOR_ID:
        return _incubator_blocking_result(state, item)
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
        if rng.randint(1, 100) <= EVOLUTION_ITEM_POOL_PERCENT:
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
        category_percent = EVOLUTION_ITEM_POOL_PERCENT if normal_entries else 100
        return round(category_percent / len(evolution_entries))

    selected_weight = next(
        (entry.weight for entry in normal_entries if entry.item_id == item_id),
        0,
    )
    total_normal_weight = sum(entry.weight for entry in normal_entries)
    if selected_weight <= 0 or total_normal_weight <= 0:
        return 0
    category_percent = NORMAL_ITEM_POOL_PERCENT_WITH_EVOLUTIONS if evolution_entries else 100
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


def use_consumable_item(
    state: PetState,
    item: ItemDefinition,
    rng: random.Random,
    lifecycle_schedule: EvolutionSchedule | None = None,
) -> ItemUseResult:
    reason = _consumable_item_blocking_reason(state, item, lifecycle_schedule)
    if reason is not None:
        return ItemUseResult(used=False, reason=reason)

    stat_gains: dict[str, int] = {}
    event: str | None = None
    for effect in item.effects:
        if effect.type == ItemEffectType.STAT_DELTA:
            if effect.stat is None or not hasattr(state, effect.stat):
                return ItemUseResult(used=False, reason="invalid_effect")
            amount = int(effect.amount)
            setattr(state, effect.stat, getattr(state, effect.stat) + amount)
            stat_gains[effect.stat] = stat_gains.get(effect.stat, 0) + amount
        elif effect.type == ItemEffectType.STAT_PERCENT:
            if effect.stat is None or not hasattr(state, effect.stat):
                return ItemUseResult(used=False, reason="invalid_effect")
            amount = _stat_percent_gain(state, effect.stat, effect.amount)
            setattr(state, effect.stat, getattr(state, effect.stat) + amount)
            stat_gains[effect.stat] = stat_gains.get(effect.stat, 0) + amount
        elif effect.type == ItemEffectType.RANDOM_STAT_DELTA:
            stat = rng.choice(RANDOM_STAT_DELTA_STATS)
            amount = int(effect.amount) * (10 if stat in {"hp", "mp"} else 1)
            setattr(state, stat, getattr(state, stat) + amount)
            stat_gains[stat] = stat_gains.get(stat, 0) + amount
        elif effect.type == ItemEffectType.RANDOM_STAT_PERCENT:
            stat = rng.choice(RANDOM_STAT_DELTA_STATS)
            amount = _stat_percent_gain(state, stat, effect.amount)
            setattr(state, stat, getattr(state, stat) + amount)
            stat_gains[stat] = stat_gains.get(stat, 0) + amount
        elif effect.type == ItemEffectType.INSTANT_DEATH:
            event = force_death(state, rng)
        elif effect.type == ItemEffectType.HALVE_LIFECYCLE_REMAINING:
            threshold = _lifecycle_threshold_for(state, lifecycle_schedule)
            remaining = max(0, threshold - state.age_seconds)
            state.age_seconds = threshold - (remaining // 2)

    state.clamp()
    _consume_item(state, item.id)
    return ItemUseResult(used=True, event=event, stat_gains=stat_gains)


def _stat_percent_gain(state: PetState, stat: str, percent: int) -> int:
    return int(getattr(state, stat) * int(percent) / 100)


def incubate_current_digimon(
    state: PetState,
    item: ItemDefinition,
    rng: random.Random,
    *,
    entry_id_factory: Callable[[], str] | None = None,
) -> ItemUseResult:
    blocked = _incubator_blocking_result(state, item)
    if not blocked.used:
        return blocked

    state.filled_incubators.append(
        FilledIncubatorState(
            id=(entry_id_factory or _new_incubator_entry_id)(),
            species_id=state.species_id,
            stage=state.stage,
            hp=state.hp,
            mp=state.mp,
            offense=state.offense,
            defense=state.defense,
            speed=state.speed,
            brains=state.brains,
        )
    )
    force_death(state, rng)
    state.needs_rebirth_choice = True
    _consume_item(state, item.id)
    state.clamp()
    return ItemUseResult(used=True, event="died:choice_required")


def _incubator_blocking_result(state: PetState, item: ItemDefinition) -> ItemUseResult:
    if item.id != INCUBATOR_ID:
        return ItemUseResult(used=False, reason="not_usable")
    if state.inventory.get(item.id, 0) <= 0:
        return ItemUseResult(used=False, reason="missing_item")
    if state.stage not in INCUBATOR_ALLOWED_STAGES:
        return ItemUseResult(used=False, reason="wrong_stage")
    return ItemUseResult(used=True)


def _new_incubator_entry_id() -> str:
    return uuid.uuid4().hex


def _consumable_item_blocking_reason(
    state: PetState,
    item: ItemDefinition,
    lifecycle_schedule: EvolutionSchedule | None = None,
) -> str | None:
    if item.type != ItemType.CONSUMABLE:
        return "not_usable"
    if state.inventory.get(item.id, 0) <= 0:
        return "missing_item"
    if not item.effects:
        return "not_usable"
    for effect in item.effects:
        if effect.type == ItemEffectType.HALVE_LIFECYCLE_REMAINING:
            threshold = _lifecycle_threshold_for(state, lifecycle_schedule)
            remaining = max(0, threshold - state.age_seconds)
            if remaining <= 60:
                return "lifecycle_too_soon"
    return None


def _lifecycle_threshold_for(
    state: PetState,
    lifecycle_schedule: EvolutionSchedule | None = None,
) -> int:
    return (lifecycle_schedule or EvolutionSchedule()).threshold_for(state.stage)


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
        inventory_category=_optional_inventory_category(raw.get("inventory_category")),
        icon_path=_optional_str(raw.get("icon_path")),
        evolution=_evolution_effect_from_dict(evolution) if evolution else None,
        effects=tuple(_item_effect_from_dict(effect) for effect in raw.get("effects", ())),
    )


def _item_effect_from_dict(raw: dict[str, Any]) -> ItemEffect:
    return ItemEffect(
        type=ItemEffectType(str(raw["type"])),
        stat=_optional_str(raw.get("stat")),
        amount=int(raw.get("amount", 0)),
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
    if item.inventory_category is not None:
        raw["inventory_category"] = item.inventory_category.value
    if item.icon_path is not None:
        raw["icon_path"] = item.icon_path
    if item.evolution is not None:
        raw["evolution"] = _evolution_effect_to_dict(item.evolution)
    if item.effects:
        raw["effects"] = [_item_effect_to_dict(effect) for effect in item.effects]
    return raw


def _item_effect_to_dict(effect: ItemEffect) -> dict[str, Any]:
    raw: dict[str, Any] = {"type": effect.type.value}
    if effect.stat is not None:
        raw["stat"] = effect.stat
    if effect.amount:
        raw["amount"] = effect.amount
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


def _optional_inventory_category(value: Any) -> InventoryCategory | None:
    if value is None:
        return None
    return InventoryCategory(str(value))
