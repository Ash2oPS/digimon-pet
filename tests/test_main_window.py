import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QLabel

from digimon_pet.app.main_window import PetWindow
from digimon_pet.domain.models import GrowthStage
from digimon_pet.storage import load_pet_state
from digimon_pet.storage import save_store


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


def test_tick_uses_debug_time_scale():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=True)
    window._debug_time_scale = 5
    window._state.age_seconds = 0

    window._tick()

    assert window._state.age_seconds == 5


def test_debug_panel_updates_pet_stat():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=True)
    window._debug_panel._stat_inputs["hp"].setValue(777)

    assert window._state.hp == 777


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
