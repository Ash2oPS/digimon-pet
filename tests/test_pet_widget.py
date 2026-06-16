import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from digimon_pet.app.pet_widget import PetWidget, SHADOW_RECT


def test_pet_widget_draws_shadow_behind_sprite():
    app = QApplication.instance() or QApplication([])
    widget = PetWidget()
    widget._pixmap = QPixmap(8, 8)
    widget._pixmap.fill(Qt.GlobalColor.transparent)

    image = QImage(widget.size(), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    widget.render(painter, QPoint(0, 0))
    painter.end()

    shadow_pixel = image.pixelColor(SHADOW_RECT.center())

    assert shadow_pixel.alpha() > 0
