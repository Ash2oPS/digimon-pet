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
    assert len(data["natural_evolutions"]) == 113
    assert len(data["special_evolutions"]) == 7


def test_dw1_digivolutions_contains_known_natural_paths():
    data = load_dw1_digivolutions()
    transitions = {item["id"]: item for item in data["natural_evolutions"]}

    agumon_to_greymon = transitions["agumon__to__greymon"]
    assert agumon_to_greymon["requirements"]["groups"]["stats"]["offense"] == 100

    greymon_to_metalgreymon = transitions["greymon__to__metalgreymon"]
    assert greymon_to_metalgreymon["requirements"]["groups"]["stats"]["hp"] == 4000


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
