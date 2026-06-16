from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from digimon_pet.domain.models import GrowthStage, PetState, Species


DEFAULT_BABY_1_ID = "botamon"
ROOKIE_FALLBACK_ID = "numemon"
BABY_1_TO_BABY_2 = {
    "botamon": "koromon",
    "punimon": "tsunomon",
    "poyomon": "tokomon",
    "yuramon": "tanemon",
}
BABY_2_TO_ROOKIE = {
    "koromon": "agumon",
    "tsunomon": "gabumon",
    "tokomon": "patamon",
    "tanemon": "palmon",
}
BABY_1_CHOICES = tuple(BABY_1_TO_BABY_2)


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
    baby_2_id = BABY_1_TO_BABY_2.get(state.species_id, "koromon")
    rookie_id = BABY_2_TO_ROOKIE.get(state.species_id, "agumon")
    label = {
        GrowthStage.BABY: f"Evolution to {baby_2_id.title()}",
        GrowthStage.BABY_2: f"Evolution to {rookie_id.title()} or Kunemon",
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
    if state.needs_rebirth_choice:
        return None
    if state.age_seconds < schedule.threshold_for(state.stage):
        return None

    if state.stage == GrowthStage.BABY:
        target_id = BABY_1_TO_BABY_2.get(state.species_id, "koromon")
        return _evolve_to(state, species[target_id])
    if state.stage == GrowthStage.BABY_2:
        if "kunemon" in species and rng.random() < 0.1:
            return _evolve_to(state, species["kunemon"])
        target_id = BABY_2_TO_ROOKIE.get(state.species_id, "agumon")
        return _evolve_to(state, species[target_id])
    if state.stage == GrowthStage.ROOKIE:
        target = _choose_valid_natural_evolution(state, species, digivolutions, rng)
        target = target or _choose_valid_special_evolution(state, species, digivolutions, rng)
        return _evolve_to(state, target or species[ROOKIE_FALLBACK_ID])
    if state.stage == GrowthStage.CHAMPION:
        target = _choose_valid_natural_evolution(state, species, digivolutions, rng)
        target = target or _choose_valid_special_evolution(state, species, digivolutions, rng)
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


def _choose_valid_special_evolution(
    state: PetState,
    species: dict[str, Species],
    digivolutions: dict[str, Any],
    rng: random.Random,
) -> Species | None:
    candidates = [
        transition
        for transition in digivolutions.get("special_evolutions", [])
        if transition.get("target_species_id") in species
        and _matches_source_selector(state, transition.get("source_selector", {}))
        and _matches_special_trigger(state, str(transition.get("trigger", "")))
    ]
    if not candidates:
        return None
    selected = rng.choice(candidates)
    return species[str(selected["target_species_id"])]


def _matches_source_selector(state: PetState, selector: dict[str, Any]) -> bool:
    if selector.get("scope") == "any":
        return True
    if "stage" in selector and selector["stage"] != state.stage.value:
        return False
    if "species_ids" in selector and state.species_id not in selector["species_ids"]:
        return False
    if "exclude_species_ids" in selector and state.species_id in selector["exclude_species_ids"]:
        return False
    return True


def _matches_special_trigger(state: PetState, trigger: str) -> bool:
    lowered = trigger.lower()
    if "full virus bar" in lowered:
        return False
    if "0 happiness" in lowered and "0 discipline" in lowered:
        return state.happiness == 0 and state.discipline == 0
    if "discipline <= 50" in lowered:
        return state.discipline <= 50
    if "lose a life" in lowered:
        return state.care_mistakes >= 10
    if "wake up with 100 discipline" in lowered:
        return state.discipline >= 100 and state.happiness >= 100 and state.fatigue == 0
    if "100 discipline" in lowered and ">=50 won battles" in lowered:
        return state.discipline >= 100 and state.won_battles >= 50
    if "100 discipline" in lowered and ">=500 defense" in lowered:
        return state.discipline >= 100 and state.defense >= 500
    if "praise or scold" in lowered and "evolution counter at least 240h" in lowered:
        return state.stage == GrowthStage.CHAMPION and state.current_action in {"happy", "angry"}
    if "monzaemon suit" in lowered:
        return False
    if "guardromon" in lowered:
        return state.species_id == "mamemon"
    if "scold or praise" in lowered:
        return state.discipline >= 80 or state.happiness >= 80
    if "sleep in kunemon" in lowered:
        return False
    return False


def _matches_known_requirements(state: PetState, requirements: dict[str, Any]) -> bool:
    groups = requirements.get("groups", {})
    base_matches = 0

    if _matches_stats(state, groups.get("stats")):
        base_matches += 1
    if _matches_weight(state, groups.get("weight")):
        base_matches += 1
    if _matches_care_mistakes(state, groups.get("care_mistakes")):
        base_matches += 1

    bonus_matches = _matches_bonus(state, groups.get("bonus"))
    return base_matches >= 3 or (base_matches >= 2 and bonus_matches)


def _matches_stats(state: PetState, rule: dict[str, Any] | None) -> bool:
    if not rule:
        return False
    return all(getattr(state, stat_name, 0) >= int(required) for stat_name, required in rule.items())


def _matches_weight(state: PetState, rule: dict[str, Any] | None) -> bool:
    if not rule:
        return False
    return int(rule.get("min", 0)) <= state.weight <= int(rule.get("max", 9999))


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
    if condition_type == "happiness":
        return state.happiness >= int(condition.get("min", 0))
    if condition_type == "won_battles":
        if "min" in condition and state.won_battles < int(condition["min"]):
            return False
        if "max" in condition and state.won_battles > int(condition["max"]):
            return False
        return True
    if condition_type == "techniques_mastered":
        return state.techniques_mastered >= int(condition.get("min", 0))
    if condition_type == "internal_flags":
        return False
    return False


def _evolve_to(state: PetState, target: Species) -> str:
    state.species_id = target.id
    state.stage = target.stage
    _reset_stage_state(state)
    return f"evolved:{target.id}"


def _die_and_rebirth(state: PetState) -> str:
    state.needs_rebirth_choice = True
    state.current_action = "idle"
    state.is_sleeping = False
    return "died:choice_required"


def choose_rebirth(state: PetState, baby_1_id: str, species: dict[str, Species]) -> str:
    if baby_1_id not in BABY_1_CHOICES:
        raise ValueError(f"Unsupported Baby1 choice: {baby_1_id}")
    target = species[baby_1_id]
    fresh = PetState(species_id=target.id, stage=target.stage)
    state.species_id = fresh.species_id
    state.stage = fresh.stage
    state.age_seconds = fresh.age_seconds
    state.hunger = fresh.hunger
    state.fatigue = fresh.fatigue
    state.discipline = fresh.discipline
    state.care_mistakes = fresh.care_mistakes
    state.training_count = fresh.training_count
    state.hp = fresh.hp
    state.mp = fresh.mp
    state.offense = fresh.offense
    state.defense = fresh.defense
    state.speed = fresh.speed
    state.brains = fresh.brains
    state.weight = fresh.weight
    state.happiness = fresh.happiness
    state.won_battles = fresh.won_battles
    state.techniques_mastered = fresh.techniques_mastered
    state.is_sleeping = fresh.is_sleeping
    state.current_action = fresh.current_action
    state.needs_rebirth_choice = False
    return f"reborn:{target.id}"


def _reset_stage_state(state: PetState) -> None:
    state.age_seconds = 0
    state.care_mistakes = 0
    state.training_count = 0
    state.is_sleeping = False
    state.current_action = "idle"
    state.needs_rebirth_choice = False
    state.clamp()
