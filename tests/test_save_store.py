from digimon_pet.domain.models import GrowthStage, PetState
from digimon_pet.storage import load_pet_state, save_pet_state


def test_save_load_roundtrip(tmp_path):
    path = tmp_path / "pet_save.json"
    state = PetState(
        species_id="koromon",
        stage=GrowthStage.BABY_2,
        age_seconds=120,
        hunger=40,
        fatigue=12,
        discipline=61,
        care_mistakes=1,
        training_count=2,
        is_sleeping=True,
        current_action="sleep",
    )

    save_pet_state(state, path)
    loaded = load_pet_state(path)

    assert loaded == state


def test_load_creates_default_save_when_missing(tmp_path):
    path = tmp_path / "missing" / "pet_save.json"

    loaded = load_pet_state(path)

    assert loaded.species_id == "botamon"
    assert loaded.stage == GrowthStage.BABY
    assert path.exists()

