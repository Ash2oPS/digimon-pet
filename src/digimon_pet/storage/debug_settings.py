from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from digimon_pet.paths import DEBUG_SETTINGS_PATH


@dataclass
class DebugSettings:
    time_scale: int = 1
    auto_rebirth_random: bool = False
    auto_lifecycle_events: bool = False

    def clamp(self) -> None:
        self.time_scale = max(1, min(3600, int(self.time_scale)))
        self.auto_rebirth_random = bool(self.auto_rebirth_random)
        self.auto_lifecycle_events = bool(self.auto_lifecycle_events)


def load_debug_settings(path: Path | None = None) -> DebugSettings:
    settings_path = path or DEBUG_SETTINGS_PATH
    if not settings_path.exists():
        return DebugSettings()
    try:
        with settings_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return DebugSettings()
    if not isinstance(raw, dict):
        return DebugSettings()
    return _settings_from_dict(raw)


def save_debug_settings(settings: DebugSettings, path: Path | None = None) -> None:
    settings_path = path or DEBUG_SETTINGS_PATH
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings.clamp()
    with settings_path.open("w", encoding="utf-8") as handle:
        json.dump(asdict(settings), handle, indent=2)
        handle.write("\n")


def _settings_from_dict(raw: dict[str, Any]) -> DebugSettings:
    settings = DebugSettings(
        time_scale=int(raw.get("time_scale", 1)),
        auto_rebirth_random=bool(raw.get("auto_rebirth_random", False)),
        auto_lifecycle_events=bool(raw.get("auto_lifecycle_events", False)),
    )
    settings.clamp()
    return settings
