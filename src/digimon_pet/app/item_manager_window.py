from __future__ import annotations

import json
import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from digimon_pet.app.theme import APP_QSS
from digimon_pet.domain.items import (
    EvolutionItemEffect,
    ItemCatalog,
    ItemDefinition,
    ItemPoolEntry,
    ItemType,
    item_catalog_to_dict,
)
from digimon_pet.domain.models import GrowthStage, Species


ITEM_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
GROWTH_STAGE_VALUES = {stage.value for stage in GrowthStage}


def validate_item_catalog(
    items: list[ItemDefinition],
    pools: dict[str, tuple[ItemPoolEntry, ...]],
    species: dict[str, Species],
    project_root: Path,
) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()

    for item in items:
        if not item.id:
            errors.append("Item id is required")
        elif not ITEM_ID_PATTERN.fullmatch(item.id):
            errors.append(f"Invalid item id: {item.id}")

        if item.id in seen_ids:
            errors.append(f"Duplicate item id: {item.id}")
        seen_ids.add(item.id)

        if not item.name.strip():
            errors.append(f"{item.id} name is required")

        if item.icon_path and not (project_root / item.icon_path).exists():
            errors.append(f"{item.id} sprite does not exist: {item.icon_path}")

        if item.type == ItemType.EVOLUTION:
            if item.evolution is None:
                errors.append(f"{item.id} needs evolution data")
                continue

            target = item.evolution.target_species_id
            if target not in species:
                errors.append(f"{item.id} targets unknown species: {target}")

            for species_id in item.evolution.required_species_ids:
                if species_id not in species:
                    errors.append(f"{item.id} requires unknown species: {species_id}")

            for stage in item.evolution.required_stages:
                if (
                    not isinstance(stage, GrowthStage)
                    and str(stage) not in GROWTH_STAGE_VALUES
                ):
                    errors.append(f"{item.id} requires unknown stage: {stage}")

    item_ids = {item.id for item in items}
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
        save_path: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self._catalog = catalog
        self._species = species
        self._project_root = project_root
        self._save_path = save_path or project_root / "data" / "items.json"
        self._loading_item = False

        self.setWindowTitle("Item Manager")
        self.setMinimumSize(820, 560)
        self.setStyleSheet(APP_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        title = QLabel("Item Manager", self)
        title.setObjectName("Title")
        layout.addWidget(title)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)

        self._item_list = QListWidget(self)
        self._refresh_item_list()
        body.addWidget(self._item_list, 1)

        right_side = QVBoxLayout()
        right_side.setContentsMargins(0, 0, 0, 0)
        right_side.setSpacing(8)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)

        self._id_input = QLineEdit(self)
        self._name_input = QLineEdit(self)
        self._description_input = QPlainTextEdit(self)
        self._description_input.setMaximumHeight(96)
        self._type_input = QComboBox(self)
        self._type_input.addItems([item_type.value for item_type in ItemType])
        self._target_species_input = QComboBox(self)
        self._target_species_input.addItems(sorted(species))
        self._required_species_input = QLineEdit(self)
        self._required_stages_input = QLineEdit(self)
        self._icon_path_input = QLineEdit(self)
        self._weight_input = QSpinBox(self)
        self._weight_input.setRange(0, 999999)

        form.addRow("ID", self._id_input)
        form.addRow("Name", self._name_input)
        form.addRow("Description", self._description_input)
        form.addRow("Type", self._type_input)
        form.addRow("Evolution Target", self._target_species_input)
        form.addRow("Required Species", self._required_species_input)
        form.addRow("Required Stages", self._required_stages_input)
        form.addRow("Icon Path", self._icon_path_input)
        form.addRow("Secondary Weight", self._weight_input)
        right_side.addLayout(form)

        validation_label = QLabel("Validation", self)
        validation_label.setObjectName("Title")
        right_side.addWidget(validation_label)

        self._validation_output = QPlainTextEdit(self)
        self._validation_output.setReadOnly(True)
        right_side.addWidget(self._validation_output, 1)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)

        self._add_button = QPushButton("Add", self)
        self._add_button.clicked.connect(self.add_item)
        button_row.addWidget(self._add_button)

        self._delete_button = QPushButton("Delete", self)
        self._delete_button.clicked.connect(self.delete_selected_item)
        button_row.addWidget(self._delete_button)

        self._apply_button = QPushButton("Apply", self)
        self._apply_button.clicked.connect(self.apply_current_item)
        button_row.addWidget(self._apply_button)

        self._save_button = QPushButton("Save", self)
        self._save_button.clicked.connect(self.save_catalog)
        button_row.addWidget(self._save_button)
        right_side.addLayout(button_row)

        body.addLayout(right_side, 2)
        layout.addLayout(body, 1)

        self._item_list.currentRowChanged.connect(self._load_selected_item)
        if self._item_list.count() > 0:
            self._item_list.setCurrentRow(0)
        self._update_editor_enabled_state()
        self._validate_current_catalog()

    def _refresh_item_list(self, selected_id: str | None = None) -> None:
        if not hasattr(self, "_item_list"):
            return

        if selected_id is None:
            selected_id = self._selected_item_key()

        self._item_list.blockSignals(True)
        self._item_list.clear()
        selected_row = -1
        for row, (item_key, item) in enumerate(self._catalog.items.items()):
            self._item_list.addItem(f"{item.name} ({item.id})")
            list_item = self._item_list.item(row)
            list_item.setData(Qt.ItemDataRole.UserRole, item_key)
            if item_key == selected_id:
                selected_row = row
        if selected_row >= 0:
            self._item_list.setCurrentRow(selected_row)
        self._item_list.blockSignals(False)

    def _selected_item_key(self) -> str | None:
        current = self._item_list.currentItem() if hasattr(self, "_item_list") else None
        if current is None:
            return None
        key = current.data(Qt.ItemDataRole.UserRole)
        return str(key) if key is not None else None

    def _update_editor_enabled_state(self) -> None:
        has_item = self._selected_item_key() is not None
        for widget in (
            self._id_input,
            self._name_input,
            self._description_input,
            self._type_input,
            self._target_species_input,
            self._required_species_input,
            self._required_stages_input,
            self._icon_path_input,
            self._weight_input,
        ):
            widget.setEnabled(has_item)
        self._apply_button.setEnabled(has_item)
        self._delete_button.setEnabled(has_item)
        self._save_button.setEnabled(True)

    def _validate_current_catalog(self) -> None:
        errors = validate_item_catalog(
            list(self._catalog.items.values()),
            self._catalog.pools,
            self._species,
            self._project_root,
        )
        self._validation_output.setPlainText("\n".join(errors) if errors else "No validation errors.")

    def _load_selected_item(self, row: int) -> None:
        item_key = self._selected_item_key()
        item = self._catalog.items.get(item_key or "")
        self._loading_item = True
        if row < 0 or item is None:
            self._clear_editor_fields()
            self._loading_item = False
            self._update_editor_enabled_state()
            return

        self._id_input.setText(item.id)
        self._name_input.setText(item.name)
        self._description_input.setPlainText(item.description)
        self._type_input.setCurrentText(item.type.value)
        self._icon_path_input.setText(item.icon_path or "")

        target_species_id = item.evolution.target_species_id if item.evolution else ""
        target_index = self._target_species_input.findText(target_species_id)
        self._target_species_input.setCurrentIndex(target_index)
        self._required_species_input.setText(
            ", ".join(item.evolution.required_species_ids) if item.evolution else ""
        )
        self._required_stages_input.setText(
            ", ".join(
                str(stage.value if isinstance(stage, GrowthStage) else stage)
                for stage in item.evolution.required_stages
            )
            if item.evolution
            else ""
        )

        weight = 0
        for entry in self._catalog.pools.get("secondary_event", ()):
            if entry.item_id == item.id:
                weight = entry.weight
                break
        self._weight_input.setValue(weight)
        self._loading_item = False
        self._update_editor_enabled_state()

    def _clear_editor_fields(self) -> None:
        self._id_input.clear()
        self._name_input.clear()
        self._description_input.clear()
        self._type_input.setCurrentIndex(0)
        self._target_species_input.setCurrentIndex(-1)
        self._required_species_input.clear()
        self._required_stages_input.clear()
        self._icon_path_input.clear()
        self._weight_input.setValue(0)

    def add_item(self) -> None:
        item_id = self._next_new_item_id()
        item = ItemDefinition(
            id=item_id,
            name="New Item",
            description="",
            type=ItemType.MISC,
            icon_path=None,
            evolution=None,
        )
        self._catalog.items[item_id] = item
        self._set_secondary_event_weight(item_id, 0)
        self._refresh_item_list(selected_id=item_id)
        self._item_list.setCurrentRow(self._row_for_item_key(item_id))
        self._load_selected_item(self._item_list.currentRow())
        self._validate_current_catalog()

    def _next_new_item_id(self) -> str:
        if "new_item" not in self._catalog.items:
            return "new_item"
        index = 2
        while f"new_item_{index}" in self._catalog.items:
            index += 1
        return f"new_item_{index}"

    def delete_selected_item(self) -> None:
        item_key = self._selected_item_key()
        if item_key is None:
            return

        row = self._item_list.currentRow()
        item = self._catalog.items.pop(item_key, None)
        item_id = item.id if item is not None else item_key
        self._remove_item_from_pools(item_id)
        self._refresh_item_list()
        if self._item_list.count() > 0:
            self._item_list.setCurrentRow(min(row, self._item_list.count() - 1))
        else:
            self._clear_editor_fields()
            self._update_editor_enabled_state()
        self._validate_current_catalog()

    def apply_current_item(self) -> bool:
        applied = self._apply_current_item_edits()
        self._validate_current_catalog()
        return applied

    def _apply_current_item_edits(self) -> bool:
        item_key = self._selected_item_key()
        item = self._catalog.items.get(item_key or "")
        if item_key is None or item is None or self._loading_item:
            return False

        new_item_id = self._id_input.text().strip()
        if new_item_id in self._catalog.items and new_item_id != item_key:
            self._validation_output.setPlainText(f"Duplicate item id: {new_item_id}")
            return False

        item_type = ItemType(self._type_input.currentText())
        evolution = None
        if item_type == ItemType.EVOLUTION:
            evolution = EvolutionItemEffect(
                target_species_id=self._target_species_input.currentText().strip(),
                required_species_ids=tuple(_split_csv(self._required_species_input.text())),
                required_stages=tuple(
                    _parse_growth_stage(value)
                    for value in _split_csv(self._required_stages_input.text())
                ),
            )

        edited_item = ItemDefinition(
            id=new_item_id,
            name=self._name_input.text(),
            description=self._description_input.toPlainText(),
            type=item_type,
            icon_path=self._icon_path_input.text().strip() or None,
            evolution=evolution,
        )
        selected_key = self._replace_item_preserving_order(item_key, edited_item)
        self._replace_item_in_pools(item.id, new_item_id)
        self._set_secondary_event_weight(new_item_id, self._weight_input.value())
        self._refresh_item_list(selected_id=selected_key)
        return True

    def _replace_item_preserving_order(self, item_key: str, edited_item: ItemDefinition) -> str:
        replacement_key = edited_item.id
        if replacement_key in self._catalog.items and replacement_key != item_key:
            replacement_key = item_key

        self._set_catalog_items({
            (replacement_key if key == item_key else key): (
                edited_item if key == item_key else item
            )
            for key, item in self._catalog.items.items()
        })
        return replacement_key

    def _row_for_item_key(self, item_key: str) -> int:
        for row in range(self._item_list.count()):
            if self._item_list.item(row).data(Qt.ItemDataRole.UserRole) == item_key:
                return row
        return -1

    def _replace_item_in_pools(self, old_item_id: str, new_item_id: str) -> None:
        if old_item_id == new_item_id:
            return
        self._set_catalog_pools({
            pool_name: tuple(
                ItemPoolEntry(
                    item_id=(
                        new_item_id if entry.item_id == old_item_id else entry.item_id
                    ),
                    weight=entry.weight,
                )
                for entry in entries
            )
            for pool_name, entries in self._catalog.pools.items()
        })

    def _remove_item_from_pools(self, item_id: str) -> None:
        self._set_catalog_pools({
            pool_name: tuple(entry for entry in entries if entry.item_id != item_id)
            for pool_name, entries in self._catalog.pools.items()
        })

    def _set_secondary_event_weight(self, item_id: str, weight: int) -> None:
        entries = list(self._catalog.pools.get("secondary_event", ()))
        for index, entry in enumerate(entries):
            if entry.item_id == item_id:
                entries[index] = ItemPoolEntry(item_id=item_id, weight=weight)
                break
        else:
            entries.append(ItemPoolEntry(item_id=item_id, weight=weight))
        self._set_catalog_pools({**self._catalog.pools, "secondary_event": tuple(entries)})

    def _set_catalog_items(self, items: dict[str, ItemDefinition]) -> None:
        object.__setattr__(self._catalog, "items", items)

    def _set_catalog_pools(self, pools: dict[str, tuple[ItemPoolEntry, ...]]) -> None:
        object.__setattr__(self._catalog, "pools", pools)

    def save_catalog(self) -> bool:
        if self._selected_item_key() is not None and not self._apply_current_item_edits():
            return False
        errors = validate_item_catalog(
            list(self._catalog.items.values()),
            self._catalog.pools,
            self._species,
            self._project_root,
        )
        self._validation_output.setPlainText("\n".join(errors) if errors else "No validation errors.")
        if errors:
            return False

        raw = json.dumps(item_catalog_to_dict(self._catalog), indent=2, ensure_ascii=False)
        self._save_path.write_text(raw + "\n", encoding="utf-8")
        return True


def _split_csv(raw: str) -> list[str]:
    return [value.strip() for value in raw.split(",") if value.strip()]


def _parse_growth_stage(raw: str) -> GrowthStage | str:
    try:
        return GrowthStage(raw)
    except ValueError:
        return raw
