from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class GrowthStage(StrEnum):
    BABY = "baby"
    BABY_2 = "baby_2"
    ROOKIE = "rookie"
    CHAMPION = "champion"
    ULTIMATE = "ultimate"


@dataclass(frozen=True)
class Species:
    id: str
    name: str
    stage: GrowthStage
    sprite_slots: dict[str, str] = field(default_factory=dict)
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class FilledIncubatorState:
    id: str
    species_id: str
    stage: GrowthStage
    hp: int = 300
    mp: int = 300
    offense: int = 30
    defense: int = 30
    speed: int = 30
    brains: int = 30


@dataclass
class PetState:
    species_id: str
    stage: GrowthStage
    age_seconds: int = 0
    hunger: int = 30
    fatigue: int = 0
    discipline: int = 50
    care_mistakes: int = 0
    training_count: int = 0
    hp: int = 300
    mp: int = 300
    offense: int = 30
    defense: int = 30
    speed: int = 30
    brains: int = 30
    weight: int = 5
    happiness: int = 50
    won_battles: int = 0
    techniques_mastered: int = 0
    is_sleeping: bool = False
    current_action: str = "idle"
    needs_rebirth_choice: bool = False
    discovered_species_ids: list[str] = field(default_factory=list)
    generation_stat_bonuses: dict[str, int] = field(default_factory=dict)
    pending_rebirth_stat_bonuses: dict[str, int] = field(default_factory=dict)
    bakemon_lineage_used: bool = False
    bakemon_generation_cooldown: int = 0
    evolution_condition_discoveries: dict[str, list[str]] = field(default_factory=dict)
    inventory: dict[str, int] = field(default_factory=dict)
    filled_incubators: list[FilledIncubatorState] = field(default_factory=list)

    def clamp(self) -> None:
        self.hunger = _clamp(self.hunger)
        self.fatigue = _clamp(self.fatigue)
        self.discipline = _clamp(self.discipline)
        self.happiness = _clamp(self.happiness)
        self.care_mistakes = max(0, self.care_mistakes)
        self.training_count = max(0, self.training_count)
        self.age_seconds = max(0, self.age_seconds)
        self.hp = _clamp_stat(self.hp, "hp")
        self.mp = _clamp_stat(self.mp, "mp")
        self.offense = _clamp_stat(self.offense, "offense")
        self.defense = _clamp_stat(self.defense, "defense")
        self.speed = _clamp_stat(self.speed, "speed")
        self.brains = _clamp_stat(self.brains, "brains")
        self.weight = max(0, self.weight)
        self.won_battles = max(0, self.won_battles)
        self.techniques_mastered = max(0, self.techniques_mastered)
        self.discovered_species_ids = _dedupe_species_ids(self.discovered_species_ids)
        self.generation_stat_bonuses = _clean_stat_bonuses(self.generation_stat_bonuses)
        self.pending_rebirth_stat_bonuses = _clean_stat_bonuses(self.pending_rebirth_stat_bonuses)
        self.bakemon_lineage_used = bool(self.bakemon_lineage_used)
        self.bakemon_generation_cooldown = max(0, int(self.bakemon_generation_cooldown))
        self.evolution_condition_discoveries = _clean_evolution_condition_discoveries(
            self.evolution_condition_discoveries
        )
        self.inventory = _clean_inventory(self.inventory)
        self.filled_incubators = _clean_filled_incubators(self.filled_incubators)

    def mark_discovered(self, species_id: str | None = None) -> None:
        target_id = species_id or self.species_id
        if target_id not in self.discovered_species_ids:
            self.discovered_species_ids.append(target_id)
        self.discovered_species_ids = _dedupe_species_ids(self.discovered_species_ids)


@dataclass(frozen=True)
class EvolutionRule:
    source_species_id: str
    target_species_id: str
    min_age_seconds: int
    min_training_count: int | None = None
    priority: int = 0


def _clamp(value: int, minimum: int = 0, maximum: int = 100) -> int:
    return max(minimum, min(maximum, value))


def _clamp_stat(value: int, stat_name: str = "") -> int:
    maximum = 99999 if stat_name in {"hp", "mp"} else 9999
    return max(0, min(maximum, value))


def _dedupe_species_ids(species_ids: list[str]) -> list[str]:
    return list(dict.fromkeys(str(species_id) for species_id in species_ids if str(species_id).strip()))


def _clean_stat_bonuses(bonuses: dict[str, int]) -> dict[str, int]:
    valid_stats = {"hp", "mp", "offense", "defense", "speed", "brains"}
    return {
        str(stat_name): max(0, int(value))
        for stat_name, value in bonuses.items()
        if str(stat_name) in valid_stats
    }


def _clean_evolution_condition_discoveries(discoveries: dict[str, list[str]]) -> dict[str, list[str]]:
    valid_stats = {"hp", "mp", "offense", "defense", "speed", "brains"}
    cleaned: dict[str, list[str]] = {}
    for transition_id, stats in discoveries.items():
        clean_transition_id = str(transition_id).strip()
        if not clean_transition_id:
            continue
        clean_stats = list(dict.fromkeys(str(stat) for stat in stats if str(stat) in valid_stats))
        if clean_stats:
            cleaned[clean_transition_id] = clean_stats
    return cleaned


def _clean_inventory(inventory: dict[str, int]) -> dict[str, int]:
    return {
        str(item_id): int(quantity)
        for item_id, quantity in inventory.items()
        if str(item_id).strip() and int(quantity) > 0
    }


def _clean_filled_incubators(incubators: list[FilledIncubatorState]) -> list[FilledIncubatorState]:
    cleaned: list[FilledIncubatorState] = []
    seen_ids: set[str] = set()
    for incubator in incubators:
        incubator_id = str(incubator.id).strip()
        species_id = str(incubator.species_id).strip()
        if not incubator_id or not species_id or incubator_id in seen_ids:
            continue
        cleaned.append(
            FilledIncubatorState(
                id=incubator_id,
                species_id=species_id,
                stage=GrowthStage(str(incubator.stage)),
                hp=_clamp_stat(int(incubator.hp), "hp"),
                mp=_clamp_stat(int(incubator.mp), "mp"),
                offense=_clamp_stat(int(incubator.offense), "offense"),
                defense=_clamp_stat(int(incubator.defense), "defense"),
                speed=_clamp_stat(int(incubator.speed), "speed"),
                brains=_clamp_stat(int(incubator.brains), "brains"),
            )
        )
        seen_ids.add(incubator_id)
    return cleaned
