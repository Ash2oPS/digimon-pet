import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QLabel

from digimon_pet import platform as desktop_platform
from digimon_pet.app.main_window import PetWindow
from digimon_pet.domain.lifecycle import BABY_1_CHOICES
from digimon_pet.domain.models import GrowthStage
from digimon_pet.storage import debug_settings
from digimon_pet.storage import load_pet_state
from digimon_pet.storage import save_store


@pytest.fixture(autouse=True)
def default_initial_baby_choice(tmp_path, monkeypatch):
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")
    monkeypatch.setattr(save_store, "LEGACY_SAVE_PATH", tmp_path / ".local" / "pet_save.json")
    monkeypatch.setattr(debug_settings, "DEBUG_SETTINGS_PATH", tmp_path / "debug_settings.json")
    monkeypatch.setattr(
        debug_settings,
        "LEGACY_DEBUG_SETTINGS_PATH",
        tmp_path / ".local" / "debug_settings.json",
    )
    monkeypatch.setattr(
        PetWindow,
        "_get_baby_choice",
        lambda self, labels: ("Botamon", True),
    )


def test_pet_window_does_not_auto_move():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=False)

    assert not window._move_timer.isActive()


def test_debug_panel_updates_lifecycle_schedule():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=True)
    window._debug_panel._schedule_inputs["baby_seconds"].setValue(42)

    assert window._lifecycle_schedule.baby_seconds == 42


def test_debug_panel_updates_time_scale():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=True)
    window._debug_panel._time_scale_input.setValue(7)

    assert window._debug_time_scale == 7


def test_debug_panel_updates_auto_rebirth_toggle():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=True)
    window._debug_panel._auto_rebirth_checkbox.setChecked(True)

    assert window._auto_rebirth_random is True


def test_debug_panel_updates_auto_lifecycle_toggle():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=True)
    window._debug_panel._auto_lifecycle_checkbox.setChecked(True)

    assert window._auto_lifecycle_events is True


def test_debug_settings_are_saved_and_loaded(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    settings_path = tmp_path / "debug_settings.json"
    monkeypatch.setattr(debug_settings, "DEBUG_SETTINGS_PATH", settings_path)

    first = PetWindow(overlay=True, debug=True)
    first._debug_panel._time_scale_input.setValue(9)
    first._debug_panel._auto_rebirth_checkbox.setChecked(True)
    first._debug_panel._auto_lifecycle_checkbox.setChecked(True)

    second = PetWindow(overlay=True, debug=True)

    assert second._debug_time_scale == 9
    assert second._auto_rebirth_random is True
    assert second._auto_lifecycle_events is True
    assert second._debug_panel._time_scale_input.value() == 9
    assert second._debug_panel._auto_rebirth_checkbox.isChecked()
    assert second._debug_panel._auto_lifecycle_checkbox.isChecked()


def test_first_launch_prompts_for_clean_baby_choice(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    save_path = tmp_path / "pet_save.json"
    monkeypatch.setattr(save_store, "SAVE_PATH", save_path)
    monkeypatch.setattr(
        PetWindow,
        "_get_baby_choice",
        lambda self, labels: ("Punimon", True),
    )

    window = PetWindow(overlay=True, debug=True)
    loaded = load_pet_state(save_path)

    assert window._state.species_id == "punimon"
    assert window._state.stage == GrowthStage.BABY
    assert window._state.age_seconds == 0
    assert window._state.hp == 300
    assert window._state.needs_rebirth_choice is False
    assert loaded.species_id == "punimon"


def test_missing_current_save_prompts_even_when_legacy_save_exists(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    save_path = tmp_path / "pet_save.json"
    legacy_path = tmp_path / ".local" / "pet_save.json"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text(
        """
{
  "species_id": "agumon",
  "stage": "rookie"
}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(save_store, "SAVE_PATH", save_path)
    monkeypatch.setattr(save_store, "LEGACY_SAVE_PATH", legacy_path)
    monkeypatch.setattr(
        PetWindow,
        "_get_baby_choice",
        lambda self, labels: ("Punimon", True),
    )

    window = PetWindow(overlay=True, debug=True)
    loaded = load_pet_state(save_path)

    assert window._state.species_id == "punimon"
    assert window._state.stage == GrowthStage.BABY
    assert loaded.species_id == "punimon"


def test_tick_uses_debug_time_scale():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=True)
    window._debug_time_scale = 5
    window._state.age_seconds = 0

    window._tick()

    assert window._state.age_seconds == 5


def test_tick_pauses_age_and_queues_evolution_at_threshold(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=True)
    window._auto_lifecycle_events = False
    window._state.species_id = "botamon"
    window._state.stage = GrowthStage.BABY
    window._state.age_seconds = window._lifecycle_schedule.baby_seconds - 1
    window._debug_time_scale = 10

    window._tick()
    queued_age = window._state.age_seconds
    window._tick()

    assert window._pending_lifecycle_kind == "evolution"
    assert queued_age == window._lifecycle_schedule.baby_seconds
    assert window._state.age_seconds == queued_age
    assert window._state.species_id == "botamon"
    assert window._pet_widget._effect_name == "pending_evolution"


def test_click_on_pet_body_starts_lifecycle_resolution_animation(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=True)
    window._auto_lifecycle_events = False
    window._state.species_id = "botamon"
    window._state.stage = GrowthStage.BABY
    window._state.age_seconds = window._lifecycle_schedule.baby_seconds
    window._queue_or_advance_lifecycle()
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(64, 64),
        QPointF(64, 64),
        QPointF(64, 64),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    release = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(64, 64),
        QPointF(64, 64),
        QPointF(64, 64),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )

    window.mousePressEvent(press)
    window.mouseReleaseEvent(release)

    assert window._pending_lifecycle_kind is None
    assert window._lifecycle_animating is True
    assert window._pet_widget._effect_name == "evolution"


def test_click_on_event_bubble_starts_lifecycle_resolution_animation(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=True)
    window._auto_lifecycle_events = False
    window._state.species_id = "botamon"
    window._state.stage = GrowthStage.BABY
    window._state.age_seconds = window._lifecycle_schedule.baby_seconds
    window._queue_or_advance_lifecycle()
    bubble_center = window._pet_widget.event_prompt_rect().center()
    bubble_point = QPointF(bubble_center)
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        bubble_point,
        bubble_point,
        bubble_point,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    release = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        bubble_point,
        bubble_point,
        bubble_point,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )

    window.mousePressEvent(press)
    window.mouseReleaseEvent(release)

    assert window._pending_lifecycle_kind is None
    assert window._lifecycle_animating is True
    assert window._pet_widget._effect_name == "evolution"


def test_lifecycle_resolution_reveals_evolved_species_after_animation(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=True)
    window._auto_lifecycle_events = False
    window._state.species_id = "botamon"
    window._state.stage = GrowthStage.BABY
    window._state.age_seconds = window._lifecycle_schedule.baby_seconds
    window._queue_or_advance_lifecycle()
    window._confirm_pending_lifecycle()

    for _index in range(70):
        window._pet_widget._advance_effect()

    assert window._lifecycle_animating is False
    assert window._state.species_id == "koromon"
    assert window._state.stage == GrowthStage.BABY_2
    assert window._state.age_seconds == 0


def test_lifecycle_resolution_reveals_evolved_species_before_animation_finishes(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=True)
    window._auto_lifecycle_events = False
    window._state.species_id = "botamon"
    window._state.stage = GrowthStage.BABY
    window._state.age_seconds = window._lifecycle_schedule.baby_seconds
    window._queue_or_advance_lifecycle()
    window._confirm_pending_lifecycle()

    for _index in range(24):
        window._pet_widget._advance_effect()

    assert window._lifecycle_animating is True
    assert window._lifecycle_resolved_during_animation is True
    assert window._state.species_id == "koromon"
    assert window._pet_widget._effect_name == "evolution"


def test_death_pending_uses_red_pulse(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=True)
    window._auto_lifecycle_events = False
    window._state.species_id = "metalgreymon"
    window._state.stage = GrowthStage.ULTIMATE
    window._state.age_seconds = window._lifecycle_schedule.ultimate_seconds
    window._queue_or_advance_lifecycle()

    assert window._pending_lifecycle_kind == "death"
    assert window._pet_widget._effect_name == "pending_death"


def test_auto_lifecycle_resolves_without_pending_animation(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=True)
    window._auto_lifecycle_events = True
    window._state.species_id = "botamon"
    window._state.stage = GrowthStage.BABY
    window._state.age_seconds = window._lifecycle_schedule.baby_seconds

    window._queue_or_advance_lifecycle()

    assert window._pending_lifecycle_kind is None
    assert window._pet_widget._effect_name is None
    assert window._state.species_id == "koromon"


def test_secondary_event_appears_after_random_delay_without_pausing_age(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=True)
    window._state.age_seconds = 0
    window._debug_time_scale = 5
    window._secondary_event_seconds_remaining = 1

    window._tick()

    assert window._state.age_seconds == 5
    assert window._secondary_event_kind in {"meat", "dumbbell"}
    assert window._secondary_event_ttl_seconds == 30
    assert window._pet_widget.event_prompt_kind().startswith("secondary_")
    assert window._pet_widget._effect_name is None


def test_secondary_event_expires_after_thirty_seconds(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=True)
    window._show_secondary_event("meat")

    for _index in range(30):
        window._tick()

    assert window._secondary_event_kind is None
    assert window._pet_widget.event_prompt_kind() is None


def test_secondary_event_click_boosts_two_random_stats_and_clears_prompt(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=True)
    window._rng = _FixedSecondaryEventRng(["hp", "offense"])
    window._show_secondary_event("dumbbell")
    bubble_center = window._pet_widget.event_prompt_rect().center()
    bubble_point = QPointF(bubble_center)
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        bubble_point,
        bubble_point,
        bubble_point,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    release = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        bubble_point,
        bubble_point,
        bubble_point,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )

    window.mousePressEvent(press)
    window.mouseReleaseEvent(release)

    assert window._state.hp == 400
    assert window._state.offense == 40
    assert window._secondary_event_kind is None
    assert window._pet_widget.event_prompt_kind() is None
    assert window._pet_widget._stat_gain_labels == ["+100HP", "+10OFF"]


def test_secondary_event_does_not_override_pending_lifecycle(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=True)
    window._auto_lifecycle_events = False
    window._state.species_id = "botamon"
    window._state.stage = GrowthStage.BABY
    window._state.age_seconds = window._lifecycle_schedule.baby_seconds
    window._secondary_event_seconds_remaining = 1

    window._tick()

    assert window._pending_lifecycle_kind == "evolution"
    assert window._secondary_event_kind is None
    assert window._pet_widget.event_prompt_kind() == "evolution"


def test_evolution_does_not_trigger_stat_gain_text(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=True)
    window._auto_lifecycle_events = True
    window._state.species_id = "botamon"
    window._state.stage = GrowthStage.BABY
    window._state.age_seconds = window._lifecycle_schedule.baby_seconds
    window._state.hp = 1000
    window._state.mp = 1000
    window._state.offense = 100

    window._queue_or_advance_lifecycle()

    assert window._pet_widget._stat_gain_labels == []


def test_new_badge_appears_for_new_evolution_species(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=True)
    window._auto_lifecycle_events = True
    window._state.species_id = "botamon"
    window._state.stage = GrowthStage.BABY
    window._state.age_seconds = window._lifecycle_schedule.baby_seconds
    window._state.discovered_species_ids = ["botamon"]

    window._queue_or_advance_lifecycle()

    assert window._state.species_id == "koromon"
    assert window._pet_widget._new_badge_elapsed_ms > 0


def test_new_badge_does_not_appear_for_known_evolution_species(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=True)
    window._auto_lifecycle_events = True
    window._state.species_id = "botamon"
    window._state.stage = GrowthStage.BABY
    window._state.age_seconds = window._lifecycle_schedule.baby_seconds
    window._state.discovered_species_ids = ["botamon", "koromon"]
    window._pet_widget._new_badge_elapsed_ms = 0
    window._pet_widget._new_badge_timer.stop()

    window._queue_or_advance_lifecycle()

    assert window._state.species_id == "koromon"
    assert window._pet_widget._new_badge_elapsed_ms == 0


def test_new_badge_appears_for_new_rebirth_baby(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=True)
    window._state.discovered_species_ids = ["botamon"]
    window._state.needs_rebirth_choice = True

    window._choose_rebirth("yuramon")

    assert window._state.species_id == "yuramon"
    assert window._pet_widget._new_badge_elapsed_ms > 0


def test_debug_panel_updates_pet_stat():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=True)
    window._debug_panel._stat_inputs["hp"].setValue(777)

    assert window._state.hp == 777


def test_debug_panel_resets_saved_stat_progression():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=True)
    window._state.hp = 999
    window._state.mp = 888
    window._state.offense = 77
    window._state.defense = 66
    window._state.speed = 55
    window._state.brains = 44
    window._state.generation_stat_bonuses = {"hp": 12, "mp": 8}
    window._state.pending_rebirth_stat_bonuses = {"hp": 45, "speed": 7}

    window._debug_panel._reset_stats_button.click()

    assert window._state.hp == 300
    assert window._state.mp == 300
    assert window._state.offense == 30
    assert window._state.defense == 30
    assert window._state.speed == 30
    assert window._state.brains == 30
    assert window._state.generation_stat_bonuses == {}
    assert window._state.pending_rebirth_stat_bonuses == {}


def test_debug_panel_resets_collection_progression():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=True)
    window._state.species_id = "agumon"
    window._state.discovered_species_ids = ["botamon", "koromon", "agumon", "greymon"]

    window._debug_panel._reset_collection_button.click()

    assert window._state.discovered_species_ids == ["agumon"]


def test_pet_tooltip_shows_current_stats():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=False)
    window._state.hp = 777
    window._state.mp = 888
    window._state.offense = 111
    window._state.defense = 222
    window._state.speed = 333
    window._state.brains = 444
    window._refresh()

    species = window._species[window._state.species_id]
    assert window._pet_widget.toolTip() == f"{species.name}\nHP: 777\nMP: 888\nOFF: 111\nDEF: 222\nSPD: 333\nINT: 444"
    assert window._pet_widget.testAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips)


def test_auto_rebirth_chooses_random_baby_on_death():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=True)
    window._auto_lifecycle_events = True
    window._auto_rebirth_random = True
    window._state.species_id = "metalgreymon"
    window._state.stage = GrowthStage.ULTIMATE
    window._state.age_seconds = window._lifecycle_schedule.ultimate_seconds

    window._advance_lifecycle()

    assert window._state.needs_rebirth_choice is False
    assert window._state.species_id in BABY_1_CHOICES
    assert window._state.stage == GrowthStage.BABY


def test_collection_dialog_opens_from_window():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=False)
    window._open_collection()

    assert window._collection_dialog is not None
    assert window._collection_dialog.windowTitle() == "Collection"


def test_collection_dialog_groups_species_by_growth_stage():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=False)
    window._open_collection()

    headers = [
        label.text().split()[0]
        for label in window._collection_dialog.findChildren(QLabel)
        if label.objectName() == "StageHeader"
    ]
    assert headers == ["Baby1", "Baby2", "Rookie", "Champion", "Ultimate"]


def test_stats_window_opens_and_refreshes_live_values():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=False)
    window._state.age_seconds = 5400
    window._state.hp = 777
    window._state.mp = 888
    window._state.offense = 111
    window._state.defense = 222
    window._state.speed = 333
    window._state.brains = 444

    window._open_stats()

    species = window._species[window._state.species_id]
    assert window._stats_window is not None
    assert window._stats_window.windowTitle() == "Stats"
    assert window._stats_window._name_label.text() == species.name
    assert window._stats_window._labels["age"].text() == "1.5 h"
    assert window._stats_window._labels["hp"].text() == "777"
    assert window._stats_window._labels["mp"].text() == "888"
    assert window._stats_window._labels["offense"].text() == "111"
    assert window._stats_window._labels["defense"].text() == "222"
    assert window._stats_window._labels["speed"].text() == "333"
    assert window._stats_window._labels["brains"].text() == "444"

    window._state.hp = 999
    window._refresh()

    assert window._stats_window._labels["hp"].text() == "999"


def test_context_menu_only_shows_stats_collection_and_close_outside_debug():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=False)
    menu = window._build_context_menu()

    assert [action.text() for action in menu.actions() if not action.isSeparator()] == ["Stats", "Collection", "Close"]


def test_context_menu_shows_toggle_debug_when_launched_in_debug():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=True)
    menu = window._build_context_menu()

    assert [action.text() for action in menu.actions() if not action.isSeparator()] == [
        "Stats",
        "Collection",
        "Toggle Debug",
        "Close",
    ]


def test_drag_release_allows_future_context_menu():
    app = QApplication.instance() or QApplication([])
    window = PetWindow(overlay=True, debug=False)
    window._drag_offset = QPoint(8, 8)
    window._was_dragging = True
    event = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(16, 16),
        QPointF(16, 16),
        QPointF(16, 16),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )

    window.mouseReleaseEvent(event)

    assert not window._was_dragging


def test_macos_overlay_path_does_not_call_windows_styles(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(desktop_platform, "is_windows", lambda: False)
    monkeypatch.setattr(desktop_platform, "is_macos", lambda: True)
    monkeypatch.setattr(
        PetWindow,
        "_apply_windows_overlay_styles",
        lambda self: (_ for _ in ()).throw(AssertionError("windows overlay should not run")),
    )

    window = PetWindow(overlay=True, debug=False)
    window._apply_platform_overlay_styles()

    assert window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint


def test_tick_persists_advanced_age(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    save_path = tmp_path / "pet_save.json"
    monkeypatch.setattr(save_store, "SAVE_PATH", save_path)

    window = PetWindow(overlay=True, debug=True)
    window._state.species_id = "agumon"
    window._state.stage = GrowthStage.ROOKIE
    window._state.age_seconds = 123
    window._debug_time_scale = 4

    window._tick()
    loaded = load_pet_state(save_path)

    assert loaded.age_seconds == 127


class _FixedSecondaryEventRng:
    def __init__(self, stats: list[str]) -> None:
        self._stats = stats

    def sample(self, population, count):
        return self._stats[:count]

    def choice(self, population):
        return population[0]

    def randint(self, minimum: int, maximum: int) -> int:
        return minimum
