from __future__ import annotations

import os
from pathlib import Path
import sys


APP_NAME = "Digimon Pet"


def is_windows(platform_name: str | None = None) -> bool:
    return (platform_name or sys.platform) == "win32"


def is_macos(platform_name: str | None = None) -> bool:
    return (platform_name or sys.platform) == "darwin"


def user_data_dir(
    app_name: str = APP_NAME,
    *,
    platform_name: str | None = None,
    home: Path | None = None,
    environ: dict[str, str] | None = None,
) -> Path:
    platform = platform_name or sys.platform
    user_home = home or Path.home()
    env = os.environ if environ is None else environ

    if is_windows(platform):
        root = env.get("APPDATA") or env.get("LOCALAPPDATA")
        if root:
            return Path(root) / app_name
        return user_home / "AppData" / "Roaming" / app_name

    if is_macos(platform):
        return user_home / "Library" / "Application Support" / app_name

    root = env.get("XDG_DATA_HOME")
    if root:
        return Path(root) / app_name
    return user_home / ".local" / "share" / app_name


def legacy_project_save_dir(project_root: Path) -> Path:
    return project_root / ".local"


def configure_process_for_desktop_app() -> None:
    if is_macos():
        os.environ.setdefault("QT_MAC_WANTS_LAYER", "1")
