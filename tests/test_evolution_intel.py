from random import Random

from digimon_pet.domain.evolution_intel import (
    DISCOVERABLE_EVOLUTION_STATS,
    direct_evolution_options,
    reveal_random_evolution_clue,
    requirement_for_stat,
)
from digimon_pet.domain.models import GrowthStage, PetState


def _digivolutions():
    return {
        "natural_evolutions": [
            {
                "id": "terriermon__to__galgomon",
                "source_species_id": "terriermon",
                "target_species_id": "galgomon",
                "target_name": "Galgomon",
                "target_stage": "champion",
                "requirements": {"groups": {"stats": {"hp": 2000, "speed": 400}}},
            }
        ],
        "indexes": {"by_source": {"terriermon": ["terriermon__to__galgomon"]}},
    }


def test_direct_evolution_options_follow_source_index_order():
    options = direct_evolution_options(_digivolutions(), "terriermon")

    assert [option["id"] for option in options] == ["terriermon__to__galgomon"]


def test_requirement_for_stat_returns_threshold_or_none_for_no_requirement():
    option = direct_evolution_options(_digivolutions(), "terriermon")[0]

    assert requirement_for_stat(option, "speed") == 400
    assert requirement_for_stat(option, "defense") is None


def test_reveal_random_evolution_clue_records_one_unknown_stat():
    state = PetState("terriermon", GrowthStage.ROOKIE)
    rng = Random(1)

    revealed = reveal_random_evolution_clue(state, _digivolutions(), rng)

    assert revealed is not None
    transition_id, stat = revealed
    assert transition_id == "terriermon__to__galgomon"
    assert stat in DISCOVERABLE_EVOLUTION_STATS
    assert state.evolution_condition_discoveries == {transition_id: [stat]}


def test_reveal_random_evolution_clue_does_nothing_when_all_direct_clues_known():
    state = PetState(
        "terriermon",
        GrowthStage.ROOKIE,
        evolution_condition_discoveries={
            "terriermon__to__galgomon": list(DISCOVERABLE_EVOLUTION_STATS),
        },
    )

    revealed = reveal_random_evolution_clue(state, _digivolutions(), Random(1))

    assert revealed is None
    assert state.evolution_condition_discoveries["terriermon__to__galgomon"] == list(
        DISCOVERABLE_EVOLUTION_STATS
    )
