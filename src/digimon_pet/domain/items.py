from __future__ import annotations

import random
from dataclasses import dataclass

from digimon_pet.domain.lifecycle import force_evolve_to
from digimon_pet.domain.models import GrowthStage, PetState, Species


MONZAEMON_HEAD_ID = "monzaemon_head"


@dataclass(frozen=True)
class EvolutionItemDefinition:
    id: str
    name: str
    target_species_id: str
    required_species_ids: tuple[str, ...] = ()
    required_stages: tuple[GrowthStage, ...] = ()
    icon_path: str | None = None


@dataclass(frozen=True)
class ItemUseResult:
    used: bool
    event: str | None = None
    reason: str | None = None


EVOLUTION_ITEMS: dict[str, EvolutionItemDefinition] = {
    MONZAEMON_HEAD_ID: EvolutionItemDefinition(
        id=MONZAEMON_HEAD_ID,
        name="Monzaemon's Head",
        target_species_id="monzaemon",
        required_species_ids=("numemon",),
        icon_path="assets/items/monzaemon_head.png",
    )
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
    item: EvolutionItemDefinition,
    species: dict[str, Species],
    rng: random.Random,
) -> ItemUseResult:
    reason = _evolution_item_blocking_reason(state, item, species)
    if reason is not None:
        return ItemUseResult(used=False, reason=reason)
    target = species.get(item.target_species_id)
    if target is None:  # Guarded above; keeps the type checker honest.
        return ItemUseResult(used=False, reason="unknown_target")

    _consume_item(state, item.id)
    event = force_evolve_to(state, target, rng)
    state.mark_discovered(target.id)
    return ItemUseResult(used=True, event=event)


def _evolution_item_blocking_reason(
    state: PetState,
    item: EvolutionItemDefinition,
    species: dict[str, Species],
) -> str | None:
    if state.inventory.get(item.id, 0) <= 0:
        return "missing_item"
    if item.required_species_ids and state.species_id not in item.required_species_ids:
        return "wrong_species"
    if item.required_stages and state.stage not in item.required_stages:
        return "wrong_stage"
    if item.target_species_id not in species:
        return "unknown_target"
    return None


def _consume_item(state: PetState, item_id: str) -> None:
    quantity = state.inventory.get(item_id, 0) - 1
    if quantity <= 0:
        state.inventory.pop(item_id, None)
    else:
        state.inventory[item_id] = quantity
