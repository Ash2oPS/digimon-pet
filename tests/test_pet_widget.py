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


def test_pet_widget_flips_sprite_and_shadow_when_on_left_side():
    app = QApplication.instance() or QApplication([])
    widget = PetWidget()
    widget.set_flipped_x(True)
    widget._pixmap = QPixmap(SPRITE_TARGET_RECT.size())
    widget._pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(widget._pixmap)
    painter.fillRect(0, 20, 12, 12, QColor("#ff0000"))
    painter.end()

    image = QImage(widget.size(), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    widget.render(painter, QPoint(0, 0))
    painter.end()

    flipped_sprite_pixel = image.pixelColor(SPRITE_TARGET_RECT.right() - 4, SPRITE_TARGET_RECT.top() + 26)
    original_side_pixel = image.pixelColor(SPRITE_TARGET_RECT.left() + 4, SPRITE_TARGET_RECT.top() + 26)
    mirrored_shadow_pixel = image.pixelColor(
        SPRITE_TARGET_RECT.right() - 4 - SHADOW_OFFSET.x(),
        SPRITE_TARGET_RECT.top() + 26 + SHADOW_OFFSET.y(),
    )

    assert flipped_sprite_pixel.red() > 200
    assert original_side_pixel.alpha() == 0
    assert mirrored_shadow_pixel.alpha() > 0
    assert mirrored_shadow_pixel.red() < 10


def test_pending_lifecycle_effect_pulses_sprite_scale():
    app = QApplication.instance() or QApplication([])
    widget = PetWidget()
    widget.set_lifecycle_pending("evolution")
    widget._effect_elapsed_ms = 900

    target = widget._effect_target_rect()

    assert target.width() > SPRITE_TARGET_RECT.width()
    assert target.height() > SPRITE_TARGET_RECT.height()


def test_death_resolution_hides_sprite_immediately_and_emits_particles():
    app = QApplication.instance() or QApplication([])
    widget = PetWidget()
    widget._pixmap = QPixmap(SPRITE_TARGET_RECT.size())
    widget._pixmap.fill(QColor("#00ff00"))
    widget.start_lifecycle_resolution("death", lambda: None)
    widget._effect_elapsed_ms = 120

    image = QImage(widget.size(), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    widget.render(painter, QPoint(0, 0))
    painter.end()

    center_pixel = image.pixelColor(SPRITE_TARGET_RECT.center())

    assert center_pixel.green() < 50
    assert any(
        image.pixelColor(x, y).red() > 150
        for x in range(image.width())
        for y in range(image.height())
    )
