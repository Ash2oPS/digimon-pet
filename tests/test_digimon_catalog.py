import json
from pathlib import Path

from digimon_pet.domain.digimon_catalog import (
    add_species,
    delete_species,
    digimon_catalog_to_digivolutions,
    digimon_catalog_to_species_rows,
    duplicate_species,
    load_digimon_catalog,
    rebuild_indexes_by_source,
    validate_digimon_catalog,
)
from digimon_pet.domain.items import EvolutionItemEffect, ItemCatalog, ItemDefinition, ItemType


def write_catalog_files(tmp_path: Path) -> tuple[Path, Path]:
    species_path = tmp_path / "species.json"
    digivolutions_path = tmp_path / "dw1_digivolutions.json"
    species_path.write_text(
        json.dumps(
            [
                {
                    "id": "koromon",
                    "name": "Koromon",
                    "stage": "baby_2",
                    "sprite_slots": {"idle": "assets/sprites/koromon/idle.png"},
                    "custom": "kept",
                },
                {
                    "id": "agumon",
                    "name": "Agumon",
                    "stage": "rookie",
                    "sprite_slots": {"idle": "assets/sprites/agumon/idle.png"},
                },
                {
                    "id": "greymon",
                    "name": "Greymon",
                    "stage": "champion",
                    "sprite_slots": {},
                },
            ],
            indent=2,
        ),
        encoding="utf-8",
    )
    digivolutions_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "custom_root": "kept",
                "natural_evolutions": [
                    {
                        "id": "koromon__to__agumon",
                        "type": "natural",
                        "source_species_id": "koromon",
                        "source_name": "Koromon",
                        "target_species_id": "agumon",
                        "target_name": "Agumon",
                        "target_stage": "rookie",
                        "chart_order": 1,
                        "requirements": {
                            "mode": "stats_only",
                            "groups": {"stats": {"hp": 10}},
                        },
                        "extra": "kept",
                    },
                    {
                        "id": "agumon__to__greymon",
                        "type": "natural",
                        "source_species_id": "agumon",
                        "source_name": "Agumon",
                        "target_species_id": "greymon",
                        "target_name": "Greymon",
                        "target_stage": "champion",
                        "chart_order": 2,
                        "requirements": {
                            "mode": "stats_only",
                            "groups": {"stats": {"offense": 100}},
                        },
                    },
                ],
                "special_evolutions": [
                    {
                        "id": "special__to__greymon",
                        "type": "special",
                        "target_species_id": "greymon",
                        "target_name": "Greymon",
                        "target_stage": "champion",
                        "source_selector": {"species_ids": ["agumon"]},
                        "trigger": "test trigger",
                        "notes": ["kept"],
                    }
                ],
                "indexes": {"by_source": {"stale": ["bad"]}},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return species_path, digivolutions_path


def test_catalog_round_trips_species_rows_without_data_loss(tmp_path):
    species_path, digivolutions_path = write_catalog_files(tmp_path)

    catalog = load_digimon_catalog(species_path, digivolutions_path)

    assert digimon_catalog_to_species_rows(catalog) == json.loads(
        species_path.read_text(encoding="utf-8")
    )


def test_catalog_round_trips_digivolutions_unknown_fields_and_rebuilds_index(tmp_path):
    species_path, digivolutions_path = write_catalog_files(tmp_path)

    catalog = load_digimon_catalog(species_path, digivolutions_path)
    raw = digimon_catalog_to_digivolutions(catalog)

    assert raw["custom_root"] == "kept"
    assert raw["natural_evolutions"][0]["extra"] == "kept"
    assert raw["indexes"]["by_source"] == {
        "agumon": ["agumon__to__greymon"],
        "koromon": ["koromon__to__agumon"],
    }


def test_add_species_generates_unique_ids(tmp_path):
    species_path, digivolutions_path = write_catalog_files(tmp_path)
    catalog = load_digimon_catalog(species_path, digivolutions_path)

    first = add_species(catalog)
    second = add_species(catalog)

    assert first == "new_digimon"
    assert second == "new_digimon_2"
    assert [row["id"] for row in catalog.species_rows[-2:]] == [
        "new_digimon",
        "new_digimon_2",
    ]


def test_duplicate_species_generates_incremented_id_and_name(tmp_path):
    species_path, digivolutions_path = write_catalog_files(tmp_path)
    catalog = load_digimon_catalog(species_path, digivolutions_path)

    duplicate_id = duplicate_species(catalog, "agumon")

    duplicate = catalog.species_by_id()[duplicate_id]
    assert duplicate_id == "agumon_2"
    assert duplicate["name"] == "Agumon 2"
    assert duplicate["sprite_slots"] == {"idle": "assets/sprites/agumon/idle.png"}


def test_delete_species_reports_and_removes_linked_evolutions(tmp_path):
    species_path, digivolutions_path = write_catalog_files(tmp_path)
    catalog = load_digimon_catalog(species_path, digivolutions_path)

    impact = delete_species(catalog, "agumon")

    assert impact.species_id == "agumon"
    assert impact.natural_as_source == ["agumon__to__greymon"]
    assert impact.natural_as_target == ["koromon__to__agumon"]
    assert impact.special_references == ["special__to__greymon"]
    assert "agumon" not in catalog.species_by_id()
    raw = digimon_catalog_to_digivolutions(catalog)
    assert raw["natural_evolutions"] == []
    assert raw["special_evolutions"] == []
    assert raw["indexes"]["by_source"] == {}


def test_rebuild_indexes_by_source_orders_sources_and_links(tmp_path):
    species_path, digivolutions_path = write_catalog_files(tmp_path)
    catalog = load_digimon_catalog(species_path, digivolutions_path)

    indexes = rebuild_indexes_by_source(catalog)

    assert indexes == {
        "agumon": ["agumon__to__greymon"],
        "koromon": ["koromon__to__agumon"],
    }


def test_validate_catalog_reports_blocking_errors(tmp_path):
    species_path, digivolutions_path = write_catalog_files(tmp_path)
    catalog = load_digimon_catalog(species_path, digivolutions_path)
    catalog.species_rows.append({"id": "agumon", "name": "", "stage": "bad"})
    catalog.natural_evolutions.append(
        {
            "id": "bad_link",
            "source_species_id": "missing",
            "target_species_id": "greymon",
            "requirements": {"groups": {"stats": {"bad_stat": -1}}},
        }
    )
    catalog.special_evolutions.append(
        {
            "id": "special__to__missing",
            "target_species_id": "missing",
            "source_selector": {"species_ids": ["also_missing"]},
            "trigger": "",
        }
    )

    result = validate_digimon_catalog(catalog, tmp_path)

    assert "Duplicate Digimon id: agumon" in result.errors
    assert "agumon name is required" in result.errors
    assert "agumon has invalid stage: bad" in result.errors
    assert "bad_link has malformed natural evolution id" in result.errors
    assert "bad_link references unknown source species: missing" in result.errors
    assert "bad_link uses unknown requirement stat: bad_stat" in result.errors
    assert "bad_link has invalid requirement value for bad_stat: -1" in result.errors
    assert "special__to__missing targets unknown species: missing" in result.errors
    assert "special__to__missing requires unknown source species: also_missing" in result.errors
    assert result.has_errors is True


def test_validate_catalog_reports_missing_sprite_paths_as_warnings(tmp_path):
    species_path, digivolutions_path = write_catalog_files(tmp_path)
    catalog = load_digimon_catalog(species_path, digivolutions_path)

    result = validate_digimon_catalog(catalog, tmp_path)

    assert result.errors == []
    assert "koromon missing sprite file for idle: assets/sprites/koromon/idle.png" in result.warnings
    assert result.has_errors is False


def test_validate_catalog_accepts_runtime_manifest_sprite_as_present(tmp_path):
    species_path, digivolutions_path = write_catalog_files(tmp_path)
    sprite_path = tmp_path / "assets" / "sprite_sources" / "digital_monster_color" / "Koromon.png"
    sprite_path.parent.mkdir(parents=True)
    sprite_path.write_bytes(b"not a real png")
    manifest_path = tmp_path / "data" / "dw1_sprite_manifest.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        json.dumps(
            {
                "entries": {
                    "koromon": {
                        "asset_path": "assets/sprite_sources/digital_monster_color/Koromon.png"
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    catalog = load_digimon_catalog(species_path, digivolutions_path)

    result = validate_digimon_catalog(catalog, tmp_path, sprite_manifest_path=manifest_path)

    assert "koromon missing sprite file for idle: assets/sprites/koromon/idle.png" not in result.warnings


def test_validate_catalog_counts_special_and_item_evolutions_as_obtainable(tmp_path):
    species_path, digivolutions_path = write_catalog_files(tmp_path)
    catalog = load_digimon_catalog(species_path, digivolutions_path)
    catalog.species_rows.extend(
        [
            {"id": "angemon", "name": "Angemon", "stage": "champion", "sprite_slots": {}},
            {"id": "devimon", "name": "Devimon", "stage": "champion", "sprite_slots": {}},
            {"id": "numemon", "name": "Numemon", "stage": "champion", "sprite_slots": {}},
        ]
    )
    catalog.special_evolutions.append(
        {
            "id": "special__to__numemon",
            "type": "special",
            "target_species_id": "numemon",
            "source_selector": {"stage": "rookie"},
            "trigger": "after 96h on Rookie level without natural evolution",
        }
    )
    item_catalog = ItemCatalog(
        items={
            "black_wings": ItemDefinition(
                id="black_wings",
                name="Black Wings",
                description="Makes Angemon digivolve into Devimon.",
                type=ItemType.EVOLUTION,
                evolution=EvolutionItemEffect(
                    target_species_id="devimon",
                    required_species_ids=("angemon",),
                ),
            )
        },
        pools={},
    )

    result = validate_digimon_catalog(catalog, tmp_path, item_catalog=item_catalog)

    assert "devimon has no incoming natural evolution" not in result.warnings
    assert "numemon has no incoming natural evolution" not in result.warnings
    assert "angemon has no outgoing natural evolution" not in result.warnings
