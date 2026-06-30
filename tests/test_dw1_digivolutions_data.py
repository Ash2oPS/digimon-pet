import json
from pathlib import Path

from digimon_pet.data import load_dw1_digivolutions, load_species


ROOT = Path(__file__).resolve().parents[1]


def load_dw1_digivolutions():
    with (ROOT / "data" / "dw1_digivolutions.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def test_dw1_digivolutions_has_expected_sources_and_counts():
    data = load_dw1_digivolutions()

    assert data["sources"]["sydmontague_gamefaqs"].startswith("https://gamefaqs.gamespot.com/")
    assert data["sources"]["anaiadnamedlaura_tumblr"] == "https://anaiadnamedlaura.tumblr.com/digivolution"
    assert len(data["digimon"]) == 65
    assert len(data["natural_evolutions"]) >= 117
    assert len(data["special_evolutions"]) == 7


def test_dw1_digivolutions_contains_known_natural_paths():
    data = load_dw1_digivolutions()
    transitions = {item["id"]: item for item in data["natural_evolutions"]}

    agumon_to_greymon = transitions["agumon__to__greymon"]
    assert agumon_to_greymon["requirements"]["groups"]["stats"]["offense"] == 100

    greymon_to_metalgreymon = transitions["greymon__to__metalgreymon"]
    assert greymon_to_metalgreymon["requirements"]["groups"]["stats"]["hp"] == 4000


def test_dw1_digivolutions_contains_complete_terriermon_line():
    data = load_dw1_digivolutions()
    transitions = {item["id"]: item for item in data["natural_evolutions"]}

    expected = [
        ("zerimon__to__gummymon", "zerimon", "gummymon", "in_training"),
        ("gummymon__to__terriermon", "gummymon", "terriermon", "rookie"),
        ("terriermon__to__galgomon", "terriermon", "galgomon", "champion"),
        ("galgomon__to__rapidmon", "galgomon", "rapidmon", "ultimate"),
    ]

    for transition_id, source_id, target_id, target_stage in expected:
        transition = transitions[transition_id]
        assert transition["source_species_id"] == source_id
        assert transition["target_species_id"] == target_id
        assert transition["target_stage"] == target_stage
        assert transition_id in data["indexes"]["by_source"][source_id]

    assert transitions["galgomon__to__rapidmon"]["target_name"] == "Rapidmon"


def test_dw1_digivolutions_only_use_stat_requirements_for_natural_paths():
    data = load_dw1_digivolutions()

    for transition in data["natural_evolutions"]:
        groups = transition["requirements"]["groups"]

        assert set(groups) <= {"stats"}


def test_dw1_digivolutions_special_paths_do_not_use_removed_care_conditions():
    data = load_dw1_digivolutions()
    removed_trigger_terms = (
        "0 happiness",
        "0 discipline",
        "discipline <=",
        "100 discipline",
        ">=50 won battles",
        "lose a life",
        "scold or praise",
    )

    for transition in data["special_evolutions"]:
        trigger = transition["trigger"].lower()

        assert not any(term in trigger for term in removed_trigger_terms)


def test_dw1_digivolutions_contains_special_paths():
    data = load_dw1_digivolutions()
    specials = {item["target_species_id"]: item for item in data["special_evolutions"]}

    assert specials["numemon"]["source_selector"] == {"stage": "rookie"}
    assert specials["numemon"]["trigger"] == "after 96h on Rookie level without natural evolution"
    assert specials["metalmamemon"]["source_selector"] == {"species_ids": ["mamemon"]}
    assert specials["giromon"]["source_selector"] == {"species_ids": ["mamemon"]}


def test_dw1_digivolutions_by_source_index_points_to_existing_transitions():
    data = load_dw1_digivolutions()
    transition_ids = {item["id"] for item in data["natural_evolutions"]}

    for source_id, indexed_ids in data["indexes"]["by_source"].items():
        assert source_id
        assert indexed_ids
        assert set(indexed_ids) <= transition_ids

    assert "agumon__to__greymon" in data["indexes"]["by_source"]["agumon"]


def test_species_contains_all_normal_dw1_evolution_targets_and_sources():
    data = load_dw1_digivolutions()
    species = load_species()
    species_ids = set(species)
    required = {"botamon", "punimon", "poyomon", "yuramon", "kunemon"}

    for transition in data["natural_evolutions"]:
        required.add(transition["source_species_id"])
        required.add(transition["target_species_id"])
    for transition in data["special_evolutions"]:
        required.add(transition["target_species_id"])
        required.update(transition.get("source_selector", {}).get("species_ids", []))

    assert required <= species_ids


def test_biyomon_is_the_only_catalog_entry_for_piyomon_alias():
    species = load_species()
    assert "biyomon" in species
    assert "piyomon" not in species
    assert "Piyomon" in species["biyomon"].aliases

    roster = json.loads((ROOT / "data" / "dw1_roster.json").read_text(encoding="utf-8"))
    roster_by_id = {item["id"]: item for item in roster}
    assert "piyomon" not in roster_by_id
    assert "Piyomon" in roster_by_id["biyomon"]["aliases"]

    data = load_dw1_digivolutions()
    assert all(row.get("id") != "piyomon" for row in data["digimon"])
    for transition in data["natural_evolutions"]:
        assert transition["source_species_id"] != "piyomon"
        assert transition["target_species_id"] != "piyomon"
    assert "piyomon" not in data["indexes"]["by_source"]

    sprite_manifest = json.loads(
        (ROOT / "data" / "dw1_sprite_manifest.json").read_text(encoding="utf-8")
    )
    assert "piyomon" not in sprite_manifest["entries"]

    artworks = json.loads((ROOT / "data" / "artwork_downloads.json").read_text(encoding="utf-8"))
    assert all(item.get("species_id") != "piyomon" for item in artworks)


def test_metal_etemon_uses_one_canonical_species_id():
    species = load_species()
    assert "metal_etemon" in species
    assert "metaletemon" not in species
    assert species["metal_etemon"].name == "MetalEtemon"
    assert species["metal_etemon"].stage.value == "mega"
    assert "Metal Etemon" in species["metal_etemon"].aliases

    roster = json.loads((ROOT / "data" / "dw1_roster.json").read_text(encoding="utf-8"))
    roster_ids = [item["id"] for item in roster]
    assert roster_ids.count("metal_etemon") == 1
    assert "metaletemon" not in roster_ids

    data = load_dw1_digivolutions()
    assert all(row.get("id") != "metaletemon" for row in data["digimon"])
    assert "metaletemon" not in data["indexes"]["by_source"]
    for transition in data["natural_evolutions"]:
        assert transition["source_species_id"] != "metaletemon"
        assert transition["target_species_id"] != "metaletemon"

    sprite_manifest = json.loads(
        (ROOT / "data" / "dw1_sprite_manifest.json").read_text(encoding="utf-8")
    )
    assert "metal_etemon" in sprite_manifest["entries"]
    assert "metaletemon" not in sprite_manifest["entries"]

    artworks = json.loads((ROOT / "data" / "artwork_downloads.json").read_text(encoding="utf-8"))
    artwork_ids = [item.get("species_id") for item in artworks]
    assert "metal_etemon" in artwork_ids
    assert "metaletemon" not in artwork_ids


def test_terriermon_line_has_runtime_assets_and_roster_entries():
    line_ids = {"zerimon", "gummymon", "terriermon", "galgomon", "rapidmon"}

    roster = json.loads((ROOT / "data" / "dw1_roster.json").read_text(encoding="utf-8"))
    roster_ids = {item["id"] for item in roster}
    assert line_ids <= roster_ids
    assert "new_digimon" not in roster_ids

    sprite_manifest = json.loads(
        (ROOT / "data" / "dw1_sprite_manifest.json").read_text(encoding="utf-8")
    )
    sprite_entries = sprite_manifest["entries"]
    assert line_ids <= set(sprite_entries)
    assert "new_digimon" not in sprite_entries
    for species_id in line_ids:
        assert (ROOT / sprite_entries[species_id]["asset_path"]).exists()

    artworks = json.loads((ROOT / "data" / "artwork_downloads.json").read_text(encoding="utf-8"))
    artwork_paths = {
        item["species_id"]: item["path"]
        for item in artworks
        if item.get("species_id") in line_ids
    }
    assert line_ids <= set(artwork_paths)
    for species_id, artwork_path in artwork_paths.items():
        assert (ROOT / artwork_path).exists(), species_id
