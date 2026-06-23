import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from digimon_pet.app import stats_window
from digimon_pet.app.stats_window import (
    StatsWindow,
    _evolution_options_for_species,
    _format_age,
    _format_requirements_progress,
    _requirement_stats,
)
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


def test_stats_window_exposes_complete_tabbed_profile(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(stats_window, "resolve_artwork_path", lambda species_id: None)
    monkeypatch.setattr(stats_window, "download_artwork_for_species", lambda species_id: None)

    window = StatsWindow()
    window.refresh(
        PetState(
            "terriermon",
            GrowthStage.ROOKIE,
            age_seconds=125,
            hp=4414,
            mp=2994,
            offense=202,
            defense=179,
            speed=238,
            brains=296,
        ),
        Species("terriermon", "Terriermon", GrowthStage.ROOKIE),
    )

    assert [window._tabs.tabText(index) for index in range(window._tabs.count())] == [
        "View",
        "Combat",
        "Care",
        "Evolution",
    ]
    assert [label.text() for label in window._label_groups["hp"]] == ["4414", "4414"]
    assert [bar.value() for bar in window._bar_groups["hunger"]] == [30, 30]


def test_terriermon_evolution_progress_reports_missing_stats():
    digivolutions = {
        "natural_evolutions": [
            {
                "id": "terriermon__to__galgomon",
                "target_name": "Galgomon",
                "requirements": {
                    "groups": {
                        "stats": {
                            "hp": 2000,
                            "mp": 3000,
                            "offense": 250,
                            "speed": 400,
                        }
                    }
                },
            }
        ],
        "indexes": {"by_source": {"terriermon": ["terriermon__to__galgomon"]}},
    }
    option = _evolution_options_for_species(digivolutions, "terriermon")[0]

    progress = _format_requirements_progress(
        PetState("terriermon", GrowthStage.ROOKIE, hp=4414, mp=2994, offense=202, speed=238),
        _requirement_stats(option),
    )

    assert "HP 4414/2000 (OK)" in progress
    assert "MP 2994/3000 (needs 6)" in progress
    assert "OFF 202/250 (needs 48)" in progress
    assert "SPD 238/400 (needs 162)" in progress


def test_stats_window_hides_unknown_evolution_requirements(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(stats_window, "resolve_artwork_path", lambda species_id: None)
    monkeypatch.setattr(stats_window, "download_artwork_for_species", lambda species_id: None)

    window = StatsWindow()
    window._digivolutions = {
        "natural_evolutions": [
            {
                "id": "terriermon__to__galgomon",
                "source_species_id": "terriermon",
                "target_species_id": "galgomon",
                "target_name": "Galgomon",
                "requirements": {"groups": {"stats": {"offense": 250}}},
            }
        ],
        "indexes": {"by_source": {"terriermon": ["terriermon__to__galgomon"]}},
    }

    window.refresh(
        PetState("terriermon", GrowthStage.ROOKIE, offense=202, discovered_species_ids=["terriermon"]),
        Species("terriermon", "Terriermon", GrowthStage.ROOKIE),
    )

    cards = [frame for frame in window.findChildren(stats_window.QFrame) if frame.objectName() == "EvolutionRequirementCard"]
    texts = [label.text() for card in cards for label in card.findChildren(type(window._name_label))]
    assert "???" in texts
    assert "Galgomon" not in texts
    assert "OFF" not in texts
    assert not any("250" in text for text in texts)


def test_stats_window_shows_discovered_evolution_requirements(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(stats_window, "resolve_artwork_path", lambda species_id: None)
    monkeypatch.setattr(stats_window, "download_artwork_for_species", lambda species_id: None)

    window = StatsWindow()
    window._digivolutions = {
        "natural_evolutions": [
            {
                "id": "terriermon__to__galgomon",
                "source_species_id": "terriermon",
                "target_species_id": "galgomon",
                "target_name": "Galgomon",
                "requirements": {"groups": {"stats": {"offense": 250}}},
            }
        ],
        "indexes": {"by_source": {"terriermon": ["terriermon__to__galgomon"]}},
    }

    window.refresh(
        PetState(
            "terriermon",
            GrowthStage.ROOKIE,
            offense=202,
            discovered_species_ids=["terriermon", "galgomon"],
        ),
        Species("terriermon", "Terriermon", GrowthStage.ROOKIE),
    )

    cards = [frame for frame in window.findChildren(stats_window.QFrame) if frame.objectName() == "EvolutionRequirementCard"]
    texts = [label.text() for card in cards for label in card.findChildren(type(window._name_label))]
    assert "Galgomon" in texts
    assert "OFF" in texts
    assert "202 / 250" in texts
    assert "Need 48" in texts
