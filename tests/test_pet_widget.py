import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from digimon_pet.app.pet_widget import PetWidget, SHADOW_OFFSET, SPRITE_TARGET_RECT
from digimon_pet.app.sprite_runtime import SpriteAnimation


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


def test_pet_widget_reuses_prepared_frame_and_shadow_between_paints(monkeypatch):
    app = QApplication.instance() or QApplication([])
    widget = PetWidget()
    widget._pixmap = QPixmap(8, 8)
    widget._pixmap.fill(QColor("#ff0000"))

    calls = {"sprite": 0, "shadow": 0}
    original_sprite = widget._sprite_pixmap
    original_shadow = widget._create_shadow_image

    def count_sprite(*args, **kwargs):
        calls["sprite"] += 1
        return original_sprite(*args, **kwargs)

    def count_shadow(*args, **kwargs):
        calls["shadow"] += 1
        return original_shadow(*args, **kwargs)

    monkeypatch.setattr(widget, "_sprite_pixmap", count_sprite)
    monkeypatch.setattr(widget, "_create_shadow_image", count_shadow)

    _render_widget(widget)
    _render_widget(widget)

    assert calls == {"sprite": 1, "shadow": 1}


def test_sprite_animation_timer_is_two_and_a_half_times_slower_than_sheet_fps():
    app = QApplication.instance() or QApplication([])
    widget = PetWidget()

    widget._configure_animation_timer(SpriteAnimation(path="unused.png", frame_count=2, fps=10))

    assert widget._animation_timer.interval() == 250


def test_pet_widget_slices_multi_row_sprite_sheets():
    app = QApplication.instance() or QApplication([])
    widget = PetWidget()
    pixmap = QPixmap(48, 64)
    pixmap.fill(Qt.GlobalColor.transparent)

    rects = widget._build_frame_rects(
        pixmap,
        SpriteAnimation(
            path="unused.png",
            frame_width=16,
            frame_height=16,
            frame_count=12,
            frame_indices=(0, 6, 10),
        ),
    )

    assert rects == [
        QRect(0, 0, 16, 16),
        QRect(0, 32, 16, 16),
        QRect(16, 48, 16, 16),
    ]


def test_pet_widget_slices_sheet_even_when_frame_count_is_static():
    app = QApplication.instance() or QApplication([])
    widget = PetWidget()
    pixmap = QPixmap(48, 64)
    pixmap.fill(Qt.GlobalColor.transparent)

    rects = widget._build_frame_rects(
        pixmap,
        SpriteAnimation(
            path="unused.png",
            frame_width=16,
            frame_height=16,
            frame_count=1,
            frame_indices=(0,),
        ),
    )

    assert rects == [QRect(0, 0, 16, 16)]


def test_static_png_animation_alternates_scale_from_bottom_center():
    app = QApplication.instance() or QApplication([])
    widget = PetWidget()
    widget._configure_animation_timer(SpriteAnimation(path="unused.png", frame_count=1, fps=10))

    normal_target = widget._effect_target_rect()
    widget._advance_frame()
    scaled_target = widget._effect_target_rect()

    assert widget._animation_timer.interval() == 250
    assert normal_target == SPRITE_TARGET_RECT
    assert scaled_target.width() == SPRITE_TARGET_RECT.width()
    assert scaled_target.height() == round(SPRITE_TARGET_RECT.height() * 0.9)
    assert scaled_target.center().x() == SPRITE_TARGET_RECT.center().x()
    assert scaled_target.bottom() == SPRITE_TARGET_RECT.bottom()


def test_static_gif_does_not_use_scale_fallback():
    app = QApplication.instance() or QApplication([])
    widget = PetWidget()

    widget._configure_animation_timer(SpriteAnimation(path="unused.gif", frame_count=1, fps=10))

    assert not widget._animation_timer.isActive()


def test_pending_lifecycle_effect_pulses_sprite_scale():
    app = QApplication.instance() or QApplication([])
    widget = PetWidget()
    widget.set_lifecycle_pending("evolution")
    widget._effect_elapsed_ms = 900

    target = widget._effect_target_rect()

    assert target.width() > SPRITE_TARGET_RECT.width()
    assert target.height() > SPRITE_TARGET_RECT.height()


def test_pending_lifecycle_event_renders_clickable_bubble():
    app = QApplication.instance() or QApplication([])
    widget = PetWidget()
    widget.set_lifecycle_pending("evolution")

    image = QImage(widget.size(), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    widget.render(painter, QPoint(0, 0))
    painter.end()

    bubble_center = widget.event_prompt_rect().center()

    assert widget.event_prompt_kind() == "evolution"
    assert widget.is_event_prompt_at(bubble_center)
    assert not widget.is_event_prompt_at(SPRITE_TARGET_RECT.center())
    assert image.pixelColor(bubble_center).alpha() > 0


def test_pet_widget_scales_canvas_and_hitboxes():
    app = QApplication.instance() or QApplication([])
    widget = PetWidget()
    widget.set_render_scale(1.5)
    widget.set_lifecycle_pending("evolution")

    prompt_center = widget.event_prompt_rect().center()
    pet_center = QPoint(round(SPRITE_TARGET_RECT.center().x() * 1.5), round(SPRITE_TARGET_RECT.center().y() * 1.5))

    assert widget.size().width() == 192
    assert widget.size().height() == 192
    assert widget.is_event_prompt_at(prompt_center)
    assert widget.is_pet_body_at(pet_center)


def test_event_bubble_switches_side_with_pet_screen_position():
    app = QApplication.instance() or QApplication([])
    widget = PetWidget()
    widget.set_lifecycle_pending("evolution")

    right_screen_rect = widget.event_prompt_rect()
    widget.set_flipped_x(True)
    left_screen_rect = widget.event_prompt_rect()

    assert right_screen_rect.center().x() < widget.width() // 2
    assert left_screen_rect.center().x() > widget.width() // 2
    assert widget.is_event_prompt_at(left_screen_rect.center())
    assert not widget.is_event_prompt_at(right_screen_rect.center())


def test_event_bubble_sits_near_outer_canvas_edges():
    app = QApplication.instance() or QApplication([])
    widget = PetWidget()
    widget.set_lifecycle_pending("evolution")

    right_screen_rect = widget.event_prompt_rect()
    widget.set_flipped_x(True)
    left_screen_rect = widget.event_prompt_rect()

    assert right_screen_rect.left() <= 4
    assert left_screen_rect.right() >= widget.width() - 5


def test_event_bubble_tail_points_toward_pet_body():
    app = QApplication.instance() or QApplication([])
    widget = PetWidget()
    widget.set_lifecycle_pending("evolution")

    left_image = _render_widget(widget)
    left_rect = widget.event_prompt_rect()

    widget.set_flipped_x(True)
    right_image = _render_widget(widget)
    right_rect = widget.event_prompt_rect()

    assert left_image.pixelColor(left_rect.right() + 2, left_rect.bottom() + 3).alpha() > 0
    assert left_image.pixelColor(left_rect.left() - 2, left_rect.bottom() + 3).alpha() == 0
    assert right_image.pixelColor(right_rect.left() - 2, right_rect.bottom() + 3).alpha() > 0
    assert right_image.pixelColor(right_rect.right() + 2, right_rect.bottom() + 3).alpha() == 0


def test_death_event_bubble_uses_skull_icon():
    app = QApplication.instance() or QApplication([])
    widget = PetWidget()
    widget.set_lifecycle_pending("death")

    image = _render_widget(widget)

    icon_center = widget.event_prompt_rect().center()
    skull_pixel = image.pixelColor(icon_center)

    assert skull_pixel.red() > 200
    assert skull_pixel.green() > 200
    assert skull_pixel.blue() > 180


def test_secondary_event_prompt_renders_without_lifecycle_effect():
    app = QApplication.instance() or QApplication([])
    widget = PetWidget()
    widget.set_secondary_event_prompt("meat")

    image = _render_widget(widget)
    icon_center = widget.event_prompt_rect().center()

    assert widget.event_prompt_kind() == "secondary_meat"
    assert widget._effect_name is None
    assert image.pixelColor(icon_center).alpha() > 0


def test_secondary_event_prompt_bounces_sprite_without_moving_bubble():
    app = QApplication.instance() or QApplication([])
    widget = PetWidget()
    widget.set_secondary_event_prompt("meat")
    bubble_rect = widget.event_prompt_rect()

    for _index in range(8):
        widget._advance_secondary_event_prompt()

    target = widget._effect_target_rect()

    assert target.top() < SPRITE_TARGET_RECT.top()
    assert target.size() == SPRITE_TARGET_RECT.size()
    assert widget.event_prompt_rect() == bubble_rect


def test_secondary_item_prompt_uses_dialog_bubble_with_question_mark():
    app = QApplication.instance() or QApplication([])
    widget = PetWidget()
    widget.set_secondary_event_prompt("item")

    image = _render_widget(widget)
    prompt_rect = widget.event_prompt_rect()
    icon_center = prompt_rect.center()

    assert widget.event_prompt_kind() == "secondary_item"
    assert image.pixelColor(icon_center).alpha() > 0
    assert image.pixelColor(prompt_rect.left() + 3, prompt_rect.top() + 3).alpha() > 0
    assert image.pixelColor(prompt_rect.right() - 3, prompt_rect.bottom() - 3).alpha() > 0
    assert image.pixelColor(icon_center).red() > 220
    assert image.pixelColor(icon_center).green() > 220


def test_clearing_lifecycle_pending_hides_event_bubble():
    app = QApplication.instance() or QApplication([])
    widget = PetWidget()
    widget.set_lifecycle_pending("death")

    widget.set_lifecycle_pending(None)

    assert widget.event_prompt_kind() is None
    assert not widget.is_event_prompt_at(QPoint(64, 24))


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


def test_evolution_resolution_calls_reveal_before_finish():
    app = QApplication.instance() or QApplication([])
    widget = PetWidget()
    events = []
    widget.start_lifecycle_resolution("evolution", lambda: events.append("finished"), lambda: events.append("revealed"))

    for _index in range(24):
        widget._advance_effect()

    assert events == ["revealed"]
    assert widget._effect_name == "evolution"


def test_new_badge_renders_above_pet():
    app = QApplication.instance() or QApplication([])
    widget = PetWidget()
    widget.trigger_new_badge()

    image = QImage(widget.size(), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    widget.render(painter, QPoint(0, 0))
    painter.end()

    assert widget._new_badge_elapsed_ms > 0
    assert any(
        image.pixelColor(x, y).alpha() > 0
        for x in range(30, 98)
        for y in range(2, 28)
    )


def test_stat_gain_text_renders_in_blue():
    app = QApplication.instance() or QApplication([])
    widget = PetWidget()
    widget.trigger_stat_gain_text({"hp": 100, "offense": 10})

    image = _render_widget(widget)

    assert widget._stat_gain_elapsed_ms > 0
    assert widget._stat_gain_labels == ["+100 HP", "+10 OFF"]
    assert any(
        pixel.blue() > 150 and pixel.red() < 120
        for x in range(12, 116)
        for y in range(0, 44)
        if (pixel := image.pixelColor(x, y)).alpha() > 0
    )


def test_item_gain_text_keeps_icon_separate_from_label():
    app = QApplication.instance() or QApplication([])
    widget = PetWidget()

    widget.trigger_stat_gain_text(
        {},
        item_gains=1,
        item_gain_icon_path="assets/items/monzaemon_head.png",
    )

    assert widget._stat_gain_labels == []
    assert widget._stat_gain_item_icon_path == "assets/items/monzaemon_head.png"


def _render_widget(widget: PetWidget) -> QImage:
    image = QImage(widget.size(), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    widget.render(painter, QPoint(0, 0))
    painter.end()
    return image
