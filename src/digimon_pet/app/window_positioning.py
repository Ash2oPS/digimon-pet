from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize


DEFAULT_INTERFACE_GAP = 16


def offset_window_position(
    pet_geometry: QRect,
    window_size: QSize,
    screen_geometry: QRect,
    gap: int = DEFAULT_INTERFACE_GAP,
) -> QPoint:
    right_space = screen_geometry.x() + screen_geometry.width() - (pet_geometry.x() + pet_geometry.width()) - gap
    left_space = pet_geometry.x() - screen_geometry.x() - gap

    if right_space >= window_size.width() or right_space >= left_space:
        x = pet_geometry.x() + pet_geometry.width() + gap
    else:
        x = pet_geometry.x() - window_size.width() - gap

    y = pet_geometry.center().y() - window_size.height() // 2
    return QPoint(
        _clamp(x, screen_geometry.x(), screen_geometry.x() + screen_geometry.width() - window_size.width()),
        _clamp(y, screen_geometry.y(), screen_geometry.y() + screen_geometry.height() - window_size.height()),
    )


def _clamp(value: int, minimum: int, maximum: int) -> int:
    if maximum < minimum:
        return minimum
    return max(minimum, min(value, maximum))
