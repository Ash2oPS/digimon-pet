from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from digimon_pet.app.artwork_runtime import resolve_artwork_path
from digimon_pet.app.theme import APP_QSS
from digimon_pet.app.stats_window import StatsWindow
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
        self._friend_details_dialog: FriendDigimonDetailsDialog | None = None
        self.setWindowTitle("Local Network")
        self.setStyleSheet(APP_QSS)
        self.setMinimumSize(760, 500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("Local Network")
        title.setObjectName("Title")
        layout.addWidget(title)

        form = QFormLayout()
        self._trainer_name_label = QLabel(settings.trainer_nickname or "-", self)
        self._trainer_name_label.setObjectName("StatsMetricValue")
        self._trainer_name_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._enabled_checkbox = QCheckBox("Available on local network", self)
        self._enabled_checkbox.setObjectName("NetworkEnabledCheckbox")
        self._enabled_checkbox.setChecked(settings.network_enabled)
        self._local_address_label = QLabel(self._local_address_text(), self)
        self._local_address_label.setObjectName("Muted")
        self._copy_address_button = QPushButton("Copy", self)
        self._copy_address_button.setObjectName("PrimaryButton")
        self._copy_address_button.setToolTip("Copy first local network address")
        self._copy_address_button.setMaximumWidth(68)
        address_row = QHBoxLayout()
        address_row.addWidget(self._local_address_label, 1)
        address_row.addWidget(self._copy_address_button)
        form.addRow("Trainer", self._trainer_name_label)
        form.addRow("", self._enabled_checkbox)
        form.addRow("Your address", address_row)
        layout.addLayout(form)

        self._notify_death_checkbox = QCheckBox("Notify when a friend's Digimon dies", self)
        self._notify_death_checkbox.setObjectName("NetworkNotifyDeathCheckbox")
        self._notify_death_checkbox.setChecked(settings.notify_friend_death)
        self._notify_ultimate_checkbox = QCheckBox("Notify when a friend's Digimon becomes Ultimate", self)
        self._notify_ultimate_checkbox.setObjectName("NetworkNotifyUltimateCheckbox")
        self._notify_ultimate_checkbox.setChecked(settings.notify_friend_ultimate)
        layout.addWidget(self._notify_death_checkbox)
        layout.addWidget(self._notify_ultimate_checkbox)

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
        self._friends_table = QTableWidget(0, 3, self)
        self._friends_table.setObjectName("NetworkFriendsTable")
        self._friends_table.setHorizontalHeaderLabels(["Trainer", "Connected", "Digimon"])
        self._friends_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._friends_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._friends_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._friends_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        content.addWidget(self._friends_table, 1)
        content.addWidget(self._build_friend_detail_panel(), 2)
        layout.addLayout(content, 1)

        self._enabled_checkbox.toggled.connect(lambda checked=False: self._save_from_inputs())
        self._notify_death_checkbox.toggled.connect(lambda checked=False: self._save_from_inputs())
        self._notify_ultimate_checkbox.toggled.connect(lambda checked=False: self._save_from_inputs())
        self._copy_address_button.clicked.connect(self._copy_local_address)
        self._add_friend_button.clicked.connect(self._add_friend)
        self._remove_friend_button.clicked.connect(self._remove_selected_friend)
        self._friends_table.customContextMenuRequested.connect(self._show_friends_context_menu)
        self._friends_table.itemSelectionChanged.connect(self._refresh_friend_detail)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start(1000)
        self.refresh()

    def refresh(self) -> None:
        self._local_address_label.setText(self._local_address_text())
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
        self._settings_changed(self._settings)
        self._enabled_checkbox.setChecked(self._settings.network_enabled)
        self._notify_death_checkbox.setChecked(self._settings.notify_friend_death)
        self._notify_ultimate_checkbox.setChecked(self._settings.notify_friend_ultimate)
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
        QApplication.clipboard().setText(self._primary_local_address_text())
        self._status_label.setText("Address copied.")

    def _remove_selected_friend(self) -> None:
        selected_rows = sorted({index.row() for index in self._friends_table.selectedIndexes()}, reverse=True)
        for row in selected_rows:
            if 0 <= row < len(self._settings.friends):
                del self._settings.friends[row]
        if selected_rows:
            self._settings_changed(self._settings)
            self.refresh()

    def _show_friends_context_menu(self, position: QPoint) -> None:
        row = self._friends_table.rowAt(position.y())
        if row < 0:
            return
        self._friends_table.selectRow(row)
        menu = QMenu(self)
        details_action = menu.addAction("View Digimon combat stats")
        details_action.setEnabled(self._payload_for_row(row) is not None)
        selected = menu.exec(self._friends_table.viewport().mapToGlobal(position))
        if selected == details_action:
            self._open_friend_details_for_row(row)

    def _open_friend_details_for_row(self, row: int) -> None:
        payload = self._payload_for_row(row)
        if payload is None:
            self._status_label.setText("Friend Digimon details are unavailable.")
            return
        self._friend_details_dialog = FriendDigimonDetailsDialog(payload, self)
        self._friend_details_dialog.show()
        self._friend_details_dialog.raise_()
        self._friend_details_dialog.activateWindow()

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

    def _primary_local_address_text(self) -> str:
        return f"{presence_module.local_ip_addresses()[0]}:{DEFAULT_LISTEN_PORT}"

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
        identity.addWidget(self._friend_detail_name_label)
        identity.addWidget(self._friend_detail_stage_label)
        identity.addWidget(self._friend_detail_trainer_label)
        identity.addStretch(1)
        header.addLayout(identity, 1)
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
            for key, label in self._friend_detail_stats.items():
                label.setText("-")
                self._friend_detail_bars[key].setValue(0)
            return
        digimon = str(payload.get("digimon_name", "Digimon"))
        trainer = str(payload.get("trainer_nickname", "")).strip()
        self._friend_detail_name_label.setText(digimon)
        self._friend_detail_trainer_label.setText(trainer)
        self._friend_detail_stage_label.setText(_format_stage(str(payload.get("stage", ""))))
        self._set_friend_sprite(payload)
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


class FriendDigimonDetailsDialog(StatsWindow):
    def __init__(self, payload: PresencePayload, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._payload = payload
        trainer = str(payload.get("trainer_nickname", "")).strip()
        digimon = str(payload.get("digimon_name", "")).strip() or "Digimon"
        self.setWindowTitle(f"{digimon} - {trainer}" if trainer else digimon)
        self._labels = {}
        self._label_groups = {}
        self._bars = {}
        self._bar_groups = {}
        while self._tabs.count():
            self._tabs.removeTab(0)
        self._tabs.addTab(self._build_friend_view_tab(), "View")
        self.refresh(_state_from_presence_payload(payload), _species_from_presence_payload(payload))
        self._summary_label.setText(f"{self._stage_label.text()} - {trainer}" if trainer else self._stage_label.text())

    def _build_friend_view_tab(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addWidget(self._combat_panel())
        layout.addStretch(1)
        return page


def _state_from_presence_payload(payload: PresencePayload) -> PetState:
    stage = _growth_stage_from_payload(payload)
    return PetState(
        species_id=str(payload["species_id"]),
        stage=stage,
        current_action=str(payload.get("current_action", "idle")),
        is_sleeping=bool(payload.get("is_sleeping", False)),
        hp=int(payload["hp"]),
        mp=int(payload["mp"]),
        offense=int(payload["offense"]),
        defense=int(payload["defense"]),
        speed=int(payload["speed"]),
        brains=int(payload["brains"]),
    )


def _species_from_presence_payload(payload: PresencePayload) -> Species:
    return Species(
        id=str(payload["species_id"]),
        name=str(payload["digimon_name"]),
        stage=_growth_stage_from_payload(payload),
    )


def _growth_stage_from_payload(payload: PresencePayload) -> GrowthStage:
    try:
        return GrowthStage(str(payload["stage"]))
    except ValueError:
        return GrowthStage.ROOKIE


def _format_stage(stage: str) -> str:
    return stage.replace("_", " ").title()


def _stat_maximum(stat: str) -> int:
    return 99999 if stat in {"hp", "mp"} else 9999
