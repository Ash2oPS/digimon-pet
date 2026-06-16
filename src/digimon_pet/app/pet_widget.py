from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from digimon_pet.domain.models import PetState, Species
from digimon_pet.paths import PROJECT_ROOT


class PetWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state: PetState | None = None
        self._species: Species | None = None
        self._pixmap: QPixmap | None = None
        self.setFixedSize(128, 128)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_pet(self, state: PetState, species: Species) -> None:
        self._state = state
        self._species = species
        self._pixmap = self._load_pixmap(state, species)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._pixmap and not self._pixmap.isNull():
            target = QRect(16, 16, 96, 96)
            painter.drawPixmap(target, self._pixmap)
        else:
            self._draw_placeholder(painter)

    def _load_pixmap(self, state: PetState, species: Species) -> QPixmap | None:
        slot = species.sprite_slots.get(state.current_action) or species.sprite_slots.get("idle")
        if not slot:
            return None
        path = PROJECT_ROOT / Path(slot)
        if not path.exists():
            return None
        return QPixmap(str(path))

    def _draw_placeholder(self, painter: QPainter) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#f08a3c"))
        painter.drawEllipse(QPoint(64, 64), 34, 30)
        painter.setBrush(QColor("#ffd166"))
        painter.drawEllipse(QPoint(51, 54), 5, 5)
        painter.drawEllipse(QPoint(77, 54), 5, 5)
        painter.setPen(QColor("#171719"))
        painter.drawArc(QRect(50, 62, 28, 16), 200 * 16, 140 * 16)
