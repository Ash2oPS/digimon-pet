import json

from PySide6.QtGui import QColor, QImage

from digimon_pet.app.artwork_runtime import download_missing_artworks, resolve_artwork_path
from digimon_pet.data.sprite_pipeline import load_roster


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_download_missing_artworks_fetches_declared_official_artwork(tmp_path):
    source_jpg = tmp_path / "remote" / "agumon.jpg"
    target_png = tmp_path / "assets" / "artworks" / "agumon.png"
    manifest_path = tmp_path / "data" / "artwork_downloads.json"
    source_jpg.parent.mkdir(parents=True)
    _save_test_artwork(source_jpg)
    _write_json(
        manifest_path,
        [
            {
                "species_id": "agumon",
                "name": "Agumon",
                "source_page": "https://www.digimon.net/reference_en/detail.php?directory_name=agumon",
                "url": source_jpg.as_uri(),
                "path": "assets/artworks/agumon.png",
            }
        ],
    )

    count = download_missing_artworks(tmp_path, manifest_path)

    assert count == 1
    assert resolve_artwork_path("agumon", tmp_path, manifest_path) == target_png
    image = QImage(str(target_png))
    assert image.pixelColor(0, 0).alpha() == 0
    assert image.pixelColor(2, 2).alpha() == 255


def test_existing_artwork_is_not_downloaded_again(tmp_path):
    source_jpg = tmp_path / "remote" / "agumon.jpg"
    target_png = tmp_path / "assets" / "artworks" / "agumon.png"
    manifest_path = tmp_path / "data" / "artwork_downloads.json"
    target_png.parent.mkdir(parents=True)
    target_png.write_bytes(b"already downloaded")
    _write_json(
        manifest_path,
        [
            {
                "species_id": "agumon",
                "name": "Agumon",
                "source_page": "https://www.digimon.net/reference_en/detail.php?directory_name=agumon",
                "url": source_jpg.as_uri(),
                "path": "assets/artworks/agumon.png",
            }
        ],
    )

    count = download_missing_artworks(tmp_path, manifest_path)

    assert count == 0
    assert target_png.read_bytes() == b"already downloaded"


def test_downloaded_artwork_keeps_internal_white_pixels_opaque(tmp_path):
    source_jpg = tmp_path / "remote" / "agumon.jpg"
    target_png = tmp_path / "assets" / "artworks" / "agumon.png"
    manifest_path = tmp_path / "data" / "artwork_downloads.json"
    source_jpg.parent.mkdir(parents=True)
    _save_test_artwork(source_jpg)
    _write_json(
        manifest_path,
        [
            {
                "species_id": "agumon",
                "name": "Agumon",
                "source_page": "https://www.digimon.net/reference_en/detail.php?directory_name=agumon",
                "url": source_jpg.as_uri(),
                "path": "assets/artworks/agumon.png",
            }
        ],
    )

    download_missing_artworks(tmp_path, manifest_path)

    image = QImage(str(target_png))
    assert image.pixelColor(0, 0).alpha() == 0
    assert image.pixelColor(3, 3).alpha() == 255


def test_official_artwork_manifest_covers_dw1_roster():
    manifest_path = "data/artwork_downloads.json"
    with open(manifest_path, "r", encoding="utf-8") as handle:
        entries = json.load(handle)

    expected_ids = {entry.id for entry in load_roster()}
    by_species_id = {str(entry["species_id"]): entry for entry in entries}

    assert set(by_species_id) == expected_ids
    for species_id, entry in by_species_id.items():
        assert entry["url"].startswith("https://www.digimon.net/cimages/digimon/")
        assert entry["url"].endswith(".jpg")
        assert entry["source_page"].startswith("https://www.digimon.net/reference_en/detail.php?directory_name=")
        assert entry["path"] == f"assets/artworks/{species_id}.png"


def _save_test_artwork(path):
    image = QImage(7, 7, QImage.Format.Format_RGB32)
    image.fill(QColor(255, 255, 255))
    for x in range(2, 5):
        image.setPixelColor(x, 2, QColor(20, 20, 20))
        image.setPixelColor(x, 4, QColor(20, 20, 20))
    for y in range(2, 5):
        image.setPixelColor(2, y, QColor(20, 20, 20))
        image.setPixelColor(4, y, QColor(20, 20, 20))
    image.setPixelColor(3, 3, QColor(255, 255, 255))
    image.save(str(path))
