from __future__ import annotations

import json
import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QFileDialog,
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
    item_drop_chance_percent,
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
        self._id_autocomplete_enabled = True

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
        self._required_species_input = QComboBox(self)
        self._required_species_input.addItem("")
        self._required_species_input.addItems(sorted(species))
        self._required_stages_input = QComboBox(self)
        self._required_stages_input.addItem("")
        self._required_stages_input.addItems([stage.value for stage in GrowthStage])
        self._icon_path_input = QLineEdit(self)
        self._browse_icon_button = QPushButton("Browse", self)
        self._icon_preview = QLabel(self)
        self._icon_preview.setObjectName("IconPreview")
        self._icon_preview.setFixedSize(72, 72)
        self._icon_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._weight_input = QSpinBox(self)
        self._weight_input.setRange(0, 999999)
        self._drop_chance_bar = QProgressBar(self)
        self._drop_chance_bar.setRange(0, 100)
        self._drop_chance_bar.setTextVisible(False)
        self._drop_chance_label = QLabel(self)
        self._drop_chance_label.setObjectName("Muted")

        form.addRow("ID", self._id_input)
        form.addRow("Name", self._name_input)
        form.addRow("Description", self._description_input)
        form.addRow("Type", self._type_input)
        form.addRow("Evolution Target", self._target_species_input)
        form.addRow("Required Species", self._required_species_input)
        form.addRow("Required Stages", self._required_stages_input)
        icon_path_row = QHBoxLayout()
        icon_path_row.setContentsMargins(0, 0, 0, 0)
        icon_path_row.setSpacing(8)
        icon_path_row.addWidget(self._icon_path_input, 1)
        icon_path_row.addWidget(self._browse_icon_button)

        form.addRow("Icon Path", icon_path_row)
        form.addRow("Sprite Preview", self._icon_preview)
        form.addRow("Secondary Weight", self._weight_input)
        drop_chance_row = QHBoxLayout()
        drop_chance_row.setContentsMargins(0, 0, 0, 0)
        drop_chance_row.setSpacing(8)
        drop_chance_row.addWidget(self._drop_chance_bar, 1)
        drop_chance_row.addWidget(self._drop_chance_label)
        form.addRow("Drop Chance", drop_chance_row)
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

        self._duplicate_button = QPushButton("Duplicate", self)
        self._duplicate_button.clicked.connect(self.duplicate_selected_item)
        button_row.addWidget(self._duplicate_button)

        self._delete_button = QPushButton("Delete", self)
        self._delete_button.clicked.connect(self.delete_selected_item)
        button_row.addWidget(self._delete_button)

        self._save_button = QPushButton("Save", self)
        self._save_button.clicked.connect(self.save_catalog)
        button_row.addWidget(self._save_button)
        right_side.addLayout(button_row)

        body.addLayout(right_side, 2)
        layout.addLayout(body, 1)

        self._id_input.textEdited.connect(self._disable_id_autocomplete)
        self._id_input.textChanged.connect(self._sync_current_item_edits)
        self._name_input.textChanged.connect(self._autocomplete_id_from_name)
        self._name_input.textChanged.connect(self._sync_current_item_edits)
        self._description_input.textChanged.connect(self._sync_current_item_edits)
        self._type_input.currentTextChanged.connect(self._sync_current_item_edits)
        self._target_species_input.currentTextChanged.connect(self._sync_current_item_edits)
        self._required_species_input.currentTextChanged.connect(self._sync_current_item_edits)
        self._required_stages_input.currentTextChanged.connect(self._sync_current_item_edits)
        self._icon_path_input.textChanged.connect(self._refresh_icon_preview)
        self._icon_path_input.textChanged.connect(self._sync_current_item_edits)
        self._browse_icon_button.clicked.connect(self._browse_icon_path)
        self._weight_input.valueChanged.connect(self._refresh_drop_chance)
        self._weight_input.valueChanged.connect(self._sync_current_item_edits)
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

    def _disable_id_autocomplete(self) -> None:
        self._id_autocomplete_enabled = False

    def _autocomplete_id_from_name(self, name: str) -> None:
        if self._loading_item or not self._id_autocomplete_enabled:
            return
        self._id_input.setText(_item_id_from_name(name))

    def _refresh_icon_preview(self) -> None:
        icon_path = self._icon_path_input.text().strip()
        if not icon_path:
            self._icon_preview.clear()
            self._icon_preview.setText("No sprite")
            return

        path = Path(icon_path)
        if not path.is_absolute():
            path = self._project_root / path
        if not path.exists():
            self._icon_preview.clear()
            self._icon_preview.setText("Missing")
            return

        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self._icon_preview.clear()
            self._icon_preview.setText("Invalid")
            return

        self._icon_preview.setText("")
        self._icon_preview.setPixmap(
            pixmap.scaled(
                64,
                64,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _browse_icon_path(self) -> None:
        items_dir = self._project_root / "assets" / "items"
        selected_path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Choose Item Sprite",
            str(items_dir),
            "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)",
        )
        if not selected_path:
            return
        self._icon_path_input.setText(_project_relative_path(Path(selected_path), self._project_root))

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
            self._browse_icon_button,
            self._weight_input,
            self._drop_chance_bar,
            self._drop_chance_label,
        ):
            widget.setEnabled(has_item)
        self._duplicate_button.setEnabled(has_item)
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
        self._refresh_icon_preview()

        target_species_id = item.evolution.target_species_id if item.evolution else ""
        target_index = self._target_species_input.findText(target_species_id)
        self._target_species_input.setCurrentIndex(target_index)
        required_species_id = item.evolution.required_species_ids[0] if item.evolution and item.evolution.required_species_ids else ""
        required_species_index = self._required_species_input.findText(required_species_id)
        self._required_species_input.setCurrentIndex(required_species_index)
        required_stage = item.evolution.required_stages[0] if item.evolution and item.evolution.required_stages else ""
        required_stage_value = required_stage.value if isinstance(required_stage, GrowthStage) else str(required_stage)
        required_stage_index = self._required_stages_input.findText(required_stage_value)
        self._required_stages_input.setCurrentIndex(required_stage_index if required_stage_index >= 0 else 0)

        weight = 0
        for entry in self._catalog.pools.get("secondary_event", ()):
            if entry.item_id == item.id:
                weight = entry.weight
                break
        self._weight_input.setValue(weight)
        self._loading_item = False
        self._id_autocomplete_enabled = True
        self._update_editor_enabled_state()
        self._sync_current_item_edits()
        self._refresh_drop_chance()

    def _clear_editor_fields(self) -> None:
        self._id_input.clear()
        self._name_input.clear()
        self._description_input.clear()
        self._type_input.setCurrentIndex(0)
        self._target_species_input.setCurrentIndex(-1)
        self._required_species_input.setCurrentIndex(0)
        self._required_stages_input.setCurrentIndex(0)
        self._icon_path_input.clear()
        self._icon_preview.clear()
        self._icon_preview.setText("No sprite")
        self._weight_input.setValue(0)
        self._refresh_drop_chance()

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

    def duplicate_selected_item(self) -> None:
        item_key = self._selected_item_key()
        item = self._catalog.items.get(item_key or "")
        if item_key is None or item is None:
            return

        base_item_id = _duplicate_base_id(item.id)
        base_name = _duplicate_base_name(item.name)
        item_id = self._next_duplicate_item_id(base_item_id)
        duplicate = ItemDefinition(
            id=item_id,
            name=self._next_duplicate_item_name(base_name, base_item_id, item_id),
            description=item.description,
            type=item.type,
            icon_path=item.icon_path,
            evolution=item.evolution,
            effects=item.effects,
        )
        self._catalog.items[item_id] = duplicate
        self._set_secondary_event_weight(item_id, self._secondary_event_weight_for_item(item.id))
        self._refresh_item_list(selected_id=item_id)
        self._item_list.setCurrentRow(self._row_for_item_key(item_id))
        self._load_selected_item(self._item_list.currentRow())
        self._validate_current_catalog()

    def _next_duplicate_item_id(self, source_item_id: str) -> str:
        index = 2
        while f"{source_item_id}_{index}" in self._catalog.items:
            index += 1
        return f"{source_item_id}_{index}"

    def _next_duplicate_item_name(
        self,
        source_name: str,
        source_item_id: str,
        duplicate_item_id: str,
    ) -> str:
        suffix = duplicate_item_id.removeprefix(f"{source_item_id}_")
        return f"{source_name} {suffix}"

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

    def _sync_current_item_edits(self) -> bool:
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
        description = self._description_input.toPlainText()
        if item_type == ItemType.EVOLUTION:
            required_species_id = self._required_species_input.currentText().strip()
            evolution = EvolutionItemEffect(
                target_species_id=self._target_species_input.currentText().strip(),
                required_species_ids=(required_species_id,) if required_species_id else (),
                required_stages=(
                    (_parse_growth_stage(self._required_stages_input.currentText()),)
                    if self._required_stages_input.currentText().strip()
                    else ()
                ),
            )
            description = _evolution_item_description(evolution, self._species)
            self._set_description_text(description)

        edited_item = ItemDefinition(
            id=new_item_id,
            name=self._name_input.text(),
            description=description,
            type=item_type,
            icon_path=self._icon_path_input.text().strip() or None,
            evolution=evolution,
            effects=item.effects,
        )
        selected_key = self._replace_item_preserving_order(item_key, edited_item)
        self._replace_item_in_pools(item.id, new_item_id)
        self._set_secondary_event_weight(new_item_id, self._weight_input.value())
        self._refresh_item_list(selected_id=selected_key)
        self._refresh_drop_chance()
        self._validate_current_catalog()
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

    def _secondary_event_weight_for_item(self, item_id: str) -> int:
        for entry in self._catalog.pools.get("secondary_event", ()):
            if entry.item_id == item_id:
                return entry.weight
        return 0

    def _refresh_drop_chance(self) -> None:
        if not hasattr(self, "_drop_chance_bar"):
            return

        percent = self._current_drop_chance_percent()
        self._drop_chance_bar.setValue(percent)
        self._drop_chance_label.setText(f"{percent}% drop chance")

    def _current_drop_chance_percent(self) -> int:
        item_key = self._selected_item_key()
        item = self._catalog.items.get(item_key or "")
        if item is None:
            return 0
        return item_drop_chance_percent(
            self._catalog,
            "secondary_event",
            item.id,
            edited_weight=self._weight_input.value(),
        )

    def _set_catalog_items(self, items: dict[str, ItemDefinition]) -> None:
        object.__setattr__(self._catalog, "items", items)

    def _set_catalog_pools(self, pools: dict[str, tuple[ItemPoolEntry, ...]]) -> None:
        object.__setattr__(self._catalog, "pools", pools)

    def save_catalog(self) -> bool:
        duplicate_item_id = self._duplicate_editor_item_id()
        if duplicate_item_id is not None:
            self._validation_output.setPlainText(f"Duplicate item id: {duplicate_item_id}")
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

    def _duplicate_editor_item_id(self) -> str | None:
        item_key = self._selected_item_key()
        if item_key is None:
            return None
        item_id = self._id_input.text().strip()
        if item_id in self._catalog.items and item_id != item_key:
            return item_id
        return None

    def _set_description_text(self, description: str) -> None:
        if self._description_input.toPlainText() == description:
            return
        self._description_input.blockSignals(True)
        self._description_input.setPlainText(description)
        self._description_input.blockSignals(False)


def _split_csv(raw: str) -> list[str]:
    return [value.strip() for value in raw.split(",") if value.strip()]


def _item_id_from_name(name: str) -> str:
    item_id = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    item_id = re.sub(r"_+", "_", item_id)
    return item_id or "new_item"


def _duplicate_base_id(item_id: str) -> str:
    return re.sub(r"_\d+$", "", item_id)


def _duplicate_base_name(name: str) -> str:
    return re.sub(r"\s+\d+$", "", name)


def _evolution_item_description(
    evolution: EvolutionItemEffect,
    species: dict[str, Species],
) -> str:
    source = _evolution_source_label(evolution, species)
    target = _species_label(evolution.target_species_id, species)
    return f"Makes {source} digivolve into {target}."


def _evolution_source_label(
    evolution: EvolutionItemEffect,
    species: dict[str, Species],
) -> str:
    if evolution.required_species_ids:
        return _join_labels(
            [_species_label(species_id, species) for species_id in evolution.required_species_ids]
        )
    if evolution.required_stages:
        stage_labels = [_stage_label(stage) for stage in evolution.required_stages]
        return f"any {_join_labels(stage_labels)} Digimon"
    return "any Digimon"


def _species_label(species_id: str, species: dict[str, Species]) -> str:
    definition = species.get(species_id)
    return definition.name if definition is not None else species_id


def _stage_label(stage: GrowthStage | str) -> str:
    value = stage.value if isinstance(stage, GrowthStage) else str(stage)
    return value.replace("_", " ").title()


def _join_labels(labels: list[str]) -> str:
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    return f"{', '.join(labels[:-1])} or {labels[-1]}"


def _project_relative_path(path: Path, project_root: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _parse_growth_stage(raw: str) -> GrowthStage | str:
    try:
        return GrowthStage(raw)
    except ValueError:
        return raw
