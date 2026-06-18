from __future__ import annotations

import math
from collections.abc import Callable
from enum import Enum

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
)
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsOpacityEffect, QPushButton, QWidget

from digimon_pet.app.theme import COLORS


class RadialArcDirection(Enum):
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"


class RadialPetMenu(QWidget):
    _SIZE = 320
    _BUTTON_SIZE = 48
    _RADIUS = 112
    _ANIMATION_MS = 180

    def __init__(
        self,
        *,
        open_stats: Callable[[], None],
        open_collection: Callable[[], None],
        close_app: Callable[[], None],
        closed: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(self._SIZE, self._SIZE)

        self._closed = closed
        self._animations: QParallelAnimationGroup | None = None
        self._buttons_by_action: dict[str, QPushButton] = {}
        self._actions = {
            "stats": open_stats,
            "collection": open_collection,
            "inventory": lambda: None,
            "close": close_app,
        }

        for action, tooltip in (
            ("stats", "Stats"),
            ("collection", "Collection"),
            ("inventory", "Inventaire"),
            ("close", "Close"),
        ):
            button = QPushButton(self)
            button.setToolTip(tooltip)
            button.setIcon(_icon_for(action))
            button.setIconSize(QSize(24, 24))
            button.setFixedSize(self._BUTTON_SIZE, self._BUTTON_SIZE)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setObjectName("RadialMenuButton")
            button.setStyleSheet(_RADIAL_BUTTON_QSS)
            button.clicked.connect(lambda checked=False, key=action: self._trigger(key))
            opacity = QGraphicsOpacityEffect(button)
            opacity.setOpacity(0.0)
            button.setGraphicsEffect(opacity)
            self._buttons_by_action[action] = button

    def action_buttons(self) -> list[QPushButton]:
        return [self._buttons_by_action[action] for action in self._actions]

    def button_for_action(self, action: str) -> QPushButton:
        return self._buttons_by_action[action]

    def show_for_pet(self, pet_geometry: QRect, screen_geometry: QRect) -> None:
        pet_center = pet_geometry.center()
        self.move(pet_center - QPoint(self.width() // 2, self.height() // 2))
        direction = self.arc_direction_for(pet_center, screen_geometry)
        self._animate_open(direction)
        self.show()
        self.raise_()
        self.activateWindow()

    def arc_direction_for(self, pet_center: QPoint, screen_geometry: QRect) -> RadialArcDirection:
        horizontal_left = pet_center.x() >= screen_geometry.center().x()
        vertical_top = pet_center.y() >= screen_geometry.center().y()
        if horizontal_left and vertical_top:
            return RadialArcDirection.TOP_LEFT
        if not horizontal_left and vertical_top:
            return RadialArcDirection.TOP_RIGHT
        if horizontal_left and not vertical_top:
            return RadialArcDirection.BOTTOM_LEFT
        return RadialArcDirection.BOTTOM_RIGHT

    def mousePressEvent(self, event) -> None:  # noqa: N802
        clicked_button = any(
            button.geometry().contains(event.position().toPoint())
            for button in self._buttons_by_action.values()
        )
        if not clicked_button:
            self.hide()
            event.accept()
            return
        super().mousePressEvent(event)

    def hideEvent(self, event) -> None:  # noqa: N802
        super().hideEvent(event)
        if self._closed is not None:
            self._closed()

    def _trigger(self, action: str) -> None:
        self.hide()
        self._actions[action]()

    def _animate_open(self, direction: RadialArcDirection) -> None:
        center = QPoint(
            (self.width() - self._BUTTON_SIZE) // 2,
            (self.height() - self._BUTTON_SIZE) // 2,
        )
        positions = self._positions_for(direction, center)
        self._animations = QParallelAnimationGroup(self)
        for action, end_pos in zip(self._actions, positions, strict=True):
            button = self._buttons_by_action[action]
            button.move(center)
            effect = button.graphicsEffect()
            if isinstance(effect, QGraphicsOpacityEffect):
                effect.setOpacity(0.0)
                fade = QPropertyAnimation(effect, b"opacity", self)
                fade.setStartValue(0.0)
                fade.setEndValue(1.0)
                fade.setDuration(self._ANIMATION_MS)
                fade.setEasingCurve(QEasingCurve.Type.OutCubic)
                self._animations.addAnimation(fade)
            move = QPropertyAnimation(button, b"pos", self)
            move.setStartValue(center)
            move.setEndValue(end_pos)
            move.setDuration(self._ANIMATION_MS)
            move.setEasingCurve(QEasingCurve.Type.OutBack)
            self._animations.addAnimation(move)
        self._animations.start()

    def _positions_for(self, direction: RadialArcDirection, center: QPoint) -> list[QPoint]:
        angle_sequences = {
            RadialArcDirection.TOP_LEFT: (150, 190, 230, 270),
            RadialArcDirection.TOP_RIGHT: (30, 350, 310, 270),
            RadialArcDirection.BOTTOM_LEFT: (210, 170, 130, 90),
            RadialArcDirection.BOTTOM_RIGHT: (330, 10, 50, 90),
        }
        center_point = center + QPoint(self._BUTTON_SIZE // 2, self._BUTTON_SIZE // 2)
        positions: list[QPoint] = []
        for angle in angle_sequences[direction]:
            radians = math.radians(angle)
            target_center = center_point + QPoint(
                round(math.cos(radians) * self._RADIUS),
                round(math.sin(radians) * self._RADIUS),
            )
            positions.append(
                target_center - QPoint(self._BUTTON_SIZE // 2, self._BUTTON_SIZE // 2)
            )
        return positions


def _icon_for(action: str) -> QIcon:
    pixmap = QPixmap(28, 28)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(
        QPen(QColor(COLORS["text"]), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    )
    painter.setBrush(QColor(COLORS["text"]))

    if action == "stats":
        for index, height in enumerate((9, 16, 22)):
            painter.drawRoundedRect(5 + index * 7, 24 - height, 4, height, 2, 2)
    elif action == "collection":
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for row in range(2):
            for column in range(2):
                painter.drawRoundedRect(5 + column * 10, 5 + row * 10, 7, 7, 2, 2)
    elif action == "inventory":
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(6, 9, 16, 13, 3, 3)
        painter.drawArc(9, 4, 10, 10, 0, 180 * 16)
    elif action == "close":
        painter.drawLine(8, 8, 20, 20)
        painter.drawLine(20, 8, 8, 20)

    painter.end()
    return QIcon(pixmap)


_RADIAL_BUTTON_QSS = f"""
QPushButton#RadialMenuButton {{
    background: {COLORS["panel_alt"]};
    border: 2px solid {COLORS["focus"]};
    border-radius: 24px;
}}

QPushButton#RadialMenuButton:hover {{
    background: {COLORS["accent"]};
    border-color: {COLORS["text"]};
}}

QPushButton#RadialMenuButton:pressed {{
    background: {COLORS["accent_pressed"]};
}}

QPushButton#RadialMenuButton:focus {{
    border-color: {COLORS["text"]};
}}
"""
