from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from digimon_pet.domain.models import GrowthStage, PetState, Species


DEFAULT_BABY_1_ID = "botamon"
DEFAULT_BABY_2_ID = "koromon"
DEFAULT_ROOKIE_ID = "agumon"
ROOKIE_FALLBACK_ID = "numemon"


@dataclass
class EvolutionSchedule:
    baby_seconds: int = 30 * 60
    baby_2_seconds: int = 60 * 60
    rookie_seconds: int = 3 * 60 * 60
    champion_seconds: int = 5 * 60 * 60
    ultimate_seconds: int = 5 * 60 * 60

    def threshold_for(self, stage: GrowthStage) -> int:
        return {
            GrowthStage.BABY: self.baby_seconds,
            GrowthStage.BABY_2: self.baby_2_seconds,
            GrowthStage.ROOKIE: self.rookie_seconds,
            GrowthStage.CHAMPION: self.champion_seconds,
            GrowthStage.ULTIMATE: self.ultimate_seconds,
        }[stage]


@dataclass(frozen=True)
class LifecycleEventPreview:
    label: str
    remaining_seconds: int


def next_lifecycle_event(state: PetState, schedule: EvolutionSchedule) -> LifecycleEventPreview:
    threshold = schedule.threshold_for(state.stage)
    remaining = max(0, threshold - state.age_seconds)
    label = {
        GrowthStage.BABY: "Evolution to Koromon",
        GrowthStage.BABY_2: "Evolution to Agumon",
        GrowthStage.ROOKIE: "Evolution check",
        GrowthStage.CHAMPION: "Ultimate check or death",
        GrowthStage.ULTIMATE: "Death and rebirth",
    }[state.stage]
    return LifecycleEventPreview(label=label, remaining_seconds=remaining)


def advance_lifecycle(
    state: PetState,
    species: dict[str, Species],
    digivolutions: dict[str, Any],
    schedule: EvolutionSchedule,
    rng: random.Random,
) -> str | None:
    if state.age_seconds < schedule.threshold_for(state.stage):
        return None

    if state.stage == GrowthStage.BABY:
        return _evolve_to(state, species[DEFAULT_BABY_2_ID])
    if state.stage == GrowthStage.BABY_2:
        return _evolve_to(state, species[DEFAULT_ROOKIE_ID])
    if state.stage == GrowthStage.ROOKIE:
        target = _choose_valid_natural_evolution(state, species, digivolutions, rng)
        return _evolve_to(state, target or species[ROOKIE_FALLBACK_ID])
    if state.stage == GrowthStage.CHAMPION:
        target = _choose_valid_natural_evolution(state, species, digivolutions, rng)
        if target is None:
            return _die_and_rebirth(state)
        return _evolve_to(state, target)
    if state.stage == GrowthStage.ULTIMATE:
        return _die_and_rebirth(state)
    return None


def _choose_valid_natural_evolution(
    state: PetState,
    species: dict[str, Species],
    digivolutions: dict[str, Any],
    rng: random.Random,
) -> Species | None:
    candidates = [
        transition
        for transition in digivolutions.get("natural_evolutions", [])
        if transition.get("source_species_id") == state.species_id
        and transition.get("target_species_id") in species
        and _matches_known_requirements(state, transition.get("requirements", {}))
    ]
    if not candidates:
        return None
    selected = rng.choice(candidates)
    return species[str(selected["target_species_id"])]


def _matches_known_requirements(state: PetState, requirements: dict[str, Any]) -> bool:
    groups = requirements.get("groups", {})
    base_matches = 0
    unknown_base_groups = 0

    if "stats" in groups:
        unknown_base_groups += 1
    if "weight" in groups:
        unknown_base_groups += 1
    if _matches_care_mistakes(state, groups.get("care_mistakes")):
        base_matches += 1

    bonus_matches = _matches_bonus(state, groups.get("bonus"))
    if unknown_base_groups:
        return base_matches >= 2 and bonus_matches
    return base_matches >= 3 or (base_matches >= 2 and bonus_matches) or (base_matches >= 1 and bonus_matches)


def _matches_care_mistakes(state: PetState, rule: dict[str, Any] | None) -> bool:
    if not rule:
        return False
    if "min" in rule and state.care_mistakes < int(rule["min"]):
        return False
    if "max" in rule and state.care_mistakes > int(rule["max"]):
        return False
    return True


def _matches_bonus(state: PetState, rule: dict[str, Any] | None) -> bool:
    if not rule:
        return False
    return any(_matches_bonus_condition(state, item) for item in rule.get("any_of", []))


def _matches_bonus_condition(state: PetState, condition: dict[str, Any]) -> bool:
    condition_type = condition.get("type")
    if condition_type == "current_digimon":
        return condition.get("species_id") == state.species_id
    if condition_type == "discipline":
        return state.discipline >= int(condition.get("min", 0))
    return False


def _evolve_to(state: PetState, target: Species) -> str:
    state.species_id = target.id
    state.stage = target.stage
    _reset_stage_state(state)
    return f"evolved:{target.id}"


def _die_and_rebirth(state: PetState) -> str:
    fresh = PetState(species_id=DEFAULT_BABY_1_ID, stage=GrowthStage.BABY)
    state.species_id = fresh.species_id
    state.stage = fresh.stage
    state.age_seconds = fresh.age_seconds
    state.hunger = fresh.hunger
    state.fatigue = fresh.fatigue
    state.discipline = fresh.discipline
    state.care_mistakes = fresh.care_mistakes
    state.training_count = fresh.training_count
    state.is_sleeping = fresh.is_sleeping
    state.current_action = fresh.current_action
    return f"died:{DEFAULT_BABY_1_ID}"


def _reset_stage_state(state: PetState) -> None:
    state.age_seconds = 0
    state.care_mistakes = 0
    state.training_count = 0
    state.is_sleeping = False
    state.current_action = "idle"
    state.clamp()
