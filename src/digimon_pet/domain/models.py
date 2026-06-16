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
    hp: int = 100
    mp: int = 100
    offense: int = 10
    defense: int = 10
    speed: int = 10
    brains: int = 10
    weight: int = 5
    happiness: int = 50
    won_battles: int = 0
    techniques_mastered: int = 0
    is_sleeping: bool = False
    current_action: str = "idle"
    needs_rebirth_choice: bool = False

    def clamp(self) -> None:
        self.hunger = _clamp(self.hunger)
        self.fatigue = _clamp(self.fatigue)
        self.discipline = _clamp(self.discipline)
        self.happiness = _clamp(self.happiness)
        self.care_mistakes = max(0, self.care_mistakes)
        self.training_count = max(0, self.training_count)
        self.age_seconds = max(0, self.age_seconds)
        self.hp = _clamp_stat(self.hp)
        self.mp = _clamp_stat(self.mp)
        self.offense = _clamp_stat(self.offense)
        self.defense = _clamp_stat(self.defense)
        self.speed = _clamp_stat(self.speed)
        self.brains = _clamp_stat(self.brains)
        self.weight = max(0, self.weight)
        self.won_battles = max(0, self.won_battles)
        self.techniques_mastered = max(0, self.techniques_mastered)


@dataclass(frozen=True)
class EvolutionRule:
    source_species_id: str
    target_species_id: str
    min_age_seconds: int
    max_care_mistakes: int | None = None
    min_discipline: int | None = None
    min_training_count: int | None = None
    priority: int = 0


def _clamp(value: int, minimum: int = 0, maximum: int = 100) -> int:
    return max(minimum, min(maximum, value))


def _clamp_stat(value: int) -> int:
    return max(0, min(9999, value))
