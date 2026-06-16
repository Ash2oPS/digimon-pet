from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
ASSETS_DIR = PROJECT_ROOT / "assets"
SAVE_DIR = PROJECT_ROOT / ".local"
SAVE_PATH = SAVE_DIR / "pet_save.json"


def ensure_save_dir() -> None:
    SAVE_DIR.mkdir(parents=True, exist_ok=True)

