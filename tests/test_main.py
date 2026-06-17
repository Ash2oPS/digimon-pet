from digimon_pet import main as app_main


def test_main_configures_normal_save_path(monkeypatch):
    calls = []
    monkeypatch.setattr(app_main.save_store, "configure_save_path", lambda *, debug: calls.append(debug))
    _stub_main_qt(monkeypatch)

    exit_code = app_main.main(["--normal"])

    assert exit_code == 0
    assert calls == [False]


def test_main_configures_debug_save_path(monkeypatch):
    calls = []
    monkeypatch.setattr(app_main.save_store, "configure_save_path", lambda *, debug: calls.append(debug))
    _stub_main_qt(monkeypatch)

    exit_code = app_main.main(["--debug", "--normal"])

    assert exit_code == 0
    assert calls == [True]


def _stub_main_qt(monkeypatch):
    class _FakeApp:
        def __init__(self, args):
            self.args = args

        def setWindowIcon(self, icon):
            self.icon = icon

        def setQuitOnLastWindowClosed(self, enabled):
            self.quit_on_last_window_closed = enabled

        def exec(self):
            return 0

    class _FakeWindow:
        def __init__(self, *, overlay, debug):
            self.overlay = overlay
            self.debug = debug

        def show(self):
            self.shown = True

    monkeypatch.setattr(app_main.desktop_platform, "configure_process_for_desktop_app", lambda: None)
    monkeypatch.setattr(app_main, "QApplication", _FakeApp)
    monkeypatch.setattr(app_main, "PetWindow", _FakeWindow)
    monkeypatch.setattr(app_main, "create_app_icon", lambda: object())
    monkeypatch.setattr(app_main, "create_tray_icon", lambda app, window: None)
