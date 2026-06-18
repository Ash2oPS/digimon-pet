import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from digimon_pet.app import stats_window
from digimon_pet.app.stats_window import StatsWindow, _format_age
from digimon_pet.domain.models import GrowthStage, PetState, Species


def test_stats_window_age_display_does_not_round_up_before_next_hour():
    assert _format_age((2 * 60 * 60) - 1) == "1 h 59 min"
    assert _format_age(2 * 60 * 60) == "2 h 00 min"


def test_stats_window_prefers_official_artwork_over_runtime_sprite(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    artwork_path = tmp_path / "assets" / "artworks" / "agumon.png"
    sprite_path = tmp_path / "assets" / "sprite_sources" / "dmc" / "agumon.png"
    artwork_path.parent.mkdir(parents=True)
    sprite_path.parent.mkdir(parents=True)
    artwork = QPixmap(44, 66)
    sprite = QPixmap(16, 16)
    artwork.save(str(artwork_path))
    sprite.save(str(sprite_path))
    monkeypatch.setattr(stats_window, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(stats_window, "download_artwork_for_species", lambda species_id: None)
    monkeypatch.setattr(stats_window, "resolve_artwork_path", lambda species_id: artwork_path)

    window = StatsWindow()
    window._manifest = {
        "entries": {
            "agumon": {
                "asset_path": "assets/sprite_sources/dmc/agumon.png",
                "metadata": {"frame_count": 1},
            }
        }
    }

    pixmap = window._pixmap_for_species(
        PetState("agumon", GrowthStage.ROOKIE),
        Species("agumon", "Agumon", GrowthStage.ROOKIE),
    )

    assert pixmap is not None
    assert pixmap.width() == 44
    assert pixmap.height() == 66


def test_stats_window_opens_without_synchronous_artwork_download(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        stats_window,
        "download_artwork_for_species",
        lambda species_id: (_ for _ in ()).throw(AssertionError("stats should not block on artwork download")),
    )

    StatsWindow()
