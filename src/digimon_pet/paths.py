from __future__ import annotations

from pathlib import Path
import sys

from digimon_pet import platform as desktop_platform


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        for root in _frozen_resource_roots():
            if (root / "data" / "default_save.json").exists() and (root / "assets").exists():
                return root
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


def _frozen_resource_roots() -> list[Path]:
    roots: list[Path] = []
    if hasattr(sys, "_MEIPASS"):
        roots.append(Path(sys._MEIPASS))

    executable = Path(sys.executable).resolve()
    if _is_macos_app_executable(executable):
        roots.append(executable.parent)
        for parent in executable.parents:
            roots.append(parent)
            if parent.name == "Contents":
                roots.append(parent / "Resources")

    unique_roots: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        if root not in seen:
            seen.add(root)
            unique_roots.append(root)
    return unique_roots


def _is_macos_app_executable(executable: Path) -> bool:
    return (
        executable.parent.name == "MacOS"
        and executable.parent.parent.name == "Contents"
        and executable.parent.parent.parent.suffix == ".app"
    )


PROJECT_ROOT = project_root()
DATA_DIR = PROJECT_ROOT / "data"
ASSETS_DIR = PROJECT_ROOT / "assets"
LEGACY_SAVE_DIR = desktop_platform.legacy_project_save_dir(PROJECT_ROOT)
SAVE_DIR = desktop_platform.user_data_dir()
SAVE_PATH = SAVE_DIR / "pet_save.json"
DEBUG_SAVE_PATH = SAVE_DIR / "Debug" / "pet_save.json"
DEBUG_SETTINGS_PATH = SAVE_DIR / "debug_settings.json"
NETWORK_SETTINGS_PATH = SAVE_DIR / "network_settings.json"
LEGACY_SAVE_PATH = LEGACY_SAVE_DIR / "pet_save.json"
LEGACY_DEBUG_SETTINGS_PATH = LEGACY_SAVE_DIR / "debug_settings.json"


def ensure_save_dir(path: Path | None = None) -> None:
    (path or SAVE_DIR).mkdir(parents=True, exist_ok=True)
