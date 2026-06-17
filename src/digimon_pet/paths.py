from __future__ import annotations

from pathlib import Path
import sys

from digimon_pet import platform as desktop_platform


def project_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = project_root()
DATA_DIR = PROJECT_ROOT / "data"
ASSETS_DIR = PROJECT_ROOT / "assets"
LEGACY_SAVE_DIR = desktop_platform.legacy_project_save_dir(PROJECT_ROOT)
SAVE_DIR = desktop_platform.user_data_dir()
SAVE_PATH = SAVE_DIR / "pet_save.json"
DEBUG_SAVE_PATH = SAVE_DIR / "Debug" / "pet_save.json"
DEBUG_SETTINGS_PATH = SAVE_DIR / "debug_settings.json"
LEGACY_SAVE_PATH = LEGACY_SAVE_DIR / "pet_save.json"
LEGACY_DEBUG_SETTINGS_PATH = LEGACY_SAVE_DIR / "debug_settings.json"


def ensure_save_dir(path: Path | None = None) -> None:
    (path or SAVE_DIR).mkdir(parents=True, exist_ok=True)
