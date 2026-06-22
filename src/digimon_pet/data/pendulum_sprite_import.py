from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter

from digimon_pet.data.sprite_pipeline import (
    DEFAULT_MANIFEST_PATH,
    DEFAULT_REPORT_PATH,
    DEFAULT_ROSTER_PATH,
    DEFAULT_SOURCE_CONFIG_PATH,
    build_sprite_manifest,
    normalize_name,
)
from digimon_pet.paths import PROJECT_ROOT


PENDULUM_COLOR_SOURCE_ID = "digimon_pendulum_color"
PENDULUM_COLOR_MANIFEST_PATH = Path("assets/sprite_sources/digimon_pendulum_color/manifest.json")
DEFAULT_PENDULUM_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class PendulumSheetSource:
    name: str
    url: str
    row_names: tuple[str, ...]
    grid_x: int = 96
    grid_y: int = 44
    cell_size: int = 16
    cell_step: int = 17
    frame_count: int = 12
    fps: int = 6


@dataclass(frozen=True)
class ImportedPendulumSprite:
    species_id: str
    name: str
    source_name: str
    path: Path
    relative_path: str
    frame_count: int
    fps: int


VIRUS_BUSTERS = PendulumSheetSource(
    name="Version Zero Virus Busters",
    url="https://www.spriters-resource.com/media/assets/505/523631.png?updated=1771776625",
    row_names=(
        "YukimiBotamon",
        "Nyaromon",
        "Agumon",
        "Gabumon",
        "Plotmon",
        "Gammamon",
        "Greymon",
        "Leomon",
        "Garurumon",
        "Igamon",
        "Angemon",
        "Tailmon",
        "BetelGammamon",
        "KausGammamon",
        "WezenGammamon",
        "GulusGammamon",
        "MetalGreymon",
        "Asuramon",
        "WereGarurumon",
        "MetalMamemon",
        "HolyAngemon",
        "Angewomon",
        "Canoweissmon",
        "Regulusmon",
        "WarGreymon",
        "MetalGarurumon",
        "Dominimon",
        "Quantumon",
        "Siriusmon",
        "Arcturusmon",
        "Omegamon",
        "Mastemon",
        "Proximamon",
    ),
)

PENDULUM_SHEET_SOURCES = (VIRUS_BUSTERS,)


def import_pendulum_color_sprite(
    species_id: str,
    name: str,
    project_root: Path = PROJECT_ROOT,
    *,
    source_manifest_path: Path | None = None,
    roster_path: Path | None = None,
    source_config_path: Path | None = None,
    runtime_manifest_path: Path | None = None,
    report_path: Path | None = None,
    timeout_seconds: float = DEFAULT_PENDULUM_TIMEOUT_SECONDS,
) -> ImportedPendulumSprite | None:
    clean_species_id = species_id.strip()
    clean_name = name.strip()
    if not clean_species_id or not clean_name:
        return None

    source, row_index, matched_name = _find_sheet_row(clean_name)
    if source is None or row_index is None or matched_name is None:
        return None

    sheet = _load_remote_image(source.url, timeout_seconds=timeout_seconds)
    if sheet.isNull():
        return None

    sprite = _extract_sprite_row(sheet, source, row_index)
    if sprite.isNull():
        return None

    target_relative = Path("assets") / "sprite_sources" / PENDULUM_COLOR_SOURCE_ID / f"{matched_name}.png"
    target_path = project_root / target_relative
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if not sprite.save(str(target_path), "PNG"):
        return None

    manifest_path = project_root / (source_manifest_path or PENDULUM_COLOR_MANIFEST_PATH)
    _upsert_source_manifest_entry(
        manifest_path,
        {
            "fps": source.fps,
            "frame_count": source.frame_count,
            "name": matched_name,
            "path": target_relative.as_posix(),
        },
    )
    effective_roster_path = project_root / (roster_path or _project_default(DEFAULT_ROSTER_PATH))
    effective_source_config_path = project_root / (source_config_path or _project_default(DEFAULT_SOURCE_CONFIG_PATH))
    effective_runtime_manifest_path = project_root / (runtime_manifest_path or _project_default(DEFAULT_MANIFEST_PATH))
    effective_report_path = project_root / (report_path or _project_default(DEFAULT_REPORT_PATH))

    _upsert_roster_entry(
        effective_roster_path,
        clean_species_id,
        clean_name,
        matched_name,
    )
    build_sprite_manifest(
        project_root,
        roster_path=effective_roster_path,
        source_config_path=effective_source_config_path,
        output_path=effective_runtime_manifest_path,
        report_path=effective_report_path,
    )
    return ImportedPendulumSprite(
        species_id=clean_species_id,
        name=matched_name,
        source_name=source.name,
        path=target_path,
        relative_path=target_relative.as_posix(),
        frame_count=source.frame_count,
        fps=source.fps,
    )


def _find_sheet_row(name: str) -> tuple[PendulumSheetSource | None, int | None, str | None]:
    target = normalize_name(name)
    for source in PENDULUM_SHEET_SOURCES:
        for index, row_name in enumerate(source.row_names):
            if normalize_name(row_name) == target:
                return source, index, row_name
    return None, None, None


def _project_default(path: Path) -> Path:
    return path.relative_to(PROJECT_ROOT)


def _load_remote_image(url: str, *, timeout_seconds: float) -> QImage:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=timeout_seconds) as response:
        payload = response.read()
    image = QImage()
    image.loadFromData(payload)
    return image.convertToFormat(QImage.Format.Format_ARGB32) if not image.isNull() else image


def _extract_sprite_row(sheet: QImage, source: PendulumSheetSource, row_index: int) -> QImage:
    output = QImage(source.frame_count * 64, 64, QImage.Format.Format_ARGB32)
    output.fill(QColor(0, 0, 0, 0))
    painter = QPainter(output)
    try:
        y = source.grid_y + row_index * source.cell_step
        for frame_index in range(source.frame_count):
            x = source.grid_x + frame_index * source.cell_step
            frame = sheet.copy(QRect(x, y, source.cell_size, source.cell_size))
            _remove_connected_cell_background(frame)
            scaled = frame.scaled(64, 64, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
            painter.drawImage(frame_index * 64, 0, scaled)
    finally:
        painter.end()
    return output


def _remove_connected_cell_background(image: QImage) -> None:
    background_colors = {(255, 0, 255), (8, 4, 33)}
    width = image.width()
    height = image.height()
    queue: deque[tuple[int, int]] = deque()
    for x in range(width):
        queue.append((x, 0))
        queue.append((x, height - 1))
    for y in range(1, height - 1):
        queue.append((0, y))
        queue.append((width - 1, y))

    visited: set[tuple[int, int]] = set()
    while queue:
        x, y = queue.popleft()
        if (x, y) in visited or not (0 <= x < width and 0 <= y < height):
            continue
        color = image.pixelColor(x, y)
        if (color.red(), color.green(), color.blue()) not in background_colors:
            continue
        visited.add((x, y))
        color.setAlpha(0)
        image.setPixelColor(x, y, color)
        queue.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))


def _upsert_source_manifest_entry(manifest_path: Path, item: dict[str, Any]) -> None:
    existing = _load_source_manifest(manifest_path)
    by_name = {normalize_name(str(entry.get("name", ""))): entry for entry in existing}
    by_name[normalize_name(str(item["name"]))] = item
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps({"sprites": list(by_name.values())}, indent=2) + "\n",
        encoding="utf-8",
    )


def _load_source_manifest(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(raw, dict) and isinstance(raw.get("sprites"), list):
        return [item for item in raw["sprites"] if isinstance(item, dict)]
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []


def _upsert_roster_entry(roster_path: Path, species_id: str, name: str, matched_name: str) -> None:
    roster = _load_roster_json(roster_path)
    aliases = []
    if normalize_name(matched_name) != normalize_name(name):
        aliases.append(matched_name)
    for entry in roster:
        if str(entry.get("id", "")) != species_id:
            continue
        existing_aliases = [str(alias) for alias in entry.get("aliases", []) if str(alias).strip()]
        for alias in aliases:
            if alias not in existing_aliases:
                existing_aliases.append(alias)
        if existing_aliases:
            entry["aliases"] = existing_aliases
        return _write_roster_json(roster_path, roster)
    entry = {"id": species_id, "name": name}
    if aliases:
        entry["aliases"] = aliases
    roster.append(entry)
    _write_roster_json(roster_path, roster)


def _load_roster_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def _write_roster_json(path: Path, payload: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["["]
    for index, item in enumerate(payload):
        suffix = "," if index < len(payload) - 1 else ""
        lines.append(f"  {json.dumps(item, ensure_ascii=False)}{suffix}")
    lines.append("]")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
