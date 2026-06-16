from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any

from digimon_pet.domain.models import GrowthStage, PetState
from digimon_pet.paths import DATA_DIR, SAVE_PATH, ensure_save_dir


def load_pet_state(path: Path | None = None) -> PetState:
    save_path = path or SAVE_PATH
    if not save_path.exists():
        _create_default_save(save_path)

    with save_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return _state_from_dict(raw)


def save_pet_state(state: PetState, path: Path | None = None) -> None:
    save_path = path or SAVE_PATH
    save_path.parent.mkdir(parents=True, exist_ok=True)
    state.mark_discovered()
    state.clamp()
    payload = asdict(state)
    payload["stage"] = state.stage.value
    with save_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def _create_default_save(path: Path) -> None:
    ensure_save_dir()
    source = DATA_DIR / "default_save.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, path)


def _state_from_dict(raw: dict[str, Any]) -> PetState:
    state = PetState(
        species_id=str(raw["species_id"]),
        stage=GrowthStage(str(raw["stage"])),
        age_seconds=int(raw.get("age_seconds", 0)),
        hunger=int(raw.get("hunger", 30)),
        fatigue=int(raw.get("fatigue", 0)),
        discipline=int(raw.get("discipline", 50)),
        care_mistakes=int(raw.get("care_mistakes", 0)),
        training_count=int(raw.get("training_count", 0)),
        hp=int(raw.get("hp", 300)),
        mp=int(raw.get("mp", 300)),
        offense=int(raw.get("offense", 30)),
        defense=int(raw.get("defense", 30)),
        speed=int(raw.get("speed", 30)),
        brains=int(raw.get("brains", 30)),
        weight=int(raw.get("weight", 5)),
        happiness=int(raw.get("happiness", 50)),
        won_battles=int(raw.get("won_battles", 0)),
        techniques_mastered=int(raw.get("techniques_mastered", 0)),
        is_sleeping=bool(raw.get("is_sleeping", False)),
        current_action=str(raw.get("current_action", "idle")),
        needs_rebirth_choice=bool(raw.get("needs_rebirth_choice", False)),
        discovered_species_ids=_species_ids_from_raw(raw.get("discovered_species_ids"), str(raw["species_id"])),
        pending_rebirth_stat_bonuses=_stat_bonuses_from_raw(raw.get("pending_rebirth_stat_bonuses")),
    )
    state.mark_discovered()
    state.clamp()
    return state


def _species_ids_from_raw(raw: Any, current_species_id: str) -> list[str]:
    if not isinstance(raw, list):
        return [current_species_id]
    return [str(item) for item in raw]


def _stat_bonuses_from_raw(raw: Any) -> dict[str, int]:
    if not isinstance(raw, dict):
        return {}
    return {str(key): int(value) for key, value in raw.items()}
