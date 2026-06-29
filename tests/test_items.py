import random

from digimon_pet.domain.items import (
    INCUBATOR_ID,
    MONZAEMON_HEAD_ID,
    EvolutionItemEffect,
    InventoryCategory,
    ItemEffect,
    ItemCatalog,
    ItemDefinition,
    ItemPoolEntry,
    ItemType,
    ItemEffectType,
    can_use_item,
    choose_weighted_item,
    incubate_current_digimon,
    item_catalog_from_dict,
    item_catalog_to_dict,
    use_evolution_item,
    use_item,
)
from digimon_pet.domain.lifecycle import EvolutionSchedule
from digimon_pet.domain.models import GrowthStage, PetState, Species


def species_map() -> dict[str, Species]:
    return {
        "agumon": Species("agumon", "Agumon", GrowthStage.ROOKIE),
        "numemon": Species("numemon", "Numemon", GrowthStage.CHAMPION),
        "monzaemon": Species("monzaemon", "Monzaemon", GrowthStage.ULTIMATE),
        "sukamon": Species("sukamon", "Sukamon", GrowthStage.CHAMPION),
    }


def test_monzaemon_head_evolves_numemon_and_consumes_item():
    state = PetState(
        "numemon",
        GrowthStage.CHAMPION,
        inventory={MONZAEMON_HEAD_ID: 1},
    )

    result = use_item(state, MONZAEMON_HEAD_ID, species_map(), random.Random(1))

    assert result.used is True
    assert result.event == "evolved:monzaemon"
    assert state.species_id == "monzaemon"
    assert state.stage == GrowthStage.ULTIMATE
    assert state.inventory == {}
    assert "monzaemon" in state.discovered_species_ids


def test_monzaemon_head_does_not_consume_item_for_other_species():
    state = PetState(
        "agumon",
        GrowthStage.ROOKIE,
        inventory={MONZAEMON_HEAD_ID: 1},
    )

    result = use_item(state, MONZAEMON_HEAD_ID, species_map(), random.Random(1))

    assert result.used is False
    assert result.reason == "wrong_species"
    assert state.species_id == "agumon"
    assert state.inventory == {MONZAEMON_HEAD_ID: 1}


def test_evolution_item_definition_can_require_a_growth_stage():
    item = ItemDefinition(
        id="champion_disk",
        name="Champion Disk",
        description="Forces a champion-stage evolution.",
        type=ItemType.EVOLUTION,
        evolution=EvolutionItemEffect(
            target_species_id="monzaemon",
            required_stages=(GrowthStage.CHAMPION,),
        ),
    )
    state = PetState(
        "agumon",
        GrowthStage.ROOKIE,
        inventory={"champion_disk": 1},
    )

    result = use_evolution_item(state, item, species_map(), random.Random(1))

    assert result.used is False
    assert result.reason == "wrong_stage"
    assert state.inventory == {"champion_disk": 1}


def test_evolution_item_without_requirements_evolves_any_digimon():
    item = ItemDefinition(
        id="golden_poop",
        name="Golden Poop",
        description="Makes any Digimon digivolve into Sukamon.",
        type=ItemType.EVOLUTION,
        evolution=EvolutionItemEffect(target_species_id="sukamon"),
    )
    state = PetState(
        "agumon",
        GrowthStage.ROOKIE,
        inventory={"golden_poop": 1},
    )

    result = use_evolution_item(state, item, species_map(), random.Random(1))

    assert result.used is True
    assert result.event == "evolved:sukamon"
    assert state.species_id == "sukamon"
    assert state.stage == GrowthStage.CHAMPION
    assert state.inventory == {}


def test_consumable_stat_delta_effect_increases_stat_and_consumes_item():
    item = ItemDefinition(
        id="digimeat",
        name="DigiMeat",
        description="Increases OFF by 25.",
        type=ItemType.CONSUMABLE,
        effects=(ItemEffect(type=ItemEffectType.STAT_DELTA, stat="offense", amount=25),),
    )
    catalog = ItemCatalog(items={item.id: item}, pools={})
    state = PetState(
        "agumon",
        GrowthStage.ROOKIE,
        offense=30,
        inventory={"digimeat": 1},
    )

    result = use_item(state, "digimeat", species_map(), random.Random(1), catalog)

    assert result.used is True
    assert result.stat_gains == {"offense": 25}
    assert state.offense == 55
    assert state.inventory == {}


def test_consumable_effect_can_apply_multiple_stat_deltas():
    item = ItemDefinition(
        id="green_thing",
        name="Green Thing",
        description="Increases HP and MP by 500 and OFF, DEF, SPD and INT by 50",
        type=ItemType.CONSUMABLE,
        effects=(
            ItemEffect(type=ItemEffectType.STAT_DELTA, stat="hp", amount=500),
            ItemEffect(type=ItemEffectType.STAT_DELTA, stat="mp", amount=500),
            ItemEffect(type=ItemEffectType.STAT_DELTA, stat="offense", amount=50),
            ItemEffect(type=ItemEffectType.STAT_DELTA, stat="defense", amount=50),
            ItemEffect(type=ItemEffectType.STAT_DELTA, stat="speed", amount=50),
            ItemEffect(type=ItemEffectType.STAT_DELTA, stat="brains", amount=50),
        ),
    )
    catalog = ItemCatalog(items={item.id: item}, pools={})
    state = PetState(
        "agumon",
        GrowthStage.ROOKIE,
        hp=300,
        mp=300,
        offense=30,
        defense=30,
        speed=30,
        brains=30,
        inventory={"green_thing": 1},
    )

    result = use_item(state, "green_thing", species_map(), random.Random(1), catalog)

    assert result.used is True
    assert result.stat_gains == {
        "hp": 500,
        "mp": 500,
        "offense": 50,
        "defense": 50,
        "speed": 50,
        "brains": 50,
    }
    assert state.hp == 800
    assert state.mp == 800
    assert state.offense == 80
    assert state.defense == 80
    assert state.speed == 80
    assert state.brains == 80
    assert state.inventory == {}


def test_consumable_random_stat_delta_effect_increases_one_random_stat_and_consumes_item():
    item = ItemDefinition(
        id="my_digibigburger",
        name="My DigiBigBurger",
        description="Increases a random stat by 100(0).",
        type=ItemType.CONSUMABLE,
        effects=(ItemEffect(type=ItemEffectType.RANDOM_STAT_DELTA, amount=100),),
    )
    catalog = ItemCatalog(items={item.id: item}, pools={})
    state = PetState(
        "agumon",
        GrowthStage.ROOKIE,
        hp=300,
        mp=300,
        offense=30,
        defense=30,
        speed=30,
        brains=30,
        inventory={"my_digibigburger": 1},
    )

    result = use_item(state, "my_digibigburger", species_map(), random.Random(0), catalog)

    assert result.used is True
    assert result.stat_gains == {"defense": 100}
    assert state.hp == 300
    assert state.mp == 300
    assert state.offense == 30
    assert state.defense == 130
    assert state.speed == 30
    assert state.brains == 30
    assert state.inventory == {}


def test_consumable_random_stat_delta_effect_scales_hp_and_mp_like_large_stats():
    item = ItemDefinition(
        id="my_digibigburger",
        name="My DigiBigBurger",
        description="Increases a random stat by 100(0).",
        type=ItemType.CONSUMABLE,
        effects=(ItemEffect(type=ItemEffectType.RANDOM_STAT_DELTA, amount=100),),
    )
    catalog = ItemCatalog(items={item.id: item}, pools={})
    state = PetState(
        "agumon",
        GrowthStage.ROOKIE,
        hp=300,
        mp=300,
        inventory={"my_digibigburger": 1},
    )

    result = use_item(state, "my_digibigburger", species_map(), random.Random(2), catalog)

    assert result.used is True
    assert result.stat_gains == {"hp": 1000}
    assert state.hp == 1300
    assert state.mp == 300
    assert state.inventory == {}


def test_consumable_stat_percent_effect_increases_stat_by_current_value_percent():
    item = ItemDefinition(
        id="off_chip",
        name="OFF Chip",
        description="Increases OFF by 10%.",
        type=ItemType.CONSUMABLE,
        effects=(ItemEffect(type=ItemEffectType.STAT_PERCENT, stat="offense", amount=10),),
    )
    catalog = ItemCatalog(items={item.id: item}, pools={})
    state = PetState(
        "agumon",
        GrowthStage.ROOKIE,
        offense=35,
        inventory={"off_chip": 1},
    )

    result = use_item(state, "off_chip", species_map(), random.Random(1), catalog)

    assert result.used is True
    assert result.stat_gains == {"offense": 3}
    assert state.offense == 38
    assert state.inventory == {}


def test_consumable_random_stat_percent_effect_increases_one_random_stat_by_percent():
    item = ItemDefinition(
        id="mega_chip",
        name="Mega Chip",
        description="Increases a random stat by 50%.",
        type=ItemType.CONSUMABLE,
        effects=(ItemEffect(type=ItemEffectType.RANDOM_STAT_PERCENT, amount=50),),
    )
    catalog = ItemCatalog(items={item.id: item}, pools={})
    state = PetState(
        "agumon",
        GrowthStage.ROOKIE,
        hp=300,
        mp=300,
        offense=30,
        defense=31,
        speed=30,
        brains=30,
        inventory={"mega_chip": 1},
    )

    result = use_item(state, "mega_chip", species_map(), random.Random(0), catalog)

    assert result.used is True
    assert result.stat_gains == {"defense": 15}
    assert state.defense == 46
    assert state.inventory == {}


def test_consumable_instant_death_effect_requires_rebirth_choice_and_consumes_item():
    item = ItemDefinition(
        id="digigun",
        name="DigiGun",
        description="Instantly kills your Digimon.",
        type=ItemType.CONSUMABLE,
        effects=(ItemEffect(type=ItemEffectType.INSTANT_DEATH),),
    )
    catalog = ItemCatalog(items={item.id: item}, pools={})
    state = PetState(
        "agumon",
        GrowthStage.ROOKIE,
        inventory={"digigun": 1},
    )

    result = use_item(state, "digigun", species_map(), random.Random(1), catalog)

    assert result.used is True
    assert result.event == "died:choice_required"
    assert state.needs_rebirth_choice is True
    assert state.inventory == {}


def test_consumable_lifecycle_halving_effect_halves_remaining_time_and_consumes_item():
    item = ItemDefinition(
        id="digialcohol",
        name="DigiAlcohol",
        description="Divide remaining time by 2.",
        type=ItemType.CONSUMABLE,
        effects=(ItemEffect(type=ItemEffectType.HALVE_LIFECYCLE_REMAINING),),
    )
    schedule = EvolutionSchedule(rookie_seconds=600)
    catalog = ItemCatalog(items={item.id: item}, pools={})
    state = PetState(
        "agumon",
        GrowthStage.ROOKIE,
        age_seconds=200,
        inventory={"digialcohol": 1},
    )

    result = use_item(state, "digialcohol", species_map(), random.Random(1), catalog, schedule)

    assert result.used is True
    assert state.age_seconds == 400
    assert state.inventory == {}


def test_consumable_lifecycle_halving_effect_is_blocked_with_one_minute_or_less_remaining():
    item = ItemDefinition(
        id="digialcohol",
        name="DigiAlcohol",
        description="Divide remaining time by 2.",
        type=ItemType.CONSUMABLE,
        effects=(ItemEffect(type=ItemEffectType.HALVE_LIFECYCLE_REMAINING),),
    )
    schedule = EvolutionSchedule(rookie_seconds=600)
    catalog = ItemCatalog(items={item.id: item}, pools={})

    for remaining_seconds in (60, 1, 0):
        state = PetState(
            "agumon",
            GrowthStage.ROOKIE,
            age_seconds=600 - remaining_seconds,
            inventory={"digialcohol": 1},
        )

        result = can_use_item(state, "digialcohol", species_map(), catalog, schedule)

        assert result.used is False
        assert result.reason == "lifecycle_too_soon"
        assert state.inventory == {"digialcohol": 1}


def test_incubator_is_blocked_for_baby_stages():
    item = ItemDefinition(
        id=INCUBATOR_ID,
        name="Incubator",
        description="Stores a Digimon for fusion.",
        type=ItemType.MISC,
    )
    for stage in (GrowthStage.BABY, GrowthStage.BABY_2):
        state = PetState("botamon", stage, inventory={INCUBATOR_ID: 1})

        result = incubate_current_digimon(state, item, random.Random(1), entry_id_factory=lambda: "filled")

        assert result.used is False
        assert result.reason == "wrong_stage"
        assert state.inventory == {INCUBATOR_ID: 1}
        assert state.filled_incubators == []


def test_incubator_stores_current_digimon_consumes_item_and_starts_rebirth():
    item = ItemDefinition(
        id=INCUBATOR_ID,
        name="Incubator",
        description="Stores a Digimon for fusion.",
        type=ItemType.MISC,
    )
    state = PetState(
        "greymon",
        GrowthStage.CHAMPION,
        hp=1200,
        mp=900,
        offense=140,
        defense=130,
        speed=90,
        brains=80,
        inventory={INCUBATOR_ID: 1},
    )

    result = incubate_current_digimon(state, item, random.Random(1), entry_id_factory=lambda: "filled-1")

    assert result.used is True
    assert result.event == "died:choice_required"
    assert state.inventory == {}
    assert state.needs_rebirth_choice is True
    assert len(state.filled_incubators) == 1
    incubator = state.filled_incubators[0]
    assert incubator.id == "filled-1"
    assert incubator.species_id == "greymon"
    assert incubator.stage == GrowthStage.CHAMPION
    assert incubator.hp == 1200
    assert incubator.mp == 900
    assert incubator.offense == 140
    assert incubator.defense == 130
    assert incubator.speed == 90
    assert incubator.brains == 80
    assert state.pending_rebirth_stat_bonuses == {}
    assert state.pending_rebirth_stat_source_stats == {
        "hp": 1200,
        "mp": 900,
        "offense": 140,
        "defense": 130,
        "speed": 90,
        "brains": 80,
    }


def test_weighted_item_choice_ignores_zero_weight_entries():
    catalog = ItemCatalog(
        items={
            "rare": ItemDefinition(
                id="rare",
                name="Rare",
                description="Rare item.",
                type=ItemType.MISC,
            ),
            "common": ItemDefinition(
                id="common",
                name="Common",
                description="Common item.",
                type=ItemType.MISC,
            ),
        },
        pools={
            "test": (
                ItemPoolEntry(item_id="rare", weight=0),
                ItemPoolEntry(item_id="common", weight=10),
            )
        },
    )

    assert choose_weighted_item(catalog, "test", random.Random(1)) == "common"


def test_weighted_item_choice_rejects_empty_effective_pool():
    catalog = ItemCatalog(
        items={
            "rare": ItemDefinition(
                id="rare",
                name="Rare",
                description="Rare item.",
                type=ItemType.MISC,
            ),
        },
        pools={"test": (ItemPoolEntry(item_id="rare", weight=0),)},
    )

    assert choose_weighted_item(catalog, "test", random.Random(1)) is None


class FixedRandom:
    def __init__(self, values: list[int]):
        self._values = values

    def randint(self, minimum: int, maximum: int) -> int:
        value = self._values.pop(0)
        assert minimum <= value <= maximum
        return value


def mixed_drop_catalog() -> ItemCatalog:
    normal_a = ItemDefinition(
        id="normal_a",
        name="Normal A",
        description="Normal weighted item.",
        type=ItemType.MISC,
    )
    normal_b = ItemDefinition(
        id="normal_b",
        name="Normal B",
        description="Normal weighted item.",
        type=ItemType.MISC,
    )
    evo_a = ItemDefinition(
        id="evo_a",
        name="Evolution A",
        description="Evolution item.",
        type=ItemType.EVOLUTION,
        evolution=EvolutionItemEffect(target_species_id="monzaemon"),
    )
    evo_b = ItemDefinition(
        id="evo_b",
        name="Evolution B",
        description="Evolution item.",
        type=ItemType.EVOLUTION,
        evolution=EvolutionItemEffect(target_species_id="monzaemon"),
    )
    return ItemCatalog(
        items={
            normal_a.id: normal_a,
            normal_b.id: normal_b,
            evo_a.id: evo_a,
            evo_b.id: evo_b,
        },
        pools={
            "test": (
                ItemPoolEntry(item_id=normal_a.id, weight=2),
                ItemPoolEntry(item_id=normal_b.id, weight=7),
                ItemPoolEntry(item_id=evo_a.id, weight=99),
                ItemPoolEntry(item_id=evo_b.id, weight=1),
            )
        },
    )


def test_weighted_item_choice_reserves_fifteen_percent_for_evolution_items():
    catalog = mixed_drop_catalog()

    assert choose_weighted_item(catalog, "test", FixedRandom([15, 1])) == "evo_a"
    assert choose_weighted_item(catalog, "test", FixedRandom([15, 2])) == "evo_b"
    assert choose_weighted_item(catalog, "test", FixedRandom([16, 2])) == "normal_a"
    assert choose_weighted_item(catalog, "test", FixedRandom([100, 9])) == "normal_b"


def test_item_catalog_serializes_inventory_category_when_explicit():
    catalog = ItemCatalog(
        items={
            "digigun": ItemDefinition(
                id="digigun",
                name="DigiGun",
                description="Instantly kills your Digimon.",
                type=ItemType.CONSUMABLE,
                inventory_category=InventoryCategory.SPECIAL,
                effects=(ItemEffect(type=ItemEffectType.INSTANT_DEATH),),
            )
        },
        pools={},
    )

    raw = item_catalog_to_dict(catalog)
    loaded = item_catalog_from_dict(raw)

    assert raw["items"][0]["inventory_category"] == "special"
    assert loaded.items["digigun"].inventory_category == InventoryCategory.SPECIAL


def test_item_catalog_keeps_inventory_category_optional_for_old_data():
    catalog = item_catalog_from_dict(
        {
            "items": [
                {
                    "id": "digimeat",
                    "name": "DigiMeat",
                    "description": "Increases OFF by 25.",
                    "type": "consumable",
                }
            ],
            "pools": {},
        }
    )

    assert catalog.items["digimeat"].inventory_category is None
