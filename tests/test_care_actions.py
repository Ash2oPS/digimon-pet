from digimon_pet.domain.care import clean, scold
from digimon_pet.domain.models import GrowthStage, PetState


def test_clean_uses_happy_action_context():
    state = PetState("agumon", GrowthStage.ROOKIE)

    clean(state)

    assert state.current_action == "happy"


def test_scold_uses_angry_action_context():
    state = PetState("agumon", GrowthStage.ROOKIE)

    scold(state)

    assert state.current_action == "angry"
