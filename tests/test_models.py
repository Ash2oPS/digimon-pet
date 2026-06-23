from digimon_pet.domain.models import FilledIncubatorState, GrowthStage, PetState


def test_pet_state_clamps_hp_mp_higher_than_combat_stats():
    state = PetState(
        species_id="agumon",
        stage=GrowthStage.ROOKIE,
        hp=120000,
        mp=100000,
        offense=12000,
        defense=10000,
        speed=-1,
        brains=9999,
    )

    state.clamp()

    assert state.hp == 99999
    assert state.mp == 99999
    assert state.offense == 9999
    assert state.defense == 9999
    assert state.speed == 0
    assert state.brains == 9999


def test_filled_incubator_cleanup_uses_same_stat_caps():
    state = PetState(
        species_id="agumon",
        stage=GrowthStage.ROOKIE,
        filled_incubators=[
            FilledIncubatorState(
                id="slot1",
                species_id="greymon",
                stage=GrowthStage.CHAMPION,
                hp=120000,
                mp=100000,
                offense=12000,
                defense=10000,
                speed=-1,
                brains=9999,
            )
        ],
    )

    state.clamp()

    incubator = state.filled_incubators[0]
    assert incubator.hp == 99999
    assert incubator.mp == 99999
    assert incubator.offense == 9999
    assert incubator.defense == 9999
    assert incubator.speed == 0
    assert incubator.brains == 9999
