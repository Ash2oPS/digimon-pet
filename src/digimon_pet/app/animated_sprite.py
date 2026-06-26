from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QPainter, QPixmap

from digimon_pet.app.sprite_frames import sprite_frame_rect
from digimon_pet.app.sprite_runtime import SpriteAnimation, resolve_sprite_animation
from digimon_pet.domain.models import PetState, Species
from digimon_pet.paths import PROJECT_ROOT

SPRITESHEET_ANIMATION_SPEED_DIVISOR = 2.5


class IdleSpriteSheet:
    def __init__(self, pixmap: QPixmap, animation: SpriteAnimation) -> None:
        self._pixmap = pixmap
        self._animation = animation
        self._cursor = 0

    @property
    def current_frame_index(self) -> int:
        return self._frame_indices[self._cursor]

    @property
    def interval_ms(self) -> int:
        return sprite_animation_interval_ms(self._animation)

    @property
    def is_animated(self) -> bool:
        return len(self._frame_indices) > 1

    def advance(self) -> None:
        if not self.is_animated:
            return
        self._cursor = (self._cursor + 1) % len(self._frame_indices)

    def frame_pixmap(self, *, silhouette: bool = False) -> QPixmap:
        frame = self._pixmap.copy(self._source_rect())
        return _silhouette(frame) if silhouette else frame

    def draw(self, painter: QPainter, target: QRect, *, silhouette: bool = False) -> None:
        if silhouette:
            painter.drawPixmap(target, self.frame_pixmap(silhouette=True))
            return
        painter.drawPixmap(target, self._pixmap, self._source_rect())

    @property
    def _frame_indices(self) -> tuple[int, ...]:
        return self._animation.frame_indices or (0,)

    def _source_rect(self) -> QRect:
        return sprite_frame_rect(self._pixmap, self._animation, self.current_frame_index) or QRect()


def idle_sprite_for_species(species: Species, manifest: dict, *, project_root: Path | None = None) -> IdleSpriteSheet | None:
    state = PetState(species_id=species.id, stage=species.stage, current_action="idle")
    animation = resolve_sprite_animation(state, species, manifest)
    if animation is None:
        return None
    root = PROJECT_ROOT if project_root is None else project_root
    path = root / Path(animation.path)
    if not path.exists():
        return None
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None
    return IdleSpriteSheet(pixmap, animation)


def idle_animation_interval_for_species(species: Species, manifest: dict) -> int | None:
    state = PetState(species_id=species.id, stage=species.stage, current_action="idle")
    animation = resolve_sprite_animation(state, species, manifest)
    return sprite_animation_interval_ms(animation) if animation is not None else None


def sprite_animation_interval_ms(animation: SpriteAnimation) -> int:
    return max(16, round((1000 / max(1, animation.fps)) * SPRITESHEET_ANIMATION_SPEED_DIVISOR))


def _silhouette(pixmap: QPixmap) -> QPixmap:
    result = QPixmap(pixmap.size())
    result.fill(QColor(0, 0, 0, 0))
    painter = QPainter(result)
    painter.drawPixmap(0, 0, pixmap)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(result.rect(), QColor("#02040a"))
    painter.end()
    return result
