from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from digimon_pet.domain.models import FilledIncubatorState, GrowthStage, PetState
from digimon_pet.paths import DATA_DIR, DEBUG_SAVE_PATH, LEGACY_SAVE_PATH, SAVE_PATH as NORMAL_SAVE_PATH, ensure_save_dir

SAVE_PATH = NORMAL_SAVE_PATH
SAVE_FORMAT = "digimon_pet_save"
SAVE_VERSION = 2
SAVE_ENCRYPTION_KEY = b"eximblQjtHVliMbw7pDdX4ijX4iIn5YoFcri3OikiEA="
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
        raw, was_legacy_plain_json = _read_save_payload(save_path)
        state = _state_from_dict(raw)
        if was_legacy_plain_json:
            save_pet_state(state, save_path)
        return state
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        _backup_corrupt_save(save_path)
        _create_default_save(save_path)
        raw, was_legacy_plain_json = _read_save_payload(save_path)
        state = _state_from_dict(raw)
        if was_legacy_plain_json:
            save_pet_state(state, save_path)
        return state


def save_pet_state(state: PetState, path: Path | None = None) -> None:
    save_path = path or SAVE_PATH
    save_path.parent.mkdir(parents=True, exist_ok=True)
    state.mark_discovered()
    state.clamp()
    envelope = _encrypt_save_payload(_state_to_payload(state))
    temp_path = save_path.with_name(f"{save_path.name}.tmp")
    try:
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(envelope, handle, indent=2)
            handle.write("\n")
        os.replace(temp_path, save_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def _state_to_payload(state: PetState) -> dict[str, Any]:
    return {
        "species_id": state.species_id,
        "stage": state.stage.value,
        "age_seconds": state.age_seconds,
        "hunger": state.hunger,
        "fatigue": state.fatigue,
        "discipline": state.discipline,
        "care_mistakes": state.care_mistakes,
        "training_count": state.training_count,
        "hp": state.hp,
        "mp": state.mp,
        "offense": state.offense,
        "defense": state.defense,
        "speed": state.speed,
        "brains": state.brains,
        "weight": state.weight,
        "happiness": state.happiness,
        "won_battles": state.won_battles,
        "techniques_mastered": state.techniques_mastered,
        "is_sleeping": state.is_sleeping,
        "current_action": state.current_action,
        "needs_rebirth_choice": state.needs_rebirth_choice,
        "discovered_species_ids": list(state.discovered_species_ids),
        "generation_stat_bonuses": dict(state.generation_stat_bonuses),
        "pending_rebirth_stat_bonuses": dict(state.pending_rebirth_stat_bonuses),
        "pending_rebirth_stat_source_stats": dict(state.pending_rebirth_stat_source_stats),
        "bakemon_lineage_used": state.bakemon_lineage_used,
        "bakemon_generation_cooldown": state.bakemon_generation_cooldown,
        "evolution_condition_discoveries": dict(state.evolution_condition_discoveries),
        "inventory": dict(state.inventory),
        "filled_incubators": [_filled_incubator_to_dict(item) for item in state.filled_incubators],
        "secondary_event_kind": state.secondary_event_kind,
        "secondary_event_ttl_seconds": state.secondary_event_ttl_seconds,
        "secondary_event_seconds_remaining": state.secondary_event_seconds_remaining,
        "window_x": state.window_x,
        "window_y": state.window_y,
        "window_screen_name": state.window_screen_name,
        "window_screen_offset_x": state.window_screen_offset_x,
        "window_screen_offset_y": state.window_screen_offset_y,
        "pet_scale_percent": state.pet_scale_percent,
    }


def _read_save_payload(path: Path) -> tuple[dict[str, Any], bool]:
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        raise ValueError("Save file must contain a JSON object.")
    if _is_encrypted_save(raw):
        return _decrypt_save_payload(raw), False
    return raw, True


def _is_encrypted_save(raw: dict[str, Any]) -> bool:
    return raw.get("format") == SAVE_FORMAT and raw.get("version") == SAVE_VERSION and "payload" in raw


def _encrypt_save_payload(payload: dict[str, Any]) -> dict[str, Any]:
    plaintext = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    encrypted_payload = Fernet(SAVE_ENCRYPTION_KEY).encrypt(plaintext).decode("ascii")
    return {
        "format": SAVE_FORMAT,
        "version": SAVE_VERSION,
        "payload": encrypted_payload,
    }


def _decrypt_save_payload(envelope: dict[str, Any]) -> dict[str, Any]:
    try:
        encrypted_payload = str(envelope["payload"]).encode("ascii")
        plaintext = Fernet(SAVE_ENCRYPTION_KEY).decrypt(encrypted_payload)
        payload = json.loads(plaintext.decode("utf-8"))
    except (InvalidToken, UnicodeDecodeError) as exc:
        raise ValueError("Save payload could not be decrypted.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Decrypted save payload must contain a JSON object.")
    return payload


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
        pending_rebirth_stat_source_stats=_stat_bonuses_from_raw(raw.get("pending_rebirth_stat_source_stats")),
        bakemon_lineage_used=bool(raw.get("bakemon_lineage_used", False)),
        bakemon_generation_cooldown=int(raw.get("bakemon_generation_cooldown", 0)),
        evolution_condition_discoveries=_evolution_condition_discoveries_from_raw(
            raw.get("evolution_condition_discoveries")
        ),
        inventory=_inventory_from_raw(raw.get("inventory")),
        filled_incubators=_filled_incubators_from_raw(raw.get("filled_incubators")),
        secondary_event_kind=_secondary_event_kind_from_raw(raw.get("secondary_event_kind")),
        secondary_event_ttl_seconds=int(raw.get("secondary_event_ttl_seconds", 0)),
        secondary_event_seconds_remaining=_optional_int_from_raw(raw.get("secondary_event_seconds_remaining")),
        window_x=_optional_int_from_raw(raw.get("window_x")),
        window_y=_optional_int_from_raw(raw.get("window_y")),
        window_screen_name=_optional_str_from_raw(raw.get("window_screen_name")),
        window_screen_offset_x=_optional_int_from_raw(raw.get("window_screen_offset_x")),
        window_screen_offset_y=_optional_int_from_raw(raw.get("window_screen_offset_y")),
        pet_scale_percent=int(raw.get("pet_scale_percent", 100)),
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


def _evolution_condition_discoveries_from_raw(raw: Any) -> dict[str, list[str]]:
    if not isinstance(raw, dict):
        return {}
    valid_stats = {"hp", "mp", "offense", "defense", "speed", "brains"}
    cleaned: dict[str, list[str]] = {}
    for transition_id, stats in raw.items():
        clean_transition_id = str(transition_id).strip()
        if not clean_transition_id or not isinstance(stats, list):
            continue
        clean_stats = list(dict.fromkeys(str(stat) for stat in stats if str(stat) in valid_stats))
        if clean_stats:
            cleaned[clean_transition_id] = clean_stats
    return cleaned


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


def _filled_incubators_from_raw(raw: Any) -> list[FilledIncubatorState]:
    if not isinstance(raw, list):
        return []
    incubators: list[FilledIncubatorState] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            incubators.append(
                FilledIncubatorState(
                    id=str(item["id"]),
                    species_id=str(item["species_id"]),
                    stage=GrowthStage(str(item["stage"])),
                    hp=int(item.get("hp", 300)),
                    mp=int(item.get("mp", 300)),
                    offense=int(item.get("offense", 30)),
                    defense=int(item.get("defense", 30)),
                    speed=int(item.get("speed", 30)),
                    brains=int(item.get("brains", 30)),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return incubators


def _filled_incubator_to_dict(item: FilledIncubatorState) -> dict[str, Any]:
    return {
        "id": item.id,
        "species_id": item.species_id,
        "stage": item.stage.value,
        "hp": item.hp,
        "mp": item.mp,
        "offense": item.offense,
        "defense": item.defense,
        "speed": item.speed,
        "brains": item.brains,
    }


def _secondary_event_kind_from_raw(raw: Any) -> str | None:
    if raw is None:
        return None
    clean_kind = str(raw).strip()
    return clean_kind if clean_kind in {"meat", "dumbbell", "item"} else None


def _optional_int_from_raw(raw: Any) -> int | None:
    if raw is None:
        return None
    return int(raw)


def _optional_str_from_raw(raw: Any) -> str | None:
    if raw is None:
        return None
    clean_value = str(raw).strip()
    return clean_value or None
