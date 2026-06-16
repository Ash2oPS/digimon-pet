from digimon_pet.data import load_evolution_rules, load_species
from digimon_pet.domain.models import GrowthStage


def test_load_species_contains_initial_line():
    species = load_species()

    assert species["botamon"].stage == GrowthStage.BABY
    assert species["koromon"].stage == GrowthStage.BABY_2
    assert species["agumon"].stage == GrowthStage.ROOKIE
    assert species["agumon"].sprite_slots["idle"].endswith("agumon/idle.png")


def test_load_evolution_rules_contains_baby_to_rookie_path():
    rules = load_evolution_rules()

    assert [rule.target_species_id for rule in rules] == ["koromon", "agumon"]
    assert rules[0].source_species_id == "botamon"
    assert rules[1].min_training_count == 1

