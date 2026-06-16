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


def test_save_load_persists_discovered_species(tmp_path):
    path = tmp_path / "pet_save.json"
    state = PetState(
        species_id="koromon",
        stage=GrowthStage.BABY_2,
        discovered_species_ids=["botamon", "koromon"],
    )

    save_pet_state(state, path)
    loaded = load_pet_state(path)

    assert loaded.discovered_species_ids == ["botamon", "koromon"]


def test_save_load_persists_pending_rebirth_stat_bonuses(tmp_path):
    path = tmp_path / "pet_save.json"
    state = PetState(
        species_id="numemon",
        stage=GrowthStage.CHAMPION,
        needs_rebirth_choice=True,
        pending_rebirth_stat_bonuses={"hp": 45, "speed": 7, "unknown": 99},
    )

    save_pet_state(state, path)
    loaded = load_pet_state(path)

    assert loaded.pending_rebirth_stat_bonuses == {"hp": 45, "speed": 7}


def test_load_legacy_save_marks_current_species_discovered(tmp_path):
    path = tmp_path / "pet_save.json"
    path.write_text(
        """
{
  "species_id": "agumon",
  "stage": "rookie"
}
""".strip(),
        encoding="utf-8",
    )

    loaded = load_pet_state(path)

    assert loaded.discovered_species_ids == ["agumon"]
    assert loaded.pending_rebirth_stat_bonuses == {}


def test_load_creates_default_save_when_missing(tmp_path):
    path = tmp_path / "missing" / "pet_save.json"

    loaded = load_pet_state(path)

    assert loaded.species_id == "botamon"
    assert loaded.stage == GrowthStage.BABY
    assert loaded.hp == 300
    assert loaded.mp == 300
    assert loaded.offense == 30
    assert loaded.defense == 30
    assert loaded.speed == 30
    assert loaded.brains == 30
    assert loaded.discovered_species_ids == ["botamon"]
    assert loaded.pending_rebirth_stat_bonuses == {}
    assert path.exists()
