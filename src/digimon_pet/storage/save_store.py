from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any

from digimon_pet.domain.models import GrowthStage, PetState
from digimon_pet.paths import DATA_DIR, DEBUG_SAVE_PATH, LEGACY_SAVE_PATH, SAVE_PATH as NORMAL_SAVE_PATH, ensure_save_dir

SAVE_PATH = NORMAL_SAVE_PATH
LEGACY_ITEM_ID_ALIASES = {
    "gun": "digigun",
}


def configure_save_path(*, debug: bool) -> None:
    global SAVE_PATH
    SAVE_PATH = DEBUG_SAVE_PATH if debug else NORMAL_SAVE_PATH


def load_pet_state(path: Path | None = None) -> PetState:
    save_path = path or SAVE_PATH
    if path is None:
        _migrate_legacy_save(save_path)
    if not save_path.exists():
        _create_default_save(save_path)

    try:
        with save_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        return _state_from_dict(raw)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        _backup_corrupt_save(save_path)
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
    ensure_save_dir(path.parent)
    source = DATA_DIR / "default_save.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, path)


def _backup_corrupt_save(path: Path) -> None:
    backup_path = path.with_suffix(f"{path.suffix}.corrupt")
    if backup_path.exists():
        backup_path.unlink()
    shutil.move(str(path), str(backup_path))


def _migrate_legacy_save(target_path: Path) -> None:
    if target_path.exists() or not LEGACY_SAVE_PATH.exists():
        return
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(LEGACY_SAVE_PATH, target_path)


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
        generation_stat_bonuses=_stat_bonuses_from_raw(raw.get("generation_stat_bonuses")),
        pending_rebirth_stat_bonuses=_stat_bonuses_from_raw(raw.get("pending_rebirth_stat_bonuses")),
        inventory=_inventory_from_raw(raw.get("inventory")),
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


def _inventory_from_raw(raw: Any) -> dict[str, int]:
    if not isinstance(raw, dict):
        return {}
    inventory: dict[str, int] = {}
    for key, value in raw.items():
        item_id = LEGACY_ITEM_ID_ALIASES.get(str(key), str(key))
        quantity = int(value)
        if item_id.strip() and quantity > 0:
            inventory[item_id] = inventory.get(item_id, 0) + quantity
    return inventory
