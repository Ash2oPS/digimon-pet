import random

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


def test_baby_2_evolves_to_current_default_rookie_line():
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
        is_sleeping=True,
        current_action="sleep",
    )

    event = advance_lifecycle(state, species_map(), {"natural_evolutions": []}, schedule, random.Random(1))

    assert event == "died:choice_required"
    assert state.needs_rebirth_choice is True
    assert state.species_id == "numemon"


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
