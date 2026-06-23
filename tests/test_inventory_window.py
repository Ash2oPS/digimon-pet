import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
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
        lambda self, baby_ids: ("botamon", True),
    )


def test_inventory_window_starts_with_empty_grid():
    app = QApplication.instance() or QApplication([])

    window = InventoryWindow(slot_count=24)
    slots = window.findChildren(InventorySlotWidget)

    assert window.windowTitle() == "Inventory"
    assert len(slots) == 24
    assert all(slot.item is None for slot in slots)
    assert all(slot.property("empty") is True for slot in slots)


def test_inventory_window_can_render_future_items():
    app = QApplication.instance() or QApplication([])
    window = InventoryWindow(slot_count=4)

    window.set_items([InventoryItem(id="meat", name="Meat", quantity=3)])
    slots = window.findChildren(InventorySlotWidget)

    assert slots[0].item == InventoryItem(id="meat", name="Meat", quantity=3)
    assert slots[0].toolTip() == "Meat x3\nDouble-click to use"
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


def test_inventory_window_shows_count_and_filters_items_by_type():
    app = QApplication.instance() or QApplication([])
    window = InventoryWindow(slot_count=6)

    window.set_items(
        [
            InventoryItem(id="meat", name="Meat", quantity=3, item_type="consumable"),
            InventoryItem(id="disk", name="Champion Disk", quantity=1, item_type="evolution"),
        ]
    )
    window.set_filter("evolution")
    slots = window.findChildren(InventorySlotWidget)

    assert window._inventory_count.text() == "2 / 6"
    assert slots[0].item is not None
    assert slots[0].item.id == "disk"
    assert slots[1].item is None


def test_inventory_window_compacts_unused_empty_storage_slots():
    app = QApplication.instance() or QApplication([])
    window = InventoryWindow(slot_count=12)

    window.set_items(
        [
            InventoryItem(id="meat", name="Meat", quantity=3),
            InventoryItem(id="fish", name="DigiFish", quantity=1),
        ]
    )
    slots = window.findChildren(InventorySlotWidget)

    assert slots[0].isHidden() is False
    assert slots[1].isHidden() is False
    assert slots[5].isHidden() is False
    assert slots[6].isHidden() is True


def test_inventory_slot_cards_show_name_and_type_chip():
    app = QApplication.instance() or QApplication([])
    window = InventoryWindow(slot_count=4)

    window.set_items([InventoryItem(id="fish", name="DigiFish", item_type="consumable")])
    slots = window.findChildren(InventorySlotWidget)

    assert slots[0]._name_label.text() == "DigiFish"
    assert slots[0]._type_label.text() == "STAT"
    assert slots[0]._quantity_label.text() == "1"
    assert slots[0]._quantity_label.isHidden() is False


def test_inventory_window_disables_unusable_selected_item_with_reason():
    app = QApplication.instance() or QApplication([])
    window = InventoryWindow(slot_count=4)

    window.set_items(
        [
            InventoryItem(
                id="disk",
                name="Champion Disk",
                item_type="evolution",
                usable=False,
                unavailable_reason="Requires Numemon.",
                description="Makes Numemon digivolve into Monzaemon.",
            )
        ]
    )

    assert window._details_status.text() == "Evolution - unavailable"
    assert window._details_description.text() == "Makes Numemon digivolve into Monzaemon."
    assert not hasattr(window, "_details_effect")
    assert window.findChild(QPushButton).isEnabled() is False


def test_inventory_window_uses_selected_item_with_enter_key():
    app = QApplication.instance() or QApplication([])
    used: list[str] = []
    window = InventoryWindow(slot_count=4, item_used=used.append)
    window.set_items([InventoryItem(id="meat", name="Meat", quantity=1)])

    window.keyPressEvent(
        QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Return,
            Qt.KeyboardModifier.NoModifier,
        )
    )

    assert used == ["meat"]


def test_inventory_window_clears_selection_when_empty_slot_is_clicked():
    app = QApplication.instance() or QApplication([])
    window = InventoryWindow(slot_count=4)
    window.set_items([InventoryItem(id="meat", name="Meat", quantity=3)])
    slots = window.findChildren(InventorySlotWidget)

    _left_click(slots[1])

    assert slots[0].property("selected") is False
    assert window._details_name.text() == "No item"
    assert window.findChild(QPushButton).isEnabled() is False


def test_pet_window_opens_inventory_window():
    app = QApplication.instance() or QApplication([])
    window = PetWindow(overlay=True, debug=False)

    window._open_inventory()

    assert window._inventory_window is not None
    assert window._inventory_window.windowTitle() == "Inventory"


def test_pet_window_does_not_grant_monzaemon_head_on_launch():
    app = QApplication.instance() or QApplication([])

    window = PetWindow(overlay=True, debug=False)

    assert MONZAEMON_HEAD_ID not in window._state.inventory


def test_pet_window_inventory_skips_unknown_item_ids():
    app = QApplication.instance() or QApplication([])
    window = PetWindow(overlay=True, debug=False)
    window._state.inventory = {MONZAEMON_HEAD_ID: 1, "deleted_item": 2}

    assert [item.id for item in window._inventory_items()] == [MONZAEMON_HEAD_ID]


def test_pet_window_inventory_marks_blocked_evolution_items():
    app = QApplication.instance() or QApplication([])
    save_store.save_pet_state(
        PetState(
            "agumon",
            GrowthStage.ROOKIE,
            inventory={MONZAEMON_HEAD_ID: 1},
        )
    )
    window = PetWindow(overlay=True, debug=False)

    items = window._inventory_items()

    assert items[0].item_type == "evolution"
    assert items[0].usable is False
    assert items[0].unavailable_reason == "Requires Numemon."


def test_pet_window_queues_monzaemon_head_evolution_from_inventory():
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

    assert window._state.species_id == "numemon"
    assert window._state.inventory == {MONZAEMON_HEAD_ID: 1}
    assert window._pending_lifecycle_kind == "evolution"
    assert window._pet_widget.event_prompt_kind() == "evolution"


def test_pet_window_resolves_queued_monzaemon_head_evolution():
    app = QApplication.instance() or QApplication([])
    save_store.save_pet_state(
        PetState(
            "numemon",
            GrowthStage.CHAMPION,
            inventory={MONZAEMON_HEAD_ID: 1},
        )
    )
    window = PetWindow(overlay=True, debug=False)

    window._use_inventory_item(MONZAEMON_HEAD_ID)
    window._resolve_lifecycle_now()

    assert window._state.species_id == "monzaemon"
    assert window._state.inventory == {}


def test_pet_window_golden_poop_evolves_any_digimon_to_sukamon():
    app = QApplication.instance() or QApplication([])
    save_store.save_pet_state(
        PetState(
            "agumon",
            GrowthStage.ROOKIE,
            inventory={"golden_poop": 1},
        )
    )
    window = PetWindow(overlay=True, debug=False)

    window._use_inventory_item("golden_poop")
    window._resolve_lifecycle_now()

    assert window._state.species_id == "sukamon"
    assert window._state.stage == GrowthStage.CHAMPION
    assert window._state.inventory == {}


def test_pet_window_consumable_item_applies_stat_effect_immediately():
    app = QApplication.instance() or QApplication([])
    save_store.save_pet_state(
        PetState(
            "agumon",
            GrowthStage.ROOKIE,
            offense=30,
            inventory={"digimeat": 1},
        )
    )
    window = PetWindow(overlay=True, debug=False)

    window._use_inventory_item("digimeat")

    assert window._state.offense == 55
    assert window._state.inventory == {}
    assert window._pending_inventory_item_id is None
    assert window._pending_lifecycle_kind is None
    assert window._pet_widget._stat_gain_labels == ["+25 OFF"]


def test_pet_window_instant_death_item_queues_death_before_consuming_item():
    app = QApplication.instance() or QApplication([])
    save_store.save_pet_state(
        PetState(
            "agumon",
            GrowthStage.ROOKIE,
            inventory={"digigun": 1},
        )
    )
    window = PetWindow(overlay=True, debug=False)

    window._use_inventory_item("digigun")

    assert window._state.species_id == "agumon"
    assert window._state.inventory == {"digigun": 1}
    assert window._pending_inventory_item_id == "digigun"
    assert window._pending_lifecycle_kind == "death"
    assert window._pet_widget.event_prompt_kind() == "death"


def test_pet_window_resolves_queued_instant_death_item():
    app = QApplication.instance() or QApplication([])
    save_store.save_pet_state(
        PetState(
            "agumon",
            GrowthStage.ROOKIE,
            inventory={"digigun": 1},
        )
    )
    window = PetWindow(overlay=True, debug=False)
    window._auto_rebirth_random = True

    window._use_inventory_item("digigun")
    window._confirm_pending_lifecycle()
    window._finish_lifecycle_resolution()

    assert window._state.inventory == {}
    assert window._pending_inventory_item_id is None
    assert window._pending_lifecycle_kind is None
    assert window._state.needs_rebirth_choice is False
    assert window._state.stage == GrowthStage.BABY


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
