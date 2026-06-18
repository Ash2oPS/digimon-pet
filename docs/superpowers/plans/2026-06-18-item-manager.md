# Item Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a debug-only Item Manager that edits item definitions, evolution item rules, sprites, and secondary-event drop weights from `data/items.json`.

**Architecture:** Add a data-backed item catalog loaded through `digimon_pet.data`, then make runtime item use and inventory display consume that catalog instead of hard-coded definitions. Add a focused PySide dialog for editing the catalog and expose it from `DebugPanel` only.

**Tech Stack:** Python 3, PySide6 widgets, JSON data files, pytest.

---

## File Structure

- Create `data/items.json`: canonical editable item catalog and `secondary_event` pool.
- Modify `src/digimon_pet/domain/items.py`: item dataclasses, validation, weighted selection, and item use helpers.
- Modify `src/digimon_pet/data/loaders.py`: load `data/items.json`.
- Modify `src/digimon_pet/data/__init__.py`: export the item loader.
- Modify `src/digimon_pet/app/inventory_window.py`: keep UI stable while receiving catalog-backed metadata.
- Create `src/digimon_pet/app/item_manager_window.py`: debug-only editor dialog.
- Modify `src/digimon_pet/app/debug_panel.py`: add "Open Item Manager" debug action.
- Modify `src/digimon_pet/app/main_window.py`: load catalog, pass definitions to inventory/runtime, open Item Manager only in debug mode.
- Modify `tests/test_items.py`: runtime item and weighted pool tests.
- Modify `tests/test_data_loading.py`: catalog loading tests.
- Modify `tests/test_inventory_window.py`: unknown item skipping via `PetWindow._inventory_items`.
- Create `tests/test_item_manager_window.py`: editor validation and save behavior tests.
- Modify `tests/test_main_window.py`: debug-only Item Manager access tests.

---

### Task 1: Data Catalog Loading

**Files:**
- Create: `data/items.json`
- Modify: `src/digimon_pet/domain/items.py`
- Modify: `src/digimon_pet/data/loaders.py`
- Modify: `src/digimon_pet/data/__init__.py`
- Test: `tests/test_data_loading.py`
- Test: `tests/test_items.py`

- [ ] **Step 1: Add failing tests for item catalog loading**

Append to `tests/test_data_loading.py`:

```python
from digimon_pet.data import load_item_catalog
from digimon_pet.domain.items import ItemType
from digimon_pet.domain.models import GrowthStage


def test_load_item_catalog_contains_monzaemon_head():
    catalog = load_item_catalog()
    item = catalog.items["monzaemon_head"]

    assert item.id == "monzaemon_head"
    assert item.name == "Monzaemon's Head"
    assert item.description
    assert item.type == ItemType.EVOLUTION
    assert item.icon_path == "assets/items/monzaemon_head.png"
    assert item.evolution is not None
    assert item.evolution.target_species_id == "monzaemon"
    assert item.evolution.required_species_ids == ("numemon",)
    assert item.evolution.required_stages == ()


def test_load_item_catalog_contains_secondary_event_pool():
    catalog = load_item_catalog()

    assert catalog.pools["secondary_event"][0].item_id == "monzaemon_head"
    assert catalog.pools["secondary_event"][0].weight == 1
```

Replace the import block in `tests/test_items.py` with:

```python
from digimon_pet.domain.items import (
    MONZAEMON_HEAD_ID,
    EvolutionItemEffect,
    ItemDefinition,
    ItemType,
    use_evolution_item,
    use_item,
)
```

Replace `test_evolution_item_definition_can_require_a_growth_stage` item creation with:

```python
    item = ItemDefinition(
        id="champion_disk",
        name="Champion Disk",
        description="Forces a champion evolution.",
        type=ItemType.EVOLUTION,
        evolution=EvolutionItemEffect(
            target_species_id="monzaemon",
            required_stages=(GrowthStage.CHAMPION,),
        ),
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_data_loading.py::test_load_item_catalog_contains_monzaemon_head tests/test_data_loading.py::test_load_item_catalog_contains_secondary_event_pool tests/test_items.py::test_evolution_item_definition_can_require_a_growth_stage -v
```

Expected: fail because `load_item_catalog`, `ItemType`, `ItemDefinition`, and `EvolutionItemEffect` do not exist.

- [ ] **Step 3: Create `data/items.json`**

Create `data/items.json`:

```json
{
  "items": [
    {
      "id": "monzaemon_head",
      "name": "Monzaemon's Head",
      "description": "Forces Numemon to evolve into Monzaemon.",
      "type": "evolution",
      "icon_path": "assets/items/monzaemon_head.png",
      "evolution": {
        "target_species_id": "monzaemon",
        "required_species_ids": ["numemon"],
        "required_stages": []
      }
    }
  ],
  "pools": {
    "secondary_event": [
      {
        "item_id": "monzaemon_head",
        "weight": 1
      }
    ]
  }
}
```

- [ ] **Step 4: Add item catalog types and JSON conversion**

Replace `EvolutionItemDefinition` in `src/digimon_pet/domain/items.py` with these definitions, keeping `MONZAEMON_HEAD_ID`:

```python
from enum import StrEnum


class ItemType(StrEnum):
    EVOLUTION = "evolution"
    CONSUMABLE = "consumable"
    KEY_ITEM = "key_item"
    MISC = "misc"


@dataclass(frozen=True)
class EvolutionItemEffect:
    target_species_id: str
    required_species_ids: tuple[str, ...] = ()
    required_stages: tuple[GrowthStage, ...] = ()


@dataclass(frozen=True)
class ItemDefinition:
    id: str
    name: str
    description: str
    type: ItemType
    icon_path: str | None = None
    evolution: EvolutionItemEffect | None = None


@dataclass(frozen=True)
class ItemPoolEntry:
    item_id: str
    weight: int


@dataclass(frozen=True)
class ItemCatalog:
    items: dict[str, ItemDefinition]
    pools: dict[str, tuple[ItemPoolEntry, ...]]
```

Add conversion helpers to the same file:

```python
def item_catalog_from_dict(raw: dict) -> ItemCatalog:
    definitions = [_item_from_dict(item) for item in raw.get("items", [])]
    items = {item.id: item for item in definitions}
    pools = {
        str(pool_name): tuple(
            ItemPoolEntry(item_id=str(entry["item_id"]), weight=int(entry.get("weight", 0)))
            for entry in entries
        )
        for pool_name, entries in dict(raw.get("pools", {})).items()
    }
    return ItemCatalog(items=items, pools=pools)


def item_catalog_to_dict(catalog: ItemCatalog) -> dict:
    return {
        "items": [_item_to_dict(item) for item in catalog.items.values()],
        "pools": {
            pool_name: [
                {"item_id": entry.item_id, "weight": entry.weight}
                for entry in entries
            ]
            for pool_name, entries in catalog.pools.items()
        },
    }


def _item_from_dict(raw: dict) -> ItemDefinition:
    evolution = raw.get("evolution")
    return ItemDefinition(
        id=str(raw["id"]),
        name=str(raw["name"]),
        description=str(raw.get("description", "")),
        type=ItemType(str(raw.get("type", ItemType.MISC))),
        icon_path=str(raw["icon_path"]) if raw.get("icon_path") else None,
        evolution=_evolution_from_dict(evolution) if isinstance(evolution, dict) else None,
    )


def _evolution_from_dict(raw: dict) -> EvolutionItemEffect:
    return EvolutionItemEffect(
        target_species_id=str(raw["target_species_id"]),
        required_species_ids=tuple(str(value) for value in raw.get("required_species_ids", [])),
        required_stages=tuple(GrowthStage(str(value)) for value in raw.get("required_stages", [])),
    )


def _item_to_dict(item: ItemDefinition) -> dict:
    raw = {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "type": item.type.value,
        "icon_path": item.icon_path,
    }
    if item.evolution is not None:
        raw["evolution"] = {
            "target_species_id": item.evolution.target_species_id,
            "required_species_ids": list(item.evolution.required_species_ids),
            "required_stages": [stage.value for stage in item.evolution.required_stages],
        }
    return raw
```

- [ ] **Step 5: Add loader export**

In `src/digimon_pet/data/loaders.py`, import `ItemCatalog` and `item_catalog_from_dict`:

```python
from digimon_pet.domain.items import ItemCatalog, item_catalog_from_dict
```

Add:

```python
def load_item_catalog(path: Path | None = None) -> ItemCatalog:
    return item_catalog_from_dict(_read_json(path or DATA_DIR / "items.json"))
```

In `src/digimon_pet/data/__init__.py`, replace contents with:

```python
from digimon_pet.data.loaders import load_dw1_digivolutions, load_evolution_rules, load_item_catalog, load_species

__all__ = ["load_dw1_digivolutions", "load_evolution_rules", "load_item_catalog", "load_species"]
```

- [ ] **Step 6: Preserve compatibility constant**

In `src/digimon_pet/domain/items.py`, replace hard-coded `EVOLUTION_ITEMS` with:

```python
EVOLUTION_ITEMS: dict[str, ItemDefinition] = {
    MONZAEMON_HEAD_ID: ItemDefinition(
        id=MONZAEMON_HEAD_ID,
        name="Monzaemon's Head",
        description="Forces Numemon to evolve into Monzaemon.",
        type=ItemType.EVOLUTION,
        icon_path="assets/items/monzaemon_head.png",
        evolution=EvolutionItemEffect(
            target_species_id="monzaemon",
            required_species_ids=("numemon",),
        ),
    )
}
```

- [ ] **Step 7: Run tests**

Run:

```bash
pytest tests/test_data_loading.py::test_load_item_catalog_contains_monzaemon_head tests/test_data_loading.py::test_load_item_catalog_contains_secondary_event_pool tests/test_items.py -v
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add data/items.json src/digimon_pet/domain/items.py src/digimon_pet/data/loaders.py src/digimon_pet/data/__init__.py tests/test_data_loading.py tests/test_items.py
git commit -m "feat(items): load item catalog from data"
```

---

### Task 2: Runtime Catalog Use and Weighted Pool Helper

**Files:**
- Modify: `src/digimon_pet/domain/items.py`
- Modify: `src/digimon_pet/app/main_window.py`
- Test: `tests/test_items.py`
- Test: `tests/test_inventory_window.py`

- [ ] **Step 1: Add failing weighted pool tests**

Append to `tests/test_items.py`:

```python
from digimon_pet.domain.items import ItemCatalog, ItemPoolEntry, choose_weighted_item


def test_weighted_item_choice_ignores_zero_weight_entries():
    catalog = ItemCatalog(
        items={
            "rare": ItemDefinition("rare", "Rare", "Rare item", ItemType.MISC),
            "common": ItemDefinition("common", "Common", "Common item", ItemType.MISC),
        },
        pools={
            "secondary_event": (
                ItemPoolEntry("rare", 0),
                ItemPoolEntry("common", 10),
            )
        },
    )

    assert choose_weighted_item(catalog, "secondary_event", random.Random(1)) == "common"


def test_weighted_item_choice_rejects_empty_effective_pool():
    catalog = ItemCatalog(
        items={"rare": ItemDefinition("rare", "Rare", "Rare item", ItemType.MISC)},
        pools={"secondary_event": (ItemPoolEntry("rare", 0),)},
    )

    result = choose_weighted_item(catalog, "secondary_event", random.Random(1))

    assert result is None
```

Append to `tests/test_inventory_window.py`:

```python
def test_pet_window_inventory_skips_unknown_item_ids():
    app = QApplication.instance() or QApplication([])
    window = PetWindow(overlay=True, debug=False)
    window._state.inventory = {MONZAEMON_HEAD_ID: 1, "deleted_item": 2}

    items = window._inventory_items()

    assert [item.id for item in items] == [MONZAEMON_HEAD_ID]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_items.py::test_weighted_item_choice_ignores_zero_weight_entries tests/test_items.py::test_weighted_item_choice_rejects_empty_effective_pool tests/test_inventory_window.py::test_pet_window_inventory_skips_unknown_item_ids -v
```

Expected: fail because `choose_weighted_item` does not exist and unknown inventory ids are still shown.

- [ ] **Step 3: Add catalog-aware item use functions**

In `src/digimon_pet/domain/items.py`, change `use_item` and `can_use_item` signatures:

```python
def use_item(
    state: PetState,
    item_id: str,
    species: dict[str, Species],
    rng: random.Random,
    catalog: ItemCatalog | None = None,
) -> ItemUseResult:
    item = _find_item(item_id, catalog)
    if item is None:
        return ItemUseResult(used=False, reason="unknown_item")
    return use_evolution_item(state, item, species, rng)


def can_use_item(
    state: PetState,
    item_id: str,
    species: dict[str, Species],
    catalog: ItemCatalog | None = None,
) -> ItemUseResult:
    item = _find_item(item_id, catalog)
    if item is None:
        return ItemUseResult(used=False, reason="unknown_item")
    reason = _evolution_item_blocking_reason(state, item, species)
    if reason is not None:
        return ItemUseResult(used=False, reason=reason)
    return ItemUseResult(used=True)
```

Add:

```python
def _find_item(item_id: str, catalog: ItemCatalog | None = None) -> ItemDefinition | None:
    if catalog is not None:
        return catalog.items.get(item_id)
    return EVOLUTION_ITEMS.get(item_id)
```

Update `use_evolution_item` and `_evolution_item_blocking_reason` to receive `ItemDefinition`. At the start of `_evolution_item_blocking_reason`, add:

```python
    if item.type != ItemType.EVOLUTION or item.evolution is None:
        return "not_usable"
```

Then replace `item.target_species_id`, `item.required_species_ids`, and `item.required_stages` references with `item.evolution.target_species_id`, `item.evolution.required_species_ids`, and `item.evolution.required_stages`.

- [ ] **Step 4: Add weighted pool helper**

Add to `src/digimon_pet/domain/items.py`:

```python
def choose_weighted_item(catalog: ItemCatalog, pool_name: str, rng: random.Random) -> str | None:
    entries = [
        entry
        for entry in catalog.pools.get(pool_name, ())
        if entry.weight > 0 and entry.item_id in catalog.items
    ]
    total_weight = sum(entry.weight for entry in entries)
    if total_weight <= 0:
        return None
    roll = rng.randint(1, total_weight)
    running_total = 0
    for entry in entries:
        running_total += entry.weight
        if roll <= running_total:
            return entry.item_id
    return None
```

- [ ] **Step 5: Wire catalog into `PetWindow`**

In `src/digimon_pet/app/main_window.py`, update imports:

```python
from digimon_pet.data import load_dw1_digivolutions, load_item_catalog, load_species
```

Remove `EVOLUTION_ITEMS` from the items import.

In `PetWindow.__init__`, after `_digivolutions`:

```python
        self._item_catalog = load_item_catalog()
```

In `_resolve_pending_inventory_item`, call:

```python
        result = use_item(self._state, item_id, self._species, self._rng, self._item_catalog)
```

In `_use_inventory_item`, call:

```python
        result = can_use_item(self._state, item_id, self._species, self._item_catalog)
```

In `_inventory_items`, replace lookup code with:

```python
            definition = self._item_catalog.items.get(item_id)
            if definition is None:
                continue
            icon_path = None
            if definition.icon_path is not None:
                icon_path = str(PROJECT_ROOT / definition.icon_path)
```

Pass `description=definition.description` when constructing `InventoryItem`.

- [ ] **Step 6: Run tests**

Run:

```bash
pytest tests/test_items.py tests/test_inventory_window.py::test_pet_window_inventory_skips_unknown_item_ids -v
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add src/digimon_pet/domain/items.py src/digimon_pet/app/main_window.py tests/test_items.py tests/test_inventory_window.py
git commit -m "feat(items): use catalog for inventory items"
```

---

### Task 3: Item Manager Validation Core

**Files:**
- Create: `src/digimon_pet/app/item_manager_window.py`
- Test: `tests/test_item_manager_window.py`

- [ ] **Step 1: Add failing validation tests**

Create `tests/test_item_manager_window.py`:

```python
from pathlib import Path

from PySide6.QtWidgets import QApplication

from digimon_pet.app.item_manager_window import ItemManagerWindow, validate_item_catalog
from digimon_pet.domain.items import EvolutionItemEffect, ItemCatalog, ItemDefinition, ItemPoolEntry, ItemType
from digimon_pet.domain.models import GrowthStage, Species


def species_map() -> dict[str, Species]:
    return {
        "numemon": Species("numemon", "Numemon", GrowthStage.CHAMPION),
        "monzaemon": Species("monzaemon", "Monzaemon", GrowthStage.ULTIMATE),
    }


def valid_catalog() -> ItemCatalog:
    return ItemCatalog(
        items={
            "monzaemon_head": ItemDefinition(
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
        },
        pools={"secondary_event": (ItemPoolEntry("monzaemon_head", 1),)},
    )


def test_validate_item_catalog_rejects_duplicate_ids():
    errors = validate_item_catalog(
        [
            valid_catalog().items["monzaemon_head"],
            valid_catalog().items["monzaemon_head"],
        ],
        valid_catalog().pools,
        species_map(),
        Path.cwd(),
    )

    assert "Duplicate item id: monzaemon_head" in errors


def test_validate_item_catalog_rejects_unknown_evolution_target():
    item = ItemDefinition(
        id="bad_disk",
        name="Bad Disk",
        description="Broken.",
        type=ItemType.EVOLUTION,
        icon_path="assets/items/monzaemon_head.png",
        evolution=EvolutionItemEffect(target_species_id="missingmon"),
    )

    errors = validate_item_catalog([item], {"secondary_event": ()}, species_map(), Path.cwd())

    assert "bad_disk targets unknown species: missingmon" in errors


def test_validate_item_catalog_rejects_negative_weights():
    catalog = valid_catalog()

    errors = validate_item_catalog(
        list(catalog.items.values()),
        {"secondary_event": (ItemPoolEntry("monzaemon_head", -1),)},
        species_map(),
        Path.cwd(),
    )

    assert "secondary_event has negative weight for monzaemon_head" in errors


def test_item_manager_window_can_open_with_catalog():
    app = QApplication.instance() or QApplication([])
    window = ItemManagerWindow(valid_catalog(), species_map(), Path.cwd())

    assert window.windowTitle() == "Item Manager"
    assert window._item_list.count() == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_item_manager_window.py -v
```

Expected: fail because `item_manager_window.py` does not exist.

- [ ] **Step 3: Implement validation and minimal window shell**

Create `src/digimon_pet/app/item_manager_window.py`:

```python
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from digimon_pet.app.theme import APP_QSS
from digimon_pet.domain.items import ItemCatalog, ItemDefinition, ItemPoolEntry, ItemType
from digimon_pet.domain.models import Species

ITEM_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


def validate_item_catalog(
    items: list[ItemDefinition],
    pools: dict[str, tuple[ItemPoolEntry, ...]],
    species: dict[str, Species],
    project_root: Path,
) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    item_ids = {item.id for item in items}
    for item in items:
        if not item.id:
            errors.append("Item id is required")
        elif not ITEM_ID_PATTERN.match(item.id):
            errors.append(f"Invalid item id: {item.id}")
        if item.id in seen:
            errors.append(f"Duplicate item id: {item.id}")
        seen.add(item.id)
        if not item.name.strip():
            errors.append(f"{item.id} name is required")
        if item.icon_path and not (project_root / item.icon_path).exists():
            errors.append(f"{item.id} sprite does not exist: {item.icon_path}")
        if item.type == ItemType.EVOLUTION:
            if item.evolution is None:
                errors.append(f"{item.id} needs evolution data")
                continue
            if item.evolution.target_species_id not in species:
                errors.append(f"{item.id} targets unknown species: {item.evolution.target_species_id}")
            for species_id in item.evolution.required_species_ids:
                if species_id not in species:
                    errors.append(f"{item.id} requires unknown species: {species_id}")
    for pool_name, entries in pools.items():
        for entry in entries:
            if entry.item_id not in item_ids:
                errors.append(f"{pool_name} references unknown item: {entry.item_id}")
            if entry.weight < 0:
                errors.append(f"{pool_name} has negative weight for {entry.item_id}")
    return errors


class ItemManagerWindow(QWidget):
    def __init__(
        self,
        catalog: ItemCatalog,
        species: dict[str, Species],
        project_root: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._catalog = catalog
        self._species = species
        self._project_root = project_root
        self.setWindowTitle("Item Manager")
        self.setMinimumSize(820, 560)
        self.setStyleSheet(APP_QSS)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QLabel("Item Manager", self)
        title.setObjectName("Title")
        root.addWidget(title)

        body = QHBoxLayout()
        self._item_list = QListWidget(self)
        for item in catalog.items.values():
            self._item_list.addItem(f"{item.name} ({item.id})")
        body.addWidget(self._item_list, 1)

        right = QVBoxLayout()
        right.addWidget(QLabel("Validation", self))
        self._validation_output = QPlainTextEdit(self)
        self._validation_output.setReadOnly(True)
        right.addWidget(self._validation_output, 1)
        self._save_button = QPushButton("Save", self)
        self._save_button.clicked.connect(self._validate_current_catalog)
        right.addWidget(self._save_button)
        body.addLayout(right, 2)
        root.addLayout(body, 1)
        self._validate_current_catalog()

    def _validate_current_catalog(self) -> None:
        errors = validate_item_catalog(
            list(self._catalog.items.values()),
            self._catalog.pools,
            self._species,
            self._project_root,
        )
        self._validation_output.setPlainText("\n".join(errors) if errors else "No validation errors.")
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/test_item_manager_window.py -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/digimon_pet/app/item_manager_window.py tests/test_item_manager_window.py
git commit -m "feat(items): validate item manager data"
```

---

### Task 4: Item Manager Editing UI and Saving

**Files:**
- Modify: `src/digimon_pet/app/item_manager_window.py`
- Test: `tests/test_item_manager_window.py`

- [ ] **Step 1: Add failing editor tests**

Append to `tests/test_item_manager_window.py`:

```python
def test_item_manager_blocks_save_when_validation_fails(tmp_path):
    app = QApplication.instance() or QApplication([])
    catalog = ItemCatalog(
        items={
            "bad_disk": ItemDefinition(
                id="bad_disk",
                name="Bad Disk",
                description="Broken.",
                type=ItemType.EVOLUTION,
                evolution=EvolutionItemEffect(target_species_id="missingmon"),
            )
        },
        pools={"secondary_event": (ItemPoolEntry("bad_disk", 1),)},
    )
    save_path = tmp_path / "items.json"
    window = ItemManagerWindow(catalog, species_map(), Path.cwd(), save_path=save_path)

    assert window.save_catalog() is False
    assert not save_path.exists()


def test_item_manager_saves_valid_catalog(tmp_path):
    app = QApplication.instance() or QApplication([])
    save_path = tmp_path / "items.json"
    window = ItemManagerWindow(valid_catalog(), species_map(), Path.cwd(), save_path=save_path)

    assert window.save_catalog() is True
    assert '"monzaemon_head"' in save_path.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_item_manager_window.py::test_item_manager_blocks_save_when_validation_fails tests/test_item_manager_window.py::test_item_manager_saves_valid_catalog -v
```

Expected: fail because `save_path` and `save_catalog` do not exist.

- [ ] **Step 3: Add editable fields and save method**

In `src/digimon_pet/app/item_manager_window.py`, add imports:

```python
import json
import shutil
from PySide6.QtWidgets import QFileDialog, QFormLayout, QLineEdit, QComboBox, QSpinBox
from digimon_pet.domain.items import item_catalog_to_dict
```

Change `ItemManagerWindow.__init__` signature:

```python
        save_path: Path | None = None,
```

Set:

```python
        self._save_path = save_path or project_root / "data" / "items.json"
```

Add simple editing widgets in the right panel before validation:

```python
        form = QFormLayout()
        self._id_input = QLineEdit(self)
        self._name_input = QLineEdit(self)
        self._description_input = QPlainTextEdit(self)
        self._type_input = QComboBox(self)
        self._type_input.addItems([item_type.value for item_type in ItemType])
        self._target_species_input = QComboBox(self)
        self._target_species_input.addItems(sorted(species))
        self._weight_input = QSpinBox(self)
        self._weight_input.setRange(0, 999999)
        form.addRow("ID", self._id_input)
        form.addRow("Name", self._name_input)
        form.addRow("Description", self._description_input)
        form.addRow("Type", self._type_input)
        form.addRow("Evolution Target", self._target_species_input)
        form.addRow("Secondary Weight", self._weight_input)
        right.addLayout(form)
```

Connect list selection:

```python
        self._item_list.currentRowChanged.connect(self._load_selected_item)
        if self._item_list.count():
            self._item_list.setCurrentRow(0)
```

Add methods:

```python
    def _load_selected_item(self, row: int) -> None:
        items = list(self._catalog.items.values())
        if row < 0 or row >= len(items):
            return
        item = items[row]
        self._id_input.setText(item.id)
        self._name_input.setText(item.name)
        self._description_input.setPlainText(item.description)
        self._type_input.setCurrentText(item.type.value)
        if item.evolution is not None:
            self._target_species_input.setCurrentText(item.evolution.target_species_id)
        weight = 0
        for entry in self._catalog.pools.get("secondary_event", ()):
            if entry.item_id == item.id:
                weight = entry.weight
                break
        self._weight_input.setValue(weight)

    def save_catalog(self) -> bool:
        errors = validate_item_catalog(
            list(self._catalog.items.values()),
            self._catalog.pools,
            self._species,
            self._project_root,
        )
        self._validation_output.setPlainText("\n".join(errors) if errors else "No validation errors.")
        if errors:
            return False
        self._save_path.write_text(
            json.dumps(item_catalog_to_dict(self._catalog), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return True
```

Change save button connection to:

```python
        self._save_button.clicked.connect(self.save_catalog)
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/test_item_manager_window.py -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/digimon_pet/app/item_manager_window.py tests/test_item_manager_window.py
git commit -m "feat(items): save item manager catalog"
```

---

### Task 5: Debug-Only Access

**Files:**
- Modify: `src/digimon_pet/app/debug_panel.py`
- Modify: `src/digimon_pet/app/main_window.py`
- Test: `tests/test_main_window.py`

- [ ] **Step 1: Add failing debug access tests**

Append to `tests/test_main_window.py`:

```python
def test_debug_panel_has_item_manager_button():
    app = QApplication.instance() or QApplication([])
    window = PetWindow(overlay=True, debug=True)

    assert window._debug_panel._item_manager_button.text() == "Item Manager"


def test_item_manager_opens_only_in_debug_mode():
    app = QApplication.instance() or QApplication([])
    debug_window = PetWindow(overlay=True, debug=True)
    normal_window = PetWindow(overlay=True, debug=False)

    debug_window._open_item_manager()
    normal_window._open_item_manager()

    assert debug_window._item_manager_window is not None
    assert normal_window._item_manager_window is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_main_window.py::test_debug_panel_has_item_manager_button tests/test_main_window.py::test_item_manager_opens_only_in_debug_mode -v
```

Expected: fail because the button and `_open_item_manager` do not exist.

- [ ] **Step 3: Add debug panel callback and button**

In `src/digimon_pet/app/debug_panel.py`, add constructor argument:

```python
        item_manager_requested: Callable[[], None] | None = None,
```

Store it:

```python
        self._item_manager_requested = item_manager_requested
```

In the Automation or Reset area, add:

```python
        tools_group = QGroupBox("Tools")
        tools_layout = QVBoxLayout(tools_group)
        tools_layout.setContentsMargins(12, 14, 12, 12)
        self._item_manager_button = QPushButton("Item Manager")
        self._item_manager_button.clicked.connect(self._emit_item_manager_requested)
        tools_layout.addWidget(self._item_manager_button)
        content_layout.addWidget(tools_group)
```

Add:

```python
    def _emit_item_manager_requested(self) -> None:
        if self._item_manager_requested is not None:
            self._item_manager_requested()
```

- [ ] **Step 4: Wire `PetWindow`**

In `src/digimon_pet/app/main_window.py`, import:

```python
from digimon_pet.app.item_manager_window import ItemManagerWindow
```

Add field in `__init__`:

```python
        self._item_manager_window: ItemManagerWindow | None = None
```

Pass callback to `DebugPanel`:

```python
            item_manager_requested=self._open_item_manager,
```

Add method:

```python
    def _open_item_manager(self) -> None:
        if not self._debug:
            return
        if self._item_manager_window is None:
            self._item_manager_window = ItemManagerWindow(
                self._item_catalog,
                self._species,
                PROJECT_ROOT,
                parent=self,
            )
        self._item_manager_window.show()
        self._item_manager_window.raise_()
        self._item_manager_window.activateWindow()
```

- [ ] **Step 5: Run tests**

Run:

```bash
pytest tests/test_main_window.py::test_debug_panel_has_item_manager_button tests/test_main_window.py::test_item_manager_opens_only_in_debug_mode -v
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add src/digimon_pet/app/debug_panel.py src/digimon_pet/app/main_window.py tests/test_main_window.py
git commit -m "feat(debug): expose item manager"
```

---

### Task 6: Final Verification

**Files:**
- All changed files from Tasks 1-5.

- [ ] **Step 1: Run focused test suite**

Run:

```bash
pytest tests/test_items.py tests/test_data_loading.py tests/test_inventory_window.py tests/test_item_manager_window.py tests/test_main_window.py -v
```

Expected: pass.

- [ ] **Step 2: Run full test suite**

Run:

```bash
pytest -q
```

Expected: pass.

- [ ] **Step 3: Manual smoke check**

Run:

```bash
python -m digimon_pet --debug --smoke-ms 1500
```

Expected: app starts without import/runtime errors and exits automatically.

- [ ] **Step 4: Commit any verification fixes**

Only if a fix was needed:

```bash
git add <fixed-files>
git commit -m "fix(items): stabilize item manager flow"
```

If no fix was needed, do not create an empty commit.

---

## Self-Review

- Spec coverage: covered debug-only entry, `data/items.json`, item metadata, evolution fields, sprite path validation, `secondary_event` weights, unknown item skip, runtime Monzaemon Head behavior, weighted random helper, and tests.
- Scope kept: the secondary event reward flow and non-evolution gameplay effects remain out of scope.
- Red-flag scan: no incomplete task remains; each task includes files, code, commands, and expected results.
