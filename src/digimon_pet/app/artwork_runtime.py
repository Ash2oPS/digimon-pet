from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.request import urlretrieve

from PySide6.QtGui import QColor, QImage

from digimon_pet.paths import PROJECT_ROOT

DEFAULT_ARTWORK_DOWNLOAD_MANIFEST_PATH = PROJECT_ROOT / "data" / "artwork_downloads.json"
BACKGROUND_RGB_THRESHOLD = 245


def download_missing_artworks(
    project_root: Path = PROJECT_ROOT,
    manifest_path: Path = DEFAULT_ARTWORK_DOWNLOAD_MANIFEST_PATH,
) -> int:
    if not manifest_path.exists():
        return 0
    count = 0
    for entry in _load_artwork_entries(manifest_path):
        target_path = _project_relative_path(project_root, entry.get("path"))
        if target_path.exists():
            continue
        url = str(entry.get("url", "")).strip()
        if not url:
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        download_path = target_path.with_name(f"{target_path.name}.download")
        try:
            urlretrieve(url, download_path)
            if not _write_transparent_artwork(download_path, target_path):
                continue
        except OSError:
            continue
        finally:
            download_path.unlink(missing_ok=True)
        count += 1
    return count


def resolve_artwork_path(
    species_id: str,
    project_root: Path = PROJECT_ROOT,
    manifest_path: Path = DEFAULT_ARTWORK_DOWNLOAD_MANIFEST_PATH,
) -> Path | None:
    if not manifest_path.exists():
        return None
    for entry in _load_artwork_entries(manifest_path):
        if str(entry.get("species_id", "")) != species_id:
            continue
        target_path = _project_relative_path(project_root, entry.get("path"))
        return target_path if target_path.exists() else None
    return None


def _load_artwork_entries(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _project_relative_path(project_root: Path, raw_path: Any) -> Path:
    path = Path(str(raw_path))
    if path.is_absolute():
        raise ValueError(f"Expected a project-relative artwork path, got {path}")
    return project_root / path


def _write_transparent_artwork(source_path: Path, target_path: Path) -> bool:
    image = QImage(str(source_path))
    if image.isNull():
        return False
    image = image.convertToFormat(QImage.Format.Format_ARGB32)
    _remove_edge_background(image)
    return image.save(str(target_path), "PNG")


def _remove_edge_background(image: QImage) -> None:
    width = image.width()
    height = image.height()
    if width <= 0 or height <= 0:
        return

    stack: list[tuple[int, int]] = []
    for x in range(width):
        stack.append((x, 0))
        stack.append((x, height - 1))
    for y in range(1, height - 1):
        stack.append((0, y))
        stack.append((width - 1, y))

    while stack:
        x, y = stack.pop()
        color = image.pixelColor(x, y)
        if not _is_background_color(color):
            continue
        color.setAlpha(0)
        image.setPixelColor(x, y, color)
        if x > 0:
            stack.append((x - 1, y))
        if x < width - 1:
            stack.append((x + 1, y))
        if y > 0:
            stack.append((x, y - 1))
        if y < height - 1:
            stack.append((x, y + 1))


def _is_background_color(color: QColor) -> bool:
    return (
        color.alpha() > 0
        and color.red() >= BACKGROUND_RGB_THRESHOLD
        and color.green() >= BACKGROUND_RGB_THRESHOLD
        and color.blue() >= BACKGROUND_RGB_THRESHOLD
    )
