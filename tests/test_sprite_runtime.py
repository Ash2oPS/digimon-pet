import json

from digimon_pet.app.sprite_runtime import load_runtime_manifest, resolve_sprite_animation
from digimon_pet.domain.models import GrowthStage, PetState, Species


def _species() -> Species:
    return Species(
        id="agumon",
        name="Agumon",
        stage=GrowthStage.ROOKIE,
        sprite_slots={
            "idle": "assets/sprites/agumon/idle.png",
            "sleep": "assets/sprites/agumon/sleep.png",
        },
    )


def test_manifest_sprite_wins_over_species_slots(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "entries": {
                    "agumon": {
                        "asset_path": "assets/sprite_sources/dmc/agumon.png",
                        "metadata": {"frame_width": 24, "frame_height": 24, "frame_count": 4, "fps": 8},
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    manifest = load_runtime_manifest(manifest_path)
    animation = resolve_sprite_animation(PetState("agumon", GrowthStage.ROOKIE), _species(), manifest)

    assert animation is not None
    assert animation.path == "assets/sprite_sources/dmc/agumon.png"
    assert animation.frame_width == 24
    assert animation.frame_height == 24
    assert animation.frame_count == 4
    assert animation.fps == 8


def test_manifest_action_metadata_uses_current_action_then_idle(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "entries": {
                    "agumon": {
                        "asset_path": "assets/sprite_sources/dmc/agumon_idle.png",
                        "metadata": {
                            "animations": {
                                "idle": {"frame_count": 2},
                                "sleep": {
                                    "path": "assets/sprite_sources/dmc/agumon_sleep.png",
                                    "frame_width": 16,
                                    "frame_height": 18,
                                    "frame_count": 3,
                                    "fps": 4,
                                },
                            }
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    manifest = load_runtime_manifest(manifest_path)
    sleep = resolve_sprite_animation(PetState("agumon", GrowthStage.ROOKIE, current_action="sleep"), _species(), manifest)
    eat = resolve_sprite_animation(PetState("agumon", GrowthStage.ROOKIE, current_action="eat"), _species(), manifest)

    assert sleep is not None
    assert sleep.path.endswith("agumon_sleep.png")
    assert sleep.frame_width == 16
    assert sleep.frame_height == 18
    assert sleep.frame_count == 3
    assert sleep.fps == 4
    assert eat is not None
    assert eat.path.endswith("agumon_idle.png")
    assert eat.frame_count == 2


def test_species_sprite_slots_are_used_when_manifest_entry_is_missing():
    state = PetState("agumon", GrowthStage.ROOKIE, current_action="sleep")

    animation = resolve_sprite_animation(state, _species(), {"entries": {}})

    assert animation is not None
    assert animation.path == "assets/sprites/agumon/sleep.png"
    assert animation.frame_count == 1
