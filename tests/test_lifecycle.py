import random

from digimon_pet.data import load_dw1_digivolutions, load_species
from digimon_pet.domain.lifecycle import (
    EvolutionSchedule,
    advance_lifecycle,
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


def test_evolution_boosts_stats_by_ten_percent():
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
    assert state.mp == 165
    assert state.offense == 22
    assert state.defense == 33
    assert state.speed == 44
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


def test_each_baby_2_uses_closest_dw1_rookie_candidate():
    schedule = EvolutionSchedule(baby_2_seconds=3600)
    cases = [
        (
            PetState(
                species_id="koromon",
                stage=GrowthStage.BABY_2,
                age_seconds=3600,
                hp=999,
                mp=999,
                offense=999,
                defense=1,
                speed=1,
                brains=1,
                weight=15,
            ),
            "gabumon",
        ),
        (
            PetState(
                species_id="tsunomon",
                stage=GrowthStage.BABY_2,
                age_seconds=3600,
                hp=999,
                mp=10,
                offense=999,
                defense=1,
                speed=999,
                brains=1,
                weight=15,
            ),
            "penguinmon",
        ),
        (
            PetState(
                species_id="tokomon",
                stage=GrowthStage.BABY_2,
                age_seconds=3600,
                hp=10,
                mp=999,
                offense=1,
                defense=999,
                speed=999,
                brains=1,
                weight=15,
            ),
            "patamon",
        ),
        (
            PetState(
                species_id="tanemon",
                stage=GrowthStage.BABY_2,
                age_seconds=3600,
                hp=999,
                mp=10,
                defense=999,
                speed=1,
                brains=1,
                weight=15,
            ),
            "palmon",
        ),
    ]

    for state, expected_species_id in cases:
        event = advance_lifecycle(
            state,
            load_species(),
            load_dw1_digivolutions(),
            schedule,
            random.Random(0),
        )

        assert event == f"evolved:{expected_species_id}"
        assert state.species_id == expected_species_id


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


def test_rebirth_choice_applies_pending_generation_stat_bonuses():
    state = PetState(
        species_id="numemon",
        stage=GrowthStage.CHAMPION,
        needs_rebirth_choice=True,
        pending_rebirth_stat_bonuses={"hp": 45, "speed": 7, "brains": 4},
    )

    event = choose_rebirth(state, "botamon", species_map())

    assert event == "reborn:botamon"
    assert state.hp == 145
    assert state.mp == 100
    assert state.offense == 10
    assert state.defense == 10
    assert state.speed == 17
    assert state.brains == 14
    assert state.pending_rebirth_stat_bonuses == {}


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
