from __future__ import annotations

from random import Random
from typing import Any

from digimon_pet.domain.models import PetState

DISCOVERABLE_EVOLUTION_STATS = ("hp", "mp", "offense", "defense", "speed", "brains")


def direct_evolution_options(digivolutions: dict[str, Any], species_id: str) -> list[dict[str, Any]]:
    transitions = {str(item.get("id")): item for item in digivolutions.get("natural_evolutions", [])}
    transition_ids = digivolutions.get("indexes", {}).get("by_source", {}).get(species_id, [])
    return [transitions[transition_id] for transition_id in transition_ids if transition_id in transitions]


def requirement_for_stat(option: dict[str, Any], stat: str) -> int | None:
    stats = option.get("requirements", {}).get("groups", {}).get("stats", {})
    if not isinstance(stats, dict) or stat not in stats:
        return None
    return int(stats[stat])


def reveal_random_evolution_clue(
    state: PetState,
    digivolutions: dict[str, Any],
    rng: Random,
) -> tuple[str, str] | None:
    candidates: list[tuple[str, list[str]]] = []
    for option in direct_evolution_options(digivolutions, state.species_id):
        transition_id = str(option.get("id", ""))
        if not transition_id:
            continue
        known = set(state.evolution_condition_discoveries.get(transition_id, []))
        unknown_stats = [stat for stat in DISCOVERABLE_EVOLUTION_STATS if stat not in known]
        if unknown_stats:
            candidates.append((transition_id, unknown_stats))
    if not candidates:
        return None

    transition_id, unknown_stats = rng.choice(candidates)
    stat = rng.choice(unknown_stats)
    discoveries = state.evolution_condition_discoveries.setdefault(transition_id, [])
    if stat not in discoveries:
        discoveries.append(stat)
    state.clamp()
    return transition_id, stat


def clean_evolution_condition_discoveries(raw: Any) -> dict[str, list[str]]:
    if not isinstance(raw, dict):
        return {}
    cleaned: dict[str, list[str]] = {}
    valid_stats = set(DISCOVERABLE_EVOLUTION_STATS)
    for transition_id, stats in raw.items():
        clean_transition_id = str(transition_id).strip()
        if not clean_transition_id or not isinstance(stats, list):
            continue
        clean_stats = list(dict.fromkeys(str(stat) for stat in stats if str(stat) in valid_stats))
        if clean_stats:
            cleaned[clean_transition_id] = clean_stats
    return cleaned
