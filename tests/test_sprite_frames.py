import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from digimon_pet.app.sprite_frames import sprite_frame_rect
from digimon_pet.app.sprite_runtime import SpriteAnimation


def test_sprite_frame_rect_infers_16px_grid_for_sprite_sheets_without_dimensions():
    app = QApplication.instance() or QApplication([])
    pixmap = QPixmap(48, 64)
    pixmap.fill()

    rect = sprite_frame_rect(pixmap, SpriteAnimation(path="unused.png", frame_count=1), 0)

    assert rect == QRect(0, 0, 16, 16)


def test_sprite_frame_rect_uses_grid_coordinates_for_later_frames():
    app = QApplication.instance() or QApplication([])
    pixmap = QPixmap(48, 64)
    pixmap.fill()

    rect = sprite_frame_rect(
        pixmap,
        SpriteAnimation(path="unused.png", frame_width=16, frame_height=16, frame_count=12),
        7,
    )

    assert rect == QRect(16, 32, 16, 16)
