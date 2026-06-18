from __future__ import annotations

from digimon_pet.domain.models import EvolutionRule, PetState, Species


def choose_evolution(
    state: PetState,
    rules: list[EvolutionRule],
    species: dict[str, Species],
) -> Species | None:
    candidates = [
        rule
        for rule in rules
        if rule.source_species_id == state.species_id and _matches_rule(state, rule)
    ]
    if not candidates:
        return None

    selected = sorted(candidates, key=lambda rule: rule.priority, reverse=True)[0]
    return species.get(selected.target_species_id)


def _matches_rule(state: PetState, rule: EvolutionRule) -> bool:
    if state.age_seconds < rule.min_age_seconds:
        return False
    if rule.min_training_count is not None and state.training_count < rule.min_training_count:
        return False
    return True
