import os
import random

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QLabel, QDialogButtonBox, QInputDialog

from digimon_pet import platform as desktop_platform
from digimon_pet.app.main_window import (
    BabyChoiceDialog,
    PetWindow,
    RebirthStatAllocationDialog,
    create_trainer_nickname_dialog,
    _friend_notification_message,
    _peer_digimon_became_numemon,
    _peer_digimon_became_ultimate,
    _peer_digimon_died,
)
from digimon_pet.app import radial_menu
from digimon_pet.app.radial_menu import RadialArcDirection
from digimon_pet.app.theme import APP_QSS
from digimon_pet.app.window_positioning import offset_window_position
from digimon_pet.data import load_species
from digimon_pet.domain.fusions import FusionCatalog, FusionRecipe
from digimon_pet.domain.models import FilledIncubatorState, GrowthStage, PetState
from digimon_pet.network.presence import PeerStatus
from digimon_pet.storage import debug_settings, network_settings
from digimon_pet.storage import load_pet_state, save_pet_state
from digimon_pet.storage import save_store


@pytest.fixture(autouse=True)
def default_initial_baby_choice(tmp_path, monkeypatch):
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")
    monkeypatch.setattr(save_store, "LEGACY_SAVE_PATH", tmp_path / ".local" / "pet_save.json")
    monkeypatch.setattr(debug_settings, "DEBUG_SETTINGS_PATH", tmp_path / "debug_settings.json")
    monkeypatch.setattr(network_settings, "NETWORK_SETTINGS_PATH", tmp_path / "network_settings.json")
    monkeypatch.setattr(
        debug_settings,
        "LEGACY_DEBUG_SETTINGS_PATH",
        tmp_path / ".local" / "debug_settings.json",
    )
    monkeypatch.setattr(
        PetWindow,
        "_get_baby_choice",
        lambda self, baby_ids: ("botamon", True),
    )
    monkeypatch.setattr(
        PetWindow,
        "_get_rebirth_stat_allocation",
        lambda self: ({"hp": 15, "mp": 10, "speed": 5}, True),
    )
    monkeypatch.setattr(
        PetWindow,
        "_get_trainer_nickname",
        lambda self: ("Tai", True),
    )


def test_pet_window_does_not_auto_move():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=False)

    assert not window._move_timer.isActive()


def test_trainer_nickname_dialog_uses_app_theme():
    app = QApplication.instance() or QApplication([])

    dialog = create_trainer_nickname_dialog(None, "Tai")

    assert isinstance(dialog, QInputDialog)
    assert dialog.windowTitle() == "Trainer Nickname"
    assert dialog.labelText() == "Enter your trainer nickname:"
    assert dialog.textValue() == "Tai"
    assert dialog.styleSheet() == APP_QSS


def test_friend_death_notification_detects_only_death_transition():
    previous = PeerStatus(
        address="127.0.0.1:54545",
        online=True,
        payload={
            "protocol_version": 1,
            "trainer_nickname": "Sora",
            "species_id": "gabumon",
            "digimon_name": "Gabumon",
            "stage": "rookie",
            "current_action": "idle",
            "is_sleeping": False,
            "needs_rebirth_choice": False,
        },
    )
    current = PeerStatus(
        address="127.0.0.1:54545",
        online=True,
        payload={**previous.payload, "needs_rebirth_choice": True},
    )

    assert _peer_digimon_died(previous, current) is True
    assert _peer_digimon_died(None, current) is False
    assert _friend_notification_message(current.payload, "death") == "Sora's Gabumon just died."


def test_friend_death_notification_survives_offline_gap():
    previous = PeerStatus(
        address="127.0.0.1:54545",
        online=False,
        payload={
            "protocol_version": 1,
            "trainer_nickname": "Sora",
            "species_id": "gabumon",
            "digimon_name": "Gabumon",
            "stage": "rookie",
            "current_action": "idle",
            "is_sleeping": False,
            "needs_rebirth_choice": False,
        },
    )
    current = PeerStatus(
        address="127.0.0.1:54545",
        online=True,
        payload={**previous.payload, "needs_rebirth_choice": True},
    )

    assert _peer_digimon_died(previous, current) is True


def test_friend_ultimate_notification_detects_only_stage_transition():
    previous = PeerStatus(
        address="127.0.0.1:54545",
        online=True,
        payload={
            "protocol_version": 1,
            "trainer_nickname": "Matt",
            "species_id": "metalgreymon",
            "digimon_name": "MetalGreymon",
            "stage": "champion",
            "current_action": "idle",
            "is_sleeping": False,
            "needs_rebirth_choice": False,
        },
    )
    current = PeerStatus(
        address="127.0.0.1:54545",
        online=True,
        payload={**previous.payload, "stage": "ultimate"},
    )

    assert _peer_digimon_became_ultimate(previous, current) is True
    assert _peer_digimon_became_ultimate(None, current) is False
    assert _friend_notification_message(current.payload, "ultimate") == "Matt's MetalGreymon just became an Ultimate."


def test_friend_numemon_notification_detects_only_species_transition():
    previous = PeerStatus(
        address="127.0.0.1:54545",
        online=False,
        payload={
            "protocol_version": 1,
            "trainer_nickname": "Mimi",
            "species_id": "agumon",
            "digimon_name": "Agumon",
            "stage": "rookie",
            "current_action": "idle",
            "is_sleeping": False,
            "needs_rebirth_choice": False,
        },
    )
    current = PeerStatus(
        address="127.0.0.1:54545",
        online=True,
        payload={**previous.payload, "species_id": "numemon", "digimon_name": "Numemon", "stage": "champion"},
    )

    assert _peer_digimon_became_numemon(previous, current) is True
    assert _peer_digimon_became_numemon(None, current) is False
    assert _friend_notification_message(current.payload, "numemon") == "Mimi's Digimon just became Numemon."


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


def test_debug_panel_has_item_manager_button():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=True)

    assert window._debug_panel._item_manager_button.text() == "Item Manager"


def test_existing_save_queues_lifecycle_event_on_startup(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    save_path = tmp_path / "pet_save.json"
    monkeypatch.setattr(save_store, "SAVE_PATH", save_path)
    save_pet_state(
        PetState(
            species_id="gummymon",
            stage=GrowthStage.BABY_2,
            age_seconds=30 * 60,
            hp=3839,
            mp=2722,
            speed=216,
        )
    )

    window = PetWindow(overlay=True, debug=True)

    assert window._pending_lifecycle_kind == "evolution"
    assert window._pet_widget._effect_name == "pending_evolution"


def test_item_manager_opens_only_in_debug_mode():
    app = QApplication.instance() or QApplication([])

    debug_window = PetWindow(overlay=True, debug=True)
    normal_window = PetWindow(overlay=True, debug=False)

    debug_window._open_item_manager()
    normal_window._open_item_manager()

    assert debug_window._item_manager_window is not None
    assert debug_window._item_manager_window.isWindow() is True
    assert normal_window._item_manager_window is None


def test_debug_panel_item_manager_button_opens_window():
    app = QApplication.instance() or QApplication([])
    window = PetWindow(overlay=True, debug=True)

    window._debug_panel._item_manager_button.click()

    assert window._item_manager_window is not None
    assert window._item_manager_window.isVisible()


def test_debug_panel_item_manager_button_positions_window_near_debug_panel():
    app = QApplication.instance() or QApplication([])
    window = PetWindow(overlay=True, debug=True)
    window.setGeometry(20, 20, 128, 128)
    window._debug_panel.setGeometry(240, 80, 460, 680)
    window._debug_panel.show()

    window._debug_panel._item_manager_button.click()

    assert window._item_manager_window is not None
    screen = QApplication.primaryScreen().availableGeometry()
    expected = offset_window_position(
        window._debug_panel.frameGeometry(),
        window._item_manager_window.size(),
        screen,
    )
    assert window._item_manager_window.pos() == expected


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
        lambda self, baby_ids: ("punimon", True),
    )

    window = PetWindow(overlay=True, debug=True)
    loaded = load_pet_state(save_path)

    assert window._state.species_id == "punimon"
    assert window._state.stage == GrowthStage.BABY
    assert window._state.age_seconds == 0
    assert window._state.hp == 300
    assert window._state.needs_rebirth_choice is False
    assert loaded.species_id == "punimon"


def test_baby_choice_prompt_uses_all_catalog_baby_1_species(monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = PetWindow(overlay=True, debug=True)
    window._species = dict(window._species)
    window._species["snowbotamon"] = window._species["botamon"].__class__(
        "snowbotamon",
        "SnowBotamon",
        GrowthStage.BABY,
    )
    captured_baby_ids = []

    def choose_snowbotamon(baby_ids):
        captured_baby_ids.extend(baby_ids)
        return "snowbotamon", True

    monkeypatch.setattr(window, "_get_baby_choice", choose_snowbotamon)

    assert window._prompt_baby_choice() == "snowbotamon"
    assert "snowbotamon" in captured_baby_ids


def test_baby_choice_dialog_returns_selected_baby_id():
    app = QApplication.instance() or QApplication([])
    species = load_species()
    dialog = BabyChoiceDialog(
        ["botamon", "punimon"],
        species,
        ["botamon"],
    )

    dialog._buttons["punimon"].click()

    assert dialog.selected_baby_id() == "punimon"
    assert dialog._buttons["botamon"].text() == "Botamon"
    assert dialog._buttons["punimon"].text() == "???"


def test_baby_choice_dialog_has_no_cancel_button():
    app = QApplication.instance() or QApplication([])
    species = load_species()
    dialog = BabyChoiceDialog(
        ["botamon", "punimon"],
        species,
        ["botamon"],
    )
    buttons = dialog.findChild(QDialogButtonBox)

    assert buttons is not None
    assert buttons.button(QDialogButtonBox.StandardButton.Ok) is not None
    assert buttons.button(QDialogButtonBox.StandardButton.Cancel) is None


def test_baby_choice_dialog_cannot_be_rejected_without_choice():
    app = QApplication.instance() or QApplication([])
    species = load_species()
    dialog = BabyChoiceDialog(
        ["botamon", "punimon"],
        species,
        ["botamon"],
    )

    dialog.show()
    dialog.reject()

    assert dialog.isVisible()


def test_rebirth_stat_allocation_dialog_requires_complete_allocation():
    app = QApplication.instance() or QApplication([])
    state = PetState(
        "numemon",
        GrowthStage.CHAMPION,
        generation_stat_bonuses={"hp": 12},
        pending_rebirth_stat_source_stats={
            "hp": 300,
            "mp": 400,
            "offense": 50,
            "defense": 60,
            "speed": 70,
            "brains": 80,
        },
    )
    dialog = RebirthStatAllocationDialog(state)
    buttons = dialog.findChild(QDialogButtonBox)
    ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)

    assert ok_button.isEnabled() is False

    for _index in range(3):
        dialog._adjust("hp", 5)
    for _index in range(2):
        dialog._adjust("mp", 5)
    dialog._adjust("speed", 5)

    assert dialog.selected_allocations() == {
        "hp": 15,
        "mp": 10,
        "offense": 0,
        "defense": 0,
        "speed": 5,
        "brains": 0,
    }
    assert dialog._bonus_labels["hp"].text() == "+45"
    assert dialog._after_labels["hp"].text() == "357"
    assert ok_button.isEnabled() is True


def test_ultimate_rebirth_stat_allocation_dialog_requires_forty_percent():
    app = QApplication.instance() or QApplication([])
    state = PetState(
        "metalgreymon",
        GrowthStage.ULTIMATE,
        pending_rebirth_stat_source_stats={
            "hp": 300,
            "mp": 400,
            "offense": 50,
            "defense": 60,
            "speed": 70,
            "brains": 80,
        },
    )
    dialog = RebirthStatAllocationDialog(state)
    buttons = dialog.findChild(QDialogButtonBox)
    ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)

    for _index in range(4):
        dialog._adjust("hp", 5)
    for _index in range(3):
        dialog._adjust("mp", 5)
    dialog._adjust("speed", 5)

    assert dialog.selected_allocations()["hp"] == 20
    assert dialog.selected_allocations()["mp"] == 15
    assert dialog.selected_allocations()["speed"] == 5
    assert dialog._bonus_labels["hp"].text() == "+60"
    assert ok_button.isEnabled() is True


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
        lambda self, baby_ids: ("punimon", True),
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


def test_normal_mode_ignores_saved_debug_time_scale(tmp_path):
    app = QApplication.instance() or QApplication([])
    debug_settings.save_debug_settings(
        debug_settings.DebugSettings(time_scale=1000),
        tmp_path / "debug_settings.json",
    )

    window = PetWindow(overlay=True, debug=False)
    window._state.age_seconds = 0

    window._tick()

    assert window._debug_time_scale == 1
    assert window._state.age_seconds == 1


def test_tick_increases_random_hp_or_mp_by_ten_each_elapsed_minute():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=True)
    window._rng = _FixedChoiceRng("mp")
    window._state.age_seconds = 59

    window._tick()

    assert window._state.mp == 310


def test_tick_increases_random_non_resource_stat_by_one_each_elapsed_minute():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=True)
    window._rng = _FixedChoiceRng("offense")
    window._state.age_seconds = 59

    window._tick()

    assert window._state.offense == 31


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


def test_tick_evolves_baby_2_to_nearest_candidate_when_requirements_are_missed(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=True)
    window._rng = random.Random(1)
    window._auto_lifecycle_events = False
    window._state.species_id = "gummymon"
    window._state.stage = GrowthStage.BABY_2
    window._state.age_seconds = window._lifecycle_schedule.baby_2_seconds - 1
    window._state.hp = 3839
    window._state.mp = 2722
    window._state.speed = 216

    window._tick()

    assert window._pending_lifecycle_kind == "evolution"
    window._confirm_pending_lifecycle()
    for _index in range(70):
        window._pet_widget._advance_effect()

    assert window._state.species_id == "terriermon"
    assert window._state.stage == GrowthStage.ROOKIE
    assert window._state.age_seconds == 0


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


def test_natural_death_can_chain_into_bakemon_evolution_without_rebirth_choice(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    def fail_baby_choice(self, baby_ids):
        raise AssertionError("Bakemon death evolution should not ask for a baby choice")

    window = PetWindow(overlay=True, debug=True)
    monkeypatch.setattr(PetWindow, "_get_baby_choice", fail_baby_choice)
    monkeypatch.setattr(window, "_roll_natural_death_evolution", lambda: True)
    window._auto_lifecycle_events = False
    window._state.species_id = "metalgreymon"
    window._state.stage = GrowthStage.ULTIMATE
    window._state.age_seconds = window._lifecycle_schedule.ultimate_seconds
    window._state.discovered_species_ids = ["metalgreymon"]

    window._queue_or_advance_lifecycle()
    window._confirm_pending_lifecycle()
    for _index in range(28):
        window._pet_widget._advance_effect()

    assert window._lifecycle_animating is True
    assert window._pet_widget._effect_name == "evolution"
    assert window._state.species_id == "metalgreymon"
    assert window._state.needs_rebirth_choice is True

    for _index in range(24):
        window._pet_widget._advance_effect()

    assert window._state.species_id == "bakemon"
    assert window._state.stage == GrowthStage.CHAMPION
    assert window._state.needs_rebirth_choice is False
    assert window._state.pending_rebirth_stat_bonuses == {}
    assert "bakemon" in window._state.discovered_species_ids
    assert window._pet_widget._new_badge_elapsed_ms > 0


def test_sudden_death_item_does_not_chain_into_bakemon(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=False)
    window._auto_rebirth_random = True
    monkeypatch.setattr(
        window,
        "_roll_natural_death_evolution",
        lambda: (_ for _ in ()).throw(AssertionError("Sudden death should not roll Bakemon")),
    )
    window._state.species_id = "agumon"
    window._state.stage = GrowthStage.ROOKIE
    window._state.inventory = {"digigun": 1}

    window._use_inventory_item("digigun")
    window._confirm_pending_lifecycle()
    for _index in range(28):
        window._pet_widget._advance_effect()

    assert window._pet_widget._effect_name is None
    assert window._state.stage == GrowthStage.BABY
    assert window._state.species_id != "bakemon"
    assert window._state.needs_rebirth_choice is False


def test_manual_rebirth_prompts_stat_allocation_before_baby_choice(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")
    calls = []

    window = PetWindow(overlay=True, debug=True)
    window._auto_lifecycle_events = True
    window._auto_rebirth_random = False
    window._roll_natural_death_evolution = lambda: False
    window._state.species_id = "metalgreymon"
    window._state.stage = GrowthStage.ULTIMATE
    window._state.age_seconds = window._lifecycle_schedule.ultimate_seconds
    window._state.hp = 300
    window._state.mp = 400
    window._state.speed = 70

    def allocate():
        calls.append(("allocation", dict(window._state.pending_rebirth_stat_source_stats)))
        return {"hp": 20, "mp": 15, "speed": 5}, True

    def choose_baby(baby_ids):
        calls.append(("baby", dict(window._state.pending_rebirth_stat_bonuses)))
        return "botamon", True

    monkeypatch.setattr(window, "_get_rebirth_stat_allocation", allocate)
    monkeypatch.setattr(window, "_get_baby_choice", choose_baby)

    window._advance_lifecycle()

    assert calls == [
        (
            "allocation",
            {
                "hp": 300,
                "mp": 400,
                "offense": 30,
                "defense": 30,
                "speed": 70,
                "brains": 30,
            },
        ),
        ("baby", {"hp": 60, "mp": 60, "speed": 3}),
    ]
    assert window._state.species_id == "botamon"
    assert window._state.hp == 360
    assert window._state.mp == 360
    assert window._state.speed == 33


def test_manual_item_death_uses_same_rebirth_stat_allocation_flow(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")
    calls = []

    window = PetWindow(overlay=True, debug=False)
    window._auto_rebirth_random = False
    window._state.species_id = "agumon"
    window._state.stage = GrowthStage.ROOKIE
    window._state.hp = 300
    window._state.mp = 400
    window._state.speed = 70
    window._state.inventory = {"digigun": 1}

    def allocate():
        calls.append(("allocation", dict(window._state.pending_rebirth_stat_source_stats)))
        return {"hp": 15, "mp": 10, "speed": 5}, True

    def choose_baby(baby_ids):
        calls.append(("baby", dict(window._state.pending_rebirth_stat_bonuses)))
        return "botamon", True

    monkeypatch.setattr(window, "_get_rebirth_stat_allocation", allocate)
    monkeypatch.setattr(window, "_get_baby_choice", choose_baby)

    window._use_inventory_item("digigun")
    window._confirm_pending_lifecycle()
    for _index in range(28):
        window._pet_widget._advance_effect()

    assert calls == [
        (
            "allocation",
            {
                "hp": 300,
                "mp": 400,
                "offense": 30,
                "defense": 30,
                "speed": 70,
                "brains": 30,
            },
        ),
        ("baby", {"hp": 45, "mp": 40, "speed": 3}),
    ]
    assert window._state.species_id == "botamon"
    assert window._state.needs_rebirth_choice is False


def test_filled_incubator_fusion_consumes_entry_and_discovers_result():
    app = QApplication.instance() or QApplication([])
    save_store.save_pet_state(
        PetState(
            "agumon",
            GrowthStage.ROOKIE,
            filled_incubators=[
                FilledIncubatorState(
                    id="filled-1",
                    species_id="gabumon",
                    stage=GrowthStage.ROOKIE,
                )
            ],
        )
    )
    window = PetWindow(overlay=True, debug=False)
    window._fusion_catalog = FusionCatalog(
        recipes=(
            FusionRecipe(
                source_species_ids=("gabumon", "agumon"),
                target_species_id="greymon",
            ),
        )
    )

    window._use_inventory_item("filled_incubator:filled-1")
    window._resolve_lifecycle_now()

    assert window._state.species_id == "greymon"
    assert window._state.stage == GrowthStage.CHAMPION
    assert window._state.filled_incubators == []
    assert "greymon" in window._state.discovered_species_ids


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
    assert window._secondary_event_kind in {"meat", "dumbbell", "item"}
    assert window._secondary_event_ttl_seconds == 30
    assert window._pet_widget.event_prompt_kind().startswith("secondary_")
    assert window._pet_widget._effect_name is None


def test_secondary_event_appearance_plays_walk_animation(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=True)

    window._show_secondary_event("meat")

    assert window._state.current_action == "walk"


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
    assert len(window._state.evolution_condition_discoveries) == 1
    transition_id, clues = next(iter(window._state.evolution_condition_discoveries.items()))
    assert transition_id
    assert clues == ["hp"]
    assert window._secondary_event_kind is None
    assert window._pet_widget.event_prompt_kind() is None
    assert window._pet_widget._stat_gain_labels == ["+100 HP", "+10 OFF"]


def test_secondary_event_timer_loads_from_save(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    save_path = tmp_path / "pet_save.json"
    monkeypatch.setattr(save_store, "SAVE_PATH", save_path)
    save_pet_state(
        PetState(
            "agumon",
            GrowthStage.ROOKIE,
            secondary_event_kind="meat",
            secondary_event_ttl_seconds=12,
            secondary_event_seconds_remaining=0,
        ),
        save_path,
    )

    window = PetWindow(overlay=True, debug=True)

    assert window._secondary_event_kind == "meat"
    assert window._secondary_event_ttl_seconds == 12
    assert window._secondary_event_seconds_remaining == 0
    assert window._pet_widget.event_prompt_kind() == "secondary_meat"


def test_secondary_event_timer_is_saved_on_quit(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    save_path = tmp_path / "pet_save.json"
    monkeypatch.setattr(save_store, "SAVE_PATH", save_path)

    window = PetWindow(overlay=True, debug=True)
    window._secondary_event_seconds_remaining = 42

    window.save_current_state()
    loaded = load_pet_state(save_path)

    assert loaded.secondary_event_kind is None
    assert loaded.secondary_event_seconds_remaining == 42


def test_window_position_is_saved_on_quit(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    save_path = tmp_path / "pet_save.json"
    monkeypatch.setattr(save_store, "SAVE_PATH", save_path)

    window = PetWindow(overlay=True, debug=True)
    window.move(111, 122)

    window.save_current_state()
    loaded = load_pet_state(save_path)
    screen_name = QApplication.primaryScreen().name().strip()

    assert loaded.window_x == 111
    assert loaded.window_y == 122
    assert loaded.window_screen_name == (screen_name or None)
    assert loaded.window_screen_offset_x is not None
    assert loaded.window_screen_offset_y is not None


def test_window_position_loads_from_save(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    save_path = tmp_path / "pet_save.json"
    monkeypatch.setattr(save_store, "SAVE_PATH", save_path)
    save_pet_state(
        PetState(
            "agumon",
            GrowthStage.ROOKIE,
            window_x=37,
            window_y=45,
        ),
        save_path,
    )

    window = PetWindow(overlay=True, debug=True)
    window.show()
    app.processEvents()

    assert window.pos() == QPoint(37, 45)


def test_pet_scale_loads_from_save(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    save_path = tmp_path / "pet_save.json"
    monkeypatch.setattr(save_store, "SAVE_PATH", save_path)
    save_pet_state(
        PetState(
            "agumon",
            GrowthStage.ROOKIE,
            pet_scale_percent=150,
        ),
        save_path,
    )

    window = PetWindow(overlay=True, debug=True)

    assert window.pet_scale_percent() == 150
    assert window.size().width() == 192
    assert window._pet_widget.size().width() == 192


def test_changing_pet_scale_resizes_only_pet_window_and_saves(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    save_path = tmp_path / "pet_save.json"
    monkeypatch.setattr(save_store, "SAVE_PATH", save_path)

    window = PetWindow(overlay=True, debug=True)
    window.move(200, 300)
    window._open_stats()
    stats_size_before = window._stats_window.size()

    window.set_pet_scale_percent(50)
    loaded = load_pet_state(save_path)

    assert window.size().width() == 64
    assert window._pet_widget.size().width() == 64
    assert window._stats_window.size() == stats_size_before
    assert loaded.pet_scale_percent == 50


def test_window_position_restore_uses_full_screen_geometry_below_taskbar(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    save_path = tmp_path / "pet_save.json"
    monkeypatch.setattr(save_store, "SAVE_PATH", save_path)
    save_pet_state(
        PetState(
            "agumon",
            GrowthStage.ROOKIE,
            window_x=1200,
            window_y=951,
            window_screen_name="Primary",
        ),
        save_path,
    )

    class _ScreenStub:
        def name(self):
            return "Primary"

        def geometry(self):
            return QRect(0, 0, 1920, 1080)

        def availableGeometry(self):
            return QRect(0, 0, 1920, 1000)

    window = PetWindow(overlay=True, debug=True)
    monkeypatch.setattr(window, "_saved_screen", lambda: _ScreenStub())

    assert window._restore_saved_position() is True
    assert window.pos() == QPoint(1200, 951)


def test_secondary_event_click_uses_larger_ultimate_boosts(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=True)
    window._state.stage = GrowthStage.ULTIMATE
    window._rng = _FixedSecondaryEventRng(["hp", "offense"])
    window._show_secondary_event("dumbbell")

    window._claim_secondary_event()

    assert window._state.hp == 420
    assert window._state.offense == 42
    assert window._pet_widget._stat_gain_labels == ["+120 HP", "+12 OFF"]


@pytest.mark.parametrize(
    ("event_kind", "expected_action"),
    [
        ("meat", "eat"),
        ("dumbbell", "train"),
        ("item", "happy"),
    ],
)
def test_secondary_event_click_plays_matching_animation(event_kind, expected_action, tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=True)
    window._rng = _FixedSecondaryEventRng(["hp", "offense"])
    window._show_secondary_event(event_kind)

    window._claim_secondary_event()

    assert window._state.current_action == expected_action


def test_one_in_three_secondary_events_is_item(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=True)
    window._rng = _SecondaryItemEventRng(["hp", "offense"])

    window._show_secondary_event()

    assert window._secondary_event_kind == "item"
    assert window._pet_widget.event_prompt_kind() == "secondary_item"


def test_secondary_item_event_boosts_stats_and_grants_weighted_item(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=True)
    window._rng = _SecondaryItemEventRng(["hp", "offense"])
    window._show_secondary_event("item")

    window._claim_secondary_event()

    assert window._state.hp == 400
    assert window._state.offense == 40
    assert window._state.inventory["monzaemon_head"] == 1
    assert window._pet_widget._stat_gain_labels == ["+100 HP", "+10 OFF"]
    assert window._pet_widget._stat_gain_item_icon_path == "assets/items/monzaemon_head.png"
    assert window._pet_widget._stat_gain_item_name == "Monzaemon's Head"


def test_auto_clicker_item_is_consumed_and_enables_auto_secondary_events(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")
    monkeypatch.setattr("digimon_pet.domain.items.time.time", lambda: 1000.0)

    window = PetWindow(overlay=True, debug=True)
    window._state.inventory = {"auto_clicker": 1}

    window._use_inventory_item("auto_clicker")

    assert window._state.inventory == {}
    assert window._state.auto_clicker_expires_at == 4600


def test_auto_clicker_claims_secondary_event_without_showing_prompt(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")
    monkeypatch.setattr("digimon_pet.app.main_window.time.time", lambda: 1000.0)

    window = PetWindow(overlay=True, debug=True)
    window._rng = _FixedSecondaryEventRng(["hp", "offense"])
    window._state.auto_clicker_expires_at = 4600
    window._secondary_event_seconds_remaining = 1

    window._tick()

    assert window._state.hp == 400
    assert window._state.offense == 40
    assert window._secondary_event_kind is None
    assert window._pet_widget.event_prompt_kind() is None
    assert window._pet_widget._stat_gain_labels == ["+100 HP", "+10 OFF"]


def test_auto_clicker_secondary_event_animation_stays_visible_longer(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")
    monkeypatch.setattr("digimon_pet.app.main_window.time.time", lambda: 1000.0)

    window = PetWindow(overlay=True, debug=True)
    window._rng = _FixedSecondaryEventRng(["hp", "offense"])
    window._state.auto_clicker_expires_at = 4600
    window._secondary_event_seconds_remaining = 1

    window._tick()
    window._tick()
    window._tick()
    window._tick()

    assert window._state.current_action == "happy"


def test_auto_clicker_expiration_uses_real_elapsed_time_after_restart(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    save_path = tmp_path / "pet_save.json"
    monkeypatch.setattr(save_store, "SAVE_PATH", save_path)
    save_pet_state(
        PetState(
            "agumon",
            GrowthStage.ROOKIE,
            auto_clicker_expires_at=4600,
        ),
        save_path,
    )
    monkeypatch.setattr("digimon_pet.app.main_window.time.time", lambda: 4700.0)

    window = PetWindow(overlay=True, debug=True)
    window._rng = _FixedSecondaryEventRng(["hp", "offense"])
    window._secondary_event_seconds_remaining = 1

    window._tick()

    assert window._state.auto_clicker_expires_at is None
    assert window._state.hp == 300
    assert window._secondary_event_kind in {"meat", "dumbbell", "item"}
    assert window._pet_widget.event_prompt_kind().startswith("secondary_")


def test_consumable_item_without_lifecycle_event_plays_eat_animation(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=True)
    window._state.inventory = {"digifish": 1}

    window._use_inventory_item("digifish")

    assert window._state.current_action == "eat"


def test_action_animation_survives_first_tick_after_play(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=True)
    window._state.inventory = {"digifish": 1}
    window._use_inventory_item("digifish")

    window._tick()

    assert window._state.current_action == "eat"


def test_passive_ultimate_growth_doubles_every_third_minute(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=True)
    window._state.stage = GrowthStage.ULTIMATE
    window._state.age_seconds = 3 * 60
    window._rng = _FixedChoiceRng("hp")

    window._apply_passive_stat_growth(previous_age_seconds=0)

    assert window._state.hp == 340


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


def test_natural_death_skips_bakemon_roll_after_bakemon_in_current_lineage(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=True)
    window._auto_lifecycle_events = True
    window._auto_rebirth_random = True
    monkeypatch.setattr(
        window._rng,
        "random",
        lambda: (_ for _ in ()).throw(AssertionError("Bakemon should not roll twice in one lineage")),
    )
    window._state.species_id = "metalgreymon"
    window._state.stage = GrowthStage.ULTIMATE
    window._state.age_seconds = window._lifecycle_schedule.ultimate_seconds
    window._state.bakemon_lineage_used = True

    window._advance_lifecycle()

    assert window._state.stage == GrowthStage.BABY
    assert window._state.species_id != "bakemon"


def test_natural_death_skips_bakemon_roll_during_generation_cooldown(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=True)
    window._auto_lifecycle_events = True
    window._auto_rebirth_random = True
    monkeypatch.setattr(
        window._rng,
        "random",
        lambda: (_ for _ in ()).throw(AssertionError("Bakemon should not roll during cooldown")),
    )
    window._state.species_id = "metalgreymon"
    window._state.stage = GrowthStage.ULTIMATE
    window._state.age_seconds = window._lifecycle_schedule.ultimate_seconds
    window._state.bakemon_generation_cooldown = 1

    window._advance_lifecycle()

    assert window._state.stage == GrowthStage.BABY
    assert window._state.species_id != "bakemon"


def test_bakemon_death_evolution_sets_lineage_and_generation_cooldown(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")

    window = PetWindow(overlay=True, debug=True)
    monkeypatch.setattr(window, "_roll_natural_death_evolution", lambda: True)
    window._auto_lifecycle_events = True
    window._auto_rebirth_random = True
    window._state.species_id = "metalgreymon"
    window._state.stage = GrowthStage.ULTIMATE
    window._state.age_seconds = window._lifecycle_schedule.ultimate_seconds

    window._advance_lifecycle()

    assert window._state.species_id == "bakemon"
    assert window._state.bakemon_lineage_used is True
    assert window._state.bakemon_generation_cooldown == 4


def test_auto_rebirth_chooses_random_baby_on_death():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=True)
    window._auto_lifecycle_events = True
    window._auto_rebirth_random = True
    window._roll_natural_death_evolution = lambda: False
    window._state.species_id = "metalgreymon"
    window._state.stage = GrowthStage.ULTIMATE
    window._state.age_seconds = window._lifecycle_schedule.ultimate_seconds

    window._advance_lifecycle()

    assert window._state.needs_rebirth_choice is False
    assert window._state.stage == GrowthStage.BABY


def test_auto_rebirth_respects_successful_bakemon_death_evolution():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=True)
    window._auto_lifecycle_events = True
    window._auto_rebirth_random = True
    window._roll_natural_death_evolution = lambda: True
    window._state.species_id = "metalgreymon"
    window._state.stage = GrowthStage.ULTIMATE
    window._state.age_seconds = window._lifecycle_schedule.ultimate_seconds

    window._advance_lifecycle()

    assert window._state.needs_rebirth_choice is False
    assert window._state.species_id == "bakemon"
    assert window._state.stage == GrowthStage.CHAMPION


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
    assert "1 h 30 min" in window._stats_window._summary_label.text()
    assert window._stats_window._labels["hp"].text() == "777"
    assert window._stats_window._labels["mp"].text() == "888"
    assert window._stats_window._labels["offense"].text() == "111"
    assert window._stats_window._labels["defense"].text() == "222"
    assert window._stats_window._labels["speed"].text() == "333"
    assert window._stats_window._labels["brains"].text() == "444"

    window._state.hp = 999
    window._refresh()

    assert window._stats_window._labels["hp"].text() == "999"


def test_radial_menu_shows_stats_network_collection_inventory_and_close():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=False)
    menu = window._ensure_radial_menu()

    assert [button.toolTip() for button in menu.action_buttons()] == [
        "Stats",
        "Collection",
        "Inventory",
        "Network",
        "Close",
    ]


def test_radial_menu_buttons_do_not_take_focus_on_open():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=False)
    menu = window._ensure_radial_menu()

    assert all(
        button.focusPolicy() == Qt.FocusPolicy.NoFocus
        for button in menu.action_buttons()
    )


def test_radial_menu_keeps_same_pet_actions_in_debug():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=True)
    menu = window._ensure_radial_menu()

    assert [button.toolTip() for button in menu.action_buttons()] == [
        "Stats",
        "Collection",
        "Inventory",
        "Network",
        "Close",
    ]


def test_network_button_opens_network_window_and_closes_menu(monkeypatch):
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=False)
    opened = []
    monkeypatch.setattr(window, "_open_network_window", lambda: opened.append("network"))
    menu = window._ensure_radial_menu()
    menu.show()

    menu.button_for_action("network").click()

    assert opened == ["network"]
    assert not menu.isVisible()


def test_network_radial_icon_uses_simple_earth_svg():
    assert hasattr(radial_menu, "_NETWORK_ICON_SVG")
    assert "<svg" in radial_menu._NETWORK_ICON_SVG
    assert 'id="ocean"' in radial_menu._NETWORK_ICON_SVG
    assert 'id="land"' in radial_menu._NETWORK_ICON_SVG


def test_radial_menu_selects_arc_away_from_screen_edges():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=False)
    menu = window._ensure_radial_menu()
    screen = QRect(0, 0, 800, 600)

    assert menu.arc_direction_for(QPoint(600, 500), screen) == RadialArcDirection.TOP_LEFT
    assert menu.arc_direction_for(QPoint(200, 500), screen) == RadialArcDirection.TOP_RIGHT
    assert menu.arc_direction_for(QPoint(600, 100), screen) == RadialArcDirection.BOTTOM_LEFT
    assert menu.arc_direction_for(QPoint(200, 100), screen) == RadialArcDirection.BOTTOM_RIGHT


def test_radial_menu_uses_quarter_circle_angles_for_each_arc():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=False)
    menu = window._ensure_radial_menu()

    assert menu._angles_for(RadialArcDirection.TOP_LEFT, 4) == [
        270.0,
        240.0,
        210.0,
        180.0,
    ]
    assert menu._angles_for(RadialArcDirection.TOP_RIGHT, 4) == [
        270.0,
        300.0,
        330.0,
        360.0,
    ]
    assert menu._angles_for(RadialArcDirection.BOTTOM_LEFT, 4) == [
        90.0,
        120.0,
        150.0,
        180.0,
    ]
    assert menu._angles_for(RadialArcDirection.BOTTOM_RIGHT, 4) == [
        90.0,
        60.0,
        30.0,
        0.0,
    ]


def test_radial_menu_spaces_angles_equally_for_any_button_count():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=False)
    menu = window._ensure_radial_menu()

    assert menu._angles_for(RadialArcDirection.BOTTOM_LEFT, 5) == [
        90.0,
        112.5,
        135.0,
        157.5,
        180.0,
    ]


def test_radial_menu_leaves_more_space_between_buttons():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=False)
    menu = window._ensure_radial_menu()
    positions = menu._positions_for(RadialArcDirection.TOP_LEFT, QPoint(100, 100))
    centers = [
        position + QPoint(menu._BUTTON_SIZE // 2, menu._BUTTON_SIZE // 2)
        for position in positions
    ]

    gaps = [
        round(((left.x() - right.x()) ** 2 + (left.y() - right.y()) ** 2) ** 0.5)
        - menu._BUTTON_SIZE
        for left, right in zip(centers, centers[1:])
    ]

    assert min(gaps) >= 20


def test_inventory_button_closes_menu_without_opening_panel():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=False)
    menu = window._ensure_radial_menu()
    menu.show()

    menu.button_for_action("inventory").click()

    assert not menu.isVisible()


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


def test_tick_defers_advanced_age_save_until_scheduled_flush(tmp_path, monkeypatch):
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

    assert loaded.age_seconds != 127
    assert window._save_timer.isActive()

    window._flush_scheduled_save()
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


class _FixedChoiceRng(_FixedSecondaryEventRng):
    def __init__(self, choice_value: str) -> None:
        super().__init__([choice_value])
        self._choice_value = choice_value

    def choice(self, population):
        return self._choice_value


class _SecondaryItemEventRng(_FixedSecondaryEventRng):
    def randint(self, minimum: int, maximum: int) -> int:
        if minimum == 1 and maximum == 3:
            return 1
        return minimum
