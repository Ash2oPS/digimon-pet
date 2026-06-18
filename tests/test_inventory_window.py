import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QPushButton

from digimon_pet.app.inventory_window import InventoryItem, InventorySlotWidget, InventoryWindow
from digimon_pet.app.main_window import PetWindow
from digimon_pet.domain.items import MONZAEMON_HEAD_ID
from digimon_pet.domain.models import GrowthStage, PetState
from digimon_pet.storage import debug_settings
from digimon_pet.storage import save_store


@pytest.fixture(autouse=True)
def default_initial_baby_choice(tmp_path, monkeypatch):
    monkeypatch.setattr(save_store, "SAVE_PATH", tmp_path / "pet_save.json")
    monkeypatch.setattr(save_store, "LEGACY_SAVE_PATH", tmp_path / ".local" / "pet_save.json")
    monkeypatch.setattr(debug_settings, "DEBUG_SETTINGS_PATH", tmp_path / "debug_settings.json")
    monkeypatch.setattr(
        debug_settings,
        "LEGACY_DEBUG_SETTINGS_PATH",
        tmp_path / ".local" / "debug_settings.json",
    )
    monkeypatch.setattr(
        PetWindow,
        "_get_baby_choice",
        lambda self, labels: ("Botamon", True),
    )


def test_inventory_window_starts_with_empty_grid():
    app = QApplication.instance() or QApplication([])

    window = InventoryWindow(slot_count=24)
    slots = window.findChildren(InventorySlotWidget)

    assert window.windowTitle() == "Inventaire"
    assert len(slots) == 24
    assert all(slot.item is None for slot in slots)
    assert all(slot.property("empty") is True for slot in slots)


def test_inventory_window_can_render_future_items():
    app = QApplication.instance() or QApplication([])
    window = InventoryWindow(slot_count=4)

    window.set_items([InventoryItem(id="meat", name="Meat", quantity=3)])
    slots = window.findChildren(InventorySlotWidget)

    assert slots[0].item == InventoryItem(id="meat", name="Meat", quantity=3)
    assert slots[0].toolTip() == "Meat x3"
    assert slots[0].property("empty") is False
    assert slots[0].property("selected") is True
    assert slots[1].item is None
    assert slots[1].property("empty") is True


def test_inventory_window_selects_items_on_click_and_uses_selected_item():
    app = QApplication.instance() or QApplication([])
    used: list[str] = []
    window = InventoryWindow(slot_count=4, item_used=used.append)
    window.set_items(
        [
            InventoryItem(id="meat", name="Meat", quantity=3),
            InventoryItem(id="disk", name="Champion Disk", quantity=1),
        ]
    )
    slots = window.findChildren(InventorySlotWidget)
    use_button = window.findChild(QPushButton)

    _left_click(slots[1])
    assert slots[0].property("selected") is False
    assert slots[1].property("selected") is True
    assert window._details_name.text() == "Champion Disk"
    assert use_button is not None
    assert use_button.isEnabled()

    use_button.click()

    assert used == ["disk"]


def test_inventory_window_clears_selection_when_empty_slot_is_clicked():
    app = QApplication.instance() or QApplication([])
    window = InventoryWindow(slot_count=4)
    window.set_items([InventoryItem(id="meat", name="Meat", quantity=3)])
    slots = window.findChildren(InventorySlotWidget)

    _left_click(slots[1])

    assert slots[0].property("selected") is False
    assert window._details_name.text() == "Aucun objet"
    assert window.findChild(QPushButton).isEnabled() is False


def test_pet_window_opens_inventory_window():
    app = QApplication.instance() or QApplication([])
    window = PetWindow(overlay=True, debug=False)

    window._open_inventory()

    assert window._inventory_window is not None
    assert window._inventory_window.windowTitle() == "Inventaire"


def test_pet_window_grants_monzaemon_head_on_launch():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=False)

    assert window._state.inventory[MONZAEMON_HEAD_ID] == 1


def test_pet_window_uses_monzaemon_head_from_inventory():
    app = QApplication.instance() or QApplication([])
    save_store.save_pet_state(
        PetState(
            "numemon",
            GrowthStage.CHAMPION,
            inventory={MONZAEMON_HEAD_ID: 1},
        )
    )
    window = PetWindow(overlay=True, debug=False)
    window._open_inventory()

    window._use_inventory_item(MONZAEMON_HEAD_ID)

    assert window._state.species_id == "monzaemon"
    assert window._state.inventory == {}


def _left_click(widget: InventorySlotWidget) -> None:
    event = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(8, 8),
        QPointF(8, 8),
        QPointF(8, 8),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.mouseReleaseEvent(event)
