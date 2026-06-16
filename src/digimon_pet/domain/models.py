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
    is_sleeping: bool = False
    current_action: str = "idle"

    def clamp(self) -> None:
        self.hunger = _clamp(self.hunger)
        self.fatigue = _clamp(self.fatigue)
        self.discipline = _clamp(self.discipline)
        self.care_mistakes = max(0, self.care_mistakes)
        self.training_count = max(0, self.training_count)
        self.age_seconds = max(0, self.age_seconds)


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

