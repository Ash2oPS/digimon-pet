import random

import pytest

from digimon_pet.data import load_dw1_digivolutions, load_species
from digimon_pet.domain.lifecycle import (
    EvolutionSchedule,
    advance_lifecycle,
    baby_1_choices,
    choose_rebirth,
    next_lifecycle_event,
)
from digimon_pet.domain.models import GrowthStage, PetState, Species


def species_map():
    return {
        "botamon": Species("botamon", "Botamon", GrowthStage.BABY),
        "punimon": Species("punimon", "Punimon", GrowthStage.BABY),
        "poyomon": Species("poyomon", "Poyomon", GrowthStage.BABY),
        "yuramon": Species("yuramon", "Yuramon", GrowthStage.BABY),
        "koromon": Species("koromon", "Koromon", GrowthStage.BABY_2),
        "tsunomon": Species("tsunomon", "Tsunomon", GrowthStage.BABY_2),
        "tokomon": Species("tokomon", "Tokomon", GrowthStage.BABY_2),
        "tanemon": Species("tanemon", "Tanemon", GrowthStage.BABY_2),
        "agumon": Species("agumon", "Agumon", GrowthStage.ROOKIE),
        "gabumon": Species("gabumon", "Gabumon", GrowthStage.ROOKIE),
        "kunemon": Species("kunemon", "Kunemon", GrowthStage.ROOKIE),
        "numemon": Species("numemon", "Numemon", GrowthStage.CHAMPION),
        "greymon": Species("greymon", "Greymon", GrowthStage.CHAMPION),
        "sukamon": Species("sukamon", "Sukamon", GrowthStage.CHAMPION),
        "metalgreymon": Species("metalgreymon", "MetalGreymon", GrowthStage.ULTIMATE),
        "monzaemon": Species("monzaemon", "Monzaemon", GrowthStage.ULTIMATE),
        "vademon": Species("vademon", "Vademon", GrowthStage.ULTIMATE),
    }


def test_default_evolution_schedule_matches_target_stage_durations():
    schedule = EvolutionSchedule()

    assert schedule.baby_seconds == 10 * 60
    assert schedule.baby_2_seconds == 30 * 60
    assert schedule.rookie_seconds == 80 * 60
    assert schedule.champion_seconds == 2 * 60 * 60
    assert schedule.ultimate_seconds == 2 * 60 * 60


def test_baby_line_evolves_forced_and_resets_stage_state():
    schedule = EvolutionSchedule(baby_seconds=1800, baby_2_seconds=3600)
    state = PetState(
        species_id="botamon",
        stage=GrowthStage.BABY,
        age_seconds=1800,
        care_mistakes=3,
        training_count=4,
        current_action="train",
    )

    event = advance_lifecycle(state, species_map(), {}, schedule, random.Random(1))

    assert event == "evolved:koromon"
    assert state.species_id == "koromon"
    assert state.stage == GrowthStage.BABY_2
    assert state.age_seconds == 0
    assert state.care_mistakes == 0
    assert state.training_count == 0
    assert state.current_action == "idle"


def test_catalog_baby_uses_declared_natural_evolution_before_builtin_fallback():
    schedule = EvolutionSchedule(baby_seconds=1800)
    species = species_map()
    species["custombaby"] = Species("custombaby", "CustomBaby", GrowthStage.BABY)
    species["customtraining"] = Species("customtraining", "CustomTraining", GrowthStage.BABY_2)
    state = PetState(
        species_id="custombaby",
        stage=GrowthStage.BABY,
        age_seconds=1800,
    )
    digivolutions = {
        "natural_evolutions": [
            {
                "source_species_id": "custombaby",
                "target_species_id": "customtraining",
                "requirements": {"groups": {"stats": {}}},
            }
        ]
    }

    event = advance_lifecycle(state, species, digivolutions, schedule, random.Random(1))

    assert event == "evolved:customtraining"
    assert state.species_id == "customtraining"
    assert state.stage == GrowthStage.BABY_2


def test_baby_1_evolves_to_declared_baby_2_without_requirements():
    schedule = EvolutionSchedule(baby_seconds=600)
    species = species_map()
    species["custombaby"] = Species("custombaby", "CustomBaby", GrowthStage.BABY)
    species["customtraining"] = Species("customtraining", "CustomTraining", GrowthStage.BABY_2)
    state = PetState(
        species_id="custombaby",
        stage=GrowthStage.BABY,
        age_seconds=600,
        hp=0,
    )
    digivolutions = {
        "natural_evolutions": [
            {
                "source_species_id": "custombaby",
                "target_species_id": "customtraining",
                "requirements": {"groups": {"stats": {"hp": 9999}}},
            }
        ]
    }

    event = advance_lifecycle(state, species, digivolutions, schedule, random.Random(1))

    assert event == "evolved:customtraining"
    assert state.species_id == "customtraining"
    assert state.stage == GrowthStage.BABY_2


def test_catalog_baby_without_declared_evolution_does_not_use_builtin_line():
    schedule = EvolutionSchedule(baby_seconds=1800)
    species = species_map()
    species["custombaby"] = Species("custombaby", "CustomBaby", GrowthStage.BABY)
    state = PetState(
        species_id="custombaby",
        stage=GrowthStage.BABY,
        age_seconds=1800,
    )

    event = advance_lifecycle(state, species, {"natural_evolutions": []}, schedule, random.Random(1))

    assert event is None
    assert state.species_id == "custombaby"
    assert state.stage == GrowthStage.BABY


def test_evolution_boosts_two_random_stats_more_than_the_others():
    schedule = EvolutionSchedule(baby_seconds=1800)
    state = PetState(
        species_id="botamon",
        stage=GrowthStage.BABY,
        age_seconds=1800,
        hp=200,
        mp=150,
        offense=20,
        defense=30,
        speed=40,
        brains=50,
    )

    advance_lifecycle(state, species_map(), {}, schedule, random.Random(1))

    assert state.hp == 220
    assert state.mp == 172
    assert state.offense == 22
    assert state.defense == 33
    assert state.speed == 46
    assert state.brains == 55
    assert state.age_seconds == 0


def test_baby_2_evolves_to_default_rookie_line_without_dw1_data():
    schedule = EvolutionSchedule(baby_2_seconds=3600)
    state = PetState(
        species_id="koromon",
        stage=GrowthStage.BABY_2,
        age_seconds=3600,
    )

    event = advance_lifecycle(state, species_map(), {}, schedule, random.Random(1))

    assert event == "evolved:agumon"
    assert state.species_id == "agumon"
    assert state.stage == GrowthStage.ROOKIE
    assert state.age_seconds == 0


def test_catalog_baby_2_uses_declared_rookie_evolution_without_builtin_mapping():
    schedule = EvolutionSchedule(baby_2_seconds=3600)
    species = species_map()
    species["customtraining"] = Species("customtraining", "CustomTraining", GrowthStage.BABY_2)
    species["customrookie"] = Species("customrookie", "CustomRookie", GrowthStage.ROOKIE)
    state = PetState(
        species_id="customtraining",
        stage=GrowthStage.BABY_2,
        age_seconds=3600,
    )
    digivolutions = {
        "natural_evolutions": [
            {
                "source_species_id": "customtraining",
                "target_species_id": "customrookie",
                "requirements": {"groups": {"stats": {}}},
            }
        ]
    }

    event = advance_lifecycle(state, species, digivolutions, schedule, random.Random(1))

    assert event == "evolved:customrookie"
    assert state.species_id == "customrookie"
    assert state.stage == GrowthStage.ROOKIE


def test_catalog_baby_2_without_matching_evolution_does_not_use_builtin_line():
    schedule = EvolutionSchedule(baby_2_seconds=3600)
    species = species_map()
    species["customtraining"] = Species("customtraining", "CustomTraining", GrowthStage.BABY_2)
    state = PetState(
        species_id="customtraining",
        stage=GrowthStage.BABY_2,
        age_seconds=3600,
    )

    event = advance_lifecycle(state, species, {"natural_evolutions": []}, schedule, random.Random(1))

    assert event is None
    assert state.species_id == "customtraining"
    assert state.stage == GrowthStage.BABY_2


def test_baby_2_can_evolve_to_valid_dw1_rookie_candidate():
    schedule = EvolutionSchedule(baby_2_seconds=3600)
    state = PetState(
        species_id="koromon",
        stage=GrowthStage.BABY_2,
        age_seconds=3600,
        weight=15,
    )
    digivolutions = {
        "natural_evolutions": [
            {
                "source_species_id": "koromon",
                "target_species_id": "agumon",
                "requirements": {
                    "groups": {
                        "stats": {"hp": 10, "mp": 10, "offense": 1},
                        "weight": {"min": 10, "max": 20},
                        "care_mistakes": {"min": 0},
                    }
                },
            },
            {
                "source_species_id": "koromon",
                "target_species_id": "gabumon",
                "requirements": {
                    "groups": {
                        "stats": {"defense": 1, "speed": 1, "brains": 1},
                        "weight": {"min": 10, "max": 20},
                        "care_mistakes": {"min": 0},
                    }
                },
            },
        ]
    }

    event = advance_lifecycle(state, species_map(), digivolutions, schedule, random.Random(0))

    assert event == "evolved:gabumon"
    assert state.species_id == "gabumon"
    assert state.stage == GrowthStage.ROOKIE


def test_baby_2_randomly_chooses_between_valid_dw1_rookie_candidates():
    schedule = EvolutionSchedule(baby_2_seconds=3600)
    species = species_map()
    del species["kunemon"]
    digivolutions = {
        "natural_evolutions": [
            {
                "source_species_id": "koromon",
                "target_species_id": "agumon",
                "requirements": {"groups": {"stats": {"hp": 10, "mp": 10, "offense": 1}}},
            },
            {
                "source_species_id": "koromon",
                "target_species_id": "gabumon",
                "requirements": {"groups": {"stats": {"defense": 1, "speed": 1, "brains": 1}}},
            },
        ]
    }
    results = set()

    for seed in range(10):
        state = PetState(
            species_id="koromon",
            stage=GrowthStage.BABY_2,
            age_seconds=3600,
            hp=999,
            mp=999,
            offense=999,
            defense=999,
            speed=999,
            brains=999,
        )

        event = advance_lifecycle(
            state,
            species,
            digivolutions,
            schedule,
            random.Random(seed),
        )

        assert event == f"evolved:{state.species_id}"
        results.add(state.species_id)

    assert results == {"agumon", "gabumon"}


def test_baby_2_has_ten_percent_chance_to_evolve_to_kunemon():
    schedule = EvolutionSchedule(baby_2_seconds=3600)
    state = PetState(
        species_id="koromon",
        stage=GrowthStage.BABY_2,
        age_seconds=3600,
    )

    event = advance_lifecycle(state, species_map(), {}, schedule, random.Random(31))

    assert event == "evolved:kunemon"
    assert state.species_id == "kunemon"
    assert state.stage == GrowthStage.ROOKIE


def test_each_baby_1_uses_its_dw1_baby_2_line():
    schedule = EvolutionSchedule(baby_seconds=1800)
    expected = {
        "botamon": "koromon",
        "punimon": "tsunomon",
        "poyomon": "tokomon",
        "yuramon": "tanemon",
    }

    for baby_1, baby_2 in expected.items():
        state = PetState(species_id=baby_1, stage=GrowthStage.BABY, age_seconds=1800)

        advance_lifecycle(state, species_map(), {}, schedule, random.Random(1))

        assert state.species_id == baby_2


def test_terriermon_line_evolves_from_loaded_catalog_data():
    species = load_species()
    digivolutions = load_dw1_digivolutions()

    state = PetState(species_id="zerimon", stage=GrowthStage.BABY, age_seconds=1800)
    event = advance_lifecycle(
        state,
        species,
        digivolutions,
        EvolutionSchedule(baby_seconds=1800),
        random.Random(1),
    )
    assert event == "evolved:gummymon"
    assert state.stage == GrowthStage.BABY_2

    state = PetState(
        species_id="gummymon",
        stage=GrowthStage.BABY_2,
        age_seconds=3600,
        speed=500,
    )
    event = advance_lifecycle(
        state,
        species,
        digivolutions,
        EvolutionSchedule(baby_2_seconds=3600),
        random.Random(1),
    )
    assert event == "evolved:terriermon"
    assert state.stage == GrowthStage.ROOKIE

    state = PetState(
        species_id="terriermon",
        stage=GrowthStage.ROOKIE,
        age_seconds=10800,
        hp=2000,
        mp=3000,
        offense=250,
        speed=400,
    )
    event = advance_lifecycle(
        state,
        species,
        digivolutions,
        EvolutionSchedule(rookie_seconds=10800),
        random.Random(1),
    )
    assert event == "evolved:galgomon"
    assert state.stage == GrowthStage.CHAMPION

    state = PetState(
        species_id="galgomon",
        stage=GrowthStage.CHAMPION,
        age_seconds=18000,
        hp=5000,
        mp=7500,
        offense=6000,
        defense=4000,
        speed=6000,
    )
    event = advance_lifecycle(
        state,
        species,
        digivolutions,
        EvolutionSchedule(champion_seconds=18000),
        random.Random(1),
    )
    assert event == "evolved:rapidmon"
    assert state.stage == GrowthStage.ULTIMATE


def test_gummymon_evolves_to_nearest_rookie_when_requirements_are_missed():
    species = load_species()
    digivolutions = load_dw1_digivolutions()
    state = PetState(
        species_id="gummymon",
        stage=GrowthStage.BABY_2,
        age_seconds=3600,
        hp=3839,
        mp=2722,
        speed=216,
    )

    event = advance_lifecycle(
        state,
        species,
        digivolutions,
        EvolutionSchedule(baby_2_seconds=3600),
        random.Random(1),
    )

    assert event == "evolved:terriermon"
    assert state.species_id == "terriermon"
    assert state.stage == GrowthStage.ROOKIE
    assert state.age_seconds == 0


def test_baby_2_uses_nearest_declared_evolution_when_no_candidate_matches():
    schedule = EvolutionSchedule(baby_2_seconds=3600)
    species = species_map()
    species["nearrookie"] = Species("nearrookie", "NearRookie", GrowthStage.ROOKIE)
    state = PetState(
        species_id="koromon",
        stage=GrowthStage.BABY_2,
        age_seconds=3600,
        hp=300,
        mp=40,
        speed=1,
    )
    digivolutions = {
        "natural_evolutions": [
            {
                "source_species_id": "koromon",
                "target_species_id": "agumon",
                "requirements": {"groups": {"stats": {"hp": 1000, "mp": 1000}}},
            },
            {
                "source_species_id": "koromon",
                "target_species_id": "nearrookie",
                "requirements": {"groups": {"stats": {"hp": 400, "mp": 100}}},
            },
        ]
    }

    event = advance_lifecycle(state, species, digivolutions, schedule, random.Random(1))

    assert event == "evolved:nearrookie"
    assert state.species_id == "nearrookie"
    assert state.stage == GrowthStage.ROOKIE


def test_gummymon_without_loaded_catalog_data_does_not_need_runtime_mapping():
    schedule = EvolutionSchedule(baby_2_seconds=3600)
    species = species_map()
    species["gummymon"] = Species("gummymon", "Gummymon", GrowthStage.BABY_2)
    species["terriermon"] = Species("terriermon", "Terriermon", GrowthStage.ROOKIE)
    state = PetState(species_id="gummymon", stage=GrowthStage.BABY_2, age_seconds=3600)

    event = advance_lifecycle(state, species, {}, schedule, random.Random(1))

    assert event is None
    assert state.species_id == "gummymon"
    assert state.stage == GrowthStage.BABY_2


def test_rookie_falls_back_to_numemon_when_no_known_conditions_match():
    schedule = EvolutionSchedule(rookie_seconds=10800)
    state = PetState(
        species_id="agumon",
        stage=GrowthStage.ROOKIE,
        age_seconds=10800,
        care_mistakes=0,
        discipline=100,
    )
    digivolutions = {
        "natural_evolutions": [
            {
                "source_species_id": "agumon",
                "target_species_id": "greymon",
                "requirements": {
                    "groups": {
                        "stats": {"offense": 100},
                        "weight": {"target": 30, "min": 25, "max": 35},
                        "care_mistakes": {"max": 1},
                        "bonus": {"any_of": [{"type": "discipline", "min": 90}]},
                    }
                },
            }
        ]
    }

    event = advance_lifecycle(state, species_map(), digivolutions, schedule, random.Random(1))

    assert event == "evolved:numemon"
    assert state.species_id == "numemon"
    assert state.stage == GrowthStage.CHAMPION
    assert state.age_seconds == 0


def test_natural_evolution_requires_matching_weight_and_care_conditions():
    schedule = EvolutionSchedule(rookie_seconds=10800)
    digivolutions = {
        "natural_evolutions": [
            {
                "source_species_id": "agumon",
                "target_species_id": "greymon",
                "requirements": {
                    "groups": {
                        "stats": {"offense": 100},
                        "weight": {"min": 25, "max": 35},
                        "care_mistakes": {"max": 1},
                    }
                },
            }
        ]
    }
    state = PetState(
        species_id="agumon",
        stage=GrowthStage.ROOKIE,
        age_seconds=10800,
        offense=100,
        weight=40,
        care_mistakes=0,
    )

    event = advance_lifecycle(state, species_map(), digivolutions, schedule, random.Random(1))

    assert event == "evolved:numemon"

    state = PetState(
        species_id="agumon",
        stage=GrowthStage.ROOKIE,
        age_seconds=10800,
        offense=100,
        weight=30,
        care_mistakes=1,
    )

    event = advance_lifecycle(state, species_map(), digivolutions, schedule, random.Random(1))

    assert event == "evolved:greymon"


def test_random_valid_rookie_evolution_is_used_when_available():
    schedule = EvolutionSchedule(rookie_seconds=10800)
    state = PetState(
        species_id="agumon",
        stage=GrowthStage.ROOKIE,
        age_seconds=10800,
        care_mistakes=0,
        discipline=100,
    )
    digivolutions = {
        "natural_evolutions": [
            {
                "source_species_id": "agumon",
                "target_species_id": "greymon",
                "requirements": {
                    "groups": {
                        "stats": {"hp": 100},
                        "weight": {"min": 0, "max": 10},
                        "care_mistakes": {"max": 1},
                        "bonus": {"any_of": [{"type": "discipline", "min": 90}]},
                    }
                },
            }
        ]
    }

    event = advance_lifecycle(state, species_map(), digivolutions, schedule, random.Random(1))

    assert event == "evolved:greymon"
    assert state.species_id == "greymon"
    assert state.stage == GrowthStage.CHAMPION


@pytest.mark.parametrize(
    ("stat_count", "matching_stat_count"),
    [(1, 1), (2, 2), (3, 3), (4, 3), (5, 3), (6, 3)],
)
def test_rookie_champion_evolution_uses_capped_matching_stat_requirement(stat_count, matching_stat_count):
    schedule = EvolutionSchedule(rookie_seconds=10800)
    stat_names = ["hp", "mp", "offense", "defense", "speed", "brains"]
    required_stats = {stat_name: 100 for stat_name in stat_names[:stat_count]}
    matched_stats = {
        stat_name: 100 if index < matching_stat_count else 0
        for index, stat_name in enumerate(stat_names)
    }
    state = PetState(
        species_id="agumon",
        stage=GrowthStage.ROOKIE,
        age_seconds=10800,
        hp=matched_stats["hp"],
        mp=matched_stats["mp"],
        offense=matched_stats["offense"],
        defense=matched_stats["defense"],
        speed=matched_stats["speed"],
        brains=matched_stats["brains"],
        weight=30,
        care_mistakes=0,
    )
    digivolutions = {
        "natural_evolutions": [
            {
                "source_species_id": "agumon",
                "target_species_id": "greymon",
                "requirements": {
                    "groups": {
                        "stats": required_stats,
                        "weight": {"min": 25, "max": 35},
                        "care_mistakes": {"max": 1},
                    }
                },
            }
        ]
    }

    event = advance_lifecycle(state, species_map(), digivolutions, schedule, random.Random(1))

    assert event == "evolved:greymon"
    assert state.species_id == "greymon"
    assert state.stage == GrowthStage.CHAMPION


def test_champion_dies_when_no_known_ultimate_conditions_match():
    schedule = EvolutionSchedule(champion_seconds=18000)
    state = PetState(
        species_id="numemon",
        stage=GrowthStage.CHAMPION,
        age_seconds=18000,
        hunger=90,
        fatigue=80,
        discipline=12,
        care_mistakes=9,
        training_count=7,
        hp=300,
        mp=400,
        offense=50,
        defense=60,
        speed=70,
        brains=80,
        is_sleeping=True,
        current_action="sleep",
    )

    event = advance_lifecycle(state, species_map(), {"natural_evolutions": []}, schedule, random.Random(1))

    assert event == "died:choice_required"
    assert state.needs_rebirth_choice is True
    assert state.species_id == "numemon"
    assert state.pending_rebirth_stat_bonuses == {
        "mp": 60,
        "speed": 7,
        "hp": 15,
    }


def test_catalog_champion_uses_declared_ultimate_evolution_for_added_species():
    schedule = EvolutionSchedule(champion_seconds=18000)
    species = species_map()
    species["customchampion"] = Species("customchampion", "CustomChampion", GrowthStage.CHAMPION)
    species["customultimate"] = Species("customultimate", "CustomUltimate", GrowthStage.ULTIMATE)
    state = PetState(
        species_id="customchampion",
        stage=GrowthStage.CHAMPION,
        age_seconds=18000,
        hp=500,
    )
    digivolutions = {
        "natural_evolutions": [
            {
                "source_species_id": "customchampion",
                "target_species_id": "customultimate",
                "requirements": {"groups": {"stats": {"hp": 500}}},
            }
        ]
    }

    event = advance_lifecycle(state, species, digivolutions, schedule, random.Random(1))

    assert event == "evolved:customultimate"
    assert state.species_id == "customultimate"
    assert state.stage == GrowthStage.ULTIMATE
    assert state.needs_rebirth_choice is False


def test_champion_does_not_auto_evolve_to_vademon_without_praise_or_scold_action():
    schedule = EvolutionSchedule(champion_seconds=18000)
    state = PetState(
        species_id="numemon",
        stage=GrowthStage.CHAMPION,
        age_seconds=18000,
        current_action="idle",
    )
    digivolutions = {
        "special_evolutions": [
            {
                "target_species_id": "vademon",
                "source_selector": {"stage": "champion"},
                "trigger": "praise or scold with evolution counter at least 240h",
            }
        ]
    }

    event = advance_lifecycle(state, species_map(), digivolutions, schedule, random.Random(1))

    assert event == "died:choice_required"
    assert state.species_id == "numemon"
    assert state.needs_rebirth_choice is True


def test_ultimate_cannot_devolve_to_sukamon_from_full_virus_bar():
    schedule = EvolutionSchedule(ultimate_seconds=18000)
    state = PetState(
        species_id="vademon",
        stage=GrowthStage.ULTIMATE,
        age_seconds=18000,
        care_mistakes=10,
    )
    digivolutions = {
        "special_evolutions": [
            {
                "target_species_id": "sukamon",
                "source_selector": {"scope": "any"},
                "trigger": "full Virus Bar",
            }
        ]
    }

    event = advance_lifecycle(state, species_map(), digivolutions, schedule, random.Random(1))

    assert event == "died:choice_required"
    assert state.species_id == "vademon"
    assert state.needs_rebirth_choice is True


def test_full_virus_bar_does_not_special_evolve_to_sukamon():
    schedule = EvolutionSchedule(rookie_seconds=10800)
    state = PetState(
        species_id="agumon",
        stage=GrowthStage.ROOKIE,
        age_seconds=10800,
        care_mistakes=10,
    )
    digivolutions = {
        "special_evolutions": [
            {
                "target_species_id": "sukamon",
                "source_selector": {"scope": "any"},
                "trigger": "full Virus Bar",
            }
        ]
    }

    event = advance_lifecycle(state, species_map(), digivolutions, schedule, random.Random(1))

    assert event == "evolved:numemon"
    assert state.species_id == "numemon"


def test_numemon_does_not_auto_evolve_to_monzaemon_without_toy_town_suit():
    schedule = EvolutionSchedule(champion_seconds=18000)
    state = PetState(
        species_id="numemon",
        stage=GrowthStage.CHAMPION,
        age_seconds=18000,
        happiness=50,
    )
    digivolutions = {
        "special_evolutions": [
            {
                "target_species_id": "monzaemon",
                "source_selector": {"species_ids": ["numemon"]},
                "trigger": "talk to the Monzaemon suit in Toy Town",
            }
        ]
    }

    event = advance_lifecycle(state, species_map(), digivolutions, schedule, random.Random(1))

    assert event == "died:choice_required"
    assert state.species_id == "numemon"
    assert state.needs_rebirth_choice is True


def test_rebirth_resets_bakemon_lineage_and_decrements_cooldown():
    state = PetState(
        species_id="bakemon",
        stage=GrowthStage.CHAMPION,
        needs_rebirth_choice=True,
        bakemon_lineage_used=True,
        bakemon_generation_cooldown=4,
    )

    choose_rebirth(state, "botamon", species_map())

    assert state.bakemon_lineage_used is False
    assert state.bakemon_generation_cooldown == 3


def test_rebirth_choice_resets_pet_to_selected_baby_1():
    state = PetState(
        species_id="numemon",
        stage=GrowthStage.CHAMPION,
        age_seconds=18000,
        hunger=90,
        fatigue=80,
        discipline=12,
        care_mistakes=9,
        training_count=7,
        needs_rebirth_choice=True,
    )

    event = choose_rebirth(state, "yuramon", species_map())

    assert event == "reborn:yuramon"
    assert state == PetState(species_id="yuramon", stage=GrowthStage.BABY)


def test_baby_1_choices_include_every_catalog_baby():
    species = species_map()
    species["snowbotamon"] = Species("snowbotamon", "SnowBotamon", GrowthStage.BABY)

    assert baby_1_choices(species) == ("botamon", "punimon", "poyomon", "yuramon", "snowbotamon")


def test_rebirth_choice_accepts_catalog_baby_1_not_in_default_mapping():
    species = species_map()
    species["snowbotamon"] = Species("snowbotamon", "SnowBotamon", GrowthStage.BABY)
    state = PetState(species_id="numemon", stage=GrowthStage.CHAMPION, needs_rebirth_choice=True)

    event = choose_rebirth(state, "snowbotamon", species)

    assert event == "reborn:snowbotamon"
    assert state.species_id == "snowbotamon"
    assert state.stage == GrowthStage.BABY


def test_rebirth_choice_applies_pending_generation_stat_bonuses():
    state = PetState(
        species_id="numemon",
        stage=GrowthStage.CHAMPION,
        needs_rebirth_choice=True,
        generation_stat_bonuses={"hp": 12, "mp": 8},
        pending_rebirth_stat_bonuses={"hp": 45, "speed": 7, "brains": 4},
    )

    event = choose_rebirth(state, "botamon", species_map())

    assert event == "reborn:botamon"
    assert state.hp == 357
    assert state.mp == 308
    assert state.offense == 30
    assert state.defense == 30
    assert state.speed == 37
    assert state.brains == 34
    assert state.generation_stat_bonuses == {"hp": 57, "mp": 8, "speed": 7, "brains": 4}
    assert state.pending_rebirth_stat_bonuses == {}


def test_rebirth_choice_reapplies_accumulated_generation_stat_bonuses():
    state = PetState(
        species_id="numemon",
        stage=GrowthStage.CHAMPION,
        needs_rebirth_choice=True,
        generation_stat_bonuses={"hp": 57, "mp": 8, "speed": 7, "brains": 4},
    )

    event = choose_rebirth(state, "punimon", species_map())

    assert event == "reborn:punimon"
    assert state.hp == 357
    assert state.mp == 308
    assert state.offense == 30
    assert state.defense == 30
    assert state.speed == 37
    assert state.brains == 34
    assert state.generation_stat_bonuses == {"hp": 57, "mp": 8, "speed": 7, "brains": 4}


def test_ultimate_dies_after_final_lifetime():
    schedule = EvolutionSchedule(ultimate_seconds=18000)
    state = PetState(
        species_id="metalgreymon",
        stage=GrowthStage.ULTIMATE,
        age_seconds=18000,
    )

    event = advance_lifecycle(state, species_map(), {}, schedule, random.Random(1))

    assert event == "died:choice_required"
    assert state.needs_rebirth_choice is True


def test_next_lifecycle_event_reports_remaining_seconds():
    schedule = EvolutionSchedule(baby_seconds=1800)
    state = PetState(
        species_id="botamon",
        stage=GrowthStage.BABY,
        age_seconds=1200,
    )

    event = next_lifecycle_event(state, schedule)

    assert event.label == "Evolution to Koromon"
    assert event.remaining_seconds == 600
