from __future__ import annotations

from collections.abc import Callable
import math
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPixmap, QTransform
from PySide6.QtWidgets import QWidget

from digimon_pet.app.animated_sprite import sprite_animation_interval_ms
from digimon_pet.app.sprite_frames import sprite_frame_rects
from digimon_pet.app.sprite_runtime import SpriteAnimation, load_runtime_manifest, resolve_sprite_animation
from digimon_pet.domain.models import PetState, Species
from digimon_pet.paths import PROJECT_ROOT

BASE_WIDGET_SIZE = 128
SPRITE_TARGET_RECT = QRect(16, 16, 96, 96)
SHADOW_OFFSET = QPoint(6, 6)
SHADOW_COLOR = QColor(0, 0, 0, 95)
EFFECT_INTERVAL_MS = 33
RESOLUTION_DURATION_MS = 1450
EVOLUTION_REVEAL_MS = 760
DEATH_RESOLUTION_DURATION_MS = 900
NEW_BADGE_DURATION_MS = 1500
STAT_GAIN_TEXT_DURATION_MS = 1700
STATIC_SPRITE_SCALE = 0.9
SECONDARY_EVENT_BOUNCE_PERIOD_MS = 1100
SECONDARY_EVENT_BOUNCE_HEIGHT = 7
LEFT_EVENT_PROMPT_RECT = QRect(4, 5, 42, 34)
RIGHT_EVENT_PROMPT_RECT = QRect(82, 5, 42, 34)
PENDING_EFFECTS = {"pending_evolution", "pending_death"}
RESOLUTION_EFFECTS = {"evolution", "death"}
SECONDARY_EVENT_PROMPTS = {"meat", "dumbbell", "item"}
STAT_LABELS = {
    "hp": "HP",
    "mp": "MP",
    "offense": "OFF",
    "defense": "DEF",
    "speed": "SPD",
    "brains": "INT",
}
PIXEL_GLYPHS = {
    "+": ("000", "010", "111", "010", "000"),
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "010", "010", "010"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
    "?": ("111", "001", "011", "000", "010"),
    "D": ("110", "101", "101", "101", "110"),
    "E": ("111", "100", "110", "100", "111"),
    "F": ("111", "100", "110", "100", "100"),
    "H": ("101", "101", "111", "101", "101"),
    "I": ("111", "010", "010", "010", "111"),
    "M": ("101", "111", "111", "101", "101"),
    "N": ("101", "111", "111", "111", "101"),
    "O": ("111", "101", "101", "101", "111"),
    "P": ("111", "101", "111", "100", "100"),
    "S": ("111", "100", "111", "001", "111"),
    "T": ("111", "010", "010", "010", "010"),
}


class PetWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._render_scale = 1.0
        self._state: PetState | None = None
        self._species: Species | None = None
        self._pixmap: QPixmap | None = None
        self._animation: SpriteAnimation | None = None
        self._frame_index = 0
        self._frame_rects: list[QRect] = []
        self._prepared_frame_cache: dict[tuple[int, bool], QPixmap] = {}
        self._prepared_shadow_cache: dict[tuple[int, bool], QImage] = {}
        self._stat_gain_item_pixmap_cache: tuple[str, QPixmap] | None = None
        self._static_scale_fallback_enabled = False
        self._static_scale_shrunken = False
        self._flipped_x = False
        self._manifest = load_runtime_manifest()
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
        self._secondary_event_elapsed_ms = 0
        self._secondary_event_timer = QTimer(self)
        self._secondary_event_timer.timeout.connect(self._advance_secondary_event_prompt)
        self._new_badge_elapsed_ms = 0
        self._new_badge_timer = QTimer(self)
        self._new_badge_timer.timeout.connect(self._advance_new_badge)
        self._stat_gain_elapsed_ms = 0
        self._stat_gain_labels: list[str] = []
        self._stat_gain_item_icon_path: str | None = None
        self._stat_gain_timer = QTimer(self)
        self._stat_gain_timer.timeout.connect(self._advance_stat_gain_text)
        self.setFixedSize(BASE_WIDGET_SIZE, BASE_WIDGET_SIZE)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips)

    def set_render_scale(self, scale: float) -> None:
        self._render_scale = max(0.5, min(1.5, float(scale)))
        scaled_size = round(BASE_WIDGET_SIZE * self._render_scale)
        self.setFixedSize(scaled_size, scaled_size)
        self.update()

    def set_pet(self, state: PetState, species: Species) -> None:
        self._state = state
        self._species = species
        self.setToolTip(_stats_tooltip(state, species))
        animation = resolve_sprite_animation(state, species, self._manifest)
        if animation != self._animation:
            self._animation = animation
            self._frame_index = 0
            self._static_scale_shrunken = False
            self._pixmap = self._load_pixmap(animation)
            self._frame_rects = self._build_frame_rects(self._pixmap, animation)
            self._clear_prepared_sprite_cache()
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

    def trigger_stat_gain_text(
        self,
        gains: dict[str, int],
        *,
        item_gains: int = 0,
        item_gain_icon_path: str | None = None,
    ) -> None:
        labels = [
            f"+{int(amount)} {STAT_LABELS[stat_name]}"
            for stat_name, amount in gains.items()
            if stat_name in STAT_LABELS and int(amount) > 0
        ]
        item_icon_path = item_gain_icon_path if item_gains > 0 else None
        if not labels and item_icon_path is None:
            return
        self._stat_gain_labels = labels
        self._stat_gain_item_icon_path = item_icon_path
        self._stat_gain_elapsed_ms = 1
        self._stat_gain_timer.start(EFFECT_INTERVAL_MS)
        self.update()

    def set_secondary_event_prompt(self, kind: str | None) -> None:
        if kind is not None and kind not in SECONDARY_EVENT_PROMPTS:
            raise ValueError(f"Unknown secondary event prompt: {kind}")
        if self._secondary_event_kind == kind:
            return
        self._secondary_event_kind = kind
        self._secondary_event_elapsed_ms = 0
        if kind is None:
            self._secondary_event_timer.stop()
        else:
            self._secondary_event_timer.start(EFFECT_INTERVAL_MS)
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
        return self._scale_rect(self._logical_event_prompt_rect())

    def is_event_prompt_at(self, point: QPoint) -> bool:
        return self.event_prompt_kind() is not None and self._logical_event_prompt_rect().contains(
            self._to_logical_point(point)
        )

    def is_pet_body_at(self, point: QPoint) -> bool:
        return SPRITE_TARGET_RECT.contains(self._to_logical_point(point))

    def set_flipped_x(self, flipped: bool) -> None:
        flipped = bool(flipped)
        if self._flipped_x == flipped:
            return
        self._flipped_x = flipped
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(self._render_scale, self._render_scale)

        if self._pixmap and not self._pixmap.isNull():
            source_pixmap = self._prepared_sprite_pixmap()
            target = self._effect_target_rect()
            if self._draws_sprite():
                self._draw_sprite_shadow(painter, source_pixmap, target)
                self._draw_effect_sprite(painter, source_pixmap, target)
        else:
            self._draw_placeholder(painter)
        self._draw_effect_particles(painter)
        self._draw_event_prompt(painter)
        self._draw_new_badge(painter)
        self._draw_stat_gain_text(painter)

    def _load_pixmap(self, animation: SpriteAnimation | None) -> QPixmap | None:
        if animation is None:
            return None
        path = PROJECT_ROOT / Path(animation.path)
        if not path.exists():
            return None
        return QPixmap(str(path))

    def _build_frame_rects(self, pixmap: QPixmap | None, animation: SpriteAnimation | None) -> list[QRect]:
        if pixmap is None or pixmap.isNull() or animation is None:
            return []
        return sprite_frame_rects(pixmap, animation)

    def _configure_animation_timer(self, animation: SpriteAnimation | None) -> None:
        self._animation_timer.stop()
        self._static_scale_fallback_enabled = False
        self._static_scale_shrunken = False
        if self._effect_name in PENDING_EFFECTS | RESOLUTION_EFFECTS:
            return
        if animation is None:
            return
        interval_ms = sprite_animation_interval_ms(animation)
        self._static_scale_fallback_enabled = _uses_static_scale_fallback(animation)
        if animation.frame_count > 1 or self._static_scale_fallback_enabled:
            self._animation_timer.start(interval_ms)

    def _advance_frame(self) -> None:
        if not self._frame_rects:
            if self._static_scale_fallback_enabled:
                self._static_scale_shrunken = not self._static_scale_shrunken
                self.update()
            return
        self._frame_index = (self._frame_index + 1) % len(self._frame_rects)
        self.update()

    def _clear_prepared_sprite_cache(self) -> None:
        self._prepared_frame_cache.clear()
        self._prepared_shadow_cache.clear()

    def _prepared_sprite_pixmap(self) -> QPixmap:
        if self._pixmap is None:
            return QPixmap()
        frame_key = self._frame_index % len(self._frame_rects) if self._frame_rects else 0
        cache_key = (frame_key, self._flipped_x)
        cached = self._prepared_frame_cache.get(cache_key)
        if cached is not None:
            return cached
        source = self._frame_rects[frame_key] if self._frame_rects else None
        prepared = self._sprite_pixmap(self._pixmap, source)
        self._prepared_frame_cache[cache_key] = prepared
        return prepared

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

    def _advance_secondary_event_prompt(self) -> None:
        if self._secondary_event_kind is None:
            self._secondary_event_elapsed_ms = 0
            self._secondary_event_timer.stop()
            return
        self._secondary_event_elapsed_ms += EFFECT_INTERVAL_MS
        self.update()

    def _advance_new_badge(self) -> None:
        self._new_badge_elapsed_ms += EFFECT_INTERVAL_MS
        if self._new_badge_elapsed_ms >= NEW_BADGE_DURATION_MS:
            self._new_badge_elapsed_ms = 0
            self._new_badge_timer.stop()
        self.update()

    def _advance_stat_gain_text(self) -> None:
        self._stat_gain_elapsed_ms += EFFECT_INTERVAL_MS
        if self._stat_gain_elapsed_ms >= STAT_GAIN_TEXT_DURATION_MS:
            self._stat_gain_elapsed_ms = 0
            self._stat_gain_labels = []
            self._stat_gain_item_icon_path = None
            self._stat_gain_timer.stop()
        self.update()

    def _sprite_pixmap(self, pixmap: QPixmap, source: QRect | None) -> QPixmap:
        source_pixmap = pixmap.copy(source) if source is not None else pixmap
        if not self._flipped_x:
            return source_pixmap
        return source_pixmap.transformed(QTransform().scale(-1, 1))

    def _draw_sprite_shadow(self, painter: QPainter, source_pixmap: QPixmap, target: QRect) -> None:
        frame_key = self._frame_index % len(self._frame_rects) if self._frame_rects else 0
        cache_key = (frame_key, self._flipped_x)
        shadow = self._prepared_shadow_cache.get(cache_key)
        if shadow is None:
            shadow = self._create_shadow_image(source_pixmap)
            self._prepared_shadow_cache[cache_key] = shadow
        painter.drawImage(target.translated(self._shadow_offset()), shadow)

    def _create_shadow_image(self, source_pixmap: QPixmap) -> QImage:
        shadow = QImage(source_pixmap.size(), QImage.Format.Format_ARGB32_Premultiplied)
        shadow.fill(Qt.GlobalColor.transparent)

        shadow_painter = QPainter(shadow)
        shadow_painter.drawPixmap(0, 0, source_pixmap)
        shadow_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        shadow_painter.fillRect(shadow.rect(), SHADOW_COLOR)
        shadow_painter.end()
        return shadow

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
            if self._static_scale_shrunken and self._static_scale_fallback_enabled:
                target = _scaled_rect_from_bottom_center(SPRITE_TARGET_RECT, 1.0, STATIC_SPRITE_SCALE)
            else:
                target = QRect(SPRITE_TARGET_RECT)
            if self._secondary_event_kind is not None:
                target.translate(0, -self._secondary_event_bounce_offset())
            return target
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

    def _secondary_event_bounce_offset(self) -> int:
        phase = (self._secondary_event_elapsed_ms % SECONDARY_EVENT_BOUNCE_PERIOD_MS) / SECONDARY_EVENT_BOUNCE_PERIOD_MS
        jump_window = 0.58
        if phase >= jump_window:
            return 0
        arc = math.sin((phase / jump_window) * math.pi)
        return round(SECONDARY_EVENT_BOUNCE_HEIGHT * math.pow(max(0.0, arc), 0.85))

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
        rect = self._logical_event_prompt_rect()
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
        elif kind == "secondary_item":
            self._draw_item_prompt_icon(painter, rect.center())
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

    def _draw_item_prompt_icon(self, painter: QPainter, center: QPoint) -> None:
        scale = 5
        text = "?"
        width = _pixel_text_width(text, scale)
        height = 5 * scale
        x = center.x() - width // 2
        y = center.y() - height // 2
        for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
            _draw_pixel_text(painter, text, x + dx, y + dy, scale, QColor(65, 43, 24, 235))
        _draw_pixel_text(painter, text, x, y, scale, QColor(255, 250, 214))

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

    def _draw_stat_gain_text(self, painter: QPainter) -> None:
        if self._stat_gain_elapsed_ms <= 0:
            return
        progress = min(1.0, self._stat_gain_elapsed_ms / STAT_GAIN_TEXT_DURATION_MS)
        fade = 1.0 if progress < 0.72 else max(0.0, 1.0 - (progress - 0.72) / 0.28)
        y_offset = round(9 * _ease_out_cubic(progress))
        alpha = round(255 * fade)

        painter.save()
        has_item_icon = self._stat_gain_item_icon_path is not None
        if has_item_icon:
            self._draw_item_gain_icon(painter, 8 - y_offset, alpha)

        rows = [" ".join(self._stat_gain_labels[index : index + 2]) for index in range(0, len(self._stat_gain_labels), 2)]
        first_text_y = 38 if has_item_icon else 14
        for row_index, text in enumerate(rows[:3]):
            y = first_text_y + row_index * 13 - y_offset
            self._draw_outlined_pixel_text(
                painter,
                y,
                text,
                QColor(0, 42, 84, alpha),
                QColor(70, 178, 255, alpha),
            )
        painter.restore()

    def _draw_outlined_pixel_text(self, painter: QPainter, y: int, text: str, outline: QColor, fill: QColor) -> None:
        scale = 2
        width = _pixel_text_width(text, scale)
        x = max(0, (BASE_WIDGET_SIZE - width) // 2)
        self._draw_outlined_pixel_text_at(painter, x, y, text, outline, fill)

    def _draw_outlined_pixel_text_at(
        self,
        painter: QPainter,
        x: int,
        y: int,
        text: str,
        outline: QColor,
        fill: QColor,
    ) -> None:
        scale = 2
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            _draw_pixel_text(painter, text, x + dx, y + dy, scale, outline)
        _draw_pixel_text(painter, text, x, y, scale, fill)

    def _draw_item_gain_icon(self, painter: QPainter, y: int, alpha: int) -> None:
        pixmap = self._stat_gain_item_pixmap()
        if pixmap is None:
            return
        icon_size = 24
        x = max(0, (BASE_WIDGET_SIZE - icon_size) // 2)
        painter.save()
        painter.setOpacity(alpha / 255)
        painter.drawPixmap(
            QRect(x, y, icon_size, icon_size),
            pixmap,
            pixmap.rect(),
        )
        painter.restore()

    def _stat_gain_item_pixmap(self) -> QPixmap | None:
        if not self._stat_gain_item_icon_path:
            self._stat_gain_item_pixmap_cache = None
            return None
        if (
            self._stat_gain_item_pixmap_cache is not None
            and self._stat_gain_item_pixmap_cache[0] == self._stat_gain_item_icon_path
        ):
            return self._stat_gain_item_pixmap_cache[1]
        path = Path(self._stat_gain_item_icon_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return None
        self._stat_gain_item_pixmap_cache = (self._stat_gain_item_icon_path, pixmap)
        return pixmap

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

    def _logical_event_prompt_rect(self) -> QRect:
        return QRect(RIGHT_EVENT_PROMPT_RECT if self._flipped_x else LEFT_EVENT_PROMPT_RECT)

    def _scale_rect(self, rect: QRect) -> QRect:
        return QRect(
            round(rect.x() * self._render_scale),
            round(rect.y() * self._render_scale),
            round(rect.width() * self._render_scale),
            round(rect.height() * self._render_scale),
        )

    def _to_logical_point(self, point: QPoint) -> QPoint:
        return QPoint(
            round(point.x() / self._render_scale),
            round(point.y() / self._render_scale),
        )


def _stats_tooltip(state: PetState, species: Species) -> str:
    return "\n".join(
        [
            species.name,
            f"HP: {state.hp}",
            f"MP: {state.mp}",
            f"OFF: {state.offense}",
            f"DEF: {state.defense}",
            f"SPD: {state.speed}",
            f"INT: {state.brains}",
        ]
    )


def _pixel_text_width(text: str, scale: int) -> int:
    width = 0
    for char in text:
        width += (2 if char == " " else 4) * scale
    return max(0, width - scale)


def _draw_pixel_text(painter: QPainter, text: str, x: int, y: int, scale: int, color: QColor) -> None:
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    cursor_x = x
    for char in text:
        if char == " ":
            cursor_x += 2 * scale
            continue
        glyph = PIXEL_GLYPHS.get(char)
        if glyph is None:
            cursor_x += 4 * scale
            continue
        for row_index, row in enumerate(glyph):
            for column_index, enabled in enumerate(row):
                if enabled == "1":
                    painter.drawRect(cursor_x + column_index * scale, y + row_index * scale, scale, scale)
        cursor_x += 4 * scale


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


def _scaled_rect_from_bottom_center(rect: QRect, x_scale: float, y_scale: float) -> QRect:
    width = round(rect.width() * x_scale)
    height = round(rect.height() * y_scale)
    center_x = rect.center().x()
    return QRect(center_x - (width - 1) // 2, rect.bottom() - height + 1, width, height)


def _uses_static_scale_fallback(animation: SpriteAnimation | None) -> bool:
    return animation is not None and animation.frame_count <= 1 and Path(animation.path).suffix.casefold() != ".gif"
