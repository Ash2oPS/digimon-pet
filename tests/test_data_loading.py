from digimon_pet.data import load_evolution_rules, load_item_catalog, load_species
from digimon_pet.domain.items import ItemType
from digimon_pet.domain.models import GrowthStage


def test_load_species_contains_initial_line():
    species = load_species()

    assert species["botamon"].stage == GrowthStage.BABY
    assert species["koromon"].stage == GrowthStage.BABY_2
    assert species["agumon"].stage == GrowthStage.ROOKIE
    assert species["agumon"].sprite_slots["idle"].endswith("agumon/idle.png")


def test_load_evolution_rules_contains_baby_to_rookie_path():
    rules = load_evolution_rules()

    assert [rule.target_species_id for rule in rules] == ["koromon", "agumon"]
    assert rules[0].source_species_id == "botamon"
    assert rules[1].min_training_count == 1


def test_load_item_catalog_contains_monzaemon_head():
    catalog = load_item_catalog()

    item = catalog.items["monzaemon_head"]

    assert item.id == "monzaemon_head"
    assert item.name == "Monzaemon's Head"
    assert item.description
    assert item.type == ItemType.EVOLUTION
    assert item.icon_path == "assets/items/monzaemon_head.png"
    assert item.evolution is not None
    assert item.evolution.target_species_id == "monzaemon"
    assert item.evolution.required_species_ids == ("numemon",)
    assert item.evolution.required_stages == ()


def test_load_item_catalog_contains_secondary_event_pool():
    catalog = load_item_catalog()

    entry = catalog.pools["secondary_event"][0]

    assert entry.item_id == "monzaemon_head"
    assert entry.weight == 1
