from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

from digimon_pet.domain.lifecycle import BABY_1_TO_BABY_2, BABY_2_TO_ROOKIE
from digimon_pet.domain.models import GrowthStage, Species


STAT_LABELS = {
    "hp": "HP",
    "mp": "MP",
    "offense": "OFF",
    "defense": "DEF",
    "speed": "SPD",
    "brains": "INT",
}

UNSUPPORTED_SPECIAL_TRIGGER_MARKERS = (
    "full virus bar",
    "after 96h",
    "sleep in kunemon",
    "monzaemon suit",
)


@dataclass(frozen=True)
class EvolutionLink:
    source_species_id: str
    target_species_id: str
    kind: str
    description: str
    order: int = 0


def build_evolution_links(species: dict[str, Species], digivolutions: dict[str, Any]) -> list[EvolutionLink]:
    links: list[EvolutionLink] = []
    links.extend(_baby_links(species))
    links.extend(_natural_links(species, digivolutions))
    links.extend(_special_links(species, digivolutions))
    return _dedupe_links(links)


def family_species_ids(selected_species_id: str, links: list[EvolutionLink]) -> set[str]:
    linked_species: dict[str, set[str]] = defaultdict(set)
    for link in links:
        linked_species[link.source_species_id].add(link.target_species_id)
        linked_species[link.target_species_id].add(link.source_species_id)

    family = {selected_species_id}
    queue = deque([selected_species_id])
    while queue:
        species_id = queue.popleft()
        for related_id in linked_species.get(species_id, set()):
            if related_id not in family:
                family.add(related_id)
                queue.append(related_id)
    return family


def _baby_links(species: dict[str, Species]) -> list[EvolutionLink]:
    links: list[EvolutionLink] = []
    for source_id, target_id in {**BABY_1_TO_BABY_2, **BABY_2_TO_ROOKIE}.items():
        if source_id in species and target_id in species:
            links.append(EvolutionLink(source_id, target_id, "baby", "Age evolution"))
    return links


def _natural_links(species: dict[str, Species], digivolutions: dict[str, Any]) -> list[EvolutionLink]:
    links: list[EvolutionLink] = []
    for raw_link in digivolutions.get("natural_evolutions", []):
        source_id = str(raw_link.get("source_species_id", ""))
        target_id = str(raw_link.get("target_species_id", ""))
        if source_id not in species or target_id not in species:
            continue
        links.append(
            EvolutionLink(
                source_id,
                target_id,
                "natural",
                _describe_natural_requirements(raw_link.get("requirements", {})),
                int(raw_link.get("chart_order", 0)),
            )
        )
    return links


def _special_links(species: dict[str, Species], digivolutions: dict[str, Any]) -> list[EvolutionLink]:
    links: list[EvolutionLink] = []
    for raw_link in digivolutions.get("special_evolutions", []):
        target_id = str(raw_link.get("target_species_id", ""))
        trigger = str(raw_link.get("trigger", ""))
        if target_id not in species or not _is_supported_special_trigger(trigger):
            continue
        for source_id in _special_source_ids(species, raw_link.get("source_selector", {})):
            if source_id != target_id:
                links.append(EvolutionLink(source_id, target_id, "special", trigger, 100))
    return links


def _special_source_ids(species: dict[str, Species], selector: dict[str, Any]) -> list[str]:
    if "species_ids" in selector:
        return [str(species_id) for species_id in selector["species_ids"] if str(species_id) in species]

    stage = str(selector.get("stage", ""))
    if stage == "in_training":
        stage = GrowthStage.BABY_2.value
    if stage:
        excluded_ids = {str(species_id) for species_id in selector.get("exclude_species_ids", [])}
        return [
            species_id
            for species_id, item in species.items()
            if item.stage.value == stage and species_id not in excluded_ids
        ]

    return []


def _is_supported_special_trigger(trigger: str) -> bool:
    lowered = trigger.lower()
    return not any(marker in lowered for marker in UNSUPPORTED_SPECIAL_TRIGGER_MARKERS)


def _describe_natural_requirements(requirements: dict[str, Any]) -> str:
    groups = requirements.get("groups", {})
    parts: list[str] = []

    stats = groups.get("stats")
    if isinstance(stats, dict):
        for stat_name, value in stats.items():
            parts.append(f"{STAT_LABELS.get(str(stat_name), str(stat_name).upper())} >= {int(value)}")

    weight = groups.get("weight")
    if isinstance(weight, dict):
        if "min" in weight and "max" in weight:
            parts.append(f"Weight {int(weight['min'])}-{int(weight['max'])}")
        elif "target" in weight:
            parts.append(f"Weight ~{int(weight['target'])}")

    care_mistakes = groups.get("care_mistakes")
    if isinstance(care_mistakes, dict):
        if "max" in care_mistakes:
            parts.append(f"Mistakes <= {int(care_mistakes['max'])}")
        if "min" in care_mistakes:
            parts.append(f"Mistakes >= {int(care_mistakes['min'])}")

    if groups.get("bonus"):
        parts.append("Bonus condition")

    return ", ".join(parts) if parts else "Natural requirements"


def _dedupe_links(links: list[EvolutionLink]) -> list[EvolutionLink]:
    deduped: dict[tuple[str, str, str], EvolutionLink] = {}
    for link in links:
        deduped.setdefault((link.source_species_id, link.target_species_id, link.kind), link)
    return list(deduped.values())
