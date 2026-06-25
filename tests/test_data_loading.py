from digimon_pet.data import load_evolution_rules, load_fusion_catalog, load_item_catalog, load_species
from digimon_pet.domain.items import ItemEffectType, ItemType
from digimon_pet.domain.models import GrowthStage


def test_load_species_contains_initial_line():
    species = load_species()

    assert species["botamon"].stage == GrowthStage.BABY
    assert species["koromon"].stage == GrowthStage.BABY_2
    assert species["agumon"].stage == GrowthStage.ROOKIE
    assert species["agumon"].sprite_slots["idle"].endswith("agumon/idle.png")


def test_load_species_keeps_aliases_for_fetching_without_affecting_name(tmp_path):
    species_path = tmp_path / "species.json"
    species_path.write_text(
        """
        [
          {
            "id": "antylamon",
            "name": "Andiramon_Virus",
            "stage": "ultimate",
            "aliases": ["Antylamon", "Andiramon"],
            "sprite_slots": {}
          }
        ]
        """,
        encoding="utf-8",
    )

    species = load_species(species_path)

    assert species["antylamon"].name == "Andiramon_Virus"
    assert species["antylamon"].aliases == ("Antylamon", "Andiramon")


def test_load_species_contains_terriermon_line_with_expected_stages():
    species = load_species()

    assert species["zerimon"].stage == GrowthStage.BABY
    assert species["gummymon"].stage == GrowthStage.BABY_2
    assert species["terriermon"].stage == GrowthStage.ROOKIE
    assert species["galgomon"].stage == GrowthStage.CHAMPION
    assert species["rapidmon"].stage == GrowthStage.ULTIMATE
    assert species["rapidmon"].name == "Rapidmon"
    assert "Rapidmon Perfect" in species["rapidmon"].aliases


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


def test_load_item_catalog_contains_golden_poop_rookie_evolution():
    catalog = load_item_catalog()

    item = catalog.items["golden_poop"]

    assert item.name == "Golden Poop"
    assert item.description == "Makes any Rookie Digimon digivolve into Sukamon."
    assert item.type == ItemType.EVOLUTION
    assert item.icon_path == "assets/items/golden_poop.png"
    assert item.evolution is not None
    assert item.evolution.target_species_id == "sukamon"
    assert item.evolution.required_species_ids == ()
    assert item.evolution.required_stages == (GrowthStage.ROOKIE,)


def test_load_item_catalog_contains_food_items_added_from_manager():
    catalog = load_item_catalog()

    expected_items = {
        "digifish": ("DigiFish", "assets/items/digianchovy-icon.png"),
        "digiberry": ("DigiBerry", "assets/items/big-berry-icon.png"),
        "digiveggie": ("DigiVeggie", "assets/items/super-veggy-icon.png"),
        "digiweed": ("DigiWeed", "assets/items/spiny-green-icon.png"),
    }

    for item_id, (name, icon_path) in expected_items.items():
        item = catalog.items[item_id]
        assert item.name == name
        assert item.type == ItemType.CONSUMABLE
        assert item.icon_path == icon_path


def test_load_item_catalog_contains_consumable_effects():
    catalog = load_item_catalog()

    expected_effects = {
        "digigun": ((ItemEffectType.INSTANT_DEATH, None, 0),),
        "digimeat": ((ItemEffectType.STAT_DELTA, "offense", 25),),
        "digimushroom": ((ItemEffectType.STAT_DELTA, "speed", 25),),
        "digifish": ((ItemEffectType.STAT_DELTA, "brains", 25),),
        "digiberry": ((ItemEffectType.STAT_DELTA, "defense", 25),),
        "digiveggie": ((ItemEffectType.STAT_DELTA, "hp", 250),),
        "digiweed": ((ItemEffectType.STAT_DELTA, "mp", 250),),
    }

    for item_id, effects in expected_effects.items():
        assert tuple(
            (effect.type, effect.stat, effect.amount)
            for effect in catalog.items[item_id].effects
        ) == effects

    green_effects = catalog.items["green_thing"].effects
    assert tuple((effect.stat, effect.amount) for effect in green_effects) == (
        ("hp", 500),
        ("mp", 500),
        ("offense", 50),
        ("defense", 50),
        ("speed", 50),
        ("brains", 50),
    )


def test_load_item_catalog_contains_secondary_event_pool():
    catalog = load_item_catalog()

    entry = catalog.pools["secondary_event"][0]

    assert entry.item_id == "monzaemon_head"
    assert entry.weight == 1


def test_load_fusion_catalog_starts_empty():
    catalog = load_fusion_catalog()

    assert catalog.recipes == ()
