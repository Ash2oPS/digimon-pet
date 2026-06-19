from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from digimon_pet.domain.models import GrowthStage, PetState, Species


DEFAULT_BABY_1_ID = "botamon"
ROOKIE_FALLBACK_ID = "numemon"
INHERITED_STAT_NAMES = ("hp", "mp", "offense", "defense", "speed", "brains")
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
    baby_seconds: int = 10 * 60
    baby_2_seconds: int = 30 * 60
    rookie_seconds: int = 80 * 60
    champion_seconds: int = 2 * 60 * 60
    ultimate_seconds: int = 2 * 60 * 60

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
        GrowthStage.BABY_2: f"Rookie evolution check, fallback to {rookie_id.title()}, or Kunemon",
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
        return _evolve_to(state, species[target_id], rng)
    if state.stage == GrowthStage.BABY_2:
        if "kunemon" in species and rng.random() < 0.1:
            return _evolve_to(state, species["kunemon"], rng)
        target = _choose_valid_natural_evolution(state, species, digivolutions, rng)
        if target is not None:
            return _evolve_to(state, target, rng)
        target_id = BABY_2_TO_ROOKIE.get(state.species_id, "agumon")
        return _evolve_to(state, species[target_id], rng)
    if state.stage == GrowthStage.ROOKIE:
        target = _choose_valid_natural_evolution(state, species, digivolutions, rng)
        target = target or _choose_valid_special_evolution(state, species, digivolutions, rng)
        return _evolve_to(state, target or species[ROOKIE_FALLBACK_ID], rng)
    if state.stage == GrowthStage.CHAMPION:
        target = _choose_valid_natural_evolution(state, species, digivolutions, rng)
        target = target or _choose_valid_special_evolution(state, species, digivolutions, rng)
        if target is None:
            return _die_and_rebirth(state, rng)
        return _evolve_to(state, target, rng)
    if state.stage == GrowthStage.ULTIMATE:
        return _die_and_rebirth(state, rng)
    return None


def _choose_valid_natural_evolution(
    state: PetState,
    species: dict[str, Species],
    digivolutions: dict[str, Any],
    rng: random.Random,
) -> Species | None:
    candidates = []
    for transition in digivolutions.get("natural_evolutions", []):
        target_id = str(transition.get("target_species_id", ""))
        target = species.get(target_id)
        if (
            transition.get("source_species_id") == state.species_id
            and target is not None
            and _matches_known_requirements(
                state,
                transition.get("requirements", {}),
                target=target,
            )
        ):
            candidates.append(transition)
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
    if "praise or scold" in lowered and "evolution counter at least 240h" in lowered:
        return state.stage == GrowthStage.CHAMPION and state.current_action in {"happy", "angry"}
    if "monzaemon suit" in lowered:
        return False
    if "guardromon" in lowered:
        return state.species_id == "mamemon"
    if "sleep in kunemon" in lowered:
        return False
    return False


def _matches_known_requirements(
    state: PetState,
    requirements: dict[str, Any],
    *,
    target: Species | None = None,
) -> bool:
    groups = requirements.get("groups", {})
    return _matches_stats(state, groups.get("stats"), target=target)


def _matches_stats(
    state: PetState,
    rule: dict[str, Any] | None,
    *,
    target: Species | None = None,
) -> bool:
    if not rule:
        return False
    matching_stats = sum(getattr(state, stat_name, 0) >= int(required) for stat_name, required in rule.items())
    required_matches = len(rule)
    if state.stage == GrowthStage.ROOKIE and target is not None and target.stage == GrowthStage.CHAMPION:
        required_matches = min(3, required_matches)
    return matching_stats >= required_matches


def _evolve_to(state: PetState, target: Species, rng: random.Random) -> str:
    state.species_id = target.id
    state.stage = target.stage
    _boost_evolution_stats(state, rng)
    _reset_stage_state(state)
    return f"evolved:{target.id}"


def force_evolve_to(state: PetState, target: Species, rng: random.Random) -> str:
    return _evolve_to(state, target, rng)


def force_death(state: PetState, rng: random.Random) -> str:
    return _die_and_rebirth(state, rng)


def _boost_evolution_stats(state: PetState, rng: random.Random) -> None:
    boosted_stats = set(rng.sample(INHERITED_STAT_NAMES, 2))
    for stat_name in INHERITED_STAT_NAMES:
        rate = 1.15 if stat_name in boosted_stats else 1.1
        setattr(state, stat_name, int(getattr(state, stat_name) * rate))


def _die_and_rebirth(state: PetState, rng: random.Random) -> str:
    state.pending_rebirth_stat_bonuses = _roll_rebirth_stat_bonuses(state, rng)
    state.needs_rebirth_choice = True
    state.current_action = "idle"
    state.is_sleeping = False
    return "died:choice_required"


def _roll_rebirth_stat_bonuses(state: PetState, rng: random.Random) -> dict[str, int]:
    rates = (0.15, 0.10, 0.05)
    selected_stats = rng.sample(INHERITED_STAT_NAMES, len(rates))
    return {
        stat_name: int(getattr(state, stat_name) * rate)
        for stat_name, rate in zip(selected_stats, rates, strict=True)
    }


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
    _promote_pending_rebirth_stat_bonuses(state)
    _apply_generation_stat_bonuses(state)
    state.weight = fresh.weight
    state.happiness = fresh.happiness
    state.won_battles = fresh.won_battles
    state.techniques_mastered = fresh.techniques_mastered
    state.is_sleeping = fresh.is_sleeping
    state.current_action = fresh.current_action
    state.needs_rebirth_choice = False
    state.pending_rebirth_stat_bonuses = {}
    state.bakemon_lineage_used = False
    state.bakemon_generation_cooldown = max(0, state.bakemon_generation_cooldown - 1)
    state.clamp()
    return f"reborn:{target.id}"


def _apply_rebirth_stat_bonuses(state: PetState) -> None:
    _apply_generation_stat_bonuses(state)


def _promote_pending_rebirth_stat_bonuses(state: PetState) -> None:
    for stat_name, bonus in state.pending_rebirth_stat_bonuses.items():
        if stat_name in INHERITED_STAT_NAMES:
            state.generation_stat_bonuses[stat_name] = state.generation_stat_bonuses.get(stat_name, 0) + int(bonus)


def _apply_generation_stat_bonuses(state: PetState) -> None:
    for stat_name, bonus in state.generation_stat_bonuses.items():
        if stat_name in INHERITED_STAT_NAMES:
            setattr(state, stat_name, getattr(state, stat_name) + int(bonus))


def _reset_stage_state(state: PetState) -> None:
    state.age_seconds = 0
    state.care_mistakes = 0
    state.training_count = 0
    state.is_sleeping = False
    state.current_action = "idle"
    state.needs_rebirth_choice = False
    state.clamp()
