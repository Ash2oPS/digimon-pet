from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from PySide6.QtGui import QColor, QImage

from digimon_pet.paths import PROJECT_ROOT

DEFAULT_ARTWORK_DOWNLOAD_MANIFEST_PATH = PROJECT_ROOT / "data" / "artwork_downloads.json"
BACKGROUND_RGB_THRESHOLD = 245
DEFAULT_DOWNLOAD_TIMEOUT_SECONDS = 8.0
WIKIMON_FRANCE_API_URL = "https://wikimon-france.fandom.com/fr/api.php"
WIKIMON_FRANCE_PAGE_BASE_URL = "https://wikimon-france.fandom.com/fr/wiki/"


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
        count += _download_artwork_entry(project_root, entry) is not None
    return count


def download_artwork_for_species(
    species_id: str,
    project_root: Path = PROJECT_ROOT,
    manifest_path: Path = DEFAULT_ARTWORK_DOWNLOAD_MANIFEST_PATH,
) -> Path | None:
    if not manifest_path.exists():
        return None
    entry = _artwork_entry_for_species(species_id, manifest_path)
    if entry is None:
        return None
    target_path = _project_relative_path(project_root, entry.get("path"))
    if target_path.exists():
        return target_path
    return _download_artwork_entry(project_root, entry)


def discover_and_download_artwork_for_species(
    species_id: str,
    name: str,
    project_root: Path = PROJECT_ROOT,
    manifest_path: Path = DEFAULT_ARTWORK_DOWNLOAD_MANIFEST_PATH,
    *,
    timeout_seconds: float = DEFAULT_DOWNLOAD_TIMEOUT_SECONDS,
) -> Path | None:
    clean_species_id = species_id.strip()
    clean_name = name.strip()
    if not clean_species_id or not clean_name:
        return None
    entry = _discover_wikimon_france_artwork_entry(
        clean_species_id,
        clean_name,
        timeout_seconds=timeout_seconds,
    )
    if entry is None:
        return None
    _upsert_artwork_manifest_entry(manifest_path, entry)
    return _download_artwork_entry(project_root, entry)


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


def _artwork_entry_for_species(species_id: str, manifest_path: Path) -> dict[str, Any] | None:
    for entry in _load_artwork_entries(manifest_path):
        if str(entry.get("species_id", "")) == species_id:
            return entry
    return None


def _discover_wikimon_france_artwork_entry(
    species_id: str,
    name: str,
    *,
    timeout_seconds: float,
) -> dict[str, Any] | None:
    for title in _wikimon_title_candidates(name):
        api_url = (
            f"{WIKIMON_FRANCE_API_URL}?action=query&titles={quote(title)}"
            "&prop=pageimages&format=json&pithumbsize=800"
        )
        try:
            with urlopen(_web_request(api_url), timeout=timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        page = _first_found_wikimon_page(payload)
        if page is None:
            continue
        thumbnail = page.get("thumbnail", {})
        if not isinstance(thumbnail, dict):
            continue
        source_url = _normalize_fandom_image_url(str(thumbnail.get("source", "")))
        if not source_url:
            continue
        page_title = str(page.get("title") or title)
        return {
            "species_id": species_id,
            "name": name,
            "official_name": page_title,
            "source_page": WIKIMON_FRANCE_PAGE_BASE_URL + quote(page_title.replace(" ", "_")),
            "url": source_url,
            "path": f"assets/artworks/{species_id}.png",
        }
    return None


def _wikimon_title_candidates(name: str) -> list[str]:
    candidates = [
        name,
        _split_camel_case(name),
        name.replace("-", " "),
        name.replace("_", " "),
    ]
    seen: set[str] = set()
    unique: list[str] = []
    for candidate in candidates:
        normalized = re.sub(r"\s+", " ", candidate).strip()
        key = normalized.casefold()
        if normalized and key not in seen:
            unique.append(normalized)
            seen.add(key)
    return unique


def _split_camel_case(value: str) -> str:
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value)
    return re.sub(r"\s+", " ", spaced).strip()


def _first_found_wikimon_page(payload: dict[str, Any]) -> dict[str, Any] | None:
    pages = payload.get("query", {}).get("pages", {})
    if not isinstance(pages, dict):
        return None
    for page in pages.values():
        if isinstance(page, dict) and "missing" not in page:
            return page
    return None


def _normalize_fandom_image_url(url: str) -> str:
    if not url.startswith("https://static.wikia.nocookie.net/wikimon-france/"):
        return ""
    return re.sub(r"/scale-to-width-down/\d+", "", url)


def _web_request(url: str) -> Request:
    return Request(url, headers={"User-Agent": "Mozilla/5.0"})


def _upsert_artwork_manifest_entry(manifest_path: Path, entry: dict[str, Any]) -> None:
    entries = _load_artwork_entries(manifest_path) if manifest_path.exists() else []
    by_species_id = {str(item.get("species_id", "")): item for item in entries}
    by_species_id[str(entry["species_id"])] = entry
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(list(by_species_id.values()), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _download_artwork_entry(project_root: Path, entry: dict[str, Any]) -> Path | None:
    target_path = _project_relative_path(project_root, entry.get("path"))
    if target_path.exists():
        return target_path
    url = str(entry.get("url", "")).strip()
    if not url:
        return None
    target_path.parent.mkdir(parents=True, exist_ok=True)
    download_path = target_path.with_name(f"{target_path.name}.download")
    try:
        with urlopen(_web_request(url), timeout=DEFAULT_DOWNLOAD_TIMEOUT_SECONDS) as response:
            download_path.write_bytes(response.read())
        if not _write_transparent_artwork(download_path, target_path):
            return None
    except OSError:
        return None
    finally:
        download_path.unlink(missing_ok=True)
    return target_path


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
