import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from digimon_pet.app.pet_widget import PetWidget, SHADOW_OFFSET, SPRITE_TARGET_RECT


def test_pet_widget_draws_shadow_from_sprite_alpha():
    app = QApplication.instance() or QApplication([])
    widget = PetWidget()
    widget._pixmap = QPixmap(8, 8)
    widget._pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(widget._pixmap)
    painter.fillRect(1, 1, 1, 1, QColor("#ff0000"))
    painter.end()

    image = QImage(widget.size(), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    widget.render(painter, QPoint(0, 0))
    painter.end()

    shadow_pixel = image.pixelColor(
        SPRITE_TARGET_RECT.left() + SHADOW_OFFSET.x() + 18,
        SPRITE_TARGET_RECT.top() + SHADOW_OFFSET.y() + 18,
    )
    transparent_pixel = image.pixelColor(
        SPRITE_TARGET_RECT.left() + SHADOW_OFFSET.x() + 80,
        SPRITE_TARGET_RECT.top() + SHADOW_OFFSET.y() + 80,
    )

    assert shadow_pixel.alpha() > 0
    assert shadow_pixel.red() < 10
    assert transparent_pixel.alpha() == 0
