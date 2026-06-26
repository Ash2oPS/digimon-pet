from digimon_pet.domain.care import apply_tick, clean, scold
from digimon_pet.domain.models import GrowthStage, PetState


def test_clean_uses_happy_action_context():
    state = PetState("agumon", GrowthStage.ROOKIE)

    clean(state)

    assert state.current_action == "happy"


def test_scold_uses_angry_action_context():
    state = PetState("agumon", GrowthStage.ROOKIE)

    scold(state)

    assert state.current_action == "angry"


def test_tick_only_advances_age_and_does_not_change_needs():
    state = PetState(
        species_id="agumon",
        stage=GrowthStage.ROOKIE,
        age_seconds=10,
        total_age_seconds=130,
        hunger=40,
        fatigue=30,
        care_mistakes=2,
        is_sleeping=False,
    )

    apply_tick(state, 5, debug_multiplier=3)

    assert state.age_seconds == 25
    assert state.total_age_seconds == 145
    assert state.hunger == 40
    assert state.fatigue == 30
    assert state.care_mistakes == 2
