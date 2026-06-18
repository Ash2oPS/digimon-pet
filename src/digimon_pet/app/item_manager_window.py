from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
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
    seen_ids: set[str] = set()

    for item in items:
        if not item.id:
            errors.append("Item id is required")
        elif not ITEM_ID_PATTERN.fullmatch(item.id):
            errors.append(f"Invalid item id: {item.id}")

        if item.id in seen_ids:
            errors.append(f"Duplicate item id: {item.id}")
        seen_ids.add(item.id)

        if not item.name:
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
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._catalog = catalog
        self._species = species
        self._project_root = project_root

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
        for item in self._catalog.items.values():
            self._item_list.addItem(f"{item.name} ({item.id})")
        body.addWidget(self._item_list, 1)

        right_side = QVBoxLayout()
        right_side.setContentsMargins(0, 0, 0, 0)
        right_side.setSpacing(8)

        validation_label = QLabel("Validation", self)
        validation_label.setObjectName("Title")
        right_side.addWidget(validation_label)

        self._validation_output = QPlainTextEdit(self)
        self._validation_output.setReadOnly(True)
        right_side.addWidget(self._validation_output, 1)

        self._save_button = QPushButton("Validate", self)
        self._save_button.clicked.connect(self._validate_current_catalog)
        right_side.addWidget(self._save_button)

        body.addLayout(right_side, 2)
        layout.addLayout(body, 1)

        self._validate_current_catalog()

    def _validate_current_catalog(self) -> None:
        errors = validate_item_catalog(
            list(self._catalog.items.values()),
            self._catalog.pools,
            self._species,
            self._project_root,
        )
        self._validation_output.setPlainText("\n".join(errors) if errors else "No validation errors.")
