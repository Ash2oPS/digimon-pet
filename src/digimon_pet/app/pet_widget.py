from __future__ import annotations

from collections.abc import Callable
import math
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPixmap, QTransform
from PySide6.QtWidgets import QWidget

from digimon_pet.app.sprite_runtime import SpriteAnimation, load_or_build_runtime_manifest, resolve_sprite_animation
from digimon_pet.domain.models import PetState, Species
from digimon_pet.paths import PROJECT_ROOT

SPRITE_TARGET_RECT = QRect(16, 16, 96, 96)
SHADOW_OFFSET = QPoint(6, 6)
SHADOW_COLOR = QColor(0, 0, 0, 95)
EFFECT_INTERVAL_MS = 33
RESOLUTION_DURATION_MS = 1450
EVOLUTION_REVEAL_MS = 760
DEATH_RESOLUTION_DURATION_MS = 900
NEW_BADGE_DURATION_MS = 1500
LEFT_EVENT_PROMPT_RECT = QRect(10, 5, 42, 34)
RIGHT_EVENT_PROMPT_RECT = QRect(76, 5, 42, 34)
PENDING_EFFECTS = {"pending_evolution", "pending_death"}
RESOLUTION_EFFECTS = {"evolution", "death"}
SECONDARY_EVENT_PROMPTS = {"meat", "dumbbell"}


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
        self._effect_reveal: Callable[[], None] | None = None
        self._effect_revealed = False
        self._effect_timer = QTimer(self)
        self._effect_timer.timeout.connect(self._advance_effect)
        self._secondary_event_kind: str | None = None
        self._new_badge_elapsed_ms = 0
        self._new_badge_timer = QTimer(self)
        self._new_badge_timer.timeout.connect(self._advance_new_badge)
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
        self._effect_reveal = None
        self._effect_revealed = False
        if effect_name is None:
            self._effect_timer.stop()
            self._configure_animation_timer(self._animation)
        else:
            self._animation_timer.stop()
            self._effect_timer.start(EFFECT_INTERVAL_MS)
        self.update()

    def start_lifecycle_resolution(
        self,
        kind: str,
        finished: Callable[[], None],
        reveal: Callable[[], None] | None = None,
    ) -> None:
        self._effect_name = kind
        self._effect_elapsed_ms = 0
        self._effect_finished = finished
        self._effect_reveal = reveal
        self._effect_revealed = False
        self._animation_timer.stop()
        self._effect_timer.start(EFFECT_INTERVAL_MS)
        self.update()

    def trigger_new_badge(self) -> None:
        self._new_badge_elapsed_ms = 1
        self._new_badge_timer.start(EFFECT_INTERVAL_MS)
        self.update()

    def set_secondary_event_prompt(self, kind: str | None) -> None:
        if kind is not None and kind not in SECONDARY_EVENT_PROMPTS:
            raise ValueError(f"Unknown secondary event prompt: {kind}")
        if self._secondary_event_kind == kind:
            return
        self._secondary_event_kind = kind
        self.update()

    def event_prompt_kind(self) -> str | None:
        if self._effect_name == "pending_evolution":
            return "evolution"
        if self._effect_name == "pending_death":
            return "death"
        if self._secondary_event_kind is not None:
            return f"secondary_{self._secondary_event_kind}"
        return None

    def event_prompt_rect(self) -> QRect:
        return QRect(RIGHT_EVENT_PROMPT_RECT if self._flipped_x else LEFT_EVENT_PROMPT_RECT)

    def is_event_prompt_at(self, point: QPoint) -> bool:
        return self.event_prompt_kind() is not None and self.event_prompt_rect().contains(point)

    def is_pet_body_at(self, point: QPoint) -> bool:
        return SPRITE_TARGET_RECT.contains(point)

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
        self._draw_event_prompt(painter)
        self._draw_new_badge(painter)

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
        if (
            self._effect_name == "evolution"
            and not self._effect_revealed
            and self._effect_elapsed_ms >= EVOLUTION_REVEAL_MS
        ):
            self._effect_revealed = True
            if self._effect_reveal is not None:
                self._effect_reveal()
        if self._effect_name in RESOLUTION_EFFECTS and self._effect_elapsed_ms >= self._effect_duration_ms():
            finished = self._effect_finished
            self._effect_name = None
            self._effect_elapsed_ms = 0
            self._effect_finished = None
            self._effect_reveal = None
            self._effect_revealed = False
            self._effect_timer.stop()
            self._configure_animation_timer(self._animation)
            if finished is not None:
                finished()
            self.update()
            return
        self.update()

    def _advance_new_badge(self) -> None:
        self._new_badge_elapsed_ms += EFFECT_INTERVAL_MS
        if self._new_badge_elapsed_ms >= NEW_BADGE_DURATION_MS:
            self._new_badge_elapsed_ms = 0
            self._new_badge_timer.stop()
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
        if self._effect_name == "evolution":
            reveal = EVOLUTION_REVEAL_MS / RESOLUTION_DURATION_MS
            if progress < reveal:
                charge = progress / reveal
                scale = 1.0 + 0.24 * _ease_out_cubic(charge) + 0.035 * math.sin(charge * math.pi * 8)
            else:
                settle = (progress - reveal) / (1.0 - reveal)
                scale = 1.0 + 0.18 * (1.0 - _ease_out_cubic(settle)) + 0.03 * math.sin(settle * math.pi * 5) * (1.0 - settle)
            return _scaled_rect(SPRITE_TARGET_RECT, scale, scale)
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
            reveal = EVOLUTION_REVEAL_MS / RESOLUTION_DURATION_MS
            distance_from_reveal = abs(progress - reveal)
            flash = max(0.0, 1.0 - distance_from_reveal / 0.28)
            alpha = round(40 + 215 * flash)
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
        self._draw_evolution_particles(painter, progress)

    def _draw_evolution_particles(self, painter: QPainter, progress: float) -> None:
        center = SPRITE_TARGET_RECT.center()
        reveal = EVOLUTION_REVEAL_MS / RESOLUTION_DURATION_MS
        burst = _ease_out_cubic(min(1.0, progress / reveal))
        settle = 0.0 if progress < reveal else (progress - reveal) / (1.0 - reveal)
        base_color = QColor(255, 255, 255)
        ring_alpha = max(0, round(210 * (1.0 - settle) * max(0.0, 1.0 - abs(progress - reveal) / 0.34)))
        if ring_alpha:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(255, 255, 255, ring_alpha), 2))
            radius_x = round(16 + 46 * burst)
            radius_y = round(11 + 33 * burst)
            painter.drawEllipse(center, radius_x, radius_y)
        painter.setPen(Qt.PenStyle.NoPen)
        for index in range(26):
            angle = (math.tau / 26) * index + progress * math.tau * 1.25
            distance = 8 + 48 * burst + 5 * math.sin(progress * math.pi * 6 + index)
            radius = 2 + round(2 * max(0.0, 1.0 - settle))
            x = round(center.x() + math.cos(angle) * distance)
            y = round(center.y() + math.sin(angle) * distance * 0.75)
            alpha = max(0, round(235 * (1.0 - settle) * math.sin(min(1.0, progress / reveal) * math.pi)))
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

    def _draw_event_prompt(self, painter: QPainter) -> None:
        kind = self.event_prompt_kind()
        if kind is None:
            return
        pulse = _smooth_pulse(self._effect_elapsed_ms, 1200)
        rect = self.event_prompt_rect()
        rect.translate(0, -round(2 * pulse))

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        tail = QPainterPath()
        if self._flipped_x:
            tail.moveTo(rect.left() + 8, rect.bottom() - 6)
            tail.lineTo(rect.left() - 3, rect.bottom() + 7)
            tail.lineTo(rect.left() + 15, rect.bottom() - 2)
        else:
            tail.moveTo(rect.right() - 8, rect.bottom() - 6)
            tail.lineTo(rect.right() + 3, rect.bottom() + 7)
            tail.lineTo(rect.right() - 15, rect.bottom() - 2)
        tail.closeSubpath()
        path = path.united(tail)
        painter.setPen(QPen(QColor(65, 43, 24, 220), 2))
        painter.setBrush(QColor(255, 250, 214, 245))
        painter.drawPath(path)

        if kind == "evolution":
            self._draw_evolution_prompt_icon(painter, rect.center())
        elif kind == "death":
            self._draw_death_prompt_icon(painter, rect.center())
        elif kind == "secondary_meat":
            self._draw_meat_prompt_icon(painter, rect.center())
        elif kind == "secondary_dumbbell":
            self._draw_dumbbell_prompt_icon(painter, rect.center())
        painter.restore()

    def _draw_evolution_prompt_icon(self, painter: QPainter, center: QPoint) -> None:
        painter.setPen(QPen(QColor(65, 43, 24), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(QColor(255, 211, 52))
        star = QPainterPath()
        for index in range(10):
            radius = 11 if index % 2 == 0 else 5
            angle = -math.pi / 2 + index * math.pi / 5
            point = QPoint(round(center.x() + math.cos(angle) * radius), round(center.y() + math.sin(angle) * radius))
            if index == 0:
                star.moveTo(point)
            else:
                star.lineTo(point)
        star.closeSubpath()
        painter.drawPath(star)

    def _draw_death_prompt_icon(self, painter: QPainter, center: QPoint) -> None:
        outline = QColor(65, 43, 24)
        skull = QPainterPath()
        skull.addEllipse(QPoint(center.x(), center.y() - 3), 10, 9)
        skull.addRoundedRect(QRect(center.x() - 7, center.y() + 2, 14, 10), 3, 3)
        painter.setPen(QPen(outline, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(QColor(248, 246, 224))
        painter.drawPath(skull)

        painter.setBrush(outline)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPoint(center.x() - 4, center.y() - 2), 2, 3)
        painter.drawEllipse(QPoint(center.x() + 4, center.y() - 2), 2, 3)
        nose = QPainterPath()
        nose.moveTo(center.x(), center.y() + 1)
        nose.lineTo(center.x() - 2, center.y() + 5)
        nose.lineTo(center.x() + 2, center.y() + 5)
        nose.closeSubpath()
        painter.drawPath(nose)

        painter.setPen(QPen(outline, 1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for x in (-4, 0, 4):
            painter.drawLine(center.x() + x, center.y() + 7, center.x() + x, center.y() + 11)

    def _draw_meat_prompt_icon(self, painter: QPainter, center: QPoint) -> None:
        outline = QColor(65, 43, 24)
        painter.setPen(QPen(outline, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(QColor(224, 84, 58))
        painter.drawEllipse(QPoint(center.x() - 2, center.y() + 1), 9, 7)
        painter.setBrush(QColor(248, 246, 224))
        painter.drawEllipse(QPoint(center.x() + 8, center.y() - 6), 4, 4)
        painter.drawEllipse(QPoint(center.x() + 10, center.y() - 1), 4, 4)
        painter.setPen(QPen(outline, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(center.x() + 4, center.y() - 2, center.x() + 10, center.y() - 5)

    def _draw_dumbbell_prompt_icon(self, painter: QPainter, center: QPoint) -> None:
        outline = QColor(65, 43, 24)
        painter.setPen(QPen(outline, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(center.x() - 9, center.y() + 5, center.x() + 9, center.y() - 5)
        painter.setPen(QPen(outline, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(QColor(122, 151, 176))
        painter.drawRoundedRect(QRect(center.x() - 15, center.y() + 2, 7, 8), 2, 2)
        painter.drawRoundedRect(QRect(center.x() - 10, center.y() - 1, 5, 8), 2, 2)
        painter.drawRoundedRect(QRect(center.x() + 8, center.y() - 10, 7, 8), 2, 2)
        painter.drawRoundedRect(QRect(center.x() + 5, center.y() - 7, 5, 8), 2, 2)

    def _draw_new_badge(self, painter: QPainter) -> None:
        if self._new_badge_elapsed_ms <= 0:
            return
        progress = min(1.0, self._new_badge_elapsed_ms / NEW_BADGE_DURATION_MS)
        pop = _ease_out_back(min(1.0, progress / 0.34))
        fade = 1.0 if progress < 0.72 else max(0.0, 1.0 - (progress - 0.72) / 0.28)
        y = 22 - round(10 * _ease_out_cubic(progress))
        scale = 0.72 + 0.34 * pop
        alpha = round(255 * fade)

        painter.save()
        painter.translate(64, y)
        painter.scale(scale, scale)
        self._draw_new_badge_strokes(painter, QColor(80, 39, 0, alpha), 6)
        self._draw_new_badge_strokes(painter, QColor(255, 255, 255, alpha), 4)
        self._draw_new_badge_strokes(painter, QColor(255, 217, 55, alpha), 2)
        painter.restore()

    def _draw_new_badge_strokes(self, painter: QPainter, color: QColor, width: int) -> None:
        painter.setPen(QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        strokes = [
            ((-26, 8), (-26, -8)),
            ((-26, -8), (-16, 8)),
            ((-16, 8), (-16, -8)),
            ((-10, -8), (-10, 8)),
            ((-10, -8), (1, -8)),
            ((-10, 0), (-1, 0)),
            ((-10, 8), (1, 8)),
            ((7, -8), (10, 8)),
            ((10, 8), (15, -2)),
            ((15, -2), (20, 8)),
            ((20, 8), (23, -8)),
            ((29, -8), (29, 3)),
            ((29, 8), (29, 8)),
        ]
        for start, end in strokes:
            painter.drawLine(start[0], start[1], end[0], end[1])

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


def _ease_out_cubic(value: float) -> float:
    clamped = max(0.0, min(1.0, value))
    return 1.0 - math.pow(1.0 - clamped, 3)


def _ease_out_back(value: float) -> float:
    clamped = max(0.0, min(1.0, value))
    overshoot = 1.70158
    shifted = clamped - 1.0
    return 1.0 + (overshoot + 1.0) * math.pow(shifted, 3) + overshoot * math.pow(shifted, 2)


def _scaled_rect(rect: QRect, x_scale: float, y_scale: float) -> QRect:
    width = round(rect.width() * x_scale)
    height = round(rect.height() * y_scale)
    center = rect.center()
    return QRect(center.x() - width // 2, center.y() - height // 2, width, height)
