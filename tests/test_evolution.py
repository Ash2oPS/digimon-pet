from digimon_pet.data import load_evolution_rules, load_species
from digimon_pet.domain.evolution import choose_evolution
from digimon_pet.domain.models import GrowthStage, PetState


def test_botamon_evolves_to_koromon_when_requirements_match():
    state = PetState(
        species_id="botamon",
        stage=GrowthStage.BABY,
        age_seconds=60,
        discipline=50,
        care_mistakes=0,
    )

    evolved = choose_evolution(state, load_evolution_rules(), load_species())

    assert evolved is not None
    assert evolved.id == "koromon"


def test_koromon_does_not_evolve_without_training():
    state = PetState(
        species_id="koromon",
        stage=GrowthStage.BABY_2,
        age_seconds=180,
        discipline=50,
        care_mistakes=0,
        training_count=0,
    )

    evolved = choose_evolution(state, load_evolution_rules(), load_species())

    assert evolved is None


def test_koromon_evolves_to_agumon_when_training_requirement_matches():
    state = PetState(
        species_id="koromon",
        stage=GrowthStage.BABY_2,
        age_seconds=180,
        discipline=50,
        care_mistakes=0,
        training_count=1,
    )

    evolved = choose_evolution(state, load_evolution_rules(), load_species())

    assert evolved is not None
    assert evolved.id == "agumon"

