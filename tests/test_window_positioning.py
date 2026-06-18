from PySide6.QtCore import QRect, QSize

from digimon_pet.app.window_positioning import offset_window_position


def test_offset_window_position_moves_window_to_pet_right_when_space_is_available():
    screen = QRect(0, 0, 800, 600)
    pet = QRect(40, 260, 96, 96)
    window_size = QSize(240, 300)

    position = offset_window_position(pet, window_size, screen)

    assert position.x() == pet.x() + pet.width() + 16
    assert position.y() == pet.center().y() - window_size.height() // 2


def test_offset_window_position_moves_window_to_pet_left_near_right_edge():
    screen = QRect(0, 0, 800, 600)
    pet = QRect(704, 260, 80, 80)
    window_size = QSize(240, 300)

    position = offset_window_position(pet, window_size, screen)

    assert position.x() == pet.x() - window_size.width() - 16
    assert position.y() == pet.center().y() - window_size.height() // 2


def test_offset_window_position_clamps_window_inside_screen():
    screen = QRect(100, 50, 500, 400)
    pet = QRect(120, 360, 80, 80)
    window_size = QSize(260, 300)

    position = offset_window_position(pet, window_size, screen)

    assert position.x() == pet.x() + pet.width() + 16
    assert position.y() == screen.y() + screen.height() - window_size.height()
