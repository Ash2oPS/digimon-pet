from __future__ import annotations

import sys

from PySide6.QtCore import QProcess
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from digimon_pet.app.main_window import PetWindow
from digimon_pet.app.theme import APP_QSS
from digimon_pet.paths import ASSETS_DIR


def create_tray_icon(app: QApplication, window: PetWindow) -> QSystemTrayIcon | None:
    if not QSystemTrayIcon.isSystemTrayAvailable():
        window.show()
        return None
    tray = QSystemTrayIcon(create_app_icon(), app)
    tray.setToolTip("Digimon Pet")
    tray.setContextMenu(_create_menu(app, window))
    tray.activated.connect(lambda reason: _handle_activation(reason, window))
    tray.show()
    return tray


def _create_menu(app: QApplication, window: PetWindow) -> QMenu:
    menu = QMenu()
    menu.setStyleSheet(APP_QSS)

    toggle_pet = QAction("Show/Hide Pet", menu)
    toggle_pet.triggered.connect(lambda: window.setVisible(not window.isVisible()))
    menu.addAction(toggle_pet)

    if getattr(window, "_debug", False):
        toggle_debug = QAction("Toggle Debug", menu)
        toggle_debug.triggered.connect(window.toggle_debug)
        menu.addAction(toggle_debug)

    menu.addSeparator()

    restart_action = QAction("Restart", menu)
    restart_action.triggered.connect(lambda: _restart_app(app, window))
    menu.addAction(restart_action)

    quit_action = QAction("Quit", menu)
    quit_action.triggered.connect(lambda: _quit_app(app, window))
    menu.addAction(quit_action)

    return menu


def _quit_app(app: QApplication, window: PetWindow) -> None:
    if hasattr(window, "save_current_state"):
        window.save_current_state()
    app.quit()


def _restart_app(app: QApplication, window: PetWindow) -> None:
    if not QProcess.startDetached(sys.executable, sys.argv[1:]):
        return
    _quit_app(app, window)


def _handle_activation(reason: QSystemTrayIcon.ActivationReason, window: PetWindow) -> None:
    if reason == QSystemTrayIcon.ActivationReason.Trigger:
        window.setVisible(not window.isVisible())


def create_app_icon() -> QIcon:
    icon_path = ASSETS_DIR / "app" / "digitama.png"
    if icon_path.exists():
        icon = QIcon(str(icon_path))
        if not icon.isNull():
            return icon
    return _create_fallback_icon()


def _create_fallback_icon() -> QIcon:
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor("#171719"))
    painter.setBrush(QColor("#f08a3c"))
    painter.drawEllipse(4, 4, 24, 24)
    painter.setBrush(QColor("#ffd166"))
    painter.drawEllipse(10, 11, 4, 4)
    painter.drawEllipse(18, 11, 4, 4)
    painter.drawArc(10, 15, 12, 7, 200 * 16, 140 * 16)
    painter.end()

    return QIcon(pixmap)
