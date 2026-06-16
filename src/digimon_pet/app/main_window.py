from __future__ import annotations

import ctypes
import sys

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QAction, QMouseEvent
from PySide6.QtWidgets import QApplication, QMenu, QVBoxLayout, QWidget

from digimon_pet.app.debug_panel import DebugPanel
from digimon_pet.app.pet_widget import PetWidget
from digimon_pet.app.theme import APP_QSS
from digimon_pet.data import load_evolution_rules, load_species
from digimon_pet.domain import clean, feed, scold, sleep, train, wake
from digimon_pet.domain.care import apply_tick
from digimon_pet.domain.evolution import choose_evolution
from digimon_pet.domain.models import PetState
from digimon_pet.storage import load_pet_state, save_pet_state


class PetWindow(QWidget):
    def __init__(self, overlay: bool, debug: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._overlay = overlay
        self._debug = debug
        self._species = load_species()
        self._rules = load_evolution_rules()
        self._state = load_pet_state()
        self._direction = QPoint(3, 0)
        self._drag_offset: QPoint | None = None
        self._was_dragging = False
        self._positioned_once = False

        self._configure_window()

        self._pet_widget = PetWidget(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._pet_widget)

        self._debug_panel = DebugPanel()
        self._debug_panel.setStyleSheet(APP_QSS)

        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start(1000)

        self._move_timer = QTimer(self)
        self._move_timer.timeout.connect(self._move_pet)

        self._refresh()

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        if self._was_dragging:
            event.ignore()
            return

        menu = QMenu(self)
        menu.setStyleSheet(APP_QSS)
        for label, action_name in [
            ("Feed", "feed"),
            ("Train", "train"),
            ("Sleep", "sleep"),
            ("Wake", "wake"),
            ("Clean", "clean"),
            ("Scold", "scold"),
        ]:
            action = QAction(label, self)
            action.triggered.connect(lambda checked=False, name=action_name: self._handle_action(name))
            menu.addAction(action)
        menu.addSeparator()
        debug_action = QAction("Toggle Debug", self)
        debug_action.triggered.connect(self._toggle_debug)
        menu.addAction(debug_action)
        menu.exec(event.globalPos())

    def _configure_window(self) -> None:
        self.setWindowTitle("Digimon Pet")
        self.setFixedSize(128, 128)
        if self._overlay:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
            self.setAutoFillBackground(False)
            flags = (
                Qt.WindowType.Window
                | Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
                | Qt.WindowType.NoDropShadowWindowHint
            )
            self.setWindowFlags(flags)
            self.setStyleSheet("background: transparent;")
        else:
            self.setWindowFlags(Qt.WindowType.Window)
            self.setStyleSheet(APP_QSS)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._positioned_once:
            self._move_to_bottom_right()
            self._positioned_once = True
        if self._overlay:
            self._apply_windows_overlay_styles()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._was_dragging = False
            self._move_timer.stop()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._was_dragging = True
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._drag_offset is not None:
            self._drag_offset = None
            self._keep_inside_screen()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _apply_windows_overlay_styles(self) -> None:
        if sys.platform != "win32":
            return

        hwnd = int(self.winId())
        user32 = ctypes.windll.user32
        gwl_style = -16
        gwl_exstyle = -20
        ws_popup = 0x80000000
        ws_visible = 0x10000000
        ws_caption = 0x00C00000
        ws_thickframe = 0x00040000
        ws_minimizebox = 0x00020000
        ws_maximizebox = 0x00010000
        ws_sysmenu = 0x00080000
        ws_ex_layered = 0x00080000
        ws_ex_toolwindow = 0x00000080
        ws_ex_topmost = 0x00000008
        hwnd_topmost = -1
        swp_nosize = 0x0001
        swp_nomove = 0x0002
        swp_noactivate = 0x0010
        swp_framechanged = 0x0020

        style = user32.GetWindowLongW(hwnd, gwl_style)
        style &= ~(ws_caption | ws_thickframe | ws_minimizebox | ws_maximizebox | ws_sysmenu)
        style |= ws_popup | ws_visible
        user32.SetWindowLongW(hwnd, gwl_style, style)

        exstyle = user32.GetWindowLongW(hwnd, gwl_exstyle)
        exstyle |= ws_ex_layered | ws_ex_toolwindow | ws_ex_topmost
        user32.SetWindowLongW(hwnd, gwl_exstyle, exstyle)

        user32.SetWindowPos(
            hwnd,
            hwnd_topmost,
            0,
            0,
            0,
            0,
            swp_nomove | swp_nosize | swp_noactivate | swp_framechanged,
        )

    def _handle_action(self, name: str) -> None:
        actions = {
            "feed": feed,
            "train": train,
            "sleep": sleep,
            "wake": wake,
            "clean": clean,
            "scold": scold,
        }
        action = actions[name]
        action(self._state)
        self._check_evolution()
        self._save_and_refresh()

    def _tick(self) -> None:
        apply_tick(self._state, 1, debug_multiplier=10 if self._debug else 1)
        if self._state.current_action not in {"sleep", "idle"}:
            self._state.current_action = "idle"
        self._check_evolution()
        self._save_and_refresh()

    def _move_pet(self) -> None:
        if not self._overlay:
            return
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        bounds = screen.availableGeometry()
        next_pos = self.pos() + self._direction
        if next_pos.x() <= bounds.left() or next_pos.x() + self.width() >= bounds.right():
            self._direction.setX(-self._direction.x())
        if next_pos.y() < bounds.top():
            next_pos.setY(bounds.top())
        if next_pos.y() + self.height() > bounds.bottom():
            next_pos.setY(bounds.bottom() - self.height())
        self.move(self.pos() + self._direction)

    def _move_to_bottom_right(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        bounds = screen.availableGeometry()
        margin = 24
        self.move(
            bounds.right() - self.width() - margin,
            bounds.bottom() - self.height() - margin,
        )

    def _keep_inside_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        bounds = screen.availableGeometry()
        x = min(max(self.x(), bounds.left()), bounds.right() - self.width())
        y = min(max(self.y(), bounds.top()), bounds.bottom() - self.height())
        self.move(x, y)

    def _check_evolution(self) -> None:
        evolved = choose_evolution(self._state, self._rules, self._species)
        if evolved is None:
            return
        self._state.species_id = evolved.id
        self._state.stage = evolved.stage
        self._state.current_action = "idle"
        self._state.clamp()

    def _save_and_refresh(self) -> None:
        save_pet_state(self._state)
        self._refresh()

    def _refresh(self) -> None:
        species = self._species[self._state.species_id]
        self._pet_widget.set_pet(self._state, species)
        self._debug_panel.refresh(self._state, species)

    def _toggle_debug(self) -> None:
        self._debug_panel.setVisible(not self._debug_panel.isVisible())

    def toggle_debug(self) -> None:
        self._toggle_debug()
