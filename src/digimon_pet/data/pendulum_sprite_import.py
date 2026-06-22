from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote
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
WIKIMON_VIRTUAL_PETS_SOURCE_ID = "wikimon_virtual_pets"
WIKIMON_VIRTUAL_PETS_MANIFEST_PATH = Path("assets/sprite_sources/wikimon_virtual_pets/manifest.json")
WIKIMON_BASE_URL = "https://wikimon.net"
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


@dataclass(frozen=True)
class SpriteImportOption:
    provider_id: str
    label: str
    detail: str
    species_id: str
    name: str
    source_url: str
    image_url: str = ""
    frame_count: int = 1
    fps: int = 6
    row_index: int | None = None
    matched_name: str = ""
    source_name: str = ""


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


def discover_sprite_import_options(
    species_id: str,
    name: str,
    project_root: Path = PROJECT_ROOT,
    *,
    timeout_seconds: float = DEFAULT_PENDULUM_TIMEOUT_SECONDS,
) -> list[SpriteImportOption]:
    clean_species_id = species_id.strip()
    clean_name = name.strip()
    if not clean_species_id or not clean_name:
        return []
    options: list[SpriteImportOption] = []
    pendulum_source, row_index, matched_name = _find_sheet_row(clean_name)
    if pendulum_source is not None and row_index is not None and matched_name is not None:
        options.append(
            SpriteImportOption(
                provider_id=PENDULUM_COLOR_SOURCE_ID,
                label=f"{pendulum_source.name} ({pendulum_source.frame_count} frames)",
                detail="Local Pendulum Color sheet extractor",
                species_id=clean_species_id,
                name=clean_name,
                source_url=pendulum_source.url,
                frame_count=pendulum_source.frame_count,
                fps=pendulum_source.fps,
                row_index=row_index,
                matched_name=matched_name,
                source_name=pendulum_source.name,
            )
        )
    options.extend(_discover_wikimon_virtual_pet_options(clean_species_id, clean_name, timeout_seconds=timeout_seconds))
    return options


def import_sprite_option(
    option: SpriteImportOption,
    project_root: Path = PROJECT_ROOT,
    *,
    source_manifest_path: Path | None = None,
    roster_path: Path | None = None,
    source_config_path: Path | None = None,
    runtime_manifest_path: Path | None = None,
    report_path: Path | None = None,
    timeout_seconds: float = DEFAULT_PENDULUM_TIMEOUT_SECONDS,
) -> ImportedPendulumSprite | None:
    if option.provider_id == PENDULUM_COLOR_SOURCE_ID:
        return import_pendulum_color_sprite(
            option.species_id,
            option.name,
            project_root,
            source_manifest_path=source_manifest_path,
            roster_path=roster_path,
            source_config_path=source_config_path,
            runtime_manifest_path=runtime_manifest_path,
            report_path=report_path,
            timeout_seconds=timeout_seconds,
        )
    if option.provider_id == WIKIMON_VIRTUAL_PETS_SOURCE_ID:
        return _import_wikimon_virtual_pet_sprite(
            option,
            project_root,
            source_manifest_path=source_manifest_path,
            roster_path=roster_path,
            source_config_path=source_config_path,
            runtime_manifest_path=runtime_manifest_path,
            report_path=report_path,
            timeout_seconds=timeout_seconds,
        )
    return None


def sprite_import_option_preview_image(
    option: SpriteImportOption,
    *,
    timeout_seconds: float = DEFAULT_PENDULUM_TIMEOUT_SECONDS,
) -> QImage:
    if option.provider_id == PENDULUM_COLOR_SOURCE_ID:
        source = _sheet_source_for_option(option)
        if source is None or option.row_index is None:
            return QImage()
        sheet = _load_remote_image(source.url, timeout_seconds=timeout_seconds)
        if sheet.isNull():
            return QImage()
        row = _extract_sprite_row(sheet, source, option.row_index)
        return row.copy(QRect(0, 0, 64, 64))
    if option.provider_id == WIKIMON_VIRTUAL_PETS_SOURCE_ID and option.image_url:
        image = _load_remote_image(option.image_url, timeout_seconds=timeout_seconds)
        return _transparent_white_background(image) if not image.isNull() else image
    return QImage()


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
        PENDULUM_COLOR_SOURCE_ID,
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


def _sheet_source_for_option(option: SpriteImportOption) -> PendulumSheetSource | None:
    for source in PENDULUM_SHEET_SOURCES:
        if source.url == option.source_url and source.name == option.source_name:
            return source
    return None


def _discover_wikimon_virtual_pet_options(
    species_id: str,
    name: str,
    *,
    timeout_seconds: float,
) -> list[SpriteImportOption]:
    page_url = f"{WIKIMON_BASE_URL}/{quote(name.replace(' ', '_'))}"
    try:
        html = _load_remote_text(page_url, timeout_seconds=timeout_seconds)
    except OSError:
        return []
    section = _virtual_pet_gallery_section(html)
    if not section:
        return []
    options: list[SpriteImportOption] = []
    for image_cells, label_cells in _gallery_row_pairs(section):
        for index, image_cell in enumerate(image_cells):
            image = _image_from_gallery_cell(image_cell)
            if image is None:
                continue
            label = _cell_text(label_cells[index]) if index < len(label_cells) else image["alt"]
            if _is_wikimon_pendulum_label(label, image["alt"]):
                continue
            options.append(
                SpriteImportOption(
                    provider_id=WIKIMON_VIRTUAL_PETS_SOURCE_ID,
                    label=label or image["alt"],
                    detail=image["alt"],
                    species_id=species_id,
                    name=name,
                    source_url=page_url,
                    image_url=image["url"],
                    source_name="Wikimon Virtual Pets",
                )
            )
    return options


def _virtual_pet_gallery_section(html: str) -> str:
    match = re.search(r'id="Virtual_Pets_2"', html)
    if not match:
        return ""
    start = match.start()
    next_heading = re.search(r"<h[12]\b", html[start + 1 :])
    end = start + 1 + next_heading.start() if next_heading else len(html)
    return html[start:end]


def _gallery_row_pairs(section: str) -> list[tuple[list[str], list[str]]]:
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", section, flags=re.S | re.I)
    pairs: list[tuple[list[str], list[str]]] = []
    index = 0
    while index < len(rows):
        image_cells = re.findall(r"<td[^>]*>(.*?)</td>", rows[index], flags=re.S | re.I)
        label_cells = re.findall(r"<td[^>]*>(.*?)</td>", rows[index + 1], flags=re.S | re.I) if index + 1 < len(rows) else []
        if any("<img" in cell.casefold() for cell in image_cells):
            pairs.append((image_cells, label_cells))
            index += 2
        else:
            index += 1
    return pairs


def _image_from_gallery_cell(cell: str) -> dict[str, str] | None:
    src_match = re.search(r'\bsrc="([^"]+)"', cell)
    alt_match = re.search(r'\balt="([^"]+)"', cell)
    if not src_match:
        return None
    return {
        "url": _full_wikimon_image_url(src_match.group(1)),
        "alt": _html_unescape(alt_match.group(1)) if alt_match else "Wikimon sprite",
    }


def _full_wikimon_image_url(raw_url: str) -> str:
    url = _html_unescape(raw_url)
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("/"):
        return f"{WIKIMON_BASE_URL}{url}"
    return url


def _cell_text(cell: str) -> str:
    text = re.sub(r"<[^>]+>", " ", cell)
    return re.sub(r"\s+", " ", _html_unescape(text)).strip()


def _html_unescape(value: str) -> str:
    return (
        value.replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&#039;", "'")
        .replace("&nbsp;", " ")
    )


def _is_wikimon_pendulum_label(label: str, alt: str) -> bool:
    value = f"{label} {alt}".casefold()
    return "pendulum" in value or re.search(r"\bpen\b", value) is not None


def _project_default(path: Path) -> Path:
    return path.relative_to(PROJECT_ROOT)


def _load_remote_image(url: str, *, timeout_seconds: float) -> QImage:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=timeout_seconds) as response:
        payload = response.read()
    image = QImage()
    image.loadFromData(payload)
    return image.convertToFormat(QImage.Format.Format_ARGB32) if not image.isNull() else image


def _load_remote_text(url: str, *, timeout_seconds: float) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8", errors="replace")


def _import_wikimon_virtual_pet_sprite(
    option: SpriteImportOption,
    project_root: Path,
    *,
    source_manifest_path: Path | None,
    roster_path: Path | None,
    source_config_path: Path | None,
    runtime_manifest_path: Path | None,
    report_path: Path | None,
    timeout_seconds: float,
) -> ImportedPendulumSprite | None:
    image = _load_remote_image(option.image_url, timeout_seconds=timeout_seconds)
    if image.isNull():
        return None
    image = _transparent_white_background(image)
    filename = f"{_asset_slug(option.name)}_{_asset_slug(option.label)}.png"
    target_relative = Path("assets") / "sprite_sources" / WIKIMON_VIRTUAL_PETS_SOURCE_ID / filename
    target_path = project_root / target_relative
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(target_path), "PNG"):
        return None

    manifest_path = project_root / (source_manifest_path or WIKIMON_VIRTUAL_PETS_MANIFEST_PATH)
    _upsert_source_manifest_entry(
        manifest_path,
        {
            "fps": option.fps,
            "frame_count": 1,
            "name": option.name,
            "path": target_relative.as_posix(),
            "source_page": option.source_url,
            "source_label": option.label,
        },
    )
    effective_roster_path = project_root / (roster_path or _project_default(DEFAULT_ROSTER_PATH))
    effective_source_config_path = project_root / (source_config_path or _project_default(DEFAULT_SOURCE_CONFIG_PATH))
    effective_runtime_manifest_path = project_root / (runtime_manifest_path or _project_default(DEFAULT_MANIFEST_PATH))
    effective_report_path = project_root / (report_path or _project_default(DEFAULT_REPORT_PATH))
    _upsert_source_config_entry(
        effective_source_config_path,
        {
            "id": WIKIMON_VIRTUAL_PETS_SOURCE_ID,
            "name": "Wikimon Virtual Pets",
            "priority": 4,
            "manifest": WIKIMON_VIRTUAL_PETS_MANIFEST_PATH.as_posix(),
        },
    )
    _upsert_roster_entry(effective_roster_path, option.species_id, option.name, option.name, WIKIMON_VIRTUAL_PETS_SOURCE_ID)
    build_sprite_manifest(
        project_root,
        roster_path=effective_roster_path,
        source_config_path=effective_source_config_path,
        output_path=effective_runtime_manifest_path,
        report_path=effective_report_path,
    )
    return ImportedPendulumSprite(
        species_id=option.species_id,
        name=option.name,
        source_name=f"Wikimon Virtual Pets - {option.label}",
        path=target_path,
        relative_path=target_relative.as_posix(),
        frame_count=1,
        fps=option.fps,
    )


def _transparent_white_background(image: QImage) -> QImage:
    converted = image.convertToFormat(QImage.Format.Format_ARGB32)
    width = converted.width()
    height = converted.height()
    for y in range(height):
        for x in range(width):
            color = converted.pixelColor(x, y)
            if color.alpha() > 0 and color.red() >= 245 and color.green() >= 245 and color.blue() >= 245:
                color.setAlpha(0)
                converted.setPixelColor(x, y, color)
    return converted


def _asset_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    return slug or "sprite"


def _upsert_source_config_entry(path: Path, item: dict[str, Any]) -> None:
    entries = _load_source_config(path)
    by_id = {str(entry.get("id", "")): entry for entry in entries}
    by_id[str(item["id"])] = item
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(list(by_id.values()), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _load_source_config(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


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


def _upsert_roster_entry(roster_path: Path, species_id: str, name: str, matched_name: str, preferred_source_id: str) -> None:
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
        entry["preferred_source_id"] = preferred_source_id
        return _write_roster_json(roster_path, roster)
    entry = {"id": species_id, "name": name}
    if aliases:
        entry["aliases"] = aliases
    entry["preferred_source_id"] = preferred_source_id
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
