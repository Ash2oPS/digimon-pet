import json

from digimon_pet.app.artwork_runtime import download_missing_artworks, resolve_artwork_path
from digimon_pet.data.sprite_pipeline import load_roster


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_download_missing_artworks_fetches_declared_official_artwork(tmp_path):
    source_jpg = tmp_path / "remote" / "agumon.jpg"
    target_jpg = tmp_path / "assets" / "artworks" / "agumon.jpg"
    manifest_path = tmp_path / "data" / "artwork_downloads.json"
    source_jpg.parent.mkdir(parents=True)
    source_jpg.write_bytes(b"official jpg")
    _write_json(
        manifest_path,
        [
            {
                "species_id": "agumon",
                "name": "Agumon",
                "source_page": "https://www.digimon.net/reference_en/detail.php?directory_name=agumon",
                "url": source_jpg.as_uri(),
                "path": "assets/artworks/agumon.jpg",
            }
        ],
    )

    count = download_missing_artworks(tmp_path, manifest_path)

    assert count == 1
    assert target_jpg.read_bytes() == b"official jpg"
    assert resolve_artwork_path("agumon", tmp_path, manifest_path) == target_jpg


def test_existing_artwork_is_not_downloaded_again(tmp_path):
    source_jpg = tmp_path / "remote" / "agumon.jpg"
    target_jpg = tmp_path / "assets" / "artworks" / "agumon.jpg"
    manifest_path = tmp_path / "data" / "artwork_downloads.json"
    target_jpg.parent.mkdir(parents=True)
    target_jpg.write_bytes(b"already downloaded")
    _write_json(
        manifest_path,
        [
            {
                "species_id": "agumon",
                "name": "Agumon",
                "source_page": "https://www.digimon.net/reference_en/detail.php?directory_name=agumon",
                "url": source_jpg.as_uri(),
                "path": "assets/artworks/agumon.jpg",
            }
        ],
    )

    count = download_missing_artworks(tmp_path, manifest_path)

    assert count == 0
    assert target_jpg.read_bytes() == b"already downloaded"


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
        assert entry["path"] == f"assets/artworks/{species_id}.jpg"
