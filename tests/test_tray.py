import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from digimon_pet.app import tray as tray_module


class _WindowStub(QWidget):
    def __init__(self, *, debug: bool) -> None:
        super().__init__()
        self._debug = debug
        self.saved = False

    def toggle_debug(self) -> None:
        pass

    def save_current_state(self) -> None:
        self.saved = True


def test_create_tray_icon_returns_none_when_system_tray_unavailable(monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = QWidget()
    monkeypatch.setattr(tray_module.QSystemTrayIcon, "isSystemTrayAvailable", lambda: False)

    tray = tray_module.create_tray_icon(app, window)

    assert tray is None


def test_tray_menu_hides_toggle_debug_outside_debug_mode():
    app = QApplication.instance() or QApplication([])
    window = _WindowStub(debug=False)

    menu = tray_module._create_menu(app, window)

    assert "Toggle Debug" not in [action.text() for action in menu.actions()]


def test_tray_menu_shows_toggle_debug_in_debug_mode():
    app = QApplication.instance() or QApplication([])
    window = _WindowStub(debug=True)

    menu = tray_module._create_menu(app, window)

    assert "Toggle Debug" in [action.text() for action in menu.actions()]


def test_tray_menu_includes_restart_action():
    app = QApplication.instance() or QApplication([])
    window = _WindowStub(debug=False)

    menu = tray_module._create_menu(app, window)

    assert "Restart" in [action.text() for action in menu.actions()]


def test_restart_starts_new_process_then_saves_and_quits(monkeypatch):
    calls = []

    class _AppStub:
        def quit(self):
            calls.append("quit")

    window = _WindowStub(debug=False)
    monkeypatch.setattr(tray_module.sys, "executable", "digimon-pet.exe")
    monkeypatch.setattr(tray_module.sys, "argv", ["digimon-pet.exe", "--debug"])
    monkeypatch.setattr(
        tray_module.QProcess,
        "startDetached",
        lambda program, args: calls.append((program, args)) or True,
    )

    tray_module._restart_app(_AppStub(), window)

    assert calls == [("digimon-pet.exe", ["--debug"]), "quit"]
    assert window.saved is True
