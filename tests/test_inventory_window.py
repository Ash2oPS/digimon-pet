import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from digimon_pet.app.inventory_window import InventoryItem, InventorySlotWidget, InventoryWindow
from digimon_pet.app.main_window import PetWindow
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
    assert slots[1].item is None
    assert slots[1].property("empty") is True


def test_pet_window_opens_inventory_window():
    app = QApplication.instance() or QApplication([])
    window = PetWindow(overlay=True, debug=False)

    window._open_inventory()

    assert window._inventory_window is not None
    assert window._inventory_window.windowTitle() == "Inventaire"
