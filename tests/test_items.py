import random

from digimon_pet.domain.items import (
    MONZAEMON_HEAD_ID,
    EvolutionItemDefinition,
    grant_starting_items,
    use_evolution_item,
    use_item,
)
from digimon_pet.domain.models import GrowthStage, PetState, Species


def species_map() -> dict[str, Species]:
    return {
        "agumon": Species("agumon", "Agumon", GrowthStage.ROOKIE),
        "numemon": Species("numemon", "Numemon", GrowthStage.CHAMPION),
        "monzaemon": Species("monzaemon", "Monzaemon", GrowthStage.ULTIMATE),
    }


def test_grant_starting_items_forces_one_monzaemon_head():
    state = PetState("botamon", GrowthStage.BABY)

    grant_starting_items(state)

    assert state.inventory[MONZAEMON_HEAD_ID] == 1


def test_grant_starting_items_does_not_stack_monzaemon_head_above_existing_count():
    state = PetState("botamon", GrowthStage.BABY, inventory={MONZAEMON_HEAD_ID: 3})

    grant_starting_items(state)

    assert state.inventory[MONZAEMON_HEAD_ID] == 3


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
    item = EvolutionItemDefinition(
        id="champion_disk",
        name="Champion Disk",
        target_species_id="monzaemon",
        required_stages=(GrowthStage.CHAMPION,),
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
