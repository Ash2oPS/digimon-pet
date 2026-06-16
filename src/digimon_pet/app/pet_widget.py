from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from digimon_pet.app.sprite_runtime import SpriteAnimation, load_or_build_runtime_manifest, resolve_sprite_animation
from digimon_pet.domain.models import PetState, Species
from digimon_pet.paths import PROJECT_ROOT

SPRITE_TARGET_RECT = QRect(16, 16, 96, 96)
SHADOW_OFFSET = QPoint(6, 6)
SHADOW_COLOR = QColor(0, 0, 0, 95)


class PetWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state: PetState | None = None
        self._species: Species | None = None
        self._pixmap: QPixmap | None = None
        self._animation: SpriteAnimation | None = None
        self._frame_index = 0
        self._frame_rects: list[QRect] = []
        self._manifest = load_or_build_runtime_manifest()
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._advance_frame)
        self.setFixedSize(128, 128)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips)

    def set_pet(self, state: PetState, species: Species) -> None:
        self._state = state
        self._species = species
        self.setToolTip(_stats_tooltip(state))
        animation = resolve_sprite_animation(state, species, self._manifest)
        if animation != self._animation:
            self._animation = animation
            self._frame_index = 0
            self._pixmap = self._load_pixmap(animation)
            self._frame_rects = self._build_frame_rects(self._pixmap, animation)
            self._configure_animation_timer(animation)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._pixmap and not self._pixmap.isNull():
            if self._frame_rects:
                source = self._frame_rects[self._frame_index % len(self._frame_rects)]
                self._draw_sprite_shadow(painter, self._pixmap, source)
                painter.drawPixmap(SPRITE_TARGET_RECT, self._pixmap, source)
            else:
                self._draw_sprite_shadow(painter, self._pixmap, None)
                painter.drawPixmap(SPRITE_TARGET_RECT, self._pixmap)
        else:
            self._draw_placeholder(painter)

    def _load_pixmap(self, animation: SpriteAnimation | None) -> QPixmap | None:
        if animation is None:
            return None
        path = PROJECT_ROOT / Path(animation.path)
        if not path.exists():
            return None
        return QPixmap(str(path))

    def _build_frame_rects(self, pixmap: QPixmap | None, animation: SpriteAnimation | None) -> list[QRect]:
        if pixmap is None or pixmap.isNull() or animation is None or animation.frame_count <= 1:
            return []
        frame_width = animation.frame_width or pixmap.width() // animation.frame_count
        frame_height = animation.frame_height or pixmap.height()
        if frame_width <= 0 or frame_height <= 0:
            return []
        max_frames = max(1, pixmap.width() // frame_width)
        return [
            QRect(index * frame_width, 0, frame_width, frame_height)
            for index in animation.frame_indices
            if index < max_frames
        ]

    def _configure_animation_timer(self, animation: SpriteAnimation | None) -> None:
        self._animation_timer.stop()
        if animation is None or animation.frame_count <= 1:
            return
        self._animation_timer.start(max(16, round(1000 / animation.fps)))

    def _advance_frame(self) -> None:
        if not self._frame_rects:
            return
        self._frame_index = (self._frame_index + 1) % len(self._frame_rects)
        self.update()

    def _draw_sprite_shadow(self, painter: QPainter, pixmap: QPixmap, source: QRect | None) -> None:
        source_pixmap = pixmap.copy(source) if source is not None else pixmap
        shadow = QImage(source_pixmap.size(), QImage.Format.Format_ARGB32_Premultiplied)
        shadow.fill(Qt.GlobalColor.transparent)

        shadow_painter = QPainter(shadow)
        shadow_painter.drawPixmap(0, 0, source_pixmap)
        shadow_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        shadow_painter.fillRect(shadow.rect(), SHADOW_COLOR)
        shadow_painter.end()

        painter.drawImage(SPRITE_TARGET_RECT.translated(SHADOW_OFFSET), shadow)

    def _draw_placeholder(self, painter: QPainter) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#f08a3c"))
        painter.drawEllipse(QPoint(64, 64), 34, 30)
        painter.setBrush(QColor("#ffd166"))
        painter.drawEllipse(QPoint(51, 54), 5, 5)
        painter.drawEllipse(QPoint(77, 54), 5, 5)
        painter.setPen(QColor("#171719"))
        painter.drawArc(QRect(50, 62, 28, 16), 200 * 16, 140 * 16)


def _stats_tooltip(state: PetState) -> str:
    return "\n".join(
        [
            f"HP: {state.hp}",
            f"MP: {state.mp}",
            f"OFF: {state.offense}",
            f"DEF: {state.defense}",
            f"SPD: {state.speed}",
            f"INT: {state.brains}",
        ]
    )
