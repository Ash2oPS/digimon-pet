from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSize, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStyle,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from digimon_pet.app.artwork_runtime import discover_and_download_artwork_for_species, resolve_artwork_path
from digimon_pet.app.item_manager_window import ItemManagerWindow
from digimon_pet.app.theme import APP_QSS
from digimon_pet.data import load_item_catalog
from digimon_pet.data.pendulum_sprite_import import (
    SpriteImportOption,
    discover_sprite_import_options,
    import_sprite_option,
    sprite_import_option_preview_image,
)
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
from digimon_pet.domain.fusions import (
    FusionCatalog,
    FusionRecipe,
    fusion_catalog_to_dict,
    validate_fusion_catalog,
)
from digimon_pet.domain.items import ItemCatalog
from digimon_pet.domain.models import GrowthStage, Species


NATURAL_STAT_FIELDS = (
    ("hp", "HP"),
    ("mp", "MP"),
    ("offense", "Offense"),
    ("defense", "Defense"),
    ("speed", "Speed"),
    ("brains", "Brains"),
)


def _parse_aliases(text: str) -> list[str]:
    aliases: list[str] = []
    seen: set[str] = set()
    for raw_alias in re.split(r"[,;\n]+", text):
        alias = raw_alias.strip()
        key = alias.casefold()
        if alias and key not in seen:
            aliases.append(alias)
            seen.add(key)
    return aliases


def _aliases_from_row(row: dict[str, Any] | None) -> list[str]:
    if row is None:
        return []
    raw_aliases = row.get("aliases", [])
    if not isinstance(raw_aliases, list):
        return []
    aliases: list[str] = []
    seen: set[str] = set()
    for raw_alias in raw_aliases:
        alias = str(raw_alias).strip()
        key = alias.casefold()
        if alias and key not in seen:
            aliases.append(alias)
            seen.add(key)
    return aliases


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


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()


class SpeciesComboBox(NoWheelComboBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setIconSize(QSize(24, 24))
        self.setMaxVisibleItems(12)
        self.lineEdit().setPlaceholderText("Search Digimon")
        completer = self.completer()
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)


class FusionManagerWindow(QWidget):
    def __init__(
        self,
        catalog: FusionCatalog,
        species_rows: list[dict[str, Any]],
        project_root: Path,
        *,
        save_path: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._catalog = catalog
        self._species_rows = species_rows
        self._project_root = project_root
        self._save_path = save_path
        self._selected_index: int | None = None
        self._loading = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        left = QVBoxLayout()
        self._recipe_list = QListWidget(self)
        left.addWidget(self._recipe_list, 1)
        actions = QHBoxLayout()
        self._add_button = QPushButton("Add", self)
        self._duplicate_button = QPushButton("Duplicate", self)
        self._delete_button = QPushButton("Delete", self)
        actions.addWidget(self._add_button)
        actions.addWidget(self._duplicate_button)
        actions.addWidget(self._delete_button)
        left.addLayout(actions)
        layout.addLayout(left, 1)

        right = QVBoxLayout()
        form = QFormLayout()
        self._source_a_input = SpeciesComboBox(self)
        self._source_b_input = SpeciesComboBox(self)
        self._target_input = SpeciesComboBox(self)
        self._notes_input = QPlainTextEdit(self)
        self._notes_input.setMaximumHeight(80)
        for input_widget in (self._source_a_input, self._source_b_input, self._target_input):
            self._populate_species_combo(input_widget)
        form.addRow("Digimon A", self._source_a_input)
        form.addRow("Digimon B", self._source_b_input)
        form.addRow("Result", self._target_input)
        form.addRow("Notes", self._notes_input)
        right.addLayout(form)
        self._apply_button = QPushButton("Apply Recipe", self)
        right.addWidget(self._apply_button)
        self._validation_output = QPlainTextEdit(self)
        self._validation_output.setReadOnly(True)
        self._validation_output.setMaximumHeight(160)
        right.addWidget(self._validation_output, 1)
        layout.addLayout(right, 2)

        self._add_button.clicked.connect(self.add_recipe)
        self._duplicate_button.clicked.connect(self.duplicate_selected_recipe)
        self._delete_button.clicked.connect(self.delete_selected_recipe)
        self._apply_button.clicked.connect(self.apply_selected_recipe)
        self._recipe_list.currentRowChanged.connect(self._select_recipe)

        self.refresh()

    def refresh_species(self, species_rows: list[dict[str, Any]]) -> None:
        self._species_rows = species_rows
        current_values = (
            self._source_a_input.currentText(),
            self._source_b_input.currentText(),
            self._target_input.currentText(),
        )
        for input_widget, value in zip(
            (self._source_a_input, self._source_b_input, self._target_input),
            current_values,
            strict=True,
        ):
            input_widget.clear()
            self._populate_species_combo(input_widget)
            input_widget.setCurrentText(value)
        self.refresh_validation()

    def add_recipe(self) -> None:
        species_ids = [str(row.get("id", "")) for row in self._species_rows if str(row.get("id", "")).strip()]
        first = species_ids[0] if species_ids else ""
        second = species_ids[1] if len(species_ids) > 1 else first
        target = species_ids[2] if len(species_ids) > 2 else first
        self._catalog.recipes = self._catalog.recipes + (
            FusionRecipe((first, second), target),
        )
        self.refresh()
        self._recipe_list.setCurrentRow(len(self._catalog.recipes) - 1)

    def duplicate_selected_recipe(self) -> None:
        if self._selected_index is None:
            return
        recipe = self._catalog.recipes[self._selected_index]
        self._catalog.recipes = self._catalog.recipes + (recipe,)
        self.refresh()
        self._recipe_list.setCurrentRow(len(self._catalog.recipes) - 1)

    def delete_selected_recipe(self) -> None:
        if self._selected_index is None:
            return
        recipes = list(self._catalog.recipes)
        recipes.pop(self._selected_index)
        self._catalog.recipes = tuple(recipes)
        self._selected_index = None
        self.refresh()

    def apply_selected_recipe(self) -> None:
        if self._selected_index is None:
            return
        recipes = list(self._catalog.recipes)
        recipes[self._selected_index] = FusionRecipe(
            (
                self._source_a_input.currentText().strip(),
                self._source_b_input.currentText().strip(),
            ),
            self._target_input.currentText().strip(),
            self._notes_input.toPlainText().strip(),
        )
        self._catalog.recipes = tuple(recipes)
        self.refresh()
        self._recipe_list.setCurrentRow(self._selected_index)

    def save_catalog(self) -> bool:
        result = self.refresh_validation()
        if result.has_errors:
            return False
        self._save_path.parent.mkdir(parents=True, exist_ok=True)
        self._save_path.write_text(
            json.dumps(fusion_catalog_to_dict(self._catalog), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return True

    def refresh(self) -> None:
        selected_index = self._selected_index
        self._recipe_list.clear()
        for recipe in self._catalog.recipes:
            self._recipe_list.addItem(_fusion_recipe_label(recipe))
        if self._catalog.recipes:
            self._recipe_list.setCurrentRow(
                selected_index if selected_index is not None and selected_index < len(self._catalog.recipes) else 0
            )
        else:
            self._clear_inputs()
        self.refresh_validation()

    def refresh_validation(self):
        result = validate_fusion_catalog(self._catalog, self._species_map())
        lines: list[str] = []
        if result.errors:
            lines.append("Errors:")
            lines.extend(f"- {message}" for message in result.errors)
        if result.warnings:
            lines.append("Warnings:")
            lines.extend(f"- {message}" for message in result.warnings)
        self._validation_output.setPlainText("\n".join(lines) if lines else "No fusion issues.")
        return result

    def _select_recipe(self, index: int) -> None:
        if not (0 <= index < len(self._catalog.recipes)):
            self._selected_index = None
            self._clear_inputs()
            return
        self._selected_index = index
        recipe = self._catalog.recipes[index]
        self._source_a_input.setCurrentText(recipe.source_species_ids[0])
        self._source_b_input.setCurrentText(recipe.source_species_ids[1])
        self._target_input.setCurrentText(recipe.target_species_id)
        self._notes_input.setPlainText(recipe.notes)

    def _clear_inputs(self) -> None:
        self._source_a_input.setCurrentText("")
        self._source_b_input.setCurrentText("")
        self._target_input.setCurrentText("")
        self._notes_input.clear()

    def _populate_species_combo(self, input_widget: SpeciesComboBox) -> None:
        for row in self._species_rows:
            species_id = str(row.get("id", "")).strip()
            if species_id:
                input_widget.addItem(species_id)

    def _species_map(self) -> dict[str, Species]:
        species: dict[str, Species] = {}
        for row in self._species_rows:
            try:
                species_id = str(row.get("id", "")).strip()
                species[species_id] = Species(
                    id=species_id,
                    name=str(row.get("name", species_id)),
                    stage=GrowthStage(str(row.get("stage", ""))),
                    sprite_slots=dict(row.get("sprite_slots", {})) if isinstance(row.get("sprite_slots", {}), dict) else {},
                )
            except ValueError:
                continue
        return species


class DigimonManagerWindow(QWidget):
    def __init__(
        self,
        catalog: DigimonCatalog,
        project_root: Path,
        *,
        species_path: Path | None = None,
        digivolutions_path: Path | None = None,
        sprite_manifest_path: Path | None = None,
        item_catalog: ItemCatalog | None = None,
        item_save_path: Path | None = None,
        fusion_catalog: FusionCatalog | None = None,
        fusion_save_path: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self._catalog = catalog
        self._project_root = project_root
        self._species_path = species_path or project_root / "data" / "species.json"
        self._digivolutions_path = digivolutions_path or project_root / "data" / "dw1_digivolutions.json"
        self._sprite_manifest_path = sprite_manifest_path or project_root / "data" / "dw1_sprite_manifest.json"
        self._item_catalog = item_catalog
        self._item_save_path = item_save_path or project_root / "data" / "items.json"
        self._fusion_catalog = fusion_catalog or FusionCatalog()
        self._fusion_save_path = fusion_save_path or project_root / "data" / "fusions.json"
        self._item_manager_window: ItemManagerWindow | None = None
        self._fusion_manager_window: FusionManagerWindow | None = None
        self._runtime_sprite_entries = self._load_runtime_sprite_entries()
        self._validation_errors_by_species: dict[str, list[str]] = {}
        self._validation_warnings_by_species: dict[str, list[str]] = {}
        self._dirty = False
        self._loading = False
        self._selected_id: str | None = None
        self._selected_row: dict[str, Any] | None = None

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

        self._main_tabs = QTabWidget(self)
        root.addWidget(self._main_tabs, 1)

        self._digimon_tab = QWidget(self)
        digimon_layout = QVBoxLayout(self._digimon_tab)
        digimon_layout.setContentsMargins(0, 0, 0, 0)
        digimon_layout.setSpacing(10)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        self._search_input = QLineEdit(self)
        self._search_input.setObjectName("SearchInput")
        self._search_input.setPlaceholderText("Search id or name")
        self._stage_filter = NoWheelComboBox(self)
        self._stage_filter.addItem("All stages", "")
        self._stage_filter.addItems([stage.value for stage in GrowthStage])
        self._status_filter = NoWheelComboBox(self)
        self._status_filter.addItem("All data", "")
        self._status_filter.addItem("Missing sprites", "missing_sprites")
        self._status_filter.addItem("Referenced", "referenced")
        filter_row.addWidget(self._search_input, 1)
        filter_row.addWidget(self._stage_filter)
        filter_row.addWidget(self._status_filter)
        digimon_layout.addLayout(filter_row)

        self._content_splitter = QSplitter(Qt.Orientation.Horizontal, self._digimon_tab)
        self._content_splitter.setChildrenCollapsible(False)
        digimon_layout.addWidget(self._content_splitter, 1)

        self._species_panel = QWidget(self._content_splitter)
        self._species_panel.setMinimumWidth(520)
        left = self._species_panel
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
        self._species_table.setColumnWidth(1, 130)
        self._species_table.setColumnWidth(2, 115)
        self._species_table.setColumnWidth(3, 90)
        self._species_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._species_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self._species_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self._species_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self._species_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
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
        self._configure_action_buttons()
        left_layout.addLayout(action_row)

        self._right_scroll_area = QScrollArea(self._content_splitter)
        self._right_scroll_area.setWidgetResizable(True)
        self._right_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._right_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._right_editor_content = QWidget()
        self._right_editor_content.setMinimumWidth(560)
        right_layout = QVBoxLayout(self._right_editor_content)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        selected_header = QFrame(self._right_editor_content)
        selected_header.setObjectName("SelectedDigimonHeader")
        selected_header_layout = QHBoxLayout(selected_header)
        selected_header_layout.setContentsMargins(10, 10, 10, 10)
        selected_header_layout.setSpacing(10)
        self._selected_sprite_label = QLabel(selected_header)
        self._selected_sprite_label.setObjectName("SelectedDigimonSprite")
        self._selected_sprite_label.setFixedSize(48, 48)
        self._selected_sprite_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        selected_header_layout.addWidget(self._selected_sprite_label)
        selected_text_layout = QVBoxLayout()
        selected_text_layout.setSpacing(3)
        self._selected_title_label = QLabel("No Digimon selected", selected_header)
        self._selected_title_label.setObjectName("SelectedDigimonTitle")
        self._selected_subtitle_label = QLabel("", selected_header)
        self._selected_subtitle_label.setObjectName("Muted")
        self._selected_status_label = QLabel("Select a row to edit", selected_header)
        self._selected_status_label.setObjectName("SelectedDigimonStatus")
        selected_text_layout.addWidget(self._selected_title_label)
        selected_text_layout.addWidget(self._selected_subtitle_label)
        selected_text_layout.addWidget(self._selected_status_label)
        selected_header_layout.addLayout(selected_text_layout, 1)
        right_layout.addWidget(selected_header)

        detail_panel = QFrame(self._right_editor_content)
        detail_panel.setObjectName("EditorSection")
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(10, 10, 10, 10)
        detail_layout.setSpacing(8)
        detail_title = QLabel("Details", detail_panel)
        detail_title.setObjectName("SectionTitle")
        detail_layout.addWidget(detail_title)
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)
        self._id_input = QLineEdit(self)
        self._name_input = QLineEdit(self)
        self._aliases_input = QLineEdit(self)
        self._aliases_input.setPlaceholderText("Comma-separated names")
        self._stage_input = NoWheelComboBox(self)
        self._stage_input.addItems([stage.value for stage in GrowthStage])
        form.addRow("ID", self._id_input)
        form.addRow("Name", self._name_input)
        form.addRow("Aliases", self._aliases_input)
        form.addRow("Stage", self._stage_input)
        detail_layout.addLayout(form)
        right_layout.addWidget(detail_panel)

        self._tabs = QTabWidget(self)
        self._tabs.setMinimumHeight(300)
        self._tabs.addTab(self._build_sprite_tab(), "Sprites")
        self._tabs.addTab(self._build_evolution_tab(), "Evolutions")
        right_layout.addWidget(self._tabs, 1)

        validation_title = QLabel("Validation", self)
        validation_title.setObjectName("Title")
        right_layout.addWidget(validation_title)
        self._validation_summary_label = QLabel("0 errors - 0 warnings", self)
        self._validation_summary_label.setObjectName("ValidationSummary")
        right_layout.addWidget(self._validation_summary_label)
        self._selected_validation_output = QPlainTextEdit(self)
        self._selected_validation_output.setObjectName("SelectedValidationOutput")
        self._selected_validation_output.setReadOnly(True)
        self._selected_validation_output.setMaximumHeight(62)
        right_layout.addWidget(self._selected_validation_output)
        self._validation_output = QPlainTextEdit(self)
        self._validation_output.setReadOnly(True)
        self._validation_output.setMaximumHeight(130)
        right_layout.addWidget(self._validation_output)
        self._move_validation_to_tab(right_layout, validation_title)

        self._right_scroll_area.setWidget(self._right_editor_content)
        self._content_splitter.addWidget(left)
        self._content_splitter.addWidget(self._right_scroll_area)
        self._content_splitter.setStretchFactor(0, 5)
        self._content_splitter.setStretchFactor(1, 6)
        self._content_splitter.setSizes([560, 720])
        self._main_tabs.addTab(self._digimon_tab, "Digimon")
        if self._item_catalog is not None:
            self._item_manager_window = ItemManagerWindow(
                self._item_catalog,
                self._species_map_for_items(),
                self._project_root,
                save_path=self._item_save_path,
                embedded=True,
                parent=self,
            )
            self._main_tabs.addTab(self._item_manager_window, "Items")
        self._fusion_manager_window = FusionManagerWindow(
            self._fusion_catalog,
            self._catalog.species_rows,
            self._project_root,
            save_path=self._fusion_save_path,
            parent=self,
        )
        self._main_tabs.addTab(self._fusion_manager_window, "Fusions")

    def _configure_action_buttons(self) -> None:
        icon_size = QSize(15, 15)
        button_specs = [
            (self._add_button, QStyle.StandardPixmap.SP_FileDialogNewFolder, "Add a new Digimon"),
            (self._duplicate_button, QStyle.StandardPixmap.SP_FileDialogDetailedView, "Duplicate selected Digimon"),
            (self._delete_button, QStyle.StandardPixmap.SP_TrashIcon, "Delete selected Digimon"),
            (self._validate_button, QStyle.StandardPixmap.SP_DialogApplyButton, "Run validation"),
            (self._save_button, QStyle.StandardPixmap.SP_DialogSaveButton, "Save species and evolution data"),
        ]
        for button, icon_id, tooltip in button_specs:
            button.setIcon(self.style().standardIcon(icon_id))
            button.setIconSize(icon_size)
            button.setToolTip(tooltip)
        self._delete_button.setObjectName("DangerButton")
        self._save_button.setObjectName("PrimaryButton")

    def _move_validation_to_tab(self, right_layout: QVBoxLayout, validation_title: QLabel) -> None:
        for widget in (
            validation_title,
            self._validation_summary_label,
            self._selected_validation_output,
            self._validation_output,
        ):
            right_layout.removeWidget(widget)

        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        validation_title.setParent(tab)
        validation_title.setObjectName("SectionTitle")
        layout.addWidget(validation_title)
        layout.addWidget(self._validation_summary_label)
        selected_title = QLabel("Selected Digimon", tab)
        selected_title.setObjectName("SectionTitle")
        layout.addWidget(selected_title)
        self._selected_validation_output.setParent(tab)
        self._selected_validation_output.setMinimumHeight(84)
        self._selected_validation_output.setMaximumHeight(112)
        layout.addWidget(self._selected_validation_output)
        global_title = QLabel("Global Validation", tab)
        global_title.setObjectName("SectionTitle")
        layout.addWidget(global_title)
        self._validation_output.setParent(tab)
        self._validation_output.setMaximumHeight(16777215)
        layout.addWidget(self._validation_output, 1)
        self._tabs.addTab(tab, "Validation")

    def _build_sprite_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)
        import_row = QHBoxLayout()
        import_row.setSpacing(8)
        self._import_sprite_button = QPushButton("Fetch sprite", tab)
        self._import_sprite_button.setObjectName("PrimaryButton")
        self._import_sprite_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        self._import_sprite_button.setToolTip("Fetch a sprite from Google Drive, local manifests, Pendulum Color, or Wikimon")
        self._import_artwork_button = QPushButton("Fetch artwork", tab)
        self._import_artwork_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self._import_artwork_button.setToolTip("Fetch artwork by the selected Digimon name")
        self._visual_import_status = QLabel("Fetch visuals from the selected name", tab)
        self._visual_import_status.setObjectName("VisualImportStatus")
        import_row.addWidget(self._import_sprite_button)
        import_row.addWidget(self._import_artwork_button)
        import_row.addWidget(self._visual_import_status, 1)
        layout.addLayout(import_row)
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

        natural_section, natural_layout = self._evolution_section(
            tab,
            "Natural Evolutions",
            "Pick a source and a target. The selected Digimon is used as source by default.",
        )
        self._natural_table = QTableWidget(0, 4, natural_section)
        self._natural_table.setObjectName("EvolutionTable")
        self._natural_table.setHorizontalHeaderLabels(["Direction", "Source", "Target", "Conditions"])
        self._configure_evolution_table(self._natural_table)
        self._natural_table.setColumnWidth(0, 82)
        self._natural_table.setColumnWidth(1, 140)
        self._natural_table.setColumnWidth(2, 140)
        natural_layout.addWidget(self._natural_table)

        natural_controls = QGridLayout()
        natural_controls.setContentsMargins(0, 0, 0, 0)
        natural_controls.setHorizontalSpacing(8)
        natural_controls.setVerticalSpacing(4)
        self._natural_source_input = SpeciesComboBox(natural_section)
        self._natural_target_input = SpeciesComboBox(natural_section)
        self._natural_add_button = QPushButton("Add", natural_section)
        self._natural_add_button.setObjectName("PrimaryButton")
        self._natural_remove_button = QPushButton("Remove selected", natural_section)
        self._natural_remove_button.setObjectName("DangerButton")
        natural_controls.addWidget(self._field_label("From", natural_section), 0, 0)
        natural_controls.addWidget(self._field_label("To", natural_section), 0, 1)
        natural_controls.addWidget(self._natural_source_input, 1, 0)
        natural_controls.addWidget(self._natural_target_input, 1, 1)
        natural_controls.addWidget(self._natural_add_button, 1, 2)
        natural_controls.addWidget(self._natural_remove_button, 1, 3)
        natural_controls.setColumnStretch(0, 1)
        natural_controls.setColumnStretch(1, 1)
        natural_layout.addLayout(natural_controls)

        conditions_panel = QFrame(natural_section)
        conditions_panel.setObjectName("EvolutionConditionsPanel")
        conditions_layout = QVBoxLayout(conditions_panel)
        conditions_layout.setContentsMargins(8, 8, 8, 8)
        conditions_layout.setSpacing(6)
        conditions_title = QLabel("Natural conditions", conditions_panel)
        conditions_title.setObjectName("SectionTitle")
        conditions_hint = QLabel("Blank fields are ignored. Filled conditions must all match for this natural evolution.", conditions_panel)
        conditions_hint.setObjectName("Muted")
        conditions_hint.setWordWrap(True)
        conditions_layout.addWidget(conditions_title)
        conditions_layout.addWidget(conditions_hint)

        self._natural_stat_inputs: dict[str, QLineEdit] = {}
        stats_grid = QGridLayout()
        stats_grid.setContentsMargins(0, 0, 0, 0)
        stats_grid.setHorizontalSpacing(8)
        stats_grid.setVerticalSpacing(4)
        for index, (stat_id, label_text) in enumerate(NATURAL_STAT_FIELDS):
            input_widget = QLineEdit(conditions_panel)
            input_widget.setPlaceholderText("min")
            input_widget.setInputMask("9999")
            self._natural_stat_inputs[stat_id] = input_widget
            column = index % 3
            row = (index // 3) * 2
            stats_grid.addWidget(self._field_label(label_text, conditions_panel), row, column)
            stats_grid.addWidget(input_widget, row + 1, column)
        conditions_layout.addLayout(stats_grid)

        other_grid = QGridLayout()
        other_grid.setContentsMargins(0, 0, 0, 0)
        other_grid.setHorizontalSpacing(8)
        other_grid.setVerticalSpacing(4)
        self._natural_weight_min_input = QLineEdit(conditions_panel)
        self._natural_weight_min_input.setPlaceholderText("min")
        self._natural_weight_min_input.setInputMask("999")
        self._natural_weight_max_input = QLineEdit(conditions_panel)
        self._natural_weight_max_input.setPlaceholderText("max")
        self._natural_weight_max_input.setInputMask("999")
        self._natural_care_min_input = QLineEdit(conditions_panel)
        self._natural_care_min_input.setPlaceholderText("min")
        self._natural_care_min_input.setInputMask("999")
        self._natural_care_max_input = QLineEdit(conditions_panel)
        self._natural_care_max_input.setPlaceholderText("max")
        self._natural_care_max_input.setInputMask("999")
        other_grid.addWidget(self._field_label("Weight", conditions_panel), 0, 0)
        other_grid.addWidget(self._natural_weight_min_input, 1, 0)
        other_grid.addWidget(self._natural_weight_max_input, 1, 1)
        other_grid.addWidget(self._field_label("Care mistakes", conditions_panel), 0, 2)
        other_grid.addWidget(self._natural_care_min_input, 1, 2)
        other_grid.addWidget(self._natural_care_max_input, 1, 3)
        conditions_layout.addLayout(other_grid)

        conditions_actions = QHBoxLayout()
        conditions_actions.setContentsMargins(0, 0, 0, 0)
        self._natural_save_conditions_button = QPushButton("Save conditions", conditions_panel)
        self._natural_save_conditions_button.setObjectName("PrimaryButton")
        self._natural_clear_conditions_button = QPushButton("Clear", conditions_panel)
        conditions_actions.addStretch(1)
        conditions_actions.addWidget(self._natural_save_conditions_button)
        conditions_actions.addWidget(self._natural_clear_conditions_button)
        conditions_layout.addLayout(conditions_actions)
        natural_layout.addWidget(conditions_panel)
        layout.addWidget(natural_section)

        special_section, special_layout = self._evolution_section(
            tab,
            "Special Evolutions",
            "Use this for event, item, or fallback evolutions with a clear trigger.",
        )
        self._special_table = QTableWidget(0, 3, special_section)
        self._special_table.setObjectName("EvolutionTable")
        self._special_table.setHorizontalHeaderLabels(["Target", "Source rule", "Trigger"])
        self._configure_evolution_table(self._special_table)
        self._special_table.setColumnWidth(0, 100)
        self._special_table.setColumnWidth(1, 140)
        special_layout.addWidget(self._special_table)

        special_controls = QGridLayout()
        special_controls.setContentsMargins(0, 0, 0, 0)
        special_controls.setHorizontalSpacing(8)
        special_controls.setVerticalSpacing(4)
        self._special_target_input = SpeciesComboBox(special_section)
        self._special_selector_input = NoWheelComboBox(special_section)
        self._special_selector_input.addItem("Any source", "any")
        self._special_selector_input.addItem("Selected Digimon only", "selected")
        self._special_trigger_input = QLineEdit(special_section)
        self._special_trigger_input.setPlaceholderText("ex: full Virus Bar")
        self._special_add_button = QPushButton("Add", special_section)
        self._special_add_button.setObjectName("PrimaryButton")
        self._special_remove_button = QPushButton("Remove selected", special_section)
        self._special_remove_button.setObjectName("DangerButton")
        special_controls.addWidget(self._field_label("To", special_section), 0, 0)
        special_controls.addWidget(self._field_label("Source rule", special_section), 0, 1)
        special_controls.addWidget(self._field_label("Trigger", special_section), 0, 2)
        special_controls.addWidget(self._special_target_input, 1, 0)
        special_controls.addWidget(self._special_selector_input, 1, 1)
        special_controls.addWidget(self._special_trigger_input, 1, 2)
        special_controls.addWidget(self._special_add_button, 1, 3)
        special_controls.addWidget(self._special_remove_button, 1, 4)
        special_controls.setColumnStretch(0, 1)
        special_controls.setColumnStretch(2, 1)
        special_layout.addLayout(special_controls)
        layout.addWidget(special_section)
        layout.addStretch(1)
        return tab

    def _evolution_section(self, parent: QWidget, title: str, hint: str) -> tuple[QFrame, QVBoxLayout]:
        section = QFrame(parent)
        section.setObjectName("EvolutionEditorSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(7)
        title_label = QLabel(title, section)
        title_label.setObjectName("SectionTitle")
        hint_label = QLabel(hint, section)
        hint_label.setObjectName("Muted")
        hint_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(hint_label)
        return section, layout

    def _field_label(self, text: str, parent: QWidget) -> QLabel:
        label = QLabel(text, parent)
        label.setObjectName("Muted")
        return label

    def _configure_evolution_table(self, table: QTableWidget) -> None:
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.setMaximumHeight(96)
        table.setMinimumHeight(78)

    def _connect_signals(self) -> None:
        self._search_input.textChanged.connect(self._refresh_table)
        self._stage_filter.currentIndexChanged.connect(self._refresh_table)
        self._status_filter.currentIndexChanged.connect(self._refresh_table)
        self._species_table.itemSelectionChanged.connect(self._load_selected_species)
        self._id_input.textChanged.connect(self._sync_species_edits)
        self._name_input.textChanged.connect(self._sync_species_edits)
        self._aliases_input.textChanged.connect(self._sync_species_edits)
        self._stage_input.currentTextChanged.connect(self._sync_species_edits)
        for input_widget in self._sprite_inputs.values():
            input_widget.textChanged.connect(self._sync_species_edits)
            input_widget.textChanged.connect(self._refresh_sprite_preview)
        self._add_button.clicked.connect(self.add_species)
        self._duplicate_button.clicked.connect(self.duplicate_selected_species)
        self._delete_button.clicked.connect(self.delete_selected_species)
        self._validate_button.clicked.connect(self._refresh_validation)
        self._save_button.clicked.connect(self.save_catalog)
        self._import_sprite_button.clicked.connect(self.import_selected_sprite)
        self._import_artwork_button.clicked.connect(self.import_selected_artwork)
        self._natural_add_button.clicked.connect(self.add_natural_evolution)
        self._natural_remove_button.clicked.connect(self.remove_selected_natural_evolution)
        self._natural_save_conditions_button.clicked.connect(self.save_selected_natural_conditions)
        self._natural_clear_conditions_button.clicked.connect(self.clear_natural_condition_inputs)
        self._special_add_button.clicked.connect(self.add_special_evolution)
        self._special_remove_button.clicked.connect(self.remove_selected_special_evolution)
        self._natural_source_input.currentIndexChanged.connect(self._refresh_evolution_actions)
        self._natural_target_input.currentIndexChanged.connect(self._refresh_evolution_actions)
        self._special_target_input.currentIndexChanged.connect(self._refresh_evolution_actions)
        self._special_selector_input.currentIndexChanged.connect(self._refresh_evolution_actions)
        self._special_trigger_input.textChanged.connect(self._refresh_evolution_actions)
        self._natural_table.itemSelectionChanged.connect(self._refresh_evolution_actions)
        self._natural_table.itemSelectionChanged.connect(self._load_selected_natural_conditions)
        self._special_table.itemSelectionChanged.connect(self._refresh_evolution_actions)

    def _species_map_for_items(self) -> dict[str, Species]:
        species_map = {}
        for row in self._catalog.species_rows:
            species_id = str(row.get("id", ""))
            stage = str(row.get("stage", GrowthStage.ROOKIE.value))
            try:
                growth_stage = GrowthStage(stage)
            except ValueError:
                growth_stage = GrowthStage.ROOKIE
            species_map[species_id] = Species(
                id=species_id,
                name=str(row.get("name", species_id)),
                stage=growth_stage,
                sprite_slots=dict(row.get("sprite_slots", {})) if isinstance(row.get("sprite_slots", {}), dict) else {},
            )
        return species_map

    def _refresh_species_options(self) -> None:
        options = [
            (
                str(row.get("name", row.get("id", ""))),
                str(row.get("id", "")),
                row,
            )
            for row in self._catalog.species_rows
        ]
        for combo in (
            self._natural_source_input,
            self._natural_target_input,
            self._special_target_input,
        ):
            current = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            for name, species_id, row_data in options:
                label = f"{name} ({species_id})"
                thumbnail = self._species_thumbnail(species_id, row_data)
                if thumbnail is not None:
                    combo.addItem(QIcon(thumbnail), label, species_id)
                else:
                    combo.addItem(label, species_id)
            index = combo.findData(current)
            if index >= 0:
                combo.setCurrentIndex(index)
            combo.blockSignals(False)
        if self._fusion_manager_window is not None:
            self._fusion_manager_window.refresh_species(self._catalog.species_rows)
        self._refresh_evolution_actions()

    def _sync_evolution_inputs_to_selection(self) -> None:
        species_id = self._selected_id or ""
        if not species_id:
            self._refresh_evolution_actions()
            return
        self._set_combo_data(self._natural_source_input, species_id)
        if self._natural_target_input.currentData() == species_id:
            self._select_first_combo_value_except(self._natural_target_input, species_id)
        if self._special_selector_input.currentData() == "selected":
            self._refresh_evolution_actions()
            return
        self._refresh_evolution_actions()

    def _set_combo_data(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0 and combo.currentIndex() != index:
            combo.setCurrentIndex(index)

    def _select_first_combo_value_except(self, combo: QComboBox, excluded_value: str) -> None:
        for index in range(combo.count()):
            if str(combo.itemData(index) or "") != excluded_value:
                combo.setCurrentIndex(index)
                return

    def _refresh_evolution_actions(self) -> None:
        if not hasattr(self, "_natural_add_button"):
            return
        natural_source = str(self._natural_source_input.currentData() or "")
        natural_target = str(self._natural_target_input.currentData() or "")
        natural_duplicate = self._natural_evolution_exists(natural_source, natural_target)
        can_add_natural = bool(natural_source and natural_target and natural_source != natural_target and not natural_duplicate)
        self._natural_add_button.setEnabled(can_add_natural)
        selected_natural_index = self._selected_evolution_index(self._natural_table)
        self._natural_remove_button.setEnabled(selected_natural_index is not None)
        self._natural_save_conditions_button.setEnabled(selected_natural_index is not None)
        if natural_source == natural_target and natural_source:
            natural_tip = "Source and target must be different."
        elif natural_duplicate:
            natural_tip = "This natural evolution already exists."
        else:
            natural_tip = "Add the selected natural evolution."
        self._natural_add_button.setToolTip(natural_tip)

        selected_id = self._selected_id or ""
        special_target = str(self._special_target_input.currentData() or "")
        selector_mode = str(self._special_selector_input.currentData() or "any")
        special_trigger = self._special_trigger_input.text().strip()
        special_selector = self._special_selector_from_mode(selector_mode, selected_id)
        special_duplicate = self._special_evolution_exists(special_target, special_selector, special_trigger)
        can_add_special = bool(
            special_target
            and special_trigger
            and special_selector
            and not special_duplicate
        )
        self._special_add_button.setEnabled(can_add_special)
        self._special_remove_button.setEnabled(self._selected_evolution_index(self._special_table) is not None)
        if selector_mode == "selected" and not selected_id:
            special_tip = "Select a Digimon before using selected-source mode."
        elif not special_trigger:
            special_tip = "Enter a trigger before adding a special evolution."
        elif special_duplicate:
            special_tip = "This special evolution already exists."
        else:
            special_tip = "Add the selected special evolution."
        self._special_add_button.setToolTip(special_tip)

    def _selected_evolution_index(self, table: QTableWidget) -> int | None:
        selected = table.selectedItems()
        if not selected:
            return None
        value = selected[0].data(Qt.ItemDataRole.UserRole)
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _natural_evolution_exists(self, source_id: str, target_id: str) -> bool:
        return any(
            str(row.get("source_species_id", "")) == source_id
            and str(row.get("target_species_id", "")) == target_id
            for row in self._catalog.natural_evolutions
        )

    def _special_evolution_exists(self, target_id: str, selector: dict[str, object], trigger: str) -> bool:
        return any(
            str(row.get("target_species_id", "")) == target_id
            and row.get("source_selector", {}) == selector
            and str(row.get("trigger", "")) == trigger
            for row in self._catalog.special_evolutions
        )

    def _special_selector_from_mode(self, selector_mode: str, selected_id: str) -> dict[str, object]:
        if selector_mode == "selected":
            return {"species_ids": [selected_id]} if selected_id else {}
        return {"scope": "any"}

    def _refresh_table(self) -> None:
        self._refresh_validation_indexes()
        selected_id = self._selected_id
        selected_row = self._selected_row
        self._species_table.blockSignals(True)
        self._species_table.setRowCount(0)
        for source_index, row_data in enumerate(self._catalog.species_rows):
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
                item.setData(Qt.ItemDataRole.UserRole + 1, source_index)
                if column == 0:
                    thumbnail = self._species_thumbnail(species_id, row_data)
                    if thumbnail is not None:
                        item.setData(Qt.ItemDataRole.DecorationRole, thumbnail)
                        item.setIcon(QIcon(thumbnail))
                if column == 4:
                    tooltip = self._species_status_tooltip(species_id)
                    if tooltip:
                        item.setToolTip(tooltip)
                    item.setForeground(QColor(self._species_status_color(species_id, row_data)))
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
        species_id = str(row.get("id", ""))
        parts = []
        error_count = len(self._validation_errors_by_species.get(species_id, []))
        warning_count = len(self._validation_warnings_by_species.get(species_id, []))
        if error_count:
            parts.append(f"{error_count} error{'s' if error_count != 1 else ''}")
        if warning_count:
            parts.append(f"{warning_count} warning{'s' if warning_count != 1 else ''}")
        if self._has_missing_sprites(row):
            parts.append("Missing sprites")
        if self._is_referenced(species_id):
            parts.append("Referenced")
        return ", ".join(parts) if parts else "Ready"

    def _species_status_tooltip(self, species_id: str) -> str:
        messages = []
        messages.extend(self._validation_errors_by_species.get(species_id, []))
        messages.extend(self._validation_warnings_by_species.get(species_id, []))
        return "\n".join(messages)

    def _species_status_color(self, species_id: str, row: dict[str, object]) -> str:
        if self._validation_errors_by_species.get(species_id):
            return "#d95f5f"
        if self._validation_warnings_by_species.get(species_id):
            return "#ffd166"
        if self._has_missing_sprites(row):
            return "#f08a3c"
        if self._is_referenced(species_id):
            return "#9fd18b"
        return "#b8b1a4"

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
        selected_row = self._selected_row
        if not species_id:
            if selected_row is None:
                return
        for row in range(self._species_table.rowCount()):
            item = self._species_table.item(row, 0)
            if not item:
                continue
            item_row = self._row_from_table_item(item)
            if (item_row is not None and item_row is selected_row) or item.data(Qt.ItemDataRole.UserRole) == species_id:
                self._species_table.selectRow(row)
                return

    def _selected_species_id(self) -> str | None:
        selected = self._species_table.selectedItems()
        if not selected:
            return None
        value = selected[0].data(Qt.ItemDataRole.UserRole)
        return str(value) if value is not None else None

    def _selected_species_row(self) -> dict[str, Any] | None:
        selected = self._species_table.selectedItems()
        if selected:
            row_data = self._row_from_table_item(selected[0])
            if row_data is not None:
                return row_data
        if self._selected_row in self._catalog.species_rows:
            return self._selected_row
        species_id = self._selected_species_id() or self._selected_id or ""
        return self._catalog.species_by_id().get(species_id)

    def _row_from_table_item(self, item: QTableWidgetItem) -> dict[str, Any] | None:
        row_index = item.data(Qt.ItemDataRole.UserRole + 1)
        try:
            row_data = self._catalog.species_rows[int(row_index)]
        except (TypeError, ValueError, IndexError):
            return None
        return row_data

    def _load_selected_species(self) -> None:
        row_data = self._selected_species_row()
        species_id = str(row_data.get("id", "")) if row_data is not None else self._selected_species_id()
        self._selected_id = species_id
        self._selected_row = row_data
        self._loading = True
        if row_data is None:
            self._clear_editor()
            self._loading = False
            return
        self._id_input.setText(str(row_data.get("id", "")))
        self._name_input.setText(str(row_data.get("name", "")))
        self._aliases_input.setText(", ".join(_aliases_from_row(row_data)))
        self._stage_input.setCurrentText(str(row_data.get("stage", GrowthStage.ROOKIE.value)))
        sprite_slots = row_data.get("sprite_slots", {})
        if not isinstance(sprite_slots, dict):
            sprite_slots = {}
        for slot_name, input_widget in self._sprite_inputs.items():
            input_widget.setText(str(sprite_slots.get(slot_name, "")))
        self._loading = False
        self._set_visual_import_status("Fetch visuals from the selected name", "neutral")
        self._sync_evolution_inputs_to_selection()
        self._refresh_sprite_preview()
        self._refresh_artwork_preview()
        self._refresh_evolution_tables()
        self._refresh_selected_context()

    def _clear_editor(self) -> None:
        self._id_input.clear()
        self._name_input.clear()
        self._aliases_input.clear()
        self._stage_input.setCurrentIndex(0)
        for input_widget in self._sprite_inputs.values():
            input_widget.clear()
        self._selected_title_label.setText("No Digimon selected")
        self._selected_subtitle_label.setText("")
        self._selected_status_label.setText("Select a row to edit")
        self._selected_sprite_label.clear()
        self._selected_validation_output.setPlainText("No Digimon selected.")
        self._set_visual_import_status("Select a Digimon before fetching visuals.", "neutral")
        self.clear_natural_condition_inputs()
        self._refresh_evolution_actions()

    def _sync_species_edits(self) -> None:
        if self._loading:
            return
        old_id = self._selected_id
        row_data = self._selected_species_row()
        if row_data is None:
            return
        new_id = self._id_input.text().strip()
        row_data["id"] = new_id
        row_data["name"] = self._name_input.text().strip()
        row_data["aliases"] = _parse_aliases(self._aliases_input.text())
        row_data["stage"] = self._stage_input.currentText()
        row_data["sprite_slots"] = {
            slot_name: input_widget.text().strip()
            for slot_name, input_widget in self._sprite_inputs.items()
            if input_widget.text().strip()
        }
        self._selected_id = new_id
        self._selected_row = row_data
        if old_id and new_id and old_id != new_id:
            self._replace_species_references(old_id, new_id)
        self._mark_dirty()
        self._refresh_species_options()
        self._refresh_table()
        self._refresh_evolution_tables()
        self._refresh_validation()
        self._refresh_selected_context()

    def import_selected_sprite(self) -> None:
        identity = self._selected_import_identity()
        if identity is None:
            self._set_visual_import_status("Select a Digimon with a name first.", "error")
            return
        species_id, name = identity
        options = self._discover_selected_sprite_options(
            species_id,
            self._selected_import_names(name),
            self._stage_input.currentText().strip(),
        )
        if not options:
            self._set_visual_import_status("No sprite source found for this name.", "error")
            return
        option = self._choose_sprite_import_option(options)
        if option is None:
            self._set_visual_import_status("Sprite import cancelled.", "neutral")
            return
        self._run_visual_import(
            self._import_sprite_button,
            f"Importing {option.label}...",
            lambda: import_sprite_option(option, self._project_root),
            self._handle_sprite_import_result,
        )

    def import_selected_artwork(self) -> None:
        identity = self._selected_import_identity()
        if identity is None:
            self._set_visual_import_status("Select a Digimon with a name first.", "error")
            return
        species_id, name = identity
        self._run_visual_import(
            self._import_artwork_button,
            f"Fetching artwork for {name}...",
            lambda: self._discover_and_download_selected_artwork(species_id, self._selected_import_names(name)),
            self._handle_artwork_import_result,
        )

    def _selected_import_identity(self) -> tuple[str, str] | None:
        species_id = self._id_input.text().strip() or self._selected_id or ""
        name = self._name_input.text().strip()
        if not species_id or not name:
            return None
        return species_id, name

    def _selected_import_names(self, name: str) -> list[str]:
        names = [name, *_parse_aliases(self._aliases_input.text())]
        unique: list[str] = []
        seen: set[str] = set()
        for candidate in names:
            clean = candidate.strip()
            key = clean.casefold()
            if clean and key not in seen:
                unique.append(clean)
                seen.add(key)
        return unique

    def _discover_selected_sprite_options(self, species_id: str, names: list[str], stage: str = "") -> list[SpriteImportOption]:
        label = names[0] if names else species_id
        self._set_visual_import_status(f"Looking up sprites for {label}...", "pending")
        self._import_sprite_button.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            return self._dedupe_sprite_import_options(
                option
                for name in names
                for option in discover_sprite_import_options(species_id, name, self._project_root, stage=stage)
            )
        except OSError as exc:
            self._set_visual_import_status(f"Network error: {exc}", "error")
            return []
        finally:
            QApplication.restoreOverrideCursor()
            self._import_sprite_button.setEnabled(True)

    def _dedupe_sprite_import_options(self, options) -> list[SpriteImportOption]:
        deduped: list[SpriteImportOption] = []
        seen: set[tuple[str, str, str, str]] = set()
        for option in options:
            key = (option.provider_id, option.name.casefold(), option.label, option.detail)
            if key in seen:
                continue
            deduped.append(option)
            seen.add(key)
        return deduped

    def _discover_and_download_selected_artwork(self, species_id: str, names: list[str]) -> Path | None:
        for name in names:
            result = discover_and_download_artwork_for_species(species_id, name, self._project_root)
            if result is not None:
                return result
        return None

    def _choose_sprite_import_option(self, options: list[SpriteImportOption]) -> SpriteImportOption | None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Choose sprite source")
        dialog.setModal(True)
        dialog.setMinimumWidth(440)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        title = QLabel("Choose the sprite to import", dialog)
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        list_widget = QListWidget(dialog)
        list_widget.setObjectName("SpriteSourceList")
        list_widget.setIconSize(QSize(52, 52))
        for option in options:
            list_widget.addItem(self._sprite_source_list_item(option))
        list_widget.setCurrentRow(0)
        layout.addWidget(list_widget, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        selected = list_widget.currentItem()
        return selected.data(Qt.ItemDataRole.UserRole) if selected is not None else None

    def _sprite_source_list_item(self, option: SpriteImportOption) -> QListWidgetItem:
        item = QListWidgetItem(f"{option.label}\n{option.detail}")
        item.setData(Qt.ItemDataRole.UserRole, option)
        item.setSizeHint(QSize(0, 68))
        preview = sprite_import_option_preview_image(option)
        if not preview.isNull():
            item.setIcon(QIcon(QPixmap.fromImage(preview)))
        return item

    def _run_visual_import(self, button: QPushButton, pending_text: str, action, on_result) -> None:
        self._set_visual_import_status(pending_text, "pending")
        button.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            result = action()
        except OSError as exc:
            self._set_visual_import_status(f"Network error: {exc}", "error")
            return
        finally:
            QApplication.restoreOverrideCursor()
            button.setEnabled(True)
        on_result(result)

    def _handle_sprite_import_result(self, result) -> None:
        if result is None:
            self._set_visual_import_status("No Pendulum Color sprite found for this name.", "error")
            return
        self._runtime_sprite_entries = self._load_runtime_sprite_entries()
        self._refresh_sprite_preview()
        self._refresh_table()
        self._refresh_validation()
        self._set_visual_import_status(
            f"Sprite imported from {result.source_name}: {result.frame_count} frame{'s' if result.frame_count != 1 else ''}.",
            "ok",
        )

    def _handle_artwork_import_result(self, result: Path | None) -> None:
        if result is None:
            self._set_visual_import_status("No artwork found for this name.", "error")
            return
        self._refresh_artwork_preview()
        self._set_visual_import_status("Artwork imported and preview refreshed.", "ok")

    def _set_visual_import_status(self, text: str, state: str) -> None:
        self._visual_import_status.setText(text)
        self._visual_import_status.setProperty("state", state)
        self._visual_import_status.style().unpolish(self._visual_import_status)
        self._visual_import_status.style().polish(self._visual_import_status)

    def _refresh_selected_context(self) -> None:
        species_id = self._selected_id or ""
        row_data = self._selected_species_row()
        if row_data is None:
            self._clear_editor()
            return
        species_id = str(row_data.get("id", "")).strip()
        name = str(row_data.get("name", species_id)).strip() or species_id
        stage = str(row_data.get("stage", "")).strip()
        self._selected_title_label.setText(name)
        self._selected_subtitle_label.setText(f"{species_id} - {stage}" if stage else species_id)
        self._selected_status_label.setText(self._species_status(row_data))
        self._selected_status_label.setProperty("state", self._selected_status_state(species_id, row_data))
        self._selected_status_label.style().unpolish(self._selected_status_label)
        self._selected_status_label.style().polish(self._selected_status_label)
        thumbnail = self._species_thumbnail(species_id, row_data)
        if thumbnail is None:
            self._selected_sprite_label.clear()
            self._selected_sprite_label.setText("No sprite")
        else:
            self._selected_sprite_label.setText("")
            self._selected_sprite_label.setPixmap(thumbnail.scaled(
                42,
                42,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            ))
        self._refresh_selected_validation()

    def _selected_status_state(self, species_id: str, row: dict[str, object]) -> str:
        if self._validation_errors_by_species.get(species_id):
            return "error"
        if self._validation_warnings_by_species.get(species_id):
            return "warning"
        if self._has_missing_sprites(row):
            return "warning"
        return "ok"

    def _refresh_selected_validation(self) -> None:
        species_id = self._selected_id or ""
        if not species_id:
            self._selected_validation_output.setPlainText("No Digimon selected.")
            return
        lines: list[str] = []
        errors = self._validation_errors_by_species.get(species_id, [])
        warnings = self._validation_warnings_by_species.get(species_id, [])
        if errors:
            lines.append("Selected Digimon errors:")
            lines.extend(f"- {error}" for error in errors)
        if warnings:
            lines.append("Selected Digimon warnings:")
            lines.extend(f"- {warning}" for warning in warnings)
        self._selected_validation_output.setPlainText("\n".join(lines) if lines else "No issues for selected Digimon.")

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
                self._species_label(source),
                self._species_label(target),
                self._conditions_summary(row_data),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, index)
                if column in {1, 2}:
                    item.setToolTip(source if column == 1 else target)
                self._natural_table.setItem(row, column, item)

        self._special_table.setRowCount(0)
        for index, row_data in enumerate(self._catalog.special_evolutions):
            if not self._special_touches_species(row_data, species_id):
                continue
            row = self._special_table.rowCount()
            self._special_table.insertRow(row)
            values = [
                self._species_label(str(row_data.get("target_species_id", ""))),
                self._selector_summary(row_data),
                str(row_data.get("trigger", "")),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, index)
                if column == 0:
                    item.setToolTip(str(row_data.get("target_species_id", "")))
                self._special_table.setItem(row, column, item)
        self._refresh_evolution_actions()

    def _species_label(self, species_id: str) -> str:
        species = self._catalog.species_by_id().get(species_id)
        if not species:
            return species_id
        name = str(species.get("name", species_id))
        return f"{name} ({species_id})"

    def _select_evolution_row(self, table: QTableWidget, catalog_index: int) -> None:
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == catalog_index:
                table.selectRow(row)
                return

    def _load_selected_natural_conditions(self) -> None:
        index = self._selected_evolution_index(self._natural_table)
        if index is None or not (0 <= index < len(self._catalog.natural_evolutions)):
            self.clear_natural_condition_inputs()
            return
        self._set_natural_condition_inputs(self._catalog.natural_evolutions[index])

    def clear_natural_condition_inputs(self) -> None:
        for input_widget in self._natural_stat_inputs.values():
            input_widget.clear()
        self._natural_weight_min_input.clear()
        self._natural_weight_max_input.clear()
        self._natural_care_min_input.clear()
        self._natural_care_max_input.clear()

    def _set_natural_condition_inputs(self, row: dict[str, object]) -> None:
        self.clear_natural_condition_inputs()
        groups = self._natural_requirement_groups(row)
        stats = groups.get("stats", {})
        if isinstance(stats, dict):
            for stat_name, input_widget in self._natural_stat_inputs.items():
                value = stats.get(stat_name)
                if value not in (None, ""):
                    input_widget.setText(str(value))
        weight = groups.get("weight", {})
        if isinstance(weight, dict):
            if weight.get("min") not in (None, ""):
                self._natural_weight_min_input.setText(str(weight.get("min")))
            if weight.get("max") not in (None, ""):
                self._natural_weight_max_input.setText(str(weight.get("max")))
        care_mistakes = groups.get("care_mistakes", {})
        if isinstance(care_mistakes, dict):
            if care_mistakes.get("min") not in (None, ""):
                self._natural_care_min_input.setText(str(care_mistakes.get("min")))
            if care_mistakes.get("max") not in (None, ""):
                self._natural_care_max_input.setText(str(care_mistakes.get("max")))

    def _natural_requirement_groups(self, row: dict[str, object]) -> dict[str, object]:
        requirements = row.get("requirements", {})
        if not isinstance(requirements, dict):
            return {}
        groups = requirements.get("groups", {})
        return groups if isinstance(groups, dict) else {}

    def _natural_conditions_from_inputs(self) -> dict[str, object]:
        groups: dict[str, object] = {}
        stats = {
            stat_name: value
            for stat_name, input_widget in self._natural_stat_inputs.items()
            if (value := self._int_input_value(input_widget)) is not None
        }
        if stats:
            groups["stats"] = stats
        weight_min = self._int_input_value(self._natural_weight_min_input)
        weight_max = self._int_input_value(self._natural_weight_max_input)
        weight = {}
        if weight_min is not None:
            weight["min"] = weight_min
        if weight_max is not None:
            weight["max"] = weight_max
        if weight:
            groups["weight"] = weight
        care_min = self._int_input_value(self._natural_care_min_input)
        care_max = self._int_input_value(self._natural_care_max_input)
        care_mistakes = {}
        if care_min is not None:
            care_mistakes["min"] = care_min
        if care_max is not None:
            care_mistakes["max"] = care_max
        if care_mistakes:
            groups["care_mistakes"] = care_mistakes
        return {"mode": "stats_only", "groups": groups}

    def _int_input_value(self, input_widget: QLineEdit) -> int | None:
        text = input_widget.text().strip()
        return int(text) if text else None

    def save_selected_natural_conditions(self) -> None:
        index = self._selected_evolution_index(self._natural_table)
        if index is None or not (0 <= index < len(self._catalog.natural_evolutions)):
            return
        self._catalog.natural_evolutions[index]["requirements"] = self._natural_conditions_from_inputs()
        self._mark_dirty()
        self._refresh_table()
        self._refresh_evolution_tables()
        self._select_evolution_row(self._natural_table, index)
        self._refresh_validation()

    def _conditions_summary(self, row: dict[str, object]) -> str:
        groups = self._natural_requirement_groups(row)
        parts: list[str] = []
        stats = groups.get("stats", {})
        if isinstance(stats, dict):
            parts.extend(f"{stat} {value}" for stat, value in stats.items())
        weight = groups.get("weight", {})
        if isinstance(weight, dict):
            parts.append(self._range_summary("weight", weight))
        care_mistakes = groups.get("care_mistakes", {})
        if isinstance(care_mistakes, dict):
            parts.append(self._range_summary("mistakes", care_mistakes))
        parts = [part for part in parts if part]
        return ", ".join(parts) if parts else "No conditions"

    def _range_summary(self, label: str, values: dict[str, object]) -> str:
        minimum = values.get("min")
        maximum = values.get("max")
        if minimum not in (None, "") and maximum not in (None, ""):
            return f"{label} {minimum}-{maximum}"
        if minimum not in (None, ""):
            return f"{label} >= {minimum}"
        if maximum not in (None, ""):
            return f"{label} <= {maximum}"
        return ""

    def _selector_summary(self, row: dict[str, object]) -> str:
        selector = row.get("source_selector", {})
        if not isinstance(selector, dict):
            return ""
        if selector.get("scope") == "any":
            return "any"
        if "stage" in selector:
            return f"stage: {selector['stage']}"
        if "species_ids" in selector:
            return ", ".join(self._species_label(str(value)) for value in selector.get("species_ids", []))
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
        self._selected_row = self._catalog.species_by_id().get(species_id)
        self._mark_dirty()
        self._refresh_species_options()
        self._refresh_table()
        self._load_selected_species()
        self._refresh_validation()

    def duplicate_selected_species(self) -> None:
        species_id = self._selected_species_id()
        if not species_id:
            return
        duplicate_id = duplicate_species(self._catalog, species_id)
        if not duplicate_id:
            return
        self._selected_id = duplicate_id
        self._selected_row = self._catalog.species_by_id().get(duplicate_id)
        self._mark_dirty()
        self._refresh_species_options()
        self._refresh_table()
        self._load_selected_species()
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
        self._selected_row = None
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
        if not source_id or not target_id or source_id == target_id or self._natural_evolution_exists(source_id, target_id):
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
            "requirements": self._natural_conditions_from_inputs(),
        }
        self._catalog.natural_evolutions.append(row)
        index = len(self._catalog.natural_evolutions) - 1
        self._mark_dirty()
        self._refresh_table()
        self._refresh_evolution_tables()
        self._select_evolution_row(self._natural_table, index)
        self._refresh_validation()

    def remove_selected_natural_evolution(self) -> None:
        index = self._selected_evolution_index(self._natural_table)
        if index is None:
            return
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
        selector = self._special_selector_from_mode(selector_mode, selected_id)
        trigger = self._special_trigger_input.text().strip()
        if not selector or not trigger or self._special_evolution_exists(target_id, selector, trigger):
            return
        row = {
            "id": f"special__to__{target_id}",
            "type": "special",
            "target_species_id": target_id,
            "source_selector": selector,
            "trigger": trigger,
            "notes": [],
        }
        self._catalog.special_evolutions.append(row)
        index = len(self._catalog.special_evolutions) - 1
        self._mark_dirty()
        self._refresh_table()
        self._refresh_evolution_tables()
        self._select_evolution_row(self._special_table, index)
        self._refresh_validation()

    def remove_selected_special_evolution(self) -> None:
        index = self._selected_evolution_index(self._special_table)
        if index is None:
            return
        if 0 <= index < len(self._catalog.special_evolutions):
            self._catalog.special_evolutions.pop(index)
            self._mark_dirty()
            self._refresh_table()
            self._refresh_evolution_tables()
            self._refresh_validation()

    def _current_item_catalog(self) -> ItemCatalog | None:
        if self._item_catalog is not None:
            return self._item_catalog
        if not self._item_save_path.exists():
            return None
        try:
            return load_item_catalog(self._item_save_path)
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None

    def _refresh_validation(self) -> None:
        result = validate_digimon_catalog(
            self._catalog,
            self._project_root,
            sprite_manifest_path=self._sprite_manifest_path,
            item_catalog=self._current_item_catalog(),
        )
        self._set_validation_indexes(result.errors, result.warnings)
        self._validation_summary_label.setText(
            f"{len(result.errors)} error{'s' if len(result.errors) != 1 else ''} - "
            f"{len(result.warnings)} warning{'s' if len(result.warnings) != 1 else ''}"
        )
        if result.errors:
            self._validation_summary_label.setProperty("state", "error")
        elif result.warnings:
            self._validation_summary_label.setProperty("state", "warning")
        else:
            self._validation_summary_label.setProperty("state", "ok")
        self._validation_summary_label.style().unpolish(self._validation_summary_label)
        self._validation_summary_label.style().polish(self._validation_summary_label)
        lines: list[str] = []
        if result.errors:
            lines.append("Errors:")
            lines.extend(f"- {error}" for error in result.errors)
        if result.warnings:
            lines.append("Warnings:")
            lines.extend(f"- {warning}" for warning in result.warnings)
        self._validation_output.setPlainText("\n".join(lines) if lines else "No validation issues.")
        self._refresh_selected_context()

    def _refresh_validation_indexes(self) -> None:
        result = validate_digimon_catalog(
            self._catalog,
            self._project_root,
            sprite_manifest_path=self._sprite_manifest_path,
            item_catalog=self._current_item_catalog(),
        )
        self._set_validation_indexes(result.errors, result.warnings)
        self._refresh_selected_validation()

    def _set_validation_indexes(self, errors: list[str], warnings: list[str]) -> None:
        self._validation_errors_by_species = self._messages_by_species(errors)
        self._validation_warnings_by_species = self._messages_by_species(warnings)

    def _messages_by_species(self, messages: list[str]) -> dict[str, list[str]]:
        species_ids = set(self._catalog.species_by_id())
        by_species: dict[str, list[str]] = {}
        for message in messages:
            species_id = _message_species_id(message, species_ids)
            if species_id is not None:
                by_species.setdefault(species_id, []).append(message)
        return by_species

    def save_catalog(self) -> bool:
        result = validate_digimon_catalog(
            self._catalog,
            self._project_root,
            sprite_manifest_path=self._sprite_manifest_path,
            item_catalog=self._current_item_catalog(),
        )
        fusion_result = (
            self._fusion_manager_window.refresh_validation()
            if self._fusion_manager_window is not None
            else None
        )
        self._refresh_validation()
        if result.has_errors or (fusion_result is not None and fusion_result.has_errors):
            self._status_label.setText("Save failed: validation errors")
            return False
        try:
            self._species_path.write_text(
                json.dumps(digimon_catalog_to_species_rows(self._catalog), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            self._digivolutions_path.write_text(
                json.dumps(digimon_catalog_to_digivolutions(self._catalog), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as error:
            path = getattr(error, "filename", None) or self._digivolutions_path
            self._status_label.setText(f"Save failed: {path}: {error.strerror or error}")
            return False
        if self._fusion_manager_window is not None and not self._fusion_manager_window.save_catalog():
            self._status_label.setText("Save failed: validation errors")
            return False
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


def _message_species_id(message: str, species_ids: set[str]) -> str | None:
    first_token = message.split(" ", 1)[0].strip()
    if first_token in species_ids:
        return first_token
    for species_id in species_ids:
        if f": {species_id}" in message or f" {species_id} " in message:
            return species_id
    return None


def _fusion_recipe_label(recipe: FusionRecipe) -> str:
    return f"{recipe.source_species_ids[0]} + {recipe.source_species_ids[1]} -> {recipe.target_species_id}"
