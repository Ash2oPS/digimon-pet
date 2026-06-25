from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from digimon_pet.app.theme import APP_QSS
from digimon_pet.app.stats_window import StatsWindow
from digimon_pet.domain.models import GrowthStage, PetState, Species
from digimon_pet.network import presence as presence_module
from digimon_pet.network.presence import PresencePayload, PresenceService
from digimon_pet.storage.network_settings import (
    MAX_PORT,
    MIN_PORT,
    NetworkSettings,
    is_valid_trainer_nickname,
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
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("Local Network")
        title.setObjectName("Title")
        layout.addWidget(title)

        form = QFormLayout()
        self._nickname_input = QLineEdit(settings.trainer_nickname, self)
        self._nickname_input.setObjectName("NetworkNicknameInput")
        self._enabled_checkbox = QCheckBox("Available on local network", self)
        self._enabled_checkbox.setObjectName("NetworkEnabledCheckbox")
        self._enabled_checkbox.setChecked(settings.network_enabled)
        self._port_input = QSpinBox(self)
        self._port_input.setObjectName("NetworkPortInput")
        self._port_input.setRange(MIN_PORT, MAX_PORT)
        self._port_input.setValue(settings.listen_port)
        self._local_address_label = QLabel(self._local_address_text(), self)
        self._local_address_label.setObjectName("Muted")
        form.addRow("Trainer", self._nickname_input)
        form.addRow("", self._enabled_checkbox)
        form.addRow("Port", self._port_input)
        form.addRow("Your address", self._local_address_label)
        layout.addLayout(form)

        friend_row = QHBoxLayout()
        self._friend_input = QLineEdit(self)
        self._friend_input.setObjectName("NetworkFriendInput")
        self._friend_input.setPlaceholderText("192.168.1.42:54545")
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

        self._friends_table = QTableWidget(0, 4, self)
        self._friends_table.setObjectName("NetworkFriendsTable")
        self._friends_table.setHorizontalHeaderLabels(["Friend", "Status", "Trainer", "Digimon"])
        self._friends_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._friends_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._friends_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._friends_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self._friends_table)

        self._save_button = QPushButton("Save", self)
        self._save_button.setObjectName("PrimaryButton")
        layout.addWidget(self._save_button)

        self._nickname_input.editingFinished.connect(self._save_from_inputs)
        self._enabled_checkbox.toggled.connect(lambda checked=False: self._save_from_inputs())
        self._port_input.valueChanged.connect(lambda value=0: self._save_from_inputs())
        self._add_friend_button.clicked.connect(self._add_friend)
        self._remove_friend_button.clicked.connect(self._remove_selected_friend)
        self._save_button.clicked.connect(self._save_from_inputs)
        self._friends_table.customContextMenuRequested.connect(self._show_friends_context_menu)

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
            trainer = str(payload["trainer_nickname"]) if payload is not None else ""
            digimon = str(payload["digimon_name"]) if payload is not None else ""
            self._friends_table.setItem(row, 0, QTableWidgetItem(address))
            self._friends_table.setItem(row, 1, QTableWidgetItem(state_text))
            self._friends_table.setItem(row, 2, QTableWidgetItem(trainer))
            self._friends_table.setItem(row, 3, QTableWidgetItem(digimon))
        if self._service.last_error:
            self._status_label.setText(self._service.last_error)
        elif self._settings.network_enabled:
            self._status_label.setText("Network availability is enabled.")
        else:
            self._status_label.setText("Network availability is disabled.")

    def _save_from_inputs(self) -> None:
        nickname = self._nickname_input.text().strip()
        if not is_valid_trainer_nickname(nickname):
            self._status_label.setText("Trainer nickname is required.")
            self._nickname_input.setText(self._settings.trainer_nickname)
            return
        self._settings.trainer_nickname = nickname
        self._settings.network_enabled = self._enabled_checkbox.isChecked()
        self._settings.listen_port = self._port_input.value()
        self._settings_changed(self._settings)
        self._enabled_checkbox.setChecked(self._settings.network_enabled)
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
        return ", ".join(f"{address}:{self._settings.listen_port}" for address in presence_module.local_ip_addresses())


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
