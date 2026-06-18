import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

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
