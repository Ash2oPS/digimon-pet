import json

from digimon_pet.app.sprite_runtime import load_or_build_runtime_manifest, load_runtime_manifest, resolve_sprite_animation
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
    assert animation.frame_indices == (0, 1)


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
    assert sleep.frame_indices == (0, 1)
    assert eat is not None
    assert eat.path.endswith("agumon_idle.png")
    assert eat.frame_count == 2
    assert eat.frame_indices == (0, 1)


def test_manifest_action_metadata_can_declare_explicit_frame_indices():
    manifest = {
        "entries": {
            "monzaemon": {
                "asset_path": "assets/sprite_sources/google_drive_sprites/monzaemon.png",
                "metadata": {
                    "frame_width": 16,
                    "frame_height": 16,
                    "frame_count": 12,
                    "animations": {
                        "idle": {"frame_indices": [0, 1]},
                        "eat": {"frame_indices": [7, 8, 11]},
                    },
                },
            }
        }
    }

    animation = resolve_sprite_animation(
        PetState("monzaemon", GrowthStage.ULTIMATE, current_action="eat"),
        Species("monzaemon", "Monzaemon", GrowthStage.ULTIMATE),
        manifest,
    )

    assert animation is not None
    assert animation.frame_indices == (7, 8, 11)


def test_species_sprite_slots_are_used_when_manifest_entry_is_missing():
    state = PetState("agumon", GrowthStage.ROOKIE, current_action="sleep")

    animation = resolve_sprite_animation(state, _species(), {"entries": {}})

    assert animation is not None
    assert animation.path == "assets/sprites/agumon/sleep.png"
    assert animation.frame_count == 1
    assert animation.frame_indices == (0,)


def test_default_digimon_sheet_uses_context_frame_sequences():
    manifest = {
        "entries": {
            "agumon": {
                "asset_path": "assets/sprite_sources/dmc/agumon.png",
                "metadata": {"frame_count": 13},
            }
        }
    }

    idle = resolve_sprite_animation(PetState("agumon", GrowthStage.ROOKIE), _species(), manifest)
    sleep = resolve_sprite_animation(PetState("agumon", GrowthStage.ROOKIE, current_action="sleep"), _species(), manifest)
    eat = resolve_sprite_animation(PetState("agumon", GrowthStage.ROOKIE, current_action="eat"), _species(), manifest)
    train = resolve_sprite_animation(PetState("agumon", GrowthStage.ROOKIE, current_action="train"), _species(), manifest)

    assert idle is not None
    assert idle.frame_indices == (0, 1)
    assert sleep is not None
    assert sleep.frame_indices == (6,)
    assert eat is not None
    assert eat.frame_indices == (5, 10)
    assert train is not None
    assert train.frame_indices == (12,)


def test_google_drive_sprite_sheet_uses_google_drive_context_frame_sequences():
    manifest = {
        "entries": {
            "terriermon": {
                "source_id": "google_drive_sprites",
                "asset_path": "assets/sprite_sources/google_drive_sprites/terriermon.png",
                "metadata": {"frame_width": 16, "frame_height": 16, "frame_count": 12},
            }
        }
    }
    species = Species("terriermon", "Terriermon", GrowthStage.ROOKIE)

    sleep = resolve_sprite_animation(
        PetState("terriermon", GrowthStage.ROOKIE, current_action="sleep"),
        species,
        manifest,
    )
    eat = resolve_sprite_animation(
        PetState("terriermon", GrowthStage.ROOKIE, current_action="eat"),
        species,
        manifest,
    )
    train = resolve_sprite_animation(
        PetState("terriermon", GrowthStage.ROOKIE, current_action="train"),
        species,
        manifest,
    )

    assert sleep is not None
    assert sleep.frame_indices == (4, 5)
    assert eat is not None
    assert eat.frame_indices == (7, 8, 11)
    assert train is not None
    assert train.frame_indices == (2, 11)


def test_default_digimon_context_frames_fall_back_to_idle_when_missing():
    manifest = {
        "entries": {
            "agumon": {
                "asset_path": "assets/sprite_sources/dmc/agumon.png",
                "metadata": {"frame_count": 2},
            }
        }
    }

    sleep = resolve_sprite_animation(PetState("agumon", GrowthStage.ROOKIE, current_action="sleep"), _species(), manifest)
    train = resolve_sprite_animation(PetState("agumon", GrowthStage.ROOKIE, current_action="train"), _species(), manifest)

    assert sleep is not None
    assert sleep.frame_indices == (0, 1)
    assert train is not None
    assert train.frame_indices == (0, 1)


def test_empty_runtime_manifest_is_rebuilt_from_local_source_manifests(tmp_path):
    roster_path = tmp_path / "data" / "roster.json"
    sources_path = tmp_path / "data" / "sources.json"
    manifest_path = tmp_path / "data" / "dw1_sprite_manifest.json"
    report_path = tmp_path / "data" / "dw1_sprite_report.md"
    source_manifest_path = tmp_path / "assets" / "sprite_sources" / "digital_monster_color" / "manifest.json"

    roster_path.parent.mkdir(parents=True)
    roster_path.write_text(json.dumps([{"id": "agumon", "name": "Agumon"}]), encoding="utf-8")
    sources_path.write_text(
        json.dumps(
            [
                {
                    "id": "digital_monster_color",
                    "name": "Digital Monster COLOR",
                    "priority": 1,
                    "manifest": "assets/sprite_sources/digital_monster_color/manifest.json",
                }
            ]
        ),
        encoding="utf-8",
    )
    manifest_path.write_text(json.dumps({"entries": {}}), encoding="utf-8")
    source_manifest_path.parent.mkdir(parents=True)
    source_manifest_path.write_text(
        json.dumps({"sprites": [{"name": "Agumon", "path": "agumon.png", "frame_count": 2}]}),
        encoding="utf-8",
    )

    manifest = load_or_build_runtime_manifest(
        tmp_path,
        manifest_path=manifest_path,
        roster_path=roster_path,
        source_config_path=sources_path,
        report_path=report_path,
    )

    assert manifest["entries"]["agumon"]["asset_path"].endswith("agumon.png")


def test_runtime_skips_declared_missing_sprite_download_by_default(tmp_path):
    roster_path = tmp_path / "data" / "roster.json"
    sources_path = tmp_path / "data" / "sources.json"
    downloads_path = tmp_path / "data" / "sprite_downloads.json"
    manifest_path = tmp_path / "data" / "dw1_sprite_manifest.json"
    report_path = tmp_path / "data" / "dw1_sprite_report.md"
    source_png = tmp_path / "remote" / "agumon.png"
    target_png = tmp_path / "assets" / "sprite_sources" / "digital_monster_color" / "agumon.png"

    roster_path.parent.mkdir(parents=True)
    roster_path.write_text(json.dumps([{"id": "agumon", "name": "Agumon"}]), encoding="utf-8")
    sources_path.write_text(
        json.dumps(
            [
                {
                    "id": "digital_monster_color",
                    "name": "Digital Monster COLOR",
                    "priority": 1,
                    "root": "assets/sprite_sources/digital_monster_color",
                    "manifest": "assets/sprite_sources/digital_monster_color/manifest.json",
                }
            ]
        ),
        encoding="utf-8",
    )
    downloads_path.write_text(
        json.dumps(
            [
                {
                    "species_id": "agumon",
                    "name": "Agumon",
                    "source_id": "digital_monster_color",
                    "url": source_png.as_uri(),
                    "path": "assets/sprite_sources/digital_monster_color/agumon.png",
                    "frame_count": 2,
                    "fps": 5,
                }
            ]
        ),
        encoding="utf-8",
    )
    source_png.parent.mkdir(parents=True)
    source_png.write_bytes(b"png bytes")

    manifest = load_or_build_runtime_manifest(
        tmp_path,
        manifest_path=manifest_path,
        roster_path=roster_path,
        source_config_path=sources_path,
        report_path=report_path,
        download_manifest_path=downloads_path,
    )

    assert not target_png.exists()
    assert manifest["entries"] == {}


def test_runtime_downloads_declared_missing_sprite_when_explicitly_allowed(tmp_path):
    roster_path = tmp_path / "data" / "roster.json"
    sources_path = tmp_path / "data" / "sources.json"
    downloads_path = tmp_path / "data" / "sprite_downloads.json"
    manifest_path = tmp_path / "data" / "dw1_sprite_manifest.json"
    report_path = tmp_path / "data" / "dw1_sprite_report.md"
    source_png = tmp_path / "remote" / "agumon.png"
    target_png = tmp_path / "assets" / "sprite_sources" / "digital_monster_color" / "agumon.png"

    roster_path.parent.mkdir(parents=True)
    roster_path.write_text(json.dumps([{"id": "agumon", "name": "Agumon"}]), encoding="utf-8")
    sources_path.write_text(
        json.dumps(
            [
                {
                    "id": "digital_monster_color",
                    "name": "Digital Monster COLOR",
                    "priority": 1,
                    "root": "assets/sprite_sources/digital_monster_color",
                    "manifest": "assets/sprite_sources/digital_monster_color/manifest.json",
                }
            ]
        ),
        encoding="utf-8",
    )
    downloads_path.write_text(
        json.dumps(
            [
                {
                    "species_id": "agumon",
                    "name": "Agumon",
                    "source_id": "digital_monster_color",
                    "url": source_png.as_uri(),
                    "path": "assets/sprite_sources/digital_monster_color/agumon.png",
                    "frame_count": 2,
                    "fps": 5,
                }
            ]
        ),
        encoding="utf-8",
    )
    source_png.parent.mkdir(parents=True)
    source_png.write_bytes(b"png bytes")

    manifest = load_or_build_runtime_manifest(
        tmp_path,
        manifest_path=manifest_path,
        roster_path=roster_path,
        source_config_path=sources_path,
        report_path=report_path,
        download_manifest_path=downloads_path,
        download_missing=True,
    )

    assert target_png.read_bytes() == b"png bytes"
    assert manifest["entries"]["agumon"]["asset_path"] == "assets/sprite_sources/digital_monster_color/agumon.png"
    assert manifest["entries"]["agumon"]["metadata"]["frame_count"] == 2
    assert manifest["entries"]["agumon"]["metadata"]["fps"] == 5


def test_runtime_writes_source_manifest_for_existing_downloaded_file(tmp_path):
    roster_path = tmp_path / "data" / "roster.json"
    sources_path = tmp_path / "data" / "sources.json"
    downloads_path = tmp_path / "data" / "sprite_downloads.json"
    manifest_path = tmp_path / "data" / "dw1_sprite_manifest.json"
    report_path = tmp_path / "data" / "dw1_sprite_report.md"
    target_png = tmp_path / "assets" / "sprite_sources" / "digital_monster_color" / "agumon.png"

    roster_path.parent.mkdir(parents=True)
    roster_path.write_text(json.dumps([{"id": "agumon", "name": "Agumon"}]), encoding="utf-8")
    sources_path.write_text(
        json.dumps(
            [
                {
                    "id": "digital_monster_color",
                    "name": "Digital Monster COLOR",
                    "priority": 1,
                    "manifest": "assets/sprite_sources/digital_monster_color/manifest.json",
                }
            ]
        ),
        encoding="utf-8",
    )
    downloads_path.write_text(
        json.dumps(
            [
                {
                    "species_id": "agumon",
                    "name": "Agumon",
                    "source_id": "digital_monster_color",
                    "url": "file:///unused/agumon.png",
                    "path": "assets/sprite_sources/digital_monster_color/agumon.png",
                    "frame_count": 2,
                }
            ]
        ),
        encoding="utf-8",
    )
    target_png.parent.mkdir(parents=True)
    target_png.write_bytes(b"already downloaded")

    manifest = load_or_build_runtime_manifest(
        tmp_path,
        manifest_path=manifest_path,
        roster_path=roster_path,
        source_config_path=sources_path,
        report_path=report_path,
        download_manifest_path=downloads_path,
        download_missing=True,
    )

    assert manifest["entries"]["agumon"]["metadata"]["frame_count"] == 2
