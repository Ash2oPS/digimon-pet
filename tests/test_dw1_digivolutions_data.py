import json
from pathlib import Path


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
    assert len(data["special_evolutions"]) == 16


def test_dw1_digivolutions_contains_known_natural_paths():
    data = load_dw1_digivolutions()
    transitions = {item["id"]: item for item in data["natural_evolutions"]}

    agumon_to_greymon = transitions["agumon__to__greymon"]
    assert agumon_to_greymon["requirements"]["groups"]["stats"]["offense"] == 100
    assert agumon_to_greymon["requirements"]["groups"]["care_mistakes"]["max"] == 1
    assert agumon_to_greymon["requirements"]["groups"]["weight"] == {
        "target": 30,
        "min": 25,
        "max": 35,
    }

    greymon_to_metalgreymon = transitions["greymon__to__metalgreymon"]
    assert greymon_to_metalgreymon["requirements"]["groups"]["stats"]["hp"] == 4000
    assert {
        "type": "discipline",
        "min": 95,
    } in greymon_to_metalgreymon["requirements"]["groups"]["bonus"]["any_of"]


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
