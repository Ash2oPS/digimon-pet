import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from digimon_pet.app import tray as tray_module


class _WindowStub(QWidget):
    def __init__(self, *, debug: bool) -> None:
        super().__init__()
        self._debug = debug
        self.saved = False
        self.scale_percent = 100

    def toggle_debug(self) -> None:
        pass

    def save_current_state(self) -> None:
        self.saved = True

    def pet_scale_percent(self) -> int:
        return self.scale_percent

    def set_pet_scale_percent(self, percent: int) -> None:
        self.scale_percent = int(percent)


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


def test_tray_menu_includes_checkable_pet_scale_actions():
    app = QApplication.instance() or QApplication([])
    window = _WindowStub(debug=False)
    window.scale_percent = 125

    menu = tray_module._create_menu(app, window)
    scale_menu = next(action.menu() for action in menu.actions() if action.text() == "Pet Scale")
    actions = scale_menu.actions()

    assert [action.text() for action in actions] == ["50%", "75%", "100%", "125%", "150%"]
    assert [action.isChecked() for action in actions] == [False, False, False, True, False]


def test_pet_scale_menu_action_changes_window_scale():
    app = QApplication.instance() or QApplication([])
    window = _WindowStub(debug=False)

    menu = tray_module._create_menu(app, window)
    scale_menu = next(action.menu() for action in menu.actions() if action.text() == "Pet Scale")
    scale_menu.actions()[0].trigger()

    assert window.scale_percent == 50


def test_restart_starts_new_process_then_saves_and_quits(monkeypatch):
    calls = []

    class _AppStub:
        def quit(self):
            calls.append("quit")

    window = _WindowStub(debug=False)
    monkeypatch.setattr(tray_module.sys, "executable", "python.exe")
    monkeypatch.setattr(tray_module.sys, "argv", ["python.exe", "--debug"])
    monkeypatch.setattr(
        tray_module.QProcess,
        "startDetached",
        lambda program, args, cwd: calls.append((program, args, cwd)) or True,
    )

    tray_module._restart_app(_AppStub(), window)

    assert calls == [("python.exe", ["-m", "digimon_pet", "--debug"], str(tray_module.PROJECT_ROOT)), "quit"]
    assert window.saved is True


def test_restart_command_uses_executable_directly_when_frozen(monkeypatch):
    monkeypatch.setattr(tray_module.sys, "executable", "digimon-pet.exe")
    monkeypatch.setattr(tray_module.sys, "argv", ["digimon-pet.exe", "--debug"])
    monkeypatch.setattr(tray_module.sys, "frozen", True, raising=False)

    assert tray_module._restart_command() == ("digimon-pet.exe", ["--debug"])
