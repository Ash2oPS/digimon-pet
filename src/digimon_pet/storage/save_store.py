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
        is_sleeping=bool(raw.get("is_sleeping", False)),
        current_action=str(raw.get("current_action", "idle")),
    )
    state.clamp()
    return state

