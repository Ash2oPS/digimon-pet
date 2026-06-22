from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRect, Qt
from PySide6.QtGui import QColor, QImage, QImageReader, QPainter

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
DOWNLOAD_MANIFEST_PROVIDER_ID = "sprite_download_manifest"
DOWNLOAD_MANIFEST_PATH = Path("data/sprite_downloads.json")
DOWNLOAD_MANIFEST_SOURCE_IDS = frozenset({"digital_monster_color", "xros_loader_toy"})
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
class AnimationSheet:
    image: QImage
    frame_count: int
    fps: int
    frame_width: int
    frame_height: int


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
    metadata: dict[str, Any] = field(default_factory=dict)


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
    download_manifest_path: Path | None = None,
    source_config_path: Path | None = None,
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
    options.extend(
        _discover_download_manifest_options(
            clean_species_id,
            clean_name,
            project_root,
            download_manifest_path=download_manifest_path,
            source_config_path=source_config_path,
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
    if option.provider_id == DOWNLOAD_MANIFEST_PROVIDER_ID:
        return _import_download_manifest_sprite(
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
        animation = _load_remote_animation_sheet(option.image_url, timeout_seconds=timeout_seconds)
        if animation.image.isNull():
            return QImage()
        return _transparent_white_background(animation.image.copy(QRect(0, 0, animation.frame_width, animation.frame_height)))
    if option.provider_id == DOWNLOAD_MANIFEST_PROVIDER_ID and option.image_url:
        animation = _load_remote_animation_sheet(
            option.image_url,
            frame_count=int(option.metadata.get("frame_count") or option.frame_count or 1),
            fps=int(option.metadata.get("fps") or option.fps or 6),
            metadata=option.metadata,
            timeout_seconds=timeout_seconds,
        )
        return animation.image.copy(QRect(0, 0, animation.frame_width, animation.frame_height)) if not animation.image.isNull() else QImage()
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


def _discover_download_manifest_options(
    species_id: str,
    name: str,
    project_root: Path,
    *,
    download_manifest_path: Path | None,
    source_config_path: Path | None,
) -> list[SpriteImportOption]:
    manifest_path = _resolve_project_path(project_root, download_manifest_path or DOWNLOAD_MANIFEST_PATH)
    entries = _load_download_manifest(manifest_path)
    if not entries:
        return []
    sources = _source_config_by_id(_resolve_project_path(project_root, source_config_path or _project_default(DEFAULT_SOURCE_CONFIG_PATH)))
    target_names = {normalize_name(name), normalize_name(species_id)}
    options: list[SpriteImportOption] = []
    for entry in entries:
        source_id = str(entry.get("source_id", ""))
        if source_id not in DOWNLOAD_MANIFEST_SOURCE_IDS or not _download_entry_matches(entry, target_names):
            continue
        source_config = sources.get(source_id, {})
        source_name = str(source_config.get("name") or source_id.replace("_", " ").title())
        entry_name = str(entry.get("name") or name)
        frame_count = _positive_int(entry.get("frame_count"), 1)
        fps = _positive_int(entry.get("fps"), 6)
        path = str(entry.get("path") or "")
        options.append(
            SpriteImportOption(
                provider_id=DOWNLOAD_MANIFEST_PROVIDER_ID,
                label=f"{source_name} ({frame_count} frames)",
                detail=Path(path).name if path else str(entry.get("url") or ""),
                species_id=species_id,
                name=name,
                source_url=str(entry.get("url") or ""),
                image_url=str(entry.get("url") or ""),
                frame_count=frame_count,
                fps=fps,
                matched_name=entry_name,
                source_name=source_name,
                metadata=dict(entry),
            )
        )
    return options


def _download_entry_matches(entry: dict[str, Any], target_names: set[str]) -> bool:
    candidates = [
        str(entry.get("species_id", "")),
        str(entry.get("name", "")),
        Path(str(entry.get("path", ""))).stem,
    ]
    return any(normalize_name(candidate) in target_names for candidate in candidates if candidate.strip())


def _load_download_manifest(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


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


def _resolve_project_path(project_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else project_root / path


def _load_remote_image(url: str, *, timeout_seconds: float) -> QImage:
    payload = _load_remote_bytes(url, timeout_seconds=timeout_seconds)
    image = QImage()
    image.loadFromData(payload)
    return image.convertToFormat(QImage.Format.Format_ARGB32) if not image.isNull() else image


def _load_remote_animation_sheet(
    url: str,
    *,
    frame_count: int = 1,
    fps: int = 6,
    metadata: dict[str, Any] | None = None,
    timeout_seconds: float,
) -> AnimationSheet:
    payload = _load_remote_bytes(url, timeout_seconds=timeout_seconds)
    frames, delays = _decode_animation_frames(payload)
    if len(frames) > 1:
        effective_fps = _fps_from_delays(delays, fps)
        return _pack_frames(frames, effective_fps)
    image = frames[0] if frames else QImage()
    if image.isNull():
        return AnimationSheet(QImage(), 0, fps, 0, 0)
    return _spritesheet_to_animation_sheet(image, frame_count=frame_count, fps=fps, metadata=metadata or {})


def _load_remote_bytes(url: str, *, timeout_seconds: float) -> bytes:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read()


def _decode_animation_frames(payload: bytes) -> tuple[list[QImage], list[int]]:
    data = QByteArray(payload)
    buffer = QBuffer()
    buffer.setData(data)
    if not buffer.open(QIODevice.OpenModeFlag.ReadOnly):
        return [], []
    reader = QImageReader(buffer)
    frames: list[QImage] = []
    delays: list[int] = []
    try:
        image_count = reader.imageCount()
        total = image_count if image_count > 0 else 1
        for _ in range(total):
            image = reader.read()
            if image.isNull():
                break
            frames.append(image.convertToFormat(QImage.Format.Format_ARGB32))
            delay = reader.nextImageDelay()
            if delay > 0:
                delays.append(delay)
    finally:
        buffer.close()
    return frames, delays


def _spritesheet_to_animation_sheet(
    image: QImage,
    *,
    frame_count: int,
    fps: int,
    metadata: dict[str, Any],
) -> AnimationSheet:
    frame_count = max(1, frame_count)
    columns = _positive_int(metadata.get("columns"), 0)
    frame_width = _positive_int(metadata.get("frame_width"), 0)
    frame_height = _positive_int(metadata.get("frame_height"), 0)
    if frame_width and frame_height:
        columns = columns or max(1, image.width() // frame_width)
        return _copy_sheet_cells(image, frame_count, fps, frame_width, frame_height, columns)
    if frame_count > 1 and image.width() % frame_count == 0:
        frame_width = image.width() // frame_count
        return AnimationSheet(image, frame_count, fps, frame_width, image.height())
    if frame_count > 1 and image.height() % frame_count == 0:
        frame_height = image.height() // frame_count
        return _copy_sheet_cells(image, frame_count, fps, image.width(), frame_height, 1)
    if frame_count > 1 and columns > 1:
        rows = (frame_count + columns - 1) // columns
        if image.width() % columns == 0 and image.height() % rows == 0:
            return _copy_sheet_cells(image, frame_count, fps, image.width() // columns, image.height() // rows, columns)
    return AnimationSheet(image, 1, fps, image.width(), image.height())


def _copy_sheet_cells(
    image: QImage,
    frame_count: int,
    fps: int,
    frame_width: int,
    frame_height: int,
    columns: int,
) -> AnimationSheet:
    output = QImage(frame_count * frame_width, frame_height, QImage.Format.Format_ARGB32)
    output.fill(QColor(0, 0, 0, 0))
    painter = QPainter(output)
    try:
        for index in range(frame_count):
            source_x = (index % columns) * frame_width
            source_y = (index // columns) * frame_height
            frame = image.copy(QRect(source_x, source_y, frame_width, frame_height))
            painter.drawImage(index * frame_width, 0, frame)
    finally:
        painter.end()
    return AnimationSheet(output, frame_count, fps, frame_width, frame_height)


def _pack_frames(frames: list[QImage], fps: int) -> AnimationSheet:
    frame_width = max((frame.width() for frame in frames), default=0)
    frame_height = max((frame.height() for frame in frames), default=0)
    if not frame_width or not frame_height:
        return AnimationSheet(QImage(), 0, fps, 0, 0)
    output = QImage(len(frames) * frame_width, frame_height, QImage.Format.Format_ARGB32)
    output.fill(QColor(0, 0, 0, 0))
    painter = QPainter(output)
    try:
        for index, frame in enumerate(frames):
            x = index * frame_width + (frame_width - frame.width()) // 2
            y = frame_height - frame.height()
            painter.drawImage(x, y, frame)
    finally:
        painter.end()
    return AnimationSheet(output, len(frames), fps, frame_width, frame_height)


def _fps_from_delays(delays: list[int], fallback: int) -> int:
    positive = [delay for delay in delays if delay > 0]
    if not positive:
        return fallback
    average = sum(positive) / len(positive)
    return max(1, round(1000 / average))


def _positive_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


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
    animation = _load_remote_animation_sheet(option.image_url, fps=option.fps, timeout_seconds=timeout_seconds)
    if animation.image.isNull():
        return None
    image = _transparent_white_background(animation.image)
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
            "frame_count": animation.frame_count,
            "frame_width": animation.frame_width,
            "frame_height": animation.frame_height,
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
        frame_count=animation.frame_count,
        fps=option.fps,
    )


def _import_download_manifest_sprite(
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
    entry = option.metadata
    source_id = str(entry.get("source_id") or "")
    if source_id not in DOWNLOAD_MANIFEST_SOURCE_IDS:
        return None
    target_relative = Path(str(entry.get("path") or ""))
    if not target_relative.as_posix():
        return None
    animation = _load_remote_animation_sheet(
        str(entry.get("url") or option.image_url),
        frame_count=_positive_int(entry.get("frame_count"), option.frame_count),
        fps=_positive_int(entry.get("fps"), option.fps),
        metadata=entry,
        timeout_seconds=timeout_seconds,
    )
    if animation.image.isNull():
        return None

    target_path = project_root / target_relative
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if not animation.image.save(str(target_path), "PNG"):
        return None

    effective_source_config_path = project_root / (source_config_path or _project_default(DEFAULT_SOURCE_CONFIG_PATH))
    manifest_path = (
        project_root / source_manifest_path
        if source_manifest_path is not None
        else _source_manifest_path(effective_source_config_path, project_root, source_id)
    )
    name = str(entry.get("name") or option.name)
    _upsert_source_manifest_entry(
        manifest_path,
        {
            "fps": animation.fps,
            "frame_count": animation.frame_count,
            "frame_width": animation.frame_width,
            "frame_height": animation.frame_height,
            "name": name,
            "path": target_relative.as_posix(),
            "source_url": str(entry.get("url") or option.image_url),
        },
    )
    effective_roster_path = project_root / (roster_path or _project_default(DEFAULT_ROSTER_PATH))
    effective_runtime_manifest_path = project_root / (runtime_manifest_path or _project_default(DEFAULT_MANIFEST_PATH))
    effective_report_path = project_root / (report_path or _project_default(DEFAULT_REPORT_PATH))
    _upsert_roster_entry(effective_roster_path, option.species_id, option.name, name, source_id)
    build_sprite_manifest(
        project_root,
        roster_path=effective_roster_path,
        source_config_path=effective_source_config_path,
        output_path=effective_runtime_manifest_path,
        report_path=effective_report_path,
    )
    return ImportedPendulumSprite(
        species_id=option.species_id,
        name=name,
        source_name=option.source_name,
        path=target_path,
        relative_path=target_relative.as_posix(),
        frame_count=animation.frame_count,
        fps=animation.fps,
    )


def _transparent_white_background(image: QImage) -> QImage:
    converted = image.convertToFormat(QImage.Format.Format_ARGB32)
    width = converted.width()
    height = converted.height()
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
        visited.add((x, y))
        color = converted.pixelColor(x, y)
        if not _is_near_white(color):
            continue
        color.setAlpha(0)
        converted.setPixelColor(x, y, color)
        queue.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    return converted


def _is_near_white(color: QColor) -> bool:
    return color.alpha() > 0 and color.red() >= 245 and color.green() >= 245 and color.blue() >= 245


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


def _source_config_by_id(path: Path) -> dict[str, dict[str, Any]]:
    return {str(entry.get("id", "")): entry for entry in _load_source_config(path)}


def _source_manifest_path(source_config_path: Path, project_root: Path, source_id: str) -> Path:
    source_config = _source_config_by_id(source_config_path).get(source_id, {})
    manifest = str(source_config.get("manifest") or "")
    if manifest:
        return _resolve_project_path(project_root, Path(manifest))
    return project_root / "assets" / "sprite_sources" / source_id / "manifest.json"


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
