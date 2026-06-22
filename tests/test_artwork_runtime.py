import json

from PySide6.QtGui import QColor, QImage

from digimon_pet.app import artwork_runtime
from digimon_pet.app.artwork_runtime import (
    discover_and_download_artwork_for_species,
    download_artwork_for_species,
    download_missing_artworks,
    resolve_artwork_path,
)
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


def test_download_artwork_for_species_fetches_only_requested_species(tmp_path):
    agumon_source = tmp_path / "remote" / "agumon.jpg"
    numemon_source = tmp_path / "remote" / "numemon.jpg"
    agumon_target = tmp_path / "assets" / "artworks" / "agumon.png"
    numemon_target = tmp_path / "assets" / "artworks" / "numemon.png"
    manifest_path = tmp_path / "data" / "artwork_downloads.json"
    agumon_source.parent.mkdir(parents=True)
    _save_test_artwork(agumon_source)
    _save_test_artwork(numemon_source)
    _write_json(
        manifest_path,
        [
            {
                "species_id": "agumon",
                "name": "Agumon",
                "url": agumon_source.as_uri(),
                "path": "assets/artworks/agumon.png",
            },
            {
                "species_id": "numemon",
                "name": "Numemon",
                "url": numemon_source.as_uri(),
                "path": "assets/artworks/numemon.png",
            },
        ],
    )

    downloaded = download_artwork_for_species("numemon", tmp_path, manifest_path)

    assert downloaded == numemon_target
    assert numemon_target.exists()
    assert not agumon_target.exists()


def test_discover_and_download_artwork_for_species_uses_wikimon_api(tmp_path, monkeypatch):
    manifest_path = tmp_path / "data" / "artwork_downloads.json"
    source_png = tmp_path / "remote" / "weregarurumon.png"
    source_png.parent.mkdir(parents=True)
    _save_test_artwork(source_png)
    image_bytes = source_png.read_bytes()
    api_payload = json.dumps(
        {
            "query": {
                "pages": {
                    "553": {
                        "pageid": 553,
                        "title": "Were Garurumon",
                        "thumbnail": {
                            "source": (
                                "https://static.wikia.nocookie.net/wikimon-france/images/1/1f/"
                                "Were_Garurumon.png/revision/latest/scale-to-width-down/335"
                                "?cb=20220628133119&path-prefix=fr"
                            )
                        },
                    }
                }
            }
        }
    ).encode("utf-8")

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return self._payload

    def fake_urlopen(url, timeout):
        raw_url = getattr(url, "full_url", str(url))
        if raw_url.startswith(artwork_runtime.WIKIMON_FRANCE_API_URL):
            return FakeResponse(api_payload)
        return FakeResponse(image_bytes)

    monkeypatch.setattr(artwork_runtime, "urlopen", fake_urlopen)

    result = discover_and_download_artwork_for_species(
        "weregarurumon",
        "WereGarurumon",
        tmp_path,
        manifest_path,
    )

    assert result == tmp_path / "assets" / "artworks" / "weregarurumon.png"
    assert result.exists()
    entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert entries[0]["source_page"] == "https://wikimon-france.fandom.com/fr/wiki/Were_Garurumon"
    assert entries[0]["url"] == (
        "https://static.wikia.nocookie.net/wikimon-france/images/1/1f/"
        "Were_Garurumon.png/revision/latest?cb=20220628133119&path-prefix=fr"
    )


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
        url = str(entry["url"])
        source_page = str(entry["source_page"])
        if url.startswith("https://static.wikia.nocookie.net/wikimon-france/"):
            assert entry["url"].startswith("https://static.wikia.nocookie.net/wikimon-france/")
            assert "/revision/latest" in entry["url"]
            assert entry["source_page"].startswith("https://wikimon-france.fandom.com/fr/wiki/")
        elif url.startswith("https://www.digimon.net/cimages/digimon/"):
            assert entry["url"].startswith("https://www.digimon.net/cimages/digimon/")
            assert entry["url"].endswith(".jpg")
            assert entry["source_page"].startswith(
                "https://www.digimon.net/reference_en/detail.php?directory_name="
            )
        else:
            raise AssertionError(f"{species_id} has unsupported artwork source: {source_page}")
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
