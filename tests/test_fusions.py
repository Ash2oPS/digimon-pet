from digimon_pet.domain.fusions import (
    FusionCatalog,
    FusionRecipe,
    find_fusion_target,
    fusion_catalog_from_dict,
    fusion_catalog_to_dict,
    validate_fusion_catalog,
)
from digimon_pet.domain.models import GrowthStage, Species


def species_map() -> dict[str, Species]:
    return {
        "wargreymon": Species("wargreymon", "WarGreymon", GrowthStage.ULTIMATE),
        "metalgarurumon": Species("metalgarurumon", "MetalGarurumon", GrowthStage.ULTIMATE),
        "omnimon": Species("omnimon", "Omnimon", GrowthStage.ULTIMATE),
        "agumon": Species("agumon", "Agumon", GrowthStage.ROOKIE),
    }


def test_fusion_catalog_roundtrip():
    raw = {
        "fusions": [
            {
                "source_species_ids": ["wargreymon", "metalgarurumon"],
                "target_species_id": "omnimon",
                "notes": "Royal knight fusion",
            }
        ]
    }

    catalog = fusion_catalog_from_dict(raw)

    assert catalog == FusionCatalog(
        recipes=(
            FusionRecipe(
                source_species_ids=("wargreymon", "metalgarurumon"),
                target_species_id="omnimon",
                notes="Royal knight fusion",
            ),
        )
    )
    assert fusion_catalog_to_dict(catalog) == raw


def test_find_fusion_target_is_symmetric():
    catalog = FusionCatalog(
        recipes=(
            FusionRecipe(
                source_species_ids=("wargreymon", "metalgarurumon"),
                target_species_id="omnimon",
            ),
        )
    )

    assert find_fusion_target(catalog, "wargreymon", "metalgarurumon") == "omnimon"
    assert find_fusion_target(catalog, "metalgarurumon", "wargreymon") == "omnimon"


def test_validate_fusion_catalog_blocks_unknown_species_and_symmetric_duplicates():
    catalog = FusionCatalog(
        recipes=(
            FusionRecipe(
                source_species_ids=("wargreymon", "unknown"),
                target_species_id="omnimon",
            ),
            FusionRecipe(
                source_species_ids=("metalgarurumon", "wargreymon"),
                target_species_id="omnimon",
            ),
            FusionRecipe(
                source_species_ids=("wargreymon", "metalgarurumon"),
                target_species_id="omnimon",
            ),
        )
    )

    result = validate_fusion_catalog(catalog, species_map())

    assert "Fusion wargreymon + unknown references unknown source species: unknown" in result.errors
    assert (
        "Duplicate fusion recipe for metalgarurumon + wargreymon"
        in result.errors
    )


def test_validate_fusion_catalog_warns_for_same_source_and_low_stage_source():
    catalog = FusionCatalog(
        recipes=(
            FusionRecipe(
                source_species_ids=("agumon", "agumon"),
                target_species_id="omnimon",
            ),
        )
    )

    result = validate_fusion_catalog(catalog, species_map())

    assert result.errors == []
    assert "Fusion agumon + agumon uses the same source twice" in result.warnings
    assert "Fusion agumon + agumon uses a non-ultimate source: agumon" in result.warnings
