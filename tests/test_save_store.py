from digimon_pet.domain.models import FilledIncubatorState, GrowthStage, PetState
from digimon_pet.storage import save_store
from digimon_pet.storage import load_pet_state, save_pet_state


def test_save_writes_protected_payload_without_plain_state_fields(tmp_path):
    path = tmp_path / "pet_save.json"
    state = PetState(
        species_id="koromon",
        stage=GrowthStage.BABY_2,
        hp=456,
    )

    save_pet_state(state, path)

    raw_save = path.read_text(encoding="utf-8")
    assert "koromon" not in raw_save
    assert "species_id" not in raw_save
    assert "456" not in raw_save
    assert load_pet_state(path) == state


def test_load_encrypts_legacy_plain_json_save_immediately(tmp_path):
    path = tmp_path / "pet_save.json"
    path.write_text(
        """
{
  "species_id": "agumon",
  "stage": "rookie",
  "age_seconds": 42
}
""".strip(),
        encoding="utf-8",
    )

    loaded = load_pet_state(path)

    raw_save = path.read_text(encoding="utf-8")
    assert loaded.species_id == "agumon"
    assert loaded.age_seconds == 42
    assert "agumon" not in raw_save
    assert "species_id" not in raw_save
    assert load_pet_state(path).species_id == "agumon"


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


def test_save_load_persists_evolution_condition_discoveries(tmp_path):
    path = tmp_path / "pet_save.json"
    state = PetState(
        species_id="terriermon",
        stage=GrowthStage.ROOKIE,
        evolution_condition_discoveries={
            "terriermon__to__galgomon": ["hp", "bad_stat", "speed", "hp"],
            "missing": ["offense"],
        },
    )

    save_pet_state(state, path)
    loaded = load_pet_state(path)

    assert loaded.evolution_condition_discoveries == {
        "terriermon__to__galgomon": ["hp", "speed"],
        "missing": ["offense"],
    }


def test_save_load_persists_generation_and_pending_rebirth_stat_bonuses(tmp_path):
    path = tmp_path / "pet_save.json"
    state = PetState(
        species_id="numemon",
        stage=GrowthStage.CHAMPION,
        needs_rebirth_choice=True,
        generation_stat_bonuses={"hp": 12, "mp": 8, "unknown": 99},
        pending_rebirth_stat_bonuses={"hp": 45, "speed": 7, "unknown": 99},
    )

    save_pet_state(state, path)
    loaded = load_pet_state(path)

    assert loaded.generation_stat_bonuses == {"hp": 12, "mp": 8}
    assert loaded.pending_rebirth_stat_bonuses == {"hp": 45, "speed": 7}


def test_save_load_persists_bakemon_lineage_limits(tmp_path):
    path = tmp_path / "pet_save.json"
    state = PetState(
        species_id="bakemon",
        stage=GrowthStage.CHAMPION,
        bakemon_lineage_used=True,
        bakemon_generation_cooldown=4,
    )

    save_pet_state(state, path)
    loaded = load_pet_state(path)

    assert loaded.bakemon_lineage_used is True
    assert loaded.bakemon_generation_cooldown == 4


def test_save_load_persists_inventory(tmp_path):
    path = tmp_path / "pet_save.json"
    state = PetState(
        species_id="numemon",
        stage=GrowthStage.CHAMPION,
        inventory={"monzaemon_head": 1, "empty": 0},
    )

    save_pet_state(state, path)
    loaded = load_pet_state(path)

    assert loaded.inventory == {"monzaemon_head": 1}


def test_load_legacy_save_defaults_to_no_filled_incubators(tmp_path):
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

    assert loaded.filled_incubators == []


def test_save_load_persists_filled_incubators(tmp_path):
    path = tmp_path / "pet_save.json"
    state = PetState(
        species_id="agumon",
        stage=GrowthStage.ROOKIE,
        filled_incubators=[
            FilledIncubatorState(
                id="filled-1",
                species_id="greymon",
                stage=GrowthStage.CHAMPION,
                hp=1200,
                mp=900,
                offense=140,
                defense=130,
                speed=90,
                brains=80,
            ),
            FilledIncubatorState(
                id="filled-2",
                species_id="garurumon",
                stage=GrowthStage.CHAMPION,
                hp=1000,
                mp=1100,
                offense=120,
                defense=100,
                speed=150,
                brains=90,
            ),
        ],
    )

    save_pet_state(state, path)
    loaded = load_pet_state(path)

    assert loaded.filled_incubators == state.filled_incubators


def test_save_load_persists_secondary_event_timer(tmp_path):
    path = tmp_path / "pet_save.json"
    state = PetState(
        species_id="agumon",
        stage=GrowthStage.ROOKIE,
        secondary_event_kind="meat",
        secondary_event_ttl_seconds=17,
        secondary_event_seconds_remaining=0,
    )

    save_pet_state(state, path)
    loaded = load_pet_state(path)

    assert loaded.secondary_event_kind == "meat"
    assert loaded.secondary_event_ttl_seconds == 17
    assert loaded.secondary_event_seconds_remaining == 0


def test_save_load_persists_window_position(tmp_path):
    path = tmp_path / "pet_save.json"
    state = PetState(
        species_id="agumon",
        stage=GrowthStage.ROOKIE,
        window_x=321,
        window_y=654,
        window_screen_name="Display 2",
        window_screen_offset_x=121,
        window_screen_offset_y=54,
    )

    save_pet_state(state, path)
    loaded = load_pet_state(path)

    assert loaded.window_x == 321
    assert loaded.window_y == 654
    assert loaded.window_screen_name == "Display 2"
    assert loaded.window_screen_offset_x == 121
    assert loaded.window_screen_offset_y == 54


def test_save_load_persists_pet_scale(tmp_path):
    path = tmp_path / "pet_save.json"
    state = PetState(
        species_id="agumon",
        stage=GrowthStage.ROOKIE,
        pet_scale_percent=150,
    )

    save_pet_state(state, path)
    loaded = load_pet_state(path)

    assert loaded.pet_scale_percent == 150


def test_invalid_saved_pet_scale_falls_back_to_default(tmp_path):
    path = tmp_path / "pet_save.json"
    path.write_text(
        """
{
  "species_id": "agumon",
  "stage": "rookie",
  "pet_scale_percent": 99
}
""".strip(),
        encoding="utf-8",
    )

    loaded = load_pet_state(path)

    assert loaded.pet_scale_percent == 100


def test_save_load_cleans_invalid_filled_incubators(tmp_path):
    path = tmp_path / "pet_save.json"
    path.write_text(
        """
{
  "species_id": "agumon",
  "stage": "rookie",
  "filled_incubators": [
    {
      "id": "",
      "species_id": "greymon",
      "stage": "champion",
      "hp": 1200
    },
    {
      "id": "valid",
      "species_id": "greymon",
      "stage": "champion",
      "hp": 1200,
      "mp": 900,
      "offense": 140,
      "defense": 130,
      "speed": 90,
      "brains": 80
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    loaded = load_pet_state(path)

    assert loaded.filled_incubators == [
        FilledIncubatorState(
            id="valid",
            species_id="greymon",
            stage=GrowthStage.CHAMPION,
            hp=1200,
            mp=900,
            offense=140,
            defense=130,
            speed=90,
            brains=80,
        )
    ]


def test_load_migrates_legacy_item_ids(tmp_path):
    path = tmp_path / "pet_save.json"
    path.write_text(
        """
{
  "species_id": "numemon",
  "stage": "champion",
  "inventory": {
    "gun": 1,
    "digigun": 2
  }
}
""".strip(),
        encoding="utf-8",
    )

    loaded = load_pet_state(path)

    assert loaded.inventory == {"digigun": 3}


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
    assert loaded.generation_stat_bonuses == {}
    assert loaded.pending_rebirth_stat_bonuses == {}
    assert loaded.evolution_condition_discoveries == {}
    assert loaded.inventory == {}


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
    assert loaded.generation_stat_bonuses == {}
    assert loaded.pending_rebirth_stat_bonuses == {}
    assert loaded.inventory == {}
    assert path.exists()


def test_load_replaces_corrupt_save_with_default_and_keeps_backup(tmp_path):
    path = tmp_path / "pet_save.json"
    path.write_text("", encoding="utf-8")

    loaded = load_pet_state(path)

    assert loaded.species_id == "botamon"
    assert loaded.stage == GrowthStage.BABY
    assert path.read_text(encoding="utf-8").strip().startswith("{")
    assert path.with_suffix(".json.corrupt").exists()


def test_save_failure_preserves_existing_save(tmp_path, monkeypatch):
    path = tmp_path / "pet_save.json"
    original = PetState(species_id="koromon", stage=GrowthStage.BABY_2)
    replacement = PetState(species_id="agumon", stage=GrowthStage.ROOKIE)
    save_pet_state(original, path)
    original_raw = path.read_text(encoding="utf-8")

    def fail_json_dump(*args, **kwargs):
        raise OSError("disk write failed")

    monkeypatch.setattr(save_store.json, "dump", fail_json_dump)

    try:
        save_pet_state(replacement, path)
    except OSError:
        pass

    assert path.read_text(encoding="utf-8") == original_raw
    assert load_pet_state(path).species_id == "koromon"


def test_load_migrates_legacy_project_save_when_default_target_missing(tmp_path, monkeypatch):
    save_path = tmp_path / "user-data" / "pet_save.json"
    legacy_path = tmp_path / ".local" / "pet_save.json"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text(
        """
{
  "species_id": "agumon",
  "stage": "rookie",
  "age_seconds": 42
}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(save_store, "SAVE_PATH", save_path)
    monkeypatch.setattr(save_store, "LEGACY_SAVE_PATH", legacy_path)

    loaded = load_pet_state()

    assert loaded.species_id == "agumon"
    assert loaded.age_seconds == 42
    assert "agumon" not in save_path.read_text(encoding="utf-8")
    assert load_pet_state(save_path).species_id == "agumon"


def test_load_does_not_replace_existing_user_save_with_legacy_save(tmp_path, monkeypatch):
    save_path = tmp_path / "user-data" / "pet_save.json"
    legacy_path = tmp_path / ".local" / "pet_save.json"
    save_path.parent.mkdir(parents=True)
    legacy_path.parent.mkdir(parents=True)
    save_path.write_text(
        """
{
  "species_id": "koromon",
  "stage": "baby_2"
}
""".strip(),
        encoding="utf-8",
    )
    legacy_path.write_text(
        """
{
  "species_id": "agumon",
  "stage": "rookie"
}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(save_store, "SAVE_PATH", save_path)
    monkeypatch.setattr(save_store, "LEGACY_SAVE_PATH", legacy_path)

    loaded = load_pet_state()

    assert loaded.species_id == "koromon"
    assert "koromon" not in save_path.read_text(encoding="utf-8")
    assert load_pet_state(save_path).species_id == "koromon"


def test_configure_save_path_uses_normal_user_save_by_default(tmp_path, monkeypatch):
    normal_path = tmp_path / "Digimon Pet" / "pet_save.json"
    debug_path = tmp_path / "Digimon Pet" / "Debug" / "pet_save.json"
    monkeypatch.setattr(save_store, "NORMAL_SAVE_PATH", normal_path)
    monkeypatch.setattr(save_store, "DEBUG_SAVE_PATH", debug_path)

    save_store.configure_save_path(debug=False)

    assert save_store.SAVE_PATH == normal_path


def test_configure_save_path_uses_debug_subfolder_for_debug_mode(tmp_path, monkeypatch):
    normal_path = tmp_path / "Digimon Pet" / "pet_save.json"
    debug_path = tmp_path / "Digimon Pet" / "Debug" / "pet_save.json"
    monkeypatch.setattr(save_store, "NORMAL_SAVE_PATH", normal_path)
    monkeypatch.setattr(save_store, "DEBUG_SAVE_PATH", debug_path)

    save_store.configure_save_path(debug=True)

    assert save_store.SAVE_PATH == debug_path
