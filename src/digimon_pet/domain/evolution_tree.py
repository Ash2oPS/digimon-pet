from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
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

BABY_TREE_SPECIAL_TARGETS = {"kunemon"}
BABY_TREE_STAGES = {GrowthStage.BABY, GrowthStage.BABY_2}


@dataclass(frozen=True)
class EvolutionLink:
    source_species_id: str | None
    target_species_id: str
    kind: str
    description: str
    order: int = 0
    source_stage: GrowthStage | None = None
    excluded_source_species_ids: frozenset[str] = field(default_factory=frozenset)


def build_evolution_links(species: dict[str, Species], digivolutions: dict[str, Any]) -> list[EvolutionLink]:
    links: list[EvolutionLink] = []
    links.extend(_baby_links(species))
    links.extend(_natural_links(species, digivolutions))
    links.extend(_special_links(species, digivolutions))
    return _dedupe_links(links)


def family_species_ids(selected_species_id: str, links: list[EvolutionLink]) -> set[str]:
    children_by_species: dict[str, set[str]] = defaultdict(set)
    parents_by_species: dict[str, set[str]] = defaultdict(set)
    for link in links:
        if link.source_species_id is None:
            continue
        children_by_species[link.source_species_id].add(link.target_species_id)
        parents_by_species[link.target_species_id].add(link.source_species_id)

    family = _connected_species(selected_species_id, parents_by_species)
    family.update(_connected_species(selected_species_id, children_by_species))
    return family


def _connected_species(selected_species_id: str, linked_species: dict[str, set[str]]) -> set[str]:
    connected = {selected_species_id}
    queue = deque([selected_species_id])
    while queue:
        species_id = queue.popleft()
        for related_id in linked_species.get(species_id, set()):
            if related_id not in connected:
                connected.add(related_id)
                queue.append(related_id)
    return connected


def graph_species_ids(selected_species_id: str, species: dict[str, Species], links: list[EvolutionLink]) -> set[str]:
    family_ids = family_species_ids(selected_species_id, links)
    graph_ids = set(family_ids)
    for link in links:
        if link.source_species_id is None and _global_link_applies_to_selected_tree(link, selected_species_id, species):
            graph_ids.add(link.target_species_id)
    return graph_ids


def graph_links(selected_species_id: str, species: dict[str, Species], links: list[EvolutionLink]) -> list[EvolutionLink]:
    family_ids = family_species_ids(selected_species_id, links)
    graph_ids = graph_species_ids(selected_species_id, species, links)
    visible_links: list[EvolutionLink] = []
    for link in links:
        if link.source_species_id is None:
            if link.target_species_id in graph_ids and _global_link_applies_to_selected_tree(link, selected_species_id, species):
                visible_links.append(link)
            continue
        if link.source_species_id in family_ids and link.target_species_id in family_ids:
            visible_links.append(link)
    return visible_links


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
        if target_id not in species:
            continue
        selector = raw_link.get("source_selector", {})
        direct_source_ids = _direct_special_source_ids(species, selector)
        if direct_source_ids:
            for source_id in direct_source_ids:
                if source_id != target_id:
                    links.append(EvolutionLink(source_id, target_id, "special", trigger, 100))
            continue

        source_stage, excluded_source_ids = _broad_special_source(selector)
        if selector.get("scope") == "any" or source_stage is not None:
            links.append(
                EvolutionLink(
                    None,
                    target_id,
                    "special",
                    trigger,
                    100,
                    source_stage=source_stage,
                    excluded_source_species_ids=frozenset(excluded_source_ids),
                )
            )
    return links


def _direct_special_source_ids(species: dict[str, Species], selector: dict[str, Any]) -> list[str]:
    if "species_ids" in selector:
        return [str(species_id) for species_id in selector["species_ids"] if str(species_id) in species]
    return []


def _broad_special_source(selector: dict[str, Any]) -> tuple[GrowthStage | None, set[str]]:
    stage = str(selector.get("stage", ""))
    if stage == "in_training":
        stage = GrowthStage.BABY_2.value
    source_stage = GrowthStage(stage) if stage else None
    excluded_ids = {str(species_id) for species_id in selector.get("exclude_species_ids", [])}
    return source_stage, excluded_ids


def _global_link_applies_to_selected_tree(
    link: EvolutionLink,
    selected_species_id: str,
    species: dict[str, Species],
) -> bool:
    selected = species.get(selected_species_id)
    if selected is None:
        return False
    return link.target_species_id in BABY_TREE_SPECIAL_TARGETS and selected.stage in BABY_TREE_STAGES


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
    deduped: dict[tuple[str | None, str, str], EvolutionLink] = {}
    for link in links:
        deduped.setdefault((link.source_species_id, link.target_species_id, link.kind), link)
    return list(deduped.values())
