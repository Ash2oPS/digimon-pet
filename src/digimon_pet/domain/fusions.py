from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from digimon_pet.domain.models import GrowthStage, Species


@dataclass(frozen=True)
class FusionRecipe:
    source_species_ids: tuple[str, str]
    target_species_id: str
    notes: str = ""


@dataclass
class FusionCatalog:
    recipes: tuple[FusionRecipe, ...] = ()


@dataclass(frozen=True)
class FusionValidationResult:
    errors: list[str]
    warnings: list[str]

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)


def fusion_catalog_from_dict(raw: dict[str, Any]) -> FusionCatalog:
    recipes: list[FusionRecipe] = []
    for item in raw.get("fusions", []):
        if not isinstance(item, dict):
            continue
        sources = tuple(str(source) for source in item.get("source_species_ids", ()))
        if len(sources) != 2:
            recipes.append(
                FusionRecipe(
                    source_species_ids=(sources[0] if sources else "", ""),
                    target_species_id=str(item.get("target_species_id", "")),
                    notes=str(item.get("notes", "")),
                )
            )
            continue
        recipes.append(
            FusionRecipe(
                source_species_ids=(sources[0], sources[1]),
                target_species_id=str(item.get("target_species_id", "")),
                notes=str(item.get("notes", "")),
            )
        )
    return FusionCatalog(recipes=tuple(recipes))


def fusion_catalog_to_dict(catalog: FusionCatalog) -> dict[str, Any]:
    return {
        "fusions": [
            {
                "source_species_ids": list(recipe.source_species_ids),
                "target_species_id": recipe.target_species_id,
                **({"notes": recipe.notes} if recipe.notes else {}),
            }
            for recipe in catalog.recipes
        ]
    }


def find_fusion_target(catalog: FusionCatalog, first_species_id: str, second_species_id: str) -> str | None:
    selected_pair = _fusion_pair(first_species_id, second_species_id)
    for recipe in catalog.recipes:
        if _fusion_pair(*recipe.source_species_ids) == selected_pair:
            return recipe.target_species_id
    return None


def validate_fusion_catalog(
    catalog: FusionCatalog,
    species: dict[str, Species],
    *,
    naturally_obtainable_species_ids: set[str] | None = None,
) -> FusionValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    seen_pairs: dict[tuple[str, str], str] = {}
    naturally_obtainable = naturally_obtainable_species_ids or set()

    for recipe in catalog.recipes:
        sources = tuple(str(source).strip() for source in recipe.source_species_ids)
        label = _recipe_label(sources)
        if len(sources) != 2 or not all(sources):
            errors.append(f"Fusion {label} must have exactly two source species")
            continue

        pair = _fusion_pair(sources[0], sources[1])
        if pair in seen_pairs:
            errors.append(f"Duplicate fusion recipe for {seen_pairs[pair]}")
        else:
            seen_pairs[pair] = label

        for source_id in sources:
            source = species.get(source_id)
            if source is None:
                errors.append(f"Fusion {label} references unknown source species: {source_id}")
            elif source.stage != GrowthStage.ULTIMATE:
                warnings.append(f"Fusion {label} uses a non-ultimate source: {source_id}")
        if sources[0] == sources[1]:
            warnings.append(f"Fusion {label} uses the same source twice")

        target_id = str(recipe.target_species_id).strip()
        if not target_id:
            errors.append(f"Fusion {label} target species is required")
        elif target_id not in species:
            errors.append(f"Fusion {label} references unknown target species: {target_id}")
        elif target_id in naturally_obtainable:
            warnings.append(f"Fusion {label} target is already obtainable by evolution: {target_id}")

    return FusionValidationResult(errors=errors, warnings=warnings)


def _fusion_pair(first_species_id: str, second_species_id: str) -> tuple[str, str]:
    pair = sorted((str(first_species_id), str(second_species_id)))
    return pair[0], pair[1]


def _recipe_label(sources: tuple[str, ...]) -> str:
    if len(sources) >= 2:
        return f"{sources[0]} + {sources[1]}"
    if len(sources) == 1:
        return f"{sources[0]} + "
    return " + "
