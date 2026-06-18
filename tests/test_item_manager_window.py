import os
import json
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFileDialog, QPushButton

from digimon_pet.app.item_manager_window import ItemManagerWindow, validate_item_catalog
from digimon_pet.domain.items import (
    EvolutionItemEffect,
    ItemCatalog,
    ItemDefinition,
    ItemPoolEntry,
    ItemType,
)
from digimon_pet.domain.models import GrowthStage, Species


def species_map() -> dict[str, Species]:
    return {
        "agumon": Species("agumon", "Agumon", GrowthStage.ROOKIE),
        "numemon": Species("numemon", "Numemon", GrowthStage.CHAMPION),
        "monzaemon": Species("monzaemon", "Monzaemon", GrowthStage.ULTIMATE),
    }


def valid_catalog() -> ItemCatalog:
    item = ItemDefinition(
        id="monzaemon_head",
        name="Monzaemon's Head",
        description="Forces Numemon to evolve into Monzaemon.",
        type=ItemType.EVOLUTION,
        icon_path="assets/items/monzaemon_head.png",
        evolution=EvolutionItemEffect(
            target_species_id="monzaemon",
            required_species_ids=("numemon",),
        ),
    )
    return ItemCatalog(
        items={item.id: item},
        pools={"secondary_event": (ItemPoolEntry(item_id=item.id, weight=1),)},
    )


def two_item_catalog() -> ItemCatalog:
    first = ItemDefinition(
        id="a",
        name="A",
        description="First item.",
        type=ItemType.MISC,
    )
    second = ItemDefinition(
        id="b",
        name="B",
        description="Second item.",
        type=ItemType.MISC,
    )
    return ItemCatalog(
        items={first.id: first, second.id: second},
        pools={
            "secondary_event": (
                ItemPoolEntry(item_id=first.id, weight=1),
                ItemPoolEntry(item_id=second.id, weight=2),
            )
        },
    )


def mixed_drop_catalog() -> ItemCatalog:
    normal_a = ItemDefinition(
        id="normal_a",
        name="Normal A",
        description="First normal item.",
        type=ItemType.MISC,
    )
    normal_b = ItemDefinition(
        id="normal_b",
        name="Normal B",
        description="Second normal item.",
        type=ItemType.MISC,
    )
    evo_a = ItemDefinition(
        id="evo_a",
        name="Evolution A",
        description="First evolution item.",
        type=ItemType.EVOLUTION,
        evolution=EvolutionItemEffect(target_species_id="monzaemon"),
    )
    evo_b = ItemDefinition(
        id="evo_b",
        name="Evolution B",
        description="Second evolution item.",
        type=ItemType.EVOLUTION,
        evolution=EvolutionItemEffect(target_species_id="monzaemon"),
    )
    return ItemCatalog(
        items={
            normal_a.id: normal_a,
            normal_b.id: normal_b,
            evo_a.id: evo_a,
            evo_b.id: evo_b,
        },
        pools={
            "secondary_event": (
                ItemPoolEntry(item_id=normal_a.id, weight=2),
                ItemPoolEntry(item_id=normal_b.id, weight=7),
                ItemPoolEntry(item_id=evo_a.id, weight=99),
                ItemPoolEntry(item_id=evo_b.id, weight=1),
            )
        },
    )


def test_validate_item_catalog_rejects_duplicate_ids():
    item = valid_catalog().items["monzaemon_head"]

    errors = validate_item_catalog([item, item], {}, species_map(), Path.cwd())

    assert "Duplicate item id: monzaemon_head" in errors


def test_validate_item_catalog_rejects_unknown_evolution_target():
    item = ItemDefinition(
        id="bad_disk",
        name="Bad Disk",
        description="Invalid evolution target.",
        type=ItemType.EVOLUTION,
        evolution=EvolutionItemEffect(target_species_id="missingmon"),
    )

    errors = validate_item_catalog([item], {}, species_map(), Path.cwd())

    assert "bad_disk targets unknown species: missingmon" in errors


def test_validate_item_catalog_rejects_unknown_required_stage():
    item = ItemDefinition(
        id="bad_disk",
        name="Bad Disk",
        description="Invalid required stage.",
        type=ItemType.EVOLUTION,
        evolution=EvolutionItemEffect(
            target_species_id="monzaemon",
            required_stages=("not_a_stage",),
        ),
    )

    errors = validate_item_catalog([item], {}, species_map(), Path.cwd())

    assert "bad_disk requires unknown stage: not_a_stage" in errors


def test_validate_item_catalog_rejects_blank_name():
    item = ItemDefinition(
        id="blank_item",
        name="   ",
        description="Blank item name.",
        type=ItemType.MISC,
    )

    errors = validate_item_catalog([item], {}, species_map(), Path.cwd())

    assert "blank_item name is required" in errors


def test_validate_item_catalog_rejects_negative_weights():
    catalog = valid_catalog()

    errors = validate_item_catalog(
        list(catalog.items.values()),
        {"secondary_event": (ItemPoolEntry(item_id="monzaemon_head", weight=-1),)},
        species_map(),
        Path.cwd(),
    )

    assert "secondary_event has negative weight for monzaemon_head" in errors


def test_item_manager_window_can_open_with_catalog():
    app = QApplication.instance() or QApplication([])

    window = ItemManagerWindow(valid_catalog(), species_map(), Path.cwd())

    assert window.windowTitle() == "Item Manager"
    assert window._item_list.count() == 1


def test_item_manager_has_no_apply_button():
    app = QApplication.instance() or QApplication([])
    window = ItemManagerWindow(valid_catalog(), species_map(), Path.cwd())

    button_labels = {button.text() for button in window.findChildren(QPushButton)}

    assert "Apply" not in button_labels


def test_item_manager_blocks_save_when_validation_fails(tmp_path):
    app = QApplication.instance() or QApplication([])
    item = ItemDefinition(
        id="bad_disk",
        name="Bad Disk",
        description="Invalid evolution target.",
        type=ItemType.EVOLUTION,
        evolution=EvolutionItemEffect(target_species_id="missingmon"),
    )
    catalog = ItemCatalog(
        items={item.id: item},
        pools={"secondary_event": (ItemPoolEntry(item_id=item.id, weight=1),)},
    )
    save_path = tmp_path / "items.json"
    window = ItemManagerWindow(catalog, species_map(), Path.cwd(), save_path=save_path)

    assert window.save_catalog() is False
    assert not save_path.exists()


def test_item_manager_saves_valid_catalog(tmp_path):
    app = QApplication.instance() or QApplication([])
    save_path = tmp_path / "items.json"
    window = ItemManagerWindow(
        valid_catalog(),
        species_map(),
        Path.cwd(),
        save_path=save_path,
    )

    assert window.save_catalog() is True
    assert '"monzaemon_head"' in save_path.read_text(encoding="utf-8")


def test_item_manager_applies_field_edits_before_save(tmp_path):
    app = QApplication.instance() or QApplication([])
    save_path = tmp_path / "items.json"
    window = ItemManagerWindow(
        valid_catalog(),
        species_map(),
        Path.cwd(),
        save_path=save_path,
    )

    window._name_input.setText("Edited Head")
    window._description_input.setPlainText("Edited description.")

    item = window._catalog.items["edited_head"]
    assert window._selected_item_key() == "edited_head"
    assert item.name == "Edited Head"
    assert item.description == "Edited description."

    assert window.save_catalog() is True
    raw = json.loads(save_path.read_text(encoding="utf-8"))
    raw_item = raw["items"][0]
    assert raw_item["name"] == "Edited Head"
    assert raw_item["description"] == "Edited description."


def test_item_manager_adds_new_item_with_unique_id():
    app = QApplication.instance() or QApplication([])
    window = ItemManagerWindow(valid_catalog(), species_map(), Path.cwd())

    window.add_item()
    window.add_item()

    assert "new_item" in window._catalog.items
    assert "new_item_2" in window._catalog.items
    assert window._item_list.count() == 3


def test_item_manager_duplicates_selected_item_with_incremented_id_and_name():
    app = QApplication.instance() or QApplication([])
    window = ItemManagerWindow(valid_catalog(), species_map(), Path.cwd())

    window.duplicate_selected_item()
    window.duplicate_selected_item()

    assert "monzaemon_head_2" in window._catalog.items
    assert "monzaemon_head_3" in window._catalog.items
    assert window._catalog.items["monzaemon_head_2"].name == "Monzaemon's Head 2"
    assert window._catalog.items["monzaemon_head_3"].name == "Monzaemon's Head 3"
    assert window._catalog.items["monzaemon_head_2"].evolution == window._catalog.items["monzaemon_head"].evolution
    assert window._catalog.pools["secondary_event"][-2:] == (
        ItemPoolEntry(item_id="monzaemon_head_2", weight=1),
        ItemPoolEntry(item_id="monzaemon_head_3", weight=1),
    )
    assert window._selected_item_key() == "monzaemon_head_3"


def test_item_manager_add_from_empty_catalog_loads_new_item():
    app = QApplication.instance() or QApplication([])
    catalog = ItemCatalog(items={}, pools={"secondary_event": ()})
    window = ItemManagerWindow(catalog, species_map(), Path.cwd())

    window.add_item()

    assert window._selected_item_key() == "new_item"
    assert window._id_input.text() == "new_item"
    assert window._name_input.text() == "New Item"
    assert window._save_button.isEnabled() is True


def test_item_manager_deletes_selected_item_and_pool_entries():
    app = QApplication.instance() or QApplication([])
    window = ItemManagerWindow(valid_catalog(), species_map(), Path.cwd())

    window.delete_selected_item()

    assert window._catalog.items == {}
    assert all(
        entry.item_id != "monzaemon_head"
        for entry in window._catalog.pools.get("secondary_event", ())
    )
    assert window._item_list.count() == 0


def test_item_manager_saves_empty_catalog_after_deleting_last_item(tmp_path):
    app = QApplication.instance() or QApplication([])
    save_path = tmp_path / "items.json"
    window = ItemManagerWindow(
        valid_catalog(),
        species_map(),
        Path.cwd(),
        save_path=save_path,
    )

    window.delete_selected_item()

    assert window._save_button.isEnabled() is True
    assert window.save_catalog() is True
    raw = json.loads(save_path.read_text(encoding="utf-8"))
    assert raw["items"] == []


def test_item_manager_updates_secondary_event_weight(tmp_path):
    app = QApplication.instance() or QApplication([])
    save_path = tmp_path / "items.json"
    window = ItemManagerWindow(
        valid_catalog(),
        species_map(),
        Path.cwd(),
        save_path=save_path,
    )

    window._weight_input.setValue(42)

    assert window.save_catalog() is True
    assert window._catalog.pools["secondary_event"][0].weight == 42
    raw = json.loads(save_path.read_text(encoding="utf-8"))
    assert raw["pools"]["secondary_event"][0]["weight"] == 42


def test_item_manager_shows_secondary_event_drop_chance():
    app = QApplication.instance() or QApplication([])
    window = ItemManagerWindow(two_item_catalog(), species_map(), Path.cwd())

    assert window._drop_chance_bar.value() == 33
    assert "33%" in window._drop_chance_label.text()

    window._item_list.setCurrentRow(1)

    assert window._drop_chance_bar.value() == 67
    assert "67%" in window._drop_chance_label.text()


def test_item_manager_updates_drop_chance_while_editing_weight():
    app = QApplication.instance() or QApplication([])
    window = ItemManagerWindow(two_item_catalog(), species_map(), Path.cwd())

    window._weight_input.setValue(4)

    assert window._drop_chance_bar.value() == 67
    assert "67%" in window._drop_chance_label.text()


def test_item_manager_drop_chance_reserves_ten_percent_for_evolution_items():
    app = QApplication.instance() or QApplication([])
    window = ItemManagerWindow(mixed_drop_catalog(), species_map(), Path.cwd())

    assert window._drop_chance_bar.value() == 20
    assert "20%" in window._drop_chance_label.text()

    window._item_list.setCurrentRow(1)

    assert window._drop_chance_bar.value() == 70
    assert "70%" in window._drop_chance_label.text()

    window._item_list.setCurrentRow(2)

    assert window._drop_chance_bar.value() == 5
    assert "5%" in window._drop_chance_label.text()


def test_item_manager_edits_evolution_conditions(tmp_path):
    app = QApplication.instance() or QApplication([])
    save_path = tmp_path / "items.json"
    window = ItemManagerWindow(
        valid_catalog(),
        species_map(),
        Path.cwd(),
        save_path=save_path,
    )

    window._required_species_input.setCurrentText("agumon")
    window._required_stages_input.setText("champion, ultimate")

    assert window.save_catalog() is True
    raw = json.loads(save_path.read_text(encoding="utf-8"))
    evolution = raw["items"][0]["evolution"]
    assert evolution["required_species_ids"] == ["agumon"]
    assert evolution["required_stages"] == ["champion", "ultimate"]


def test_item_manager_previews_icon_path():
    app = QApplication.instance() or QApplication([])
    window = ItemManagerWindow(valid_catalog(), species_map(), Path.cwd())

    assert window._icon_preview.pixmap() is not None
    assert not window._icon_preview.pixmap().isNull()


def test_item_manager_autocompletes_id_from_name():
    app = QApplication.instance() or QApplication([])
    window = ItemManagerWindow(valid_catalog(), species_map(), Path.cwd())

    window.add_item()
    window._name_input.setText("Special Evolution Disk")

    assert window._id_input.text() == "special_evolution_disk"


def test_item_manager_uses_required_species_dropdown(tmp_path):
    app = QApplication.instance() or QApplication([])
    save_path = tmp_path / "items.json"
    window = ItemManagerWindow(
        valid_catalog(),
        species_map(),
        Path.cwd(),
        save_path=save_path,
    )

    assert window._required_species_input.findText("agumon") >= 0
    window._required_species_input.setCurrentText("agumon")

    assert window.save_catalog() is True
    raw = json.loads(save_path.read_text(encoding="utf-8"))
    assert raw["items"][0]["evolution"]["required_species_ids"] == ["agumon"]


def test_item_manager_icon_path_browse_opens_items_folder(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    project_root = tmp_path
    items_dir = project_root / "assets" / "items"
    items_dir.mkdir(parents=True)
    selected_icon = items_dir / "gun.png"
    selected_icon.write_bytes(b"not a real png")
    opened_directories = []

    def fake_get_open_file_name(parent, title, directory, file_filter):
        opened_directories.append(Path(directory))
        return str(selected_icon), file_filter

    monkeypatch.setattr(QFileDialog, "getOpenFileName", fake_get_open_file_name)
    window = ItemManagerWindow(valid_catalog(), species_map(), project_root)

    window._browse_icon_path()

    assert opened_directories == [items_dir]
    assert window._icon_path_input.text() == "assets/items/gun.png"


def test_item_manager_rejects_duplicate_id_without_rewriting_pools(tmp_path):
    app = QApplication.instance() or QApplication([])
    save_path = tmp_path / "items.json"
    catalog = two_item_catalog()
    window = ItemManagerWindow(catalog, species_map(), Path.cwd(), save_path=save_path)

    window._id_input.setText("b")
    window._weight_input.setValue(99)

    assert window.save_catalog() is False
    assert tuple(catalog.items) == ("a", "b")
    assert catalog.items["a"].id == "a"
    assert catalog.items["b"].id == "b"
    assert catalog.pools["secondary_event"] == (
        ItemPoolEntry(item_id="a", weight=1),
        ItemPoolEntry(item_id="b", weight=2),
    )
    assert "Duplicate item id: b" in window._validation_output.toPlainText()
    assert not save_path.exists()
