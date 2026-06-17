from __future__ import annotations

from collections.abc import Callable
import math
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap, QTransform
from PySide6.QtWidgets import QWidget

from digimon_pet.app.sprite_runtime import SpriteAnimation, load_or_build_runtime_manifest, resolve_sprite_animation
from digimon_pet.domain.models import PetState, Species
from digimon_pet.paths import PROJECT_ROOT

SPRITE_TARGET_RECT = QRect(16, 16, 96, 96)
SHADOW_OFFSET = QPoint(6, 6)
SHADOW_COLOR = QColor(0, 0, 0, 95)
EFFECT_INTERVAL_MS = 33
RESOLUTION_DURATION_MS = 2200
DEATH_RESOLUTION_DURATION_MS = 900
PENDING_EFFECTS = {"pending_evolution", "pending_death"}
RESOLUTION_EFFECTS = {"evolution", "death"}


class PetWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state: PetState | None = None
        self._species: Species | None = None
        self._pixmap: QPixmap | None = None
        self._animation: SpriteAnimation | None = None
        self._frame_index = 0
        self._frame_rects: list[QRect] = []
        self._flipped_x = False
        self._manifest = load_or_build_runtime_manifest()
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._advance_frame)
        self._effect_name: str | None = None
        self._effect_elapsed_ms = 0
        self._effect_finished: Callable[[], None] | None = None
        self._effect_timer = QTimer(self)
        self._effect_timer.timeout.connect(self._advance_effect)
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
        if self._effect_name in PENDING_EFFECTS | RESOLUTION_EFFECTS:
            self._animation_timer.stop()
        self.update()

    def set_lifecycle_pending(self, kind: str | None) -> None:
        effect_name = {
            None: None,
            "evolution": "pending_evolution",
            "death": "pending_death",
        }[kind]
        if self._effect_name == effect_name:
            return
        self._effect_name = effect_name
        self._effect_elapsed_ms = 0
        self._effect_finished = None
        if effect_name is None:
            self._effect_timer.stop()
            self._configure_animation_timer(self._animation)
        else:
            self._animation_timer.stop()
            self._effect_timer.start(EFFECT_INTERVAL_MS)
        self.update()

    def start_lifecycle_resolution(self, kind: str, finished: Callable[[], None]) -> None:
        self._effect_name = kind
        self._effect_elapsed_ms = 0
        self._effect_finished = finished
        self._animation_timer.stop()
        self._effect_timer.start(EFFECT_INTERVAL_MS)
        self.update()

    def set_flipped_x(self, flipped: bool) -> None:
        flipped = bool(flipped)
        if self._flipped_x == flipped:
            return
        self._flipped_x = flipped
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._pixmap and not self._pixmap.isNull():
            if self._frame_rects:
                source = self._frame_rects[self._frame_index % len(self._frame_rects)]
                source_pixmap = self._sprite_pixmap(self._pixmap, source)
            else:
                source_pixmap = self._sprite_pixmap(self._pixmap, None)
            target = self._effect_target_rect()
            if self._draws_sprite():
                self._draw_sprite_shadow(painter, source_pixmap, target)
                self._draw_effect_sprite(painter, source_pixmap, target)
        else:
            self._draw_placeholder(painter)
        self._draw_effect_particles(painter)

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
        if self._effect_name in PENDING_EFFECTS | RESOLUTION_EFFECTS:
            return
        if animation is None or animation.frame_count <= 1:
            return
        self._animation_timer.start(max(16, round(1000 / animation.fps)))

    def _advance_frame(self) -> None:
        if not self._frame_rects:
            return
        self._frame_index = (self._frame_index + 1) % len(self._frame_rects)
        self.update()

    def _advance_effect(self) -> None:
        self._effect_elapsed_ms += EFFECT_INTERVAL_MS
        if self._effect_name in RESOLUTION_EFFECTS and self._effect_elapsed_ms >= self._effect_duration_ms():
            finished = self._effect_finished
            self._effect_name = None
            self._effect_elapsed_ms = 0
            self._effect_finished = None
            self._effect_timer.stop()
            self._configure_animation_timer(self._animation)
            if finished is not None:
                finished()
            self.update()
            return
        self.update()

    def _sprite_pixmap(self, pixmap: QPixmap, source: QRect | None) -> QPixmap:
        source_pixmap = pixmap.copy(source) if source is not None else pixmap
        if not self._flipped_x:
            return source_pixmap
        return source_pixmap.transformed(QTransform().scale(-1, 1))

    def _draw_sprite_shadow(self, painter: QPainter, source_pixmap: QPixmap, target: QRect) -> None:
        shadow = QImage(source_pixmap.size(), QImage.Format.Format_ARGB32_Premultiplied)
        shadow.fill(Qt.GlobalColor.transparent)

        shadow_painter = QPainter(shadow)
        shadow_painter.drawPixmap(0, 0, source_pixmap)
        shadow_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        shadow_painter.fillRect(shadow.rect(), SHADOW_COLOR)
        shadow_painter.end()

        painter.drawImage(target.translated(self._shadow_offset()), shadow)

    def _draw_effect_sprite(self, painter: QPainter, source_pixmap: QPixmap, target: QRect) -> None:
        painter.drawPixmap(target, source_pixmap)
        overlay = self._effect_overlay_color()
        if overlay.alpha() <= 0:
            return
        tinted = QImage(source_pixmap.size(), QImage.Format.Format_ARGB32_Premultiplied)
        tinted.fill(Qt.GlobalColor.transparent)
        tint_painter = QPainter(tinted)
        tint_painter.drawPixmap(0, 0, source_pixmap)
        tint_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        tint_painter.fillRect(tinted.rect(), overlay)
        tint_painter.end()
        painter.drawImage(target, tinted)

    def _draws_sprite(self) -> bool:
        return self._effect_name != "death"

    def _effect_target_rect(self) -> QRect:
        if self._effect_name in PENDING_EFFECTS:
            scale = 1.0 + 0.055 * _smooth_pulse(self._effect_elapsed_ms, 1800)
            return _scaled_rect(SPRITE_TARGET_RECT, scale, scale)
        if self._effect_name not in RESOLUTION_EFFECTS:
            return SPRITE_TARGET_RECT
        progress = min(1.0, self._effect_elapsed_ms / self._effect_duration_ms())
        wave = math.sin(progress * math.pi * 3)
        scale = 1.0 + (0.18 * math.sin(progress * math.pi)) + (0.04 * wave)
        return _scaled_rect(SPRITE_TARGET_RECT, scale, 1.0 + (scale - 1.0) * 0.75)

    def _effect_overlay_color(self) -> QColor:
        if self._effect_name == "pending_evolution":
            alpha = 55 + round(70 * _smooth_pulse(self._effect_elapsed_ms, 1800))
            return QColor(255, 255, 255, alpha)
        if self._effect_name == "pending_death":
            alpha = 50 + round(75 * _smooth_pulse(self._effect_elapsed_ms, 1800))
            return QColor(255, 28, 44, alpha)
        if self._effect_name == "evolution":
            progress = min(1.0, self._effect_elapsed_ms / self._effect_duration_ms())
            alpha = round(230 * math.sin(progress * math.pi))
            return QColor(255, 255, 255, alpha)
        if self._effect_name == "death":
            progress = min(1.0, self._effect_elapsed_ms / self._effect_duration_ms())
            alpha = round(210 * math.sin(progress * math.pi))
            return QColor(255, 22, 42, alpha)
        return QColor(255, 255, 255, 0)

    def _draw_effect_particles(self, painter: QPainter) -> None:
        if self._effect_name not in RESOLUTION_EFFECTS:
            return
        progress = min(1.0, self._effect_elapsed_ms / self._effect_duration_ms())
        if self._effect_name == "death":
            self._draw_death_particles(painter, progress)
            return
        center = SPRITE_TARGET_RECT.center()
        base_color = QColor(255, 255, 255)
        painter.setPen(Qt.PenStyle.NoPen)
        for index in range(18):
            angle = (math.tau / 18) * index + progress * math.tau * 0.45
            distance = 10 + 42 * progress + 5 * math.sin(progress * math.pi * 4 + index)
            radius = 2 + round(2 * math.sin(progress * math.pi))
            x = round(center.x() + math.cos(angle) * distance)
            y = round(center.y() + math.sin(angle) * distance * 0.75)
            alpha = max(0, round(210 * math.sin(progress * math.pi)))
            color = QColor(base_color)
            color.setAlpha(alpha)
            painter.setBrush(color)
            painter.drawEllipse(QPoint(x, y), radius, radius)

    def _draw_death_particles(self, painter: QPainter, progress: float) -> None:
        center = SPRITE_TARGET_RECT.center()
        painter.setPen(Qt.PenStyle.NoPen)
        burst = math.pow(progress, 0.55)
        for index in range(30):
            angle = (math.tau / 30) * index + math.sin(index * 1.7) * 0.35
            distance = 8 + 64 * burst + 9 * math.sin(index + progress * math.pi)
            radius = max(1, round(4 - 2.7 * progress))
            x = round(center.x() + math.cos(angle) * distance)
            y = round(center.y() + math.sin(angle) * distance * 0.72)
            alpha = max(0, round(235 * (1.0 - progress)))
            color = QColor(255, 34 + (index % 4) * 16, 42, alpha)
            painter.setBrush(color)
            painter.drawEllipse(QPoint(x, y), radius, radius)

    def _effect_duration_ms(self) -> int:
        if self._effect_name == "death":
            return DEATH_RESOLUTION_DURATION_MS
        return RESOLUTION_DURATION_MS

    def _shadow_offset(self) -> QPoint:
        if self._flipped_x:
            return QPoint(-SHADOW_OFFSET.x(), SHADOW_OFFSET.y())
        return SHADOW_OFFSET

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


def _smooth_pulse(elapsed_ms: int, period_ms: int) -> float:
    phase = (elapsed_ms % period_ms) / period_ms
    return 0.5 - 0.5 * math.cos(math.tau * phase)


def _scaled_rect(rect: QRect, x_scale: float, y_scale: float) -> QRect:
    width = round(rect.width() * x_scale)
    height = round(rect.height() * y_scale)
    center = rect.center()
    return QRect(center.x() - width // 2, center.y() - height // 2, width, height)
