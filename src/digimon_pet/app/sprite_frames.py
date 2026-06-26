from __future__ import annotations

from PySide6.QtCore import QRect
from PySide6.QtGui import QPixmap

from digimon_pet.app.sprite_runtime import SpriteAnimation


def sprite_frame_rect(pixmap: QPixmap, animation: SpriteAnimation, frame_index: int = 0) -> QRect | None:
    if pixmap.isNull():
        return None
    frame_width = animation.frame_width or _inferred_frame_width(pixmap, animation)
    frame_height = animation.frame_height or _inferred_frame_height(pixmap, animation)
    if frame_width <= 0 or frame_height <= 0:
        return None

    columns = max(1, pixmap.width() // frame_width)
    rows = max(1, pixmap.height() // frame_height)
    max_frames = min(max(1, animation.frame_count), columns * rows)
    index = min(max(0, frame_index), max_frames - 1)
    return QRect((index % columns) * frame_width, (index // columns) * frame_height, frame_width, frame_height)


def sprite_frame_rects(pixmap: QPixmap, animation: SpriteAnimation) -> list[QRect]:
    if pixmap.isNull():
        return []
    return [
        rect
        for index in animation.frame_indices
        if (rect := sprite_frame_rect(pixmap, animation, index)) is not None
    ]


def _inferred_frame_width(pixmap: QPixmap, animation: SpriteAnimation) -> int:
    horizontal_width = _horizontal_band_frame_width(pixmap, animation)
    if horizontal_width is not None:
        return horizontal_width
    if _looks_like_16px_grid(pixmap):
        return 16
    return max(1, pixmap.width() // max(1, animation.frame_count))


def _inferred_frame_height(pixmap: QPixmap, animation: SpriteAnimation) -> int:
    if _horizontal_band_frame_width(pixmap, animation) is not None:
        return pixmap.height()
    if _looks_like_16px_grid(pixmap):
        return 16
    return pixmap.height()


def _horizontal_band_frame_width(pixmap: QPixmap, animation: SpriteAnimation) -> int | None:
    if animation.frame_count <= 1 or pixmap.width() % animation.frame_count != 0:
        return None
    frame_width = pixmap.width() // animation.frame_count
    if frame_width < 16:
        return None
    return frame_width


def _looks_like_16px_grid(pixmap: QPixmap) -> bool:
    if pixmap.width() == 48 and pixmap.height() % 16 == 0 and pixmap.height() > 16:
        return True
    return pixmap.height() == 16 and pixmap.width() % 16 == 0 and pixmap.width() > 16
