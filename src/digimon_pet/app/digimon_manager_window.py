from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from digimon_pet.app.artwork_runtime import resolve_artwork_path
from digimon_pet.app.theme import APP_QSS
from digimon_pet.domain.digimon_catalog import (
    SPRITE_SLOT_NAMES,
    DigimonCatalog,
    add_species,
    delete_species,
    digimon_catalog_to_digivolutions,
    digimon_catalog_to_species_rows,
    duplicate_species,
    validate_digimon_catalog,
)
from digimon_pet.domain.models import GrowthStage


class RuntimeSpritePreview(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._frame_count = 1
        self._fps = 6
        self._frame_index = 0
        self._status_text = "No runtime sprite"
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance_frame)
        self.setObjectName("RuntimeSpritePreview")
        self.setMinimumSize(220, 220)

    def set_sprite(self, path: Path | None, *, frame_count: int = 1, fps: int = 6) -> None:
        self._timer.stop()
        self._frame_index = 0
        self._frame_count = max(1, int(frame_count or 1))
        self._fps = max(1, int(fps or 6))
        if path is None or not path.exists():
            self._pixmap = None
            self._status_text = "No runtime sprite"
            self.update()
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self._pixmap = None
            self._status_text = "Invalid runtime sprite"
            self.update()
            return
        self._pixmap = pixmap
        self._status_text = ""
        if self._frame_count > 1:
            self._timer.start(max(40, round(1000 / self._fps)))
        self.update()

    def _advance_frame(self) -> None:
        if self._frame_count <= 1:
            return
        self._frame_index = (self._frame_index + 1) % self._frame_count
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(self.rect(), QColor("#111113"))
        if self._pixmap is None or self._pixmap.isNull():
            painter.setPen(QColor("#b8b1a4"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._status_text)
            return
        source = self._source_rect()
        target = self._target_rect(source)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawPixmap(target, self._pixmap, source)

    def _source_rect(self) -> QRect:
        if self._pixmap is None or self._pixmap.isNull():
            return QRect()
        frame_width = max(1, self._pixmap.width() // self._frame_count)
        frame_height = self._pixmap.height()
        frame_index = min(self._frame_index, self._frame_count - 1)
        return QRect(frame_index * frame_width, 0, frame_width, frame_height)

    def _target_rect(self, source: QRect) -> QRect:
        if source.width() <= 0 or source.height() <= 0:
            return QRect()
        margin = 16
        max_width = max(1, self.width() - margin * 2)
        max_height = max(1, self.height() - margin * 2)
        scale = max(1, min(max_width // source.width(), max_height // source.height()))
        width = source.width() * scale
        height = source.height() * scale
        return QRect((self.width() - width) // 2, (self.height() - height) // 2, width, height)


class DigimonManagerWindow(QWidget):
    def __init__(
        self,
        catalog: DigimonCatalog,
        project_root: Path,
        *,
        species_path: Path | None = None,
        digivolutions_path: Path | None = None,
        sprite_manifest_path: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self._catalog = catalog
        self._project_root = project_root
        self._species_path = species_path or project_root / "data" / "species.json"
        self._digivolutions_path = digivolutions_path or project_root / "data" / "dw1_digivolutions.json"
        self._sprite_manifest_path = sprite_manifest_path or project_root / "data" / "dw1_sprite_manifest.json"
        self._runtime_sprite_entries = self._load_runtime_sprite_entries()
        self._dirty = False
        self._loading = False
        self._selected_id: str | None = None

        self.setWindowTitle("Digimon Manager")
        self.setMinimumSize(1120, 680)
        self.setStyleSheet(APP_QSS)
        self._build_ui()
        self._connect_signals()
        self._refresh_species_options()
        self._refresh_table()
        if self._species_table.rowCount() > 0:
            self._species_table.selectRow(0)
        self._refresh_validation()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Digimon Manager", self)
        title.setObjectName("Title")
        header.addWidget(title)
        header.addStretch(1)
        self._status_label = QLabel("Saved", self)
        self._status_label.setObjectName("Muted")
        header.addWidget(self._status_label)
        root.addLayout(header)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        self._search_input = QLineEdit(self)
        self._search_input.setObjectName("SearchInput")
        self._search_input.setPlaceholderText("Search id or name")
        self._stage_filter = QComboBox(self)
        self._stage_filter.addItem("All stages", "")
        self._stage_filter.addItems([stage.value for stage in GrowthStage])
        self._status_filter = QComboBox(self)
        self._status_filter.addItem("All data", "")
        self._status_filter.addItem("Missing sprites", "missing_sprites")
        self._status_filter.addItem("Referenced", "referenced")
        filter_row.addWidget(self._search_input, 1)
        filter_row.addWidget(self._stage_filter)
        filter_row.addWidget(self._status_filter)
        root.addLayout(filter_row)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        root.addWidget(splitter, 1)

        left = QWidget(splitter)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        self._species_table = QTableWidget(0, 5, left)
        self._species_table.setObjectName("DigimonTable")
        self._species_table.setHorizontalHeaderLabels(["", "Name", "ID", "Stage", "Status"])
        self._species_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._species_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._species_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._species_table.verticalHeader().setVisible(False)
        self._species_table.horizontalHeader().setStretchLastSection(True)
        self._species_table.setIconSize(QRect(0, 0, 34, 34).size())
        self._species_table.setColumnWidth(0, 46)
        left_layout.addWidget(self._species_table, 1)

        action_row = QHBoxLayout()
        self._add_button = QPushButton("Add", self)
        self._duplicate_button = QPushButton("Duplicate", self)
        self._delete_button = QPushButton("Delete", self)
        self._validate_button = QPushButton("Validate", self)
        self._save_button = QPushButton("Save", self)
        for button in (
            self._add_button,
            self._duplicate_button,
            self._delete_button,
            self._validate_button,
            self._save_button,
        ):
            action_row.addWidget(button)
        left_layout.addLayout(action_row)

        right = QWidget(splitter)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)
        self._id_input = QLineEdit(self)
        self._name_input = QLineEdit(self)
        self._stage_input = QComboBox(self)
        self._stage_input.addItems([stage.value for stage in GrowthStage])
        form.addRow("ID", self._id_input)
        form.addRow("Name", self._name_input)
        form.addRow("Stage", self._stage_input)
        right_layout.addLayout(form)

        self._tabs = QTabWidget(self)
        self._tabs.addTab(self._build_sprite_tab(), "Sprites")
        self._tabs.addTab(self._build_evolution_tab(), "Evolutions")
        right_layout.addWidget(self._tabs, 1)

        validation_title = QLabel("Validation", self)
        validation_title.setObjectName("Title")
        right_layout.addWidget(validation_title)
        self._validation_output = QPlainTextEdit(self)
        self._validation_output.setReadOnly(True)
        self._validation_output.setMaximumHeight(130)
        right_layout.addWidget(self._validation_output)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([640, 480])

    def _build_sprite_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        self._sprite_inputs: dict[str, QLineEdit] = {}
        for row, slot_name in enumerate(SPRITE_SLOT_NAMES):
            label = QLabel(slot_name.title(), tab)
            input_widget = QLineEdit(tab)
            input_widget.setObjectName(f"SpriteInput_{slot_name}")
            self._sprite_inputs[slot_name] = input_widget
            grid.addWidget(label, row, 0)
            grid.addWidget(input_widget, row, 1)
        layout.addLayout(grid)
        preview_row = QHBoxLayout()
        preview_row.setSpacing(12)
        self._runtime_sprite_preview = RuntimeSpritePreview(tab)
        preview_row.addWidget(self._runtime_sprite_preview, 1)
        artwork_panel = QVBoxLayout()
        artwork_panel.setSpacing(6)
        artwork_title = QLabel("Artwork", tab)
        artwork_title.setObjectName("Muted")
        self._artwork_preview = QLabel("No artwork", tab)
        self._artwork_preview.setObjectName("ArtworkPreview")
        self._artwork_preview.setMinimumSize(220, 220)
        self._artwork_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        artwork_panel.addWidget(artwork_title)
        artwork_panel.addWidget(self._artwork_preview, 1)
        preview_row.addLayout(artwork_panel, 1)
        layout.addLayout(preview_row, 1)
        layout.addStretch(1)
        return tab

    def _build_evolution_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self._natural_table = QTableWidget(0, 4, tab)
        self._natural_table.setHorizontalHeaderLabels(["Kind", "Source", "Target", "Stats"])
        self._natural_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._natural_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._natural_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._natural_table.verticalHeader().setVisible(False)
        self._natural_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(QLabel("Natural Evolutions", tab))
        layout.addWidget(self._natural_table, 1)

        natural_controls = QHBoxLayout()
        self._natural_source_input = QComboBox(tab)
        self._natural_target_input = QComboBox(tab)
        self._natural_add_button = QPushButton("Add Natural", tab)
        self._natural_remove_button = QPushButton("Remove Natural", tab)
        natural_controls.addWidget(self._natural_source_input)
        natural_controls.addWidget(self._natural_target_input)
        natural_controls.addWidget(self._natural_add_button)
        natural_controls.addWidget(self._natural_remove_button)
        layout.addLayout(natural_controls)

        self._special_table = QTableWidget(0, 3, tab)
        self._special_table.setHorizontalHeaderLabels(["Target", "Selector", "Trigger"])
        self._special_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._special_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._special_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._special_table.verticalHeader().setVisible(False)
        self._special_table.horizontalHeader().setStretchLastSection(True)
        self._special_table.setColumnWidth(0, 100)
        self._special_table.setColumnWidth(1, 140)
        layout.addWidget(QLabel("Special Evolutions", tab))
        layout.addWidget(self._special_table, 1)

        special_controls = QHBoxLayout()
        self._special_target_input = QComboBox(tab)
        self._special_selector_input = QComboBox(tab)
        self._special_selector_input.addItem("Any source", "any")
        self._special_selector_input.addItem("Selected source", "selected")
        self._special_trigger_input = QLineEdit(tab)
        self._special_trigger_input.setPlaceholderText("Trigger")
        self._special_add_button = QPushButton("Add Special", tab)
        self._special_remove_button = QPushButton("Remove Special", tab)
        special_controls.addWidget(self._special_target_input)
        special_controls.addWidget(self._special_selector_input)
        special_controls.addWidget(self._special_trigger_input, 1)
        special_controls.addWidget(self._special_add_button)
        special_controls.addWidget(self._special_remove_button)
        layout.addLayout(special_controls)
        return tab

    def _connect_signals(self) -> None:
        self._search_input.textChanged.connect(self._refresh_table)
        self._stage_filter.currentIndexChanged.connect(self._refresh_table)
        self._status_filter.currentIndexChanged.connect(self._refresh_table)
        self._species_table.itemSelectionChanged.connect(self._load_selected_species)
        self._id_input.textChanged.connect(self._sync_species_edits)
        self._name_input.textChanged.connect(self._sync_species_edits)
        self._stage_input.currentTextChanged.connect(self._sync_species_edits)
        for input_widget in self._sprite_inputs.values():
            input_widget.textChanged.connect(self._sync_species_edits)
            input_widget.textChanged.connect(self._refresh_sprite_preview)
        self._add_button.clicked.connect(self.add_species)
        self._duplicate_button.clicked.connect(self.duplicate_selected_species)
        self._delete_button.clicked.connect(self.delete_selected_species)
        self._validate_button.clicked.connect(self._refresh_validation)
        self._save_button.clicked.connect(self.save_catalog)
        self._natural_add_button.clicked.connect(self.add_natural_evolution)
        self._natural_remove_button.clicked.connect(self.remove_selected_natural_evolution)
        self._special_add_button.clicked.connect(self.add_special_evolution)
        self._special_remove_button.clicked.connect(self.remove_selected_special_evolution)

    def _refresh_species_options(self) -> None:
        options = [(str(row.get("name", row.get("id", ""))), str(row.get("id", ""))) for row in self._catalog.species_rows]
        for combo in (
            self._natural_source_input,
            self._natural_target_input,
            self._special_target_input,
        ):
            current = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            for name, species_id in options:
                combo.addItem(f"{name} ({species_id})", species_id)
            index = combo.findData(current)
            if index >= 0:
                combo.setCurrentIndex(index)
            combo.blockSignals(False)

    def _refresh_table(self) -> None:
        selected_id = self._selected_id
        self._species_table.blockSignals(True)
        self._species_table.setRowCount(0)
        for row_data in self._catalog.species_rows:
            species_id = str(row_data.get("id", ""))
            if not self._matches_filters(row_data):
                continue
            row = self._species_table.rowCount()
            self._species_table.insertRow(row)
            self._species_table.setRowHeight(row, 42)
            values = [
                "",
                str(row_data.get("name", "")),
                species_id,
                str(row_data.get("stage", "")),
                self._species_status(row_data),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, species_id)
                if column == 0:
                    thumbnail = self._species_thumbnail(species_id, row_data)
                    if thumbnail is not None:
                        item.setData(Qt.ItemDataRole.DecorationRole, thumbnail)
                        item.setIcon(QIcon(thumbnail))
                self._species_table.setItem(row, column, item)
        self._species_table.blockSignals(False)
        self._select_species_id(selected_id)

    def _matches_filters(self, row: dict[str, object]) -> bool:
        query = self._search_input.text().strip().lower()
        species_id = str(row.get("id", ""))
        name = str(row.get("name", ""))
        if query and query not in species_id.lower() and query not in name.lower():
            return False
        stage_filter = str(self._stage_filter.currentData() or "")
        if stage_filter and str(row.get("stage", "")) != stage_filter:
            return False
        status_filter = str(self._status_filter.currentData() or "")
        if status_filter == "missing_sprites" and "Missing sprites" not in self._species_status(row):
            return False
        if status_filter == "referenced" and not self._is_referenced(species_id):
            return False
        return True

    def _species_status(self, row: dict[str, object]) -> str:
        parts = []
        if self._has_missing_sprites(row):
            parts.append("Missing sprites")
        if self._is_referenced(str(row.get("id", ""))):
            parts.append("Referenced")
        return ", ".join(parts) if parts else "Ready"

    def _has_missing_sprites(self, row: dict[str, object]) -> bool:
        if self._runtime_sprite_path_for(str(row.get("id", ""))) is not None:
            return False
        sprite_slots = row.get("sprite_slots", {})
        if not isinstance(sprite_slots, dict):
            return False
        for sprite_path in sprite_slots.values():
            if not str(sprite_path).strip():
                continue
            path = Path(str(sprite_path))
            if not path.is_absolute():
                path = self._project_root / path
            if not path.exists():
                return True
        return False

    def _is_referenced(self, species_id: str) -> bool:
        return any(
            str(row.get("source_species_id", "")) == species_id
            or str(row.get("target_species_id", "")) == species_id
            for row in self._catalog.natural_evolutions
        ) or any(
            str(row.get("target_species_id", "")) == species_id
            or species_id in {str(value) for value in row.get("source_selector", {}).get("species_ids", [])}
            for row in self._catalog.special_evolutions
            if isinstance(row.get("source_selector", {}), dict)
        )

    def _select_species_id(self, species_id: str | None) -> None:
        if not species_id:
            return
        for row in range(self._species_table.rowCount()):
            item = self._species_table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == species_id:
                self._species_table.selectRow(row)
                return

    def _selected_species_id(self) -> str | None:
        selected = self._species_table.selectedItems()
        if not selected:
            return None
        value = selected[0].data(Qt.ItemDataRole.UserRole)
        return str(value) if value is not None else None

    def _load_selected_species(self) -> None:
        species_id = self._selected_species_id()
        row_data = self._catalog.species_by_id().get(species_id or "")
        self._selected_id = species_id
        self._loading = True
        if row_data is None:
            self._clear_editor()
            self._loading = False
            return
        self._id_input.setText(str(row_data.get("id", "")))
        self._name_input.setText(str(row_data.get("name", "")))
        self._stage_input.setCurrentText(str(row_data.get("stage", GrowthStage.ROOKIE.value)))
        sprite_slots = row_data.get("sprite_slots", {})
        if not isinstance(sprite_slots, dict):
            sprite_slots = {}
        for slot_name, input_widget in self._sprite_inputs.items():
            input_widget.setText(str(sprite_slots.get(slot_name, "")))
        self._loading = False
        self._refresh_sprite_preview()
        self._refresh_artwork_preview()
        self._refresh_evolution_tables()

    def _clear_editor(self) -> None:
        self._id_input.clear()
        self._name_input.clear()
        self._stage_input.setCurrentIndex(0)
        for input_widget in self._sprite_inputs.values():
            input_widget.clear()
        self._sprite_preview.setText("No sprite")
        self._sprite_preview.clear()

    def _sync_species_edits(self) -> None:
        if self._loading:
            return
        old_id = self._selected_id
        row_data = self._catalog.species_by_id().get(old_id or "")
        if row_data is None:
            return
        new_id = self._id_input.text().strip()
        row_data["id"] = new_id
        row_data["name"] = self._name_input.text().strip()
        row_data["stage"] = self._stage_input.currentText()
        row_data["sprite_slots"] = {
            slot_name: input_widget.text().strip()
            for slot_name, input_widget in self._sprite_inputs.items()
            if input_widget.text().strip()
        }
        if old_id and new_id and old_id != new_id:
            self._replace_species_references(old_id, new_id)
            self._selected_id = new_id
        self._mark_dirty()
        self._refresh_species_options()
        self._refresh_table()
        self._refresh_evolution_tables()
        self._refresh_validation()

    def _replace_species_references(self, old_id: str, new_id: str) -> None:
        for row in self._catalog.natural_evolutions:
            if str(row.get("source_species_id", "")) == old_id:
                row["source_species_id"] = new_id
            if str(row.get("target_species_id", "")) == old_id:
                row["target_species_id"] = new_id
            source = str(row.get("source_species_id", ""))
            target = str(row.get("target_species_id", ""))
            if source and target:
                row["id"] = f"{source}__to__{target}"
        for row in self._catalog.special_evolutions:
            if str(row.get("target_species_id", "")) == old_id:
                row["target_species_id"] = new_id
            selector = row.get("source_selector", {})
            if isinstance(selector, dict) and "species_ids" in selector:
                selector["species_ids"] = [
                    new_id if str(value) == old_id else str(value)
                    for value in selector.get("species_ids", [])
                ]

    def _refresh_sprite_preview(self) -> None:
        runtime_entry = self._runtime_sprite_entry_for(self._selected_id or "")
        if runtime_entry is not None:
            path = self._project_path(str(runtime_entry.get("asset_path", "")))
            metadata = runtime_entry.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            self._runtime_sprite_preview.set_sprite(
                path,
                frame_count=int(metadata.get("frame_count", 1)),
                fps=int(metadata.get("fps", 6)),
            )
            return
        idle_path = self._sprite_inputs["idle"].text().strip()
        path = self._project_path(idle_path) if idle_path else None
        self._runtime_sprite_preview.set_sprite(path, frame_count=1, fps=6)

    def _refresh_artwork_preview(self) -> None:
        species_id = self._selected_id or ""
        artwork_path = resolve_artwork_path(species_id, self._project_root)
        if artwork_path is None:
            fallback = self._project_root / "assets" / "artworks" / f"{species_id}.png"
            artwork_path = fallback if fallback.exists() else None
        if artwork_path is None:
            self._artwork_preview.clear()
            self._artwork_preview.setText("No artwork")
            return
        pixmap = QPixmap(str(artwork_path))
        if pixmap.isNull():
            self._artwork_preview.clear()
            self._artwork_preview.setText("Invalid artwork")
            return
        self._artwork_preview.setText("")
        self._artwork_preview.setPixmap(
            pixmap.scaled(
                210,
                210,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _refresh_evolution_tables(self) -> None:
        species_id = self._selected_id or ""
        self._natural_table.setRowCount(0)
        for index, row_data in enumerate(self._catalog.natural_evolutions):
            source = str(row_data.get("source_species_id", ""))
            target = str(row_data.get("target_species_id", ""))
            if species_id not in {source, target}:
                continue
            row = self._natural_table.rowCount()
            self._natural_table.insertRow(row)
            values = [
                "Outgoing" if source == species_id else "Incoming",
                source,
                target,
                self._stats_summary(row_data),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, index)
                self._natural_table.setItem(row, column, item)

        self._special_table.setRowCount(0)
        for index, row_data in enumerate(self._catalog.special_evolutions):
            if not self._special_touches_species(row_data, species_id):
                continue
            row = self._special_table.rowCount()
            self._special_table.insertRow(row)
            values = [
                str(row_data.get("target_species_id", "")),
                self._selector_summary(row_data),
                str(row_data.get("trigger", "")),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, index)
                self._special_table.setItem(row, column, item)

    def _stats_summary(self, row: dict[str, object]) -> str:
        stats = row.get("requirements", {}).get("groups", {}).get("stats", {})  # type: ignore[union-attr]
        if not isinstance(stats, dict) or not stats:
            return "No stats"
        return ", ".join(f"{stat} {value}" for stat, value in stats.items())

    def _selector_summary(self, row: dict[str, object]) -> str:
        selector = row.get("source_selector", {})
        if not isinstance(selector, dict):
            return ""
        if selector.get("scope") == "any":
            return "any"
        if "stage" in selector:
            return f"stage: {selector['stage']}"
        if "species_ids" in selector:
            return ", ".join(str(value) for value in selector.get("species_ids", []))
        return ""

    def _special_touches_species(self, row: dict[str, object], species_id: str) -> bool:
        if str(row.get("target_species_id", "")) == species_id:
            return True
        selector = row.get("source_selector", {})
        if not isinstance(selector, dict):
            return False
        if selector.get("scope") == "any":
            return True
        if species_id in {str(value) for value in selector.get("species_ids", [])}:
            return True
        selector_stage = _app_stage_from_dw1_stage(str(selector.get("stage", "")))
        species = self._catalog.species_by_id().get(species_id)
        return species is not None and selector_stage == str(species.get("stage", ""))

    def add_species(self) -> None:
        species_id = add_species(self._catalog)
        self._selected_id = species_id
        self._mark_dirty()
        self._refresh_species_options()
        self._refresh_table()
        self._refresh_validation()

    def duplicate_selected_species(self) -> None:
        species_id = self._selected_species_id()
        if not species_id:
            return
        duplicate_id = duplicate_species(self._catalog, species_id)
        if not duplicate_id:
            return
        self._selected_id = duplicate_id
        self._mark_dirty()
        self._refresh_species_options()
        self._refresh_table()
        self._refresh_validation()

    def delete_selected_species(self) -> None:
        species_id = self._selected_species_id()
        if not species_id:
            return
        preview = self._delete_impact_preview(species_id)
        message = self._format_delete_impact(preview)
        result = QMessageBox.question(
            self,
            "Delete Digimon",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result != QMessageBox.StandardButton.Yes:
            return
        delete_species(self._catalog, species_id)
        self._selected_id = None
        self._mark_dirty()
        self._refresh_species_options()
        self._refresh_table()
        if self._species_table.rowCount() > 0:
            self._species_table.selectRow(0)
        else:
            self._clear_editor()
        self._refresh_validation()

    def _delete_impact_preview(self, species_id: str):
        from digimon_pet.domain.digimon_catalog import DigimonDeleteImpact

        species = self._catalog.species_by_id().get(species_id)
        sprite_slots = species.get("sprite_slots", {}) if species else {}
        sprite_paths = list(sprite_slots.values()) if isinstance(sprite_slots, dict) else []
        natural_as_source = [
            str(row.get("id", ""))
            for row in self._catalog.natural_evolutions
            if str(row.get("source_species_id", "")) == species_id
        ]
        natural_as_target = [
            str(row.get("id", ""))
            for row in self._catalog.natural_evolutions
            if str(row.get("target_species_id", "")) == species_id
        ]
        special_references = [
            str(row.get("id", ""))
            for row in self._catalog.special_evolutions
            if self._special_touches_species(row, species_id)
        ]
        return DigimonDeleteImpact(
            species_id=species_id,
            natural_as_source=natural_as_source,
            natural_as_target=natural_as_target,
            special_references=special_references,
            sprite_paths=[str(path) for path in sprite_paths],
        )

    def _format_delete_impact(self, impact) -> str:
        lines = [f"Delete {impact.species_id}?"]
        lines.append(f"Natural as source: {_join_or_none(impact.natural_as_source)}")
        lines.append(f"Natural as target: {_join_or_none(impact.natural_as_target)}")
        lines.append(f"Special references: {_join_or_none(impact.special_references)}")
        lines.append(f"Sprite paths: {_join_or_none(impact.sprite_paths)}")
        return "\n".join(lines)

    def add_natural_evolution(self) -> None:
        source_id = str(self._natural_source_input.currentData() or "")
        target_id = str(self._natural_target_input.currentData() or "")
        if not source_id or not target_id:
            return
        species = self._catalog.species_by_id()
        target = species.get(target_id, {})
        row = {
            "id": f"{source_id}__to__{target_id}",
            "type": "natural",
            "source_species_id": source_id,
            "target_species_id": target_id,
            "target_stage": str(target.get("stage", "")),
            "chart_order": 1,
            "requirements": {"mode": "stats_only", "groups": {"stats": {}}},
        }
        self._catalog.natural_evolutions.append(row)
        self._mark_dirty()
        self._refresh_table()
        self._refresh_evolution_tables()
        self._refresh_validation()

    def remove_selected_natural_evolution(self) -> None:
        selected = self._natural_table.selectedItems()
        if not selected:
            return
        index = int(selected[0].data(Qt.ItemDataRole.UserRole))
        if 0 <= index < len(self._catalog.natural_evolutions):
            self._catalog.natural_evolutions.pop(index)
            self._mark_dirty()
            self._refresh_table()
            self._refresh_evolution_tables()
            self._refresh_validation()

    def add_special_evolution(self) -> None:
        target_id = str(self._special_target_input.currentData() or "")
        if not target_id:
            return
        selected_id = self._selected_id or ""
        selector_mode = str(self._special_selector_input.currentData() or "any")
        selector = {"scope": "any"} if selector_mode == "any" else {"species_ids": [selected_id]}
        row = {
            "id": f"special__to__{target_id}",
            "type": "special",
            "target_species_id": target_id,
            "source_selector": selector,
            "trigger": self._special_trigger_input.text().strip(),
            "notes": [],
        }
        self._catalog.special_evolutions.append(row)
        self._mark_dirty()
        self._refresh_table()
        self._refresh_evolution_tables()
        self._refresh_validation()

    def remove_selected_special_evolution(self) -> None:
        selected = self._special_table.selectedItems()
        if not selected:
            return
        index = int(selected[0].data(Qt.ItemDataRole.UserRole))
        if 0 <= index < len(self._catalog.special_evolutions):
            self._catalog.special_evolutions.pop(index)
            self._mark_dirty()
            self._refresh_table()
            self._refresh_evolution_tables()
            self._refresh_validation()

    def _refresh_validation(self) -> None:
        result = validate_digimon_catalog(
            self._catalog,
            self._project_root,
            sprite_manifest_path=self._sprite_manifest_path,
        )
        lines: list[str] = []
        if result.errors:
            lines.append("Errors:")
            lines.extend(f"- {error}" for error in result.errors)
        if result.warnings:
            lines.append("Warnings:")
            lines.extend(f"- {warning}" for warning in result.warnings)
        self._validation_output.setPlainText("\n".join(lines) if lines else "No validation issues.")

    def save_catalog(self) -> bool:
        result = validate_digimon_catalog(
            self._catalog,
            self._project_root,
            sprite_manifest_path=self._sprite_manifest_path,
        )
        self._refresh_validation()
        if result.has_errors:
            return False
        self._species_path.write_text(
            json.dumps(digimon_catalog_to_species_rows(self._catalog), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self._digivolutions_path.write_text(
            json.dumps(digimon_catalog_to_digivolutions(self._catalog), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self._dirty = False
        self._status_label.setText("Saved")
        return True

    def _mark_dirty(self) -> None:
        self._dirty = True
        self._status_label.setText("Unsaved changes")

    def _load_runtime_sprite_entries(self) -> dict[str, dict[str, Any]]:
        if not self._sprite_manifest_path.exists():
            return {}
        try:
            raw = json.loads(self._sprite_manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        entries = raw.get("entries", {}) if isinstance(raw, dict) else {}
        if not isinstance(entries, dict):
            return {}
        runtime_entries: dict[str, dict[str, Any]] = {}
        for species_id, entry in entries.items():
            if isinstance(entry, dict):
                asset_path = str(entry.get("asset_path", "")).strip()
                if asset_path:
                    runtime_entries[str(species_id)] = entry
        return runtime_entries

    def _runtime_sprite_path_for(self, species_id: str) -> str | None:
        entry = self._runtime_sprite_entry_for(species_id)
        raw_path = str(entry.get("asset_path", "")) if entry else ""
        if raw_path and self._project_path_exists(raw_path):
            return raw_path
        return None

    def _species_thumbnail(self, species_id: str, row_data: dict[str, object]) -> QPixmap | None:
        runtime_entry = self._runtime_sprite_entry_for(species_id)
        if runtime_entry is not None:
            metadata = runtime_entry.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            return _first_frame_thumbnail(
                self._project_path(str(runtime_entry.get("asset_path", ""))),
                frame_count=max(1, int(metadata.get("frame_count", 1))),
            )
        sprite_slots = row_data.get("sprite_slots", {})
        if isinstance(sprite_slots, dict):
            idle_path = str(sprite_slots.get("idle", "")).strip()
            if idle_path and self._project_path_exists(idle_path):
                return _first_frame_thumbnail(self._project_path(idle_path), frame_count=1)
        return None

    def _runtime_sprite_entry_for(self, species_id: str) -> dict[str, Any] | None:
        entry = self._runtime_sprite_entries.get(species_id)
        if entry and self._project_path_exists(str(entry.get("asset_path", ""))):
            return entry
        return None

    def _project_path_exists(self, raw_path: str) -> bool:
        return self._project_path(raw_path).exists()

    def _project_path(self, raw_path: str) -> Path:
        path = Path(raw_path)
        if not path.is_absolute():
            path = self._project_root / path
        return path


def _join_or_none(values: list[str]) -> str:
    return ", ".join(values) if values else "none"


def species_id_from_name(name: str) -> str:
    species_id = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return re.sub(r"_+", "_", species_id) or "new_digimon"


def _app_stage_from_dw1_stage(stage: str) -> str:
    if stage == "fresh":
        return GrowthStage.BABY.value
    if stage == "in_training":
        return GrowthStage.BABY_2.value
    return stage


def _first_frame_thumbnail(path: Path, *, frame_count: int) -> QPixmap | None:
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None
    frame_width = max(1, pixmap.width() // max(1, frame_count))
    frame = pixmap.copy(QRect(0, 0, frame_width, pixmap.height()))
    return frame.scaled(
        34,
        34,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.FastTransformation,
    )
