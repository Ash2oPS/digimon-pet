import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from digimon_pet.app.main_window import PetWindow


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
