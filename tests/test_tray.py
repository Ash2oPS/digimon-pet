import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from digimon_pet.app import tray as tray_module


def test_create_tray_icon_returns_none_when_system_tray_unavailable(monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = QWidget()
    monkeypatch.setattr(tray_module.QSystemTrayIcon, "isSystemTrayAvailable", lambda: False)

    tray = tray_module.create_tray_icon(app, window)

    assert tray is None
