from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from digimon_pet.app.artwork_runtime import resolve_artwork_path
from digimon_pet.app.animated_sprite import IdleSpriteSheet, idle_sprite_for_species
from digimon_pet.app.sprite_runtime import load_runtime_manifest
from digimon_pet.app.theme import APP_QSS
from digimon_pet.app.stats_window import _format_age
from digimon_pet.data import load_species
from digimon_pet.domain.models import GrowthStage, PetState, Species
from digimon_pet.network import presence as presence_module
from digimon_pet.network.presence import PresencePayload, PresenceService
from digimon_pet.storage.network_settings import (
    DEFAULT_LISTEN_PORT,
    NetworkSettings,
    normalize_friend_address,
)


class NetworkWindow(QDialog):
    def __init__(
        self,
        settings: NetworkSettings,
        service: PresenceService,
        settings_changed: Callable[[NetworkSettings], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._service = service
        self._settings_changed = settings_changed
        self._species_by_id = load_species()
        self._manifest = load_runtime_manifest()
        self._lineage_sprite_labels: list[tuple[QLabel, IdleSpriteSheet]] = []
        self._friend_table_sprite_labels: list[tuple[QLabel, IdleSpriteSheet]] = []
        self.setWindowTitle("Local Network")
        self.setStyleSheet(APP_QSS)
        self.setMinimumSize(760, 500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self._settings_panel = QFrame(self)
        self._settings_panel.setObjectName("StatsPanel")
        self._settings_panel.setMaximumHeight(112)
        settings_layout = QVBoxLayout(self._settings_panel)
        settings_layout.setContentsMargins(10, 8, 10, 8)
        settings_layout.setSpacing(6)

        settings_top_row = QHBoxLayout()
        settings_top_row.setSpacing(10)
        title = QLabel("Local Network", self)
        title.setObjectName("Title")
        settings_top_row.addWidget(title)

        trainer_label = QLabel("Trainer", self)
        trainer_label.setObjectName("Muted")
        settings_top_row.addWidget(trainer_label)
        self._trainer_name_label = QLabel(settings.trainer_nickname or "-", self)
        self._trainer_name_label.setObjectName("StatsMetricValue")
        self._trainer_name_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        settings_top_row.addWidget(self._trainer_name_label)
        self._enabled_checkbox = QCheckBox("Available on local network", self)
        self._enabled_checkbox.setObjectName("NetworkEnabledCheckbox")
        self._enabled_checkbox.setChecked(settings.network_enabled)
        settings_top_row.addWidget(self._enabled_checkbox)
        self._local_address_label = QLabel(self._local_address_text(), self)
        self._local_address_label.setObjectName("Muted")
        self._local_address_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        settings_top_row.addStretch(1)
        address_label = QLabel("Your address", self)
        address_label.setObjectName("Muted")
        settings_top_row.addWidget(address_label)
        settings_top_row.addWidget(self._local_address_label, 1)
        self._copy_address_button = QPushButton("Copy", self)
        self._copy_address_button.setObjectName("PrimaryButton")
        self._copy_address_button.setToolTip("Copy first local network address")
        self._copy_address_button.setMaximumWidth(68)
        settings_top_row.addWidget(self._copy_address_button)
        settings_layout.addLayout(settings_top_row)

        self._notify_death_checkbox = QCheckBox("Notify when a friend's Digimon dies", self)
        self._notify_death_checkbox.setObjectName("NetworkNotifyDeathCheckbox")
        self._notify_death_checkbox.setChecked(settings.notify_friend_death)
        self._notify_ultimate_checkbox = QCheckBox("Notify when a friend's Digimon becomes Ultimate", self)
        self._notify_ultimate_checkbox.setObjectName("NetworkNotifyUltimateCheckbox")
        self._notify_ultimate_checkbox.setChecked(settings.notify_friend_ultimate)
        self._notify_numemon_checkbox = QCheckBox("Notify when a friend gets Numemon", self)
        self._notify_numemon_checkbox.setObjectName("NetworkNotifyNumemonCheckbox")
        self._notify_numemon_checkbox.setChecked(settings.notify_friend_numemon)
        settings_bottom_row = QHBoxLayout()
        settings_bottom_row.setSpacing(14)
        settings_bottom_row.addWidget(self._notify_death_checkbox)
        settings_bottom_row.addWidget(self._notify_ultimate_checkbox)
        settings_bottom_row.addWidget(self._notify_numemon_checkbox)
        settings_bottom_row.addStretch(1)
        settings_layout.addLayout(settings_bottom_row)
        layout.addWidget(self._settings_panel)

        friend_row = QHBoxLayout()
        self._friend_input = QLineEdit(self)
        self._friend_input.setObjectName("NetworkFriendInput")
        self._friend_input.setPlaceholderText("192.168.1.42")
        self._add_friend_button = QPushButton("Add", self)
        self._add_friend_button.setObjectName("PrimaryButton")
        self._remove_friend_button = QPushButton("Remove", self)
        friend_row.addWidget(self._friend_input, 1)
        friend_row.addWidget(self._add_friend_button)
        friend_row.addWidget(self._remove_friend_button)
        layout.addLayout(friend_row)

        self._status_label = QLabel("", self)
        self._status_label.setObjectName("Muted")
        layout.addWidget(self._status_label)

        content = QHBoxLayout()
        content.setSpacing(10)
        self._friends_table = QTableWidget(0, 4, self)
        self._friends_table.setObjectName("NetworkFriendsTable")
        self._friends_table.setHorizontalHeaderLabels(["Trainer", "Connected", "Digimon", "Sprite"])
        self._friends_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._friends_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._friends_table.verticalHeader().setDefaultSectionSize(42)
        self._friends_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._friends_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        content.addWidget(self._friends_table, 1)
        content.addWidget(self._build_friend_detail_panel(), 2)
        layout.addLayout(content, 1)

        self._enabled_checkbox.toggled.connect(lambda checked=False: self._save_from_inputs())
        self._notify_death_checkbox.toggled.connect(lambda checked=False: self._save_from_inputs())
        self._notify_ultimate_checkbox.toggled.connect(lambda checked=False: self._save_from_inputs())
        self._notify_numemon_checkbox.toggled.connect(lambda checked=False: self._save_from_inputs())
        self._copy_address_button.clicked.connect(self._copy_local_address)
        self._add_friend_button.clicked.connect(self._add_friend)
        self._remove_friend_button.clicked.connect(self._remove_selected_friend)
        self._friends_table.itemSelectionChanged.connect(self._refresh_friend_detail)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start(1000)
        self._sprite_animation_timer = QTimer(self)
        self._sprite_animation_timer.timeout.connect(self._advance_idle_sprites)
        self._sprite_animation_timer.start(250)
        self.refresh()

    def refresh(self) -> None:
        self._local_address_label.setText(self._local_address_text())
        self._friend_table_sprite_labels = []
        self._friends_table.setRowCount(len(self._settings.friends))
        statuses = {status.address: status for status in self._service.peer_statuses()}
        for row, address in enumerate(self._settings.friends):
            status = statuses.get(address)
            payload = status.payload if status is not None else None
            state_text = "Online" if status is not None and status.online else "Offline"
            trainer = str(payload["trainer_nickname"]) if payload is not None else address.split(":", 1)[0]
            digimon = str(payload["digimon_name"]) if payload is not None else ""
            trainer_item = QTableWidgetItem(trainer)
            trainer_item.setToolTip(address)
            self._friends_table.setItem(row, 0, trainer_item)
            self._friends_table.setItem(row, 1, QTableWidgetItem(state_text))
            self._friends_table.setItem(row, 2, QTableWidgetItem(digimon))
            self._set_friend_table_sprite(row, payload if status is not None and status.online else None)
        if self._service.last_error:
            self._status_label.setText(self._service.last_error)
        elif self._settings.network_enabled:
            self._status_label.setText("Network availability is enabled.")
        else:
            self._status_label.setText("Network availability is disabled.")
        self._refresh_friend_detail()

    def _save_from_inputs(self) -> None:
        self._settings.network_enabled = self._enabled_checkbox.isChecked()
        self._settings.listen_port = DEFAULT_LISTEN_PORT
        self._settings.notify_friend_death = self._notify_death_checkbox.isChecked()
        self._settings.notify_friend_ultimate = self._notify_ultimate_checkbox.isChecked()
        self._settings.notify_friend_numemon = self._notify_numemon_checkbox.isChecked()
        self._settings_changed(self._settings)
        self._enabled_checkbox.setChecked(self._settings.network_enabled)
        self._notify_death_checkbox.setChecked(self._settings.notify_friend_death)
        self._notify_ultimate_checkbox.setChecked(self._settings.notify_friend_ultimate)
        self._notify_numemon_checkbox.setChecked(self._settings.notify_friend_numemon)
        self.refresh()

    def _add_friend(self) -> None:
        try:
            address = normalize_friend_address(self._friend_input.text())
        except ValueError as exc:
            self._status_label.setText(str(exc))
            return
        if address not in self._settings.friends:
            self._settings.friends.append(address)
        self._friend_input.clear()
        self._settings_changed(self._settings)
        self.refresh()

    def _copy_local_address(self) -> None:
        QApplication.clipboard().setText(self._primary_local_ip_text())
        self._status_label.setText("IP copied.")

    def _remove_selected_friend(self) -> None:
        selected_rows = sorted({index.row() for index in self._friends_table.selectedIndexes()}, reverse=True)
        for row in selected_rows:
            if 0 <= row < len(self._settings.friends):
                del self._settings.friends[row]
        if selected_rows:
            self._settings_changed(self._settings)
            self.refresh()

    def _payload_for_row(self, row: int) -> PresencePayload | None:
        if row < 0 or row >= len(self._settings.friends):
            return None
        address = self._settings.friends[row]
        statuses = {status.address: status for status in self._service.peer_statuses()}
        status = statuses.get(address)
        if status is None or not status.online:
            return None
        return status.payload

    def _local_address_text(self) -> str:
        return ", ".join(f"{address}:{DEFAULT_LISTEN_PORT}" for address in presence_module.local_ip_addresses())

    def _primary_local_ip_text(self) -> str:
        return presence_module.local_ip_addresses()[0]

    def _build_friend_detail_panel(self) -> QFrame:
        panel = QFrame(self)
        panel.setObjectName("StatsPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(10)
        self._friend_detail_sprite_label = QLabel(self)
        self._friend_detail_sprite_label.setObjectName("StatsPortrait")
        self._friend_detail_sprite_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._friend_detail_sprite_label.setFixedSize(116, 116)
        header.addWidget(self._friend_detail_sprite_label)

        identity = QVBoxLayout()
        identity.setSpacing(3)
        self._friend_detail_name_label = QLabel("Select a friend", self)
        self._friend_detail_name_label.setObjectName("Title")
        self._friend_detail_trainer_label = QLabel("", self)
        self._friend_detail_trainer_label.setObjectName("Muted")
        self._friend_detail_stage_label = QLabel("", self)
        self._friend_detail_stage_label.setObjectName("StatsStage")
        self._friend_detail_age_label = QLabel("", self)
        self._friend_detail_age_label.setObjectName("Muted")
        identity.addWidget(self._friend_detail_name_label)
        identity.addWidget(self._friend_detail_stage_label)
        identity.addWidget(self._friend_detail_age_label)
        identity.addWidget(self._friend_detail_trainer_label)
        identity.addStretch(1)
        header.addLayout(identity, 1)

        self._friend_lineage_scroll = QScrollArea(self)
        self._friend_lineage_scroll.setObjectName("FriendLineageScroll")
        self._friend_lineage_scroll.setWidgetResizable(True)
        self._friend_lineage_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._friend_lineage_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._friend_lineage_scroll.setMinimumHeight(92)
        self._friend_lineage_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._friend_lineage_content = QWidget(self._friend_lineage_scroll)
        self._friend_lineage_layout = QHBoxLayout(self._friend_lineage_content)
        self._friend_lineage_layout.setContentsMargins(4, 2, 4, 2)
        self._friend_lineage_layout.setSpacing(8)
        self._friend_lineage_scroll.setWidget(self._friend_lineage_content)
        header.addWidget(self._friend_lineage_scroll, 3)
        layout.addLayout(header)

        title = QLabel("Combat", self)
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(6)
        layout.addLayout(grid)
        self._friend_detail_stats: dict[str, QLabel] = {}
        self._friend_detail_bars: dict[str, QProgressBar] = {}
        for index, (key, label) in enumerate(
            [
                ("hp", "HP"),
                ("mp", "MP"),
                ("offense", "OFF"),
                ("defense", "DEF"),
                ("speed", "SPD"),
                ("brains", "INT"),
            ]
        ):
            cell = self._friend_stat_cell(key, label)
            grid.addLayout(cell, index // 2, index % 2)
        layout.addStretch(1)
        return panel

    def _friend_stat_cell(self, key: str, title: str) -> QVBoxLayout:
        cell = QVBoxLayout()
        cell.setSpacing(3)
        header = QHBoxLayout()
        header.setSpacing(6)
        title_label = QLabel(title, self)
        title_label.setObjectName("Muted")
        value = QLabel("-", self)
        value.setObjectName("StatsMetricValue")
        value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        header.addWidget(title_label)
        header.addStretch(1)
        header.addWidget(value)
        bar = QProgressBar(self)
        bar.setRange(0, _stat_maximum(key))
        bar.setTextVisible(False)
        bar.setObjectName(f"StatsCombatBar_{key}")
        bar.setFixedHeight(4)
        self._friend_detail_stats[key] = value
        self._friend_detail_bars[key] = bar
        cell.addLayout(header)
        cell.addWidget(bar)
        return cell

    def _refresh_friend_detail(self) -> None:
        row = self._friends_table.currentRow()
        payload = self._payload_for_row(row)
        if payload is None:
            self._friend_detail_sprite_label.clear()
            self._friend_detail_name_label.setText("Select an online friend")
            self._friend_detail_trainer_label.setText("")
            self._friend_detail_stage_label.setText("")
            self._friend_detail_age_label.setText("")
            self._set_friend_lineage([])
            for key, label in self._friend_detail_stats.items():
                label.setText("-")
                self._friend_detail_bars[key].setValue(0)
            return
        digimon = str(payload.get("digimon_name", "Digimon"))
        trainer = str(payload.get("trainer_nickname", "")).strip()
        self._friend_detail_name_label.setText(digimon)
        self._friend_detail_trainer_label.setText(trainer)
        self._friend_detail_stage_label.setText(_format_stage(str(payload.get("stage", ""))))
        self._friend_detail_age_label.setText(
            f"Generation {int(payload.get('generation_count', 1))} - {_format_age(int(payload.get('age_seconds', 0)))}"
        )
        self._set_friend_sprite(payload)
        self._set_friend_lineage(_lineage_species_ids_from_payload(payload))
        for key in self._friend_detail_stats:
            value = int(payload.get(key, 0))
            maximum = _stat_maximum(key)
            self._friend_detail_stats[key].setText(str(value))
            self._friend_detail_bars[key].setRange(0, maximum)
            self._friend_detail_bars[key].setValue(max(0, min(maximum, value)))

    def _set_friend_sprite(self, payload: PresencePayload) -> None:
        path = resolve_artwork_path(str(payload.get("species_id", "")))
        if path is None:
            self._friend_detail_sprite_label.clear()
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self._friend_detail_sprite_label.clear()
            return
        self._friend_detail_sprite_label.setPixmap(
            pixmap.scaled(
                108,
                108,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _set_friend_table_sprite(self, row: int, payload: PresencePayload | None) -> None:
        label = QLabel(self._friends_table)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedSize(40, 36)
        self._friends_table.setCellWidget(row, 3, label)
        if payload is None:
            return
        sprite = self._idle_sprite_from_payload(payload)
        if sprite is None:
            return
        self._friend_table_sprite_labels.append((label, sprite))
        _set_table_sprite_frame(label, sprite)

    def _idle_sprite_from_payload(self, payload: PresencePayload) -> IdleSpriteSheet | None:
        species_id = str(payload.get("species_id", "")).strip()
        if not species_id:
            return None
        species = self._species_by_id.get(species_id)
        if species is None:
            try:
                stage = GrowthStage(str(payload.get("stage", GrowthStage.ROOKIE.value)))
            except ValueError:
                stage = GrowthStage.ROOKIE
            species = Species(species_id, _species_name(species_id), stage)
        return idle_sprite_for_species(species, self._manifest)

    def _set_friend_lineage(self, species_ids: list[str]) -> None:
        self._lineage_sprite_labels = []
        while self._friend_lineage_layout.count():
            item = self._friend_lineage_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not species_ids:
            empty = QLabel("Select an online friend", self._friend_lineage_content)
            empty.setObjectName("Muted")
            self._friend_lineage_layout.addWidget(empty)
            self._friend_lineage_layout.addStretch(1)
            return
        for index, species_id in enumerate(species_ids):
            if index > 0:
                arrow = QLabel("->", self._friend_lineage_content)
                arrow.setObjectName("FriendLineageArrow")
                arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._friend_lineage_layout.addWidget(arrow)
            self._friend_lineage_layout.addWidget(self._lineage_cell(species_id))
        self._friend_lineage_layout.addStretch(1)

    def _lineage_cell(self, species_id: str) -> QWidget:
        species = self._species_by_id.get(species_id, Species(species_id, _species_name(species_id), GrowthStage.ROOKIE))
        cell = QWidget(self._friend_lineage_content)
        cell.setObjectName("FriendLineageCell")
        layout = QVBoxLayout(cell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        sprite_label = QLabel(cell)
        sprite_label.setObjectName("FriendLineageSprite")
        sprite_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sprite_label.setFixedSize(48, 48)
        name_label = QLabel(species.name, cell)
        name_label.setObjectName("FriendLineageName")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setFixedWidth(74)
        name_label.setWordWrap(True)
        layout.addWidget(sprite_label, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)
        sprite = idle_sprite_for_species(species, self._manifest)
        if sprite is not None:
            self._lineage_sprite_labels.append((sprite_label, sprite))
            _set_lineage_sprite_frame(sprite_label, sprite)
        return cell

    def _advance_idle_sprites(self) -> None:
        for label, sprite in self._friend_table_sprite_labels:
            sprite.advance()
            _set_table_sprite_frame(label, sprite)
        for label, sprite in self._lineage_sprite_labels:
            sprite.advance()
            _set_lineage_sprite_frame(label, sprite)


def _format_stage(stage: str) -> str:
    return stage.replace("_", " ").title()


def _stat_maximum(stat: str) -> int:
    return 99999 if stat in {"hp", "mp"} else 9999


def _lineage_species_ids_from_payload(payload: PresencePayload) -> list[str]:
    raw = payload.get("current_generation_species_ids")
    if isinstance(raw, list):
        cleaned = [str(species_id) for species_id in raw if str(species_id).strip()]
        if cleaned:
            return cleaned
    return [str(payload.get("species_id", ""))]


def _species_name(species_id: str) -> str:
    return species_id.replace("_", " ").title() or "Digimon"


def _set_lineage_sprite_frame(label: QLabel, sprite: IdleSpriteSheet) -> None:
    pixmap = sprite.frame_pixmap()
    if pixmap.isNull():
        label.clear()
        return
    label.setPixmap(
        pixmap.scaled(
            44,
            44,
            Qt.AspectRatioMode.KeepAspectRatio,
            _lineage_sprite_transformation_mode(),
        )
    )


def _set_table_sprite_frame(label: QLabel, sprite: IdleSpriteSheet) -> None:
    pixmap = sprite.frame_pixmap()
    if pixmap.isNull():
        label.clear()
        return
    label.setPixmap(
        pixmap.scaled(
            32,
            32,
            Qt.AspectRatioMode.KeepAspectRatio,
            _lineage_sprite_transformation_mode(),
        )
    )


def _lineage_sprite_transformation_mode() -> Qt.TransformationMode:
    return Qt.TransformationMode.FastTransformation
