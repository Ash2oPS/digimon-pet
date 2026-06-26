import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QFrame, QLabel

from digimon_pet.app import stats_window
from digimon_pet.app.stats_window import (
    STATS_PORTRAIT_PIXMAP_SIZE,
    STATS_PORTRAIT_SIZE,
    StatsWindow,
    _evolution_options_for_species,
    _format_age,
    _format_requirements_progress,
    _requirement_stats,
)
from digimon_pet.domain.models import GrowthStage, PetState, Species


def _write_two_frame_sprite(path) -> None:
    pixmap = QPixmap(48, 24)
    pixmap.fill()
    painter = QPainter(pixmap)
    painter.fillRect(0, 0, 24, 24, QColor("red"))
    painter.fillRect(24, 0, 24, 24, QColor("blue"))
    painter.end()
    pixmap.save(str(path))


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


def test_stats_window_uses_large_artwork_portrait(monkeypatch):
    app = QApplication.instance() or QApplication([])
    portrait = QPixmap(240, 180)
    monkeypatch.setattr(stats_window, "resolve_artwork_path", lambda species_id: None)
    monkeypatch.setattr(stats_window, "download_artwork_for_species", lambda species_id: None)

    window = StatsWindow()
    monkeypatch.setattr(window, "_pixmap_for_species", lambda state, species: portrait)
    window.refresh(
        PetState("agumon", GrowthStage.ROOKIE),
        Species("agumon", "Agumon", GrowthStage.ROOKIE),
    )

    rendered = window._sprite_label.pixmap()

    assert window._sprite_label.width() == STATS_PORTRAIT_SIZE
    assert window._sprite_label.height() == STATS_PORTRAIT_SIZE
    assert rendered is not None
    assert rendered.width() == STATS_PORTRAIT_PIXMAP_SIZE


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
    monkeypatch.setattr(stats_window, "load_runtime_manifest", lambda: {"entries": {}})
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
        "Stats",
        "Evolutions",
    ]
    labels = [label.text() for label in window.findChildren(QLabel)]
    assert "Evolutions" in labels
    assert "Direct evolutions" not in labels
    assert [label.text() for label in window._label_groups["hp"]] == ["4414"]
    assert [bar.value() for bar in window._bar_groups["hunger"]] == [30]


def test_stats_window_displays_current_stage_age_not_total_generation_age(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(stats_window, "load_runtime_manifest", lambda: {"entries": {}})
    monkeypatch.setattr(stats_window, "resolve_artwork_path", lambda species_id: None)
    monkeypatch.setattr(stats_window, "download_artwork_for_species", lambda species_id: None)

    window = StatsWindow()
    window.refresh(
        PetState(
            "skullgreymon",
            GrowthStage.ULTIMATE,
            age_seconds=55 * 60,
            total_age_seconds=(4 * 60 + 55) * 60,
        ),
        Species("skullgreymon", "SkullGreymon", GrowthStage.ULTIMATE),
    )

    assert window._summary_label.text().startswith("0 h 55 min")


def test_stats_window_combat_stats_have_compact_max_gauges(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(stats_window, "resolve_artwork_path", lambda species_id: None)
    monkeypatch.setattr(stats_window, "download_artwork_for_species", lambda species_id: None)

    window = StatsWindow()
    window.refresh(
        PetState(
            "commandramon",
            GrowthStage.ROOKIE,
            hp=6442,
            mp=3202,
            offense=381,
            defense=391,
            speed=314,
            brains=451,
        ),
        Species("commandramon", "Commandramon", GrowthStage.ROOKIE),
    )

    assert [label.text() for label in window._label_groups["hp"]] == ["6442"]
    assert [bar.maximum() for bar in window._bar_groups["hp"]] == [99999]
    assert [bar.value() for bar in window._bar_groups["hp"]] == [6442]
    assert [bar.maximum() for bar in window._bar_groups["offense"]] == [9999]
    assert [bar.value() for bar in window._bar_groups["offense"]] == [381]
    assert window._bar_groups["hp"][0].toolTip() == "HP 6442 / 99999"
    assert window._bar_groups["offense"][0].toolTip() == "OFF 381 / 9999"
    assert window._label_groups["hp"][0].objectName() == "StatsBarValue"
    assert window._label_groups["offense"][0].objectName() == "StatsBarValue"


def test_stats_window_care_gauges_use_compact_bars(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(stats_window, "load_runtime_manifest", lambda: {"entries": {}})
    monkeypatch.setattr(stats_window, "resolve_artwork_path", lambda species_id: None)
    monkeypatch.setattr(stats_window, "download_artwork_for_species", lambda species_id: None)

    window = StatsWindow()
    window.refresh(
        PetState(
            "numemon",
            GrowthStage.CHAMPION,
            hunger=30,
            happiness=50,
            discipline=50,
            fatigue=0,
        ),
        Species("numemon", "Numemon", GrowthStage.CHAMPION),
    )

    assert [label.text() for label in window._label_groups["hunger_bar_value"]] == ["30"]
    assert window._bar_groups["hunger"][0].maximum() == 100
    assert window._bar_groups["hunger"][0].value() == 30
    window.show()
    app.processEvents()
    assert window._bar_groups["hunger"][0].height() == 8
    assert window._bar_groups["hunger"][0].toolTip() == "Hunger 30 / 100"


def test_stats_window_view_tab_omits_redundant_summary_cards(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(stats_window, "load_runtime_manifest", lambda: {"entries": {}})
    monkeypatch.setattr(stats_window, "resolve_artwork_path", lambda species_id: None)
    monkeypatch.setattr(stats_window, "download_artwork_for_species", lambda species_id: None)

    window = StatsWindow()
    window.refresh(
        PetState("numemon", GrowthStage.CHAMPION, age_seconds=240),
        Species("numemon", "Numemon", GrowthStage.CHAMPION),
    )

    view_tab = window._tabs.widget(0)
    labels = [label.text() for label in view_tab.findChildren(QLabel)]

    assert view_tab.findChildren(QFrame, "StatsMetricCard") == []
    assert "Combat" in labels
    assert "Care gauges" in labels
    assert labels.index("Combat") < labels.index("Care gauges")


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


def test_stats_window_evolution_intel_lists_direct_evolutions_and_hides_unknown_values(monkeypatch):
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
                "target_stage": "champion",
                "requirements": {"groups": {"stats": {"offense": 250}}},
            },
            {
                "id": "terriermon__to__rapidmon",
                "source_species_id": "terriermon",
                "target_species_id": "rapidmon",
                "target_name": "Rapidmon",
                "target_stage": "ultimate",
                "requirements": {"groups": {"stats": {"speed": 400}}},
            }
        ],
        "indexes": {"by_source": {"terriermon": ["terriermon__to__galgomon", "terriermon__to__rapidmon"]}},
    }

    window.refresh(
        PetState(
            "terriermon",
            GrowthStage.ROOKIE,
            offense=202,
            discovered_species_ids=["terriermon"],
            evolution_condition_discoveries={"terriermon__to__galgomon": ["offense", "defense"]},
        ),
        Species("terriermon", "Terriermon", GrowthStage.ROOKIE),
    )

    cards = window.findChildren(stats_window.QToolButton, "EvolutionIntelCard")
    assert len(cards) == 2
    assert [card.property("transition_id") for card in cards] == [
        "terriermon__to__galgomon",
        "terriermon__to__rapidmon",
    ]
    assert "???" in cards[0].text()
    texts = [label.text() for label in window.findChildren(QLabel)]
    assert "Unknown Champion" in texts
    assert "2 of 6 clues discovered" in texts
    assert "Known conditions" in texts
    assert "Unknown clues" in texts
    assert "Galgomon" not in texts
    assert "OFF" in texts
    assert "202 / 250" in texts
    assert "No requirement" in texts
    assert "SPD" in texts
    assert "400" not in texts


def test_stats_window_evolution_card_uses_hidden_target_idle_sprite_on_top(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    sprite_path = tmp_path / "rapidmon_idle.png"
    pixmap = QPixmap(24, 24)
    pixmap.fill()
    pixmap.save(str(sprite_path))
    monkeypatch.setattr(stats_window, "resolve_artwork_path", lambda species_id: None)
    monkeypatch.setattr(stats_window, "download_artwork_for_species", lambda species_id: None)

    window = StatsWindow()
    window._species_by_id = {
        "rapidmon": Species(
            "rapidmon",
            "Rapidmon",
            GrowthStage.ULTIMATE,
            sprite_slots={"idle": str(sprite_path)},
        )
    }
    window._digivolutions = {
        "natural_evolutions": [
            {
                "id": "terriermon__to__rapidmon",
                "source_species_id": "terriermon",
                "target_species_id": "rapidmon",
                "target_name": "Rapidmon",
                "target_stage": "ultimate",
                "requirements": {"groups": {"stats": {"speed": 400}}},
            }
        ],
        "indexes": {"by_source": {"terriermon": ["terriermon__to__rapidmon"]}},
    }

    window.refresh(
        PetState("terriermon", GrowthStage.ROOKIE, discovered_species_ids=["terriermon"]),
        Species("terriermon", "Terriermon", GrowthStage.ROOKIE),
    )

    cards = window.findChildren(stats_window.QToolButton, "EvolutionIntelCard")
    assert len(cards) == 1
    assert cards[0].toolButtonStyle() == stats_window.Qt.ToolButtonStyle.ToolButtonTextUnderIcon
    assert cards[0].text().startswith("???")
    assert "?" not in cards[0].text().splitlines()
    assert not cards[0].icon().isNull()


def test_stats_window_evolution_card_animates_hidden_target_idle_sprite(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    sprite_path = tmp_path / "rapidmon_idle.png"
    _write_two_frame_sprite(sprite_path)
    monkeypatch.setattr(stats_window, "resolve_artwork_path", lambda species_id: None)
    monkeypatch.setattr(stats_window, "download_artwork_for_species", lambda species_id: None)

    window = StatsWindow()
    window._manifest = {
        "entries": {
            "terriermon": {
                "asset_path": str(sprite_path),
                "metadata": {"frame_count": 2, "fps": 10},
            },
            "rapidmon": {
                "asset_path": str(sprite_path),
                "metadata": {"frame_count": 2, "fps": 2},
            },
        }
    }
    window._species_by_id = {
        "rapidmon": Species(
            "rapidmon",
            "Rapidmon",
            GrowthStage.ULTIMATE,
            sprite_slots={"idle": str(sprite_path)},
        )
    }
    window._digivolutions = {
        "natural_evolutions": [
            {
                "id": "terriermon__to__rapidmon",
                "source_species_id": "terriermon",
                "target_species_id": "rapidmon",
                "target_name": "Rapidmon",
                "target_stage": "ultimate",
                "requirements": {"groups": {"stats": {"speed": 400}}},
            }
        ],
        "indexes": {"by_source": {"terriermon": ["terriermon__to__rapidmon"]}},
    }

    window.refresh(
        PetState("terriermon", GrowthStage.ROOKIE, discovered_species_ids=["terriermon"]),
        Species("terriermon", "Terriermon", GrowthStage.ROOKIE),
    )

    card, sprite, hidden = window._evolution_card_sprites["terriermon__to__rapidmon"]
    assert hidden is True
    assert not card.icon().isNull()
    assert window._evolution_animation_timer.interval() == 250
    assert sprite.current_frame_index == 0

    window._advance_evolution_card_sprites()

    assert sprite.current_frame_index == 1


def test_stats_window_evolution_intel_click_updates_detail(monkeypatch):
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
            },
            {
                "id": "terriermon__to__rapidmon",
                "source_species_id": "terriermon",
                "target_species_id": "rapidmon",
                "target_name": "Rapidmon",
                "target_stage": "ultimate",
                "requirements": {"groups": {"stats": {"speed": 400}}},
            }
        ],
        "indexes": {"by_source": {"terriermon": ["terriermon__to__galgomon", "terriermon__to__rapidmon"]}},
    }

    window.refresh(
        PetState(
            "terriermon",
            GrowthStage.ROOKIE,
            offense=202,
            speed=238,
            discovered_species_ids=["terriermon", "galgomon", "rapidmon"],
            evolution_condition_discoveries={
                "terriermon__to__galgomon": ["offense"],
                "terriermon__to__rapidmon": ["speed"],
            },
        ),
        Species("terriermon", "Terriermon", GrowthStage.ROOKIE),
    )

    cards = window.findChildren(stats_window.QToolButton, "EvolutionIntelCard")
    cards[1].click()
    texts = [label.text() for label in window.findChildren(QLabel)]

    assert "Rapidmon" in texts
    assert "SPD" in texts
    assert "238 / 400" in texts
    assert "Need 162" in texts


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
            evolution_condition_discoveries={"terriermon__to__galgomon": ["offense"]},
        ),
        Species("terriermon", "Terriermon", GrowthStage.ROOKIE),
    )

    texts = [label.text() for label in window.findChildren(QLabel)]
    assert "Galgomon" in texts
    assert "OFF" in texts
    assert "202 / 250" in texts
    assert "Need 48" in texts


def test_stats_window_evolution_requirements_use_compact_grid(monkeypatch):
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
                "requirements": {
                    "groups": {
                        "stats": {
                            "hp": 2000,
                            "mp": 3000,
                            "offense": 250,
                            "defense": 200,
                        }
                    }
                },
            }
        ],
        "indexes": {"by_source": {"terriermon": ["terriermon__to__galgomon"]}},
    }

    window.refresh(
        PetState(
            "terriermon",
            GrowthStage.ROOKIE,
            hp=4414,
            mp=2994,
            offense=202,
            defense=179,
            discovered_species_ids=["terriermon", "galgomon"],
            evolution_condition_discoveries={
                "terriermon__to__galgomon": ["hp", "mp", "offense", "defense"]
            },
        ),
        Species("terriermon", "Terriermon", GrowthStage.ROOKIE),
    )

    grid = window._evolution_known_conditions_grid

    assert grid is not None
    assert grid.itemAtPosition(0, 0).widget().objectName() == "EvolutionStatRequirement"
    assert grid.itemAtPosition(0, 1).widget().objectName() == "EvolutionStatRequirement"
    assert grid.itemAtPosition(1, 0).widget().objectName() == "EvolutionStatRequirement"
    assert grid.itemAtPosition(1, 1).widget().objectName() == "EvolutionStatRequirement"
