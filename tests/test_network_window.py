import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QScrollArea

from digimon_pet.app import network_window
from digimon_pet.app.network_window import (
    LINEAGE_NAME_WIDTH,
    LINEAGE_SCROLL_HEIGHT,
    LINEAGE_SPRITE_LABEL_SIZE,
    NetworkWindow,
    _lineage_sprite_transformation_mode,
)
from digimon_pet.domain.models import GrowthStage, PetState, Species
from digimon_pet.network import presence as presence_module
from digimon_pet.network.presence import PeerStatus, PresenceService, build_presence_payload
from digimon_pet.storage.network_settings import NetworkSettings


def _service(settings: NetworkSettings) -> PresenceService:
    state = PetState(species_id="agumon", stage=GrowthStage.ROOKIE)
    species = Species(id="agumon", name="Agumon", stage=GrowthStage.ROOKIE)
    return PresenceService(
        settings=settings,
        payload_provider=lambda: build_presence_payload(settings.trainer_nickname, state, species),
    )


def _write_two_frame_sprite(path) -> None:
    pixmap = QPixmap(48, 24)
    pixmap.fill()
    painter = QPainter(pixmap)
    painter.fillRect(0, 0, 24, 24, QColor("red"))
    painter.fillRect(24, 0, 24, 24, QColor("blue"))
    painter.end()
    pixmap.save(str(path))


def test_network_window_adds_and_removes_friend():
    app = QApplication.instance() or QApplication([])
    settings = NetworkSettings(trainer_nickname="Tai")
    saved = []
    window = NetworkWindow(settings, _service(settings), lambda updated: saved.append(list(updated.friends)))

    window._friend_input.setText("192.168.1.42")
    window._add_friend_button.click()

    assert settings.friends == ["192.168.1.42:54545"]
    assert saved[-1] == ["192.168.1.42:54545"]
    assert window._friends_table.rowCount() == 1
    assert window._friends_table.columnCount() == 7

    window._friends_table.selectRow(0)
    window._remove_friend_button.click()

    assert settings.friends == []
    assert saved[-1] == []


def test_network_window_shows_read_only_trainer_and_applies_enabled_state():
    app = QApplication.instance() or QApplication([])
    settings = NetworkSettings(trainer_nickname="Tai")
    saved = []
    service = _service(settings)
    window = NetworkWindow(settings, service, lambda updated: saved.append(updated.network_enabled))

    assert not hasattr(window, "_nickname_input")
    assert window._trainer_name_label.text() == "Tai"
    window._enabled_checkbox.setChecked(False)
    window._enabled_checkbox.setChecked(True)

    assert settings.trainer_nickname == "Tai"
    assert settings.network_enabled is True
    assert saved[-1] is True
    service.stop()


def test_network_window_has_no_save_button():
    app = QApplication.instance() or QApplication([])
    settings = NetworkSettings(trainer_nickname="Tai")

    window = NetworkWindow(settings, _service(settings), lambda updated: None)

    assert not hasattr(window, "_save_button")


def test_network_window_settings_header_is_compact():
    app = QApplication.instance() or QApplication([])
    settings = NetworkSettings(trainer_nickname="Tai")

    window = NetworkWindow(settings, _service(settings), lambda updated: None)

    assert window._settings_panel.maximumHeight() <= 118


def test_network_window_gives_friend_list_more_width_than_stats_panel():
    app = QApplication.instance() or QApplication([])
    settings = NetworkSettings(trainer_nickname="Tai")

    window = NetworkWindow(settings, _service(settings), lambda updated: None)

    assert window._content_layout.stretch(0) > window._content_layout.stretch(1)


def test_network_window_refresh_does_not_select_friend_without_user_selection():
    app = QApplication.instance() or QApplication([])
    settings = NetworkSettings(trainer_nickname="Tai", friends=["192.168.1.42:54545"])

    window = NetworkWindow(settings, _service(settings), lambda updated: None)
    window.refresh()

    assert window._friends_table.selectedIndexes() == []
    assert window._friends_table.currentRow() == -1


def test_network_window_saves_notification_toggles():
    app = QApplication.instance() or QApplication([])
    settings = NetworkSettings(trainer_nickname="Tai")
    saved = []
    service = _service(settings)
    window = NetworkWindow(
        settings,
        service,
        lambda updated: saved.append(
            (updated.notify_friend_death, updated.notify_friend_ultimate, updated.notify_friend_numemon)
        ),
    )

    assert window._notify_death_checkbox.isChecked() is True
    assert window._notify_ultimate_checkbox.isChecked() is True
    assert window._notify_numemon_checkbox.isChecked() is True

    window._notify_death_checkbox.setChecked(False)
    window._notify_ultimate_checkbox.setChecked(False)
    window._notify_numemon_checkbox.setChecked(False)

    assert settings.notify_friend_death is False
    assert settings.notify_friend_ultimate is False
    assert settings.notify_friend_numemon is False
    assert saved[-1] == (False, False, False)
    service.stop()


def test_network_window_shows_all_local_address_candidates(monkeypatch):
    app = QApplication.instance() or QApplication([])
    settings = NetworkSettings(trainer_nickname="Tai", listen_port=54545)
    monkeypatch.setattr(presence_module, "local_ip_addresses", lambda: ["192.168.0.134", "192.168.0.254"])

    window = NetworkWindow(settings, _service(settings), lambda updated: None)

    assert window._local_address_label.text() == "192.168.0.134:54545, 192.168.0.254:54545"


def test_network_window_copies_first_local_ip_candidate(monkeypatch):
    app = QApplication.instance() or QApplication([])
    settings = NetworkSettings(trainer_nickname="Tai", listen_port=54545)
    monkeypatch.setattr(presence_module, "local_ip_addresses", lambda: ["192.168.0.134", "192.168.0.254"])

    window = NetworkWindow(settings, _service(settings), lambda updated: None)

    window._copy_address_button.click()

    assert app.clipboard().text() == "192.168.0.134"


def test_network_window_rejects_friend_address_with_port():
    app = QApplication.instance() or QApplication([])
    settings = NetworkSettings(trainer_nickname="Tai")
    window = NetworkWindow(settings, _service(settings), lambda updated: None)

    window._friend_input.setText("192.168.1.42:54545")
    window._add_friend_button.click()

    assert settings.friends == []
    assert window._status_label.text() == "Enter the IP only."


def test_network_window_has_no_friend_combat_stats_context_action():
    app = QApplication.instance() or QApplication([])
    settings = NetworkSettings(trainer_nickname="Tai", friends=["192.168.1.42:54545"])
    service = _service(settings)
    payload = {
        "protocol_version": 1,
        "trainer_nickname": "Sora",
        "species_id": "numemon",
        "digimon_name": "Numemon",
        "stage": "champion",
        "age_seconds": 5400,
        "generation_count": 7,
        "collected_species_count": 12,
        "current_generation_species_ids": ["botamon", "koromon", "agumon", "numemon"],
        "current_action": "idle",
        "is_sleeping": False,
        "hp": 9370,
        "mp": 5618,
        "offense": 526,
        "defense": 625,
        "speed": 447,
        "brains": 458,
    }
    service._peers["192.168.1.42:54545"] = PeerStatus(
        address="192.168.1.42:54545",
        online=True,
        payload=payload,
    )
    window = NetworkWindow(settings, service, lambda updated: None)

    assert not hasattr(window, "_friend_details_dialog")
    assert not hasattr(window, "_open_friend_details_for_row")


def test_network_window_embeds_selected_friend_combat_stats():
    app = QApplication.instance() or QApplication([])
    settings = NetworkSettings(trainer_nickname="Tai", friends=["192.168.1.42:54545"])
    service = _service(settings)
    payload = {
        "protocol_version": 1,
        "trainer_nickname": "Sora",
        "species_id": "numemon",
        "digimon_name": "Numemon",
        "stage": "champion",
        "age_seconds": 5400,
        "generation_count": 7,
        "collected_species_count": 12,
        "current_generation_species_ids": ["botamon", "koromon", "agumon", "numemon"],
        "current_action": "idle",
        "is_sleeping": False,
        "hp": 9370,
        "mp": 5618,
        "offense": 526,
        "defense": 625,
        "speed": 447,
        "brains": 458,
    }
    service._peers["192.168.1.42:54545"] = PeerStatus(
        address="192.168.1.42:54545",
        online=True,
        payload=payload,
    )
    window = NetworkWindow(settings, service, lambda updated: None)

    window._friends_table.selectRow(0)

    assert window._friend_detail_name_label.text() == "Numemon"
    assert window._friend_detail_trainer_label.text() == "Sora"
    assert window._friend_detail_stage_label.text() == "Champion"
    assert window._friend_detail_age_label.text() == "Generation 7 - 1 h 30 min"
    assert isinstance(window._friend_lineage_scroll, QScrollArea)
    assert window._friend_lineage_scroll.horizontalScrollBarPolicy().name == "ScrollBarAsNeeded"
    lineage_labels = [
        label.text()
        for label in window._friend_lineage_content.findChildren(QLabel)
        if label.objectName() in {"FriendLineageName", "FriendLineageArrow"}
    ]
    assert lineage_labels == ["Botamon", "->", "Koromon", "->", "Agumon", "->", "Numemon"]
    assert window._friend_detail_stats["hp"].text() == "9370"
    assert window._friend_detail_stats["mp"].text() == "5618"


def test_network_window_lineage_history_uses_compact_detail_strip():
    app = QApplication.instance() or QApplication([])
    settings = NetworkSettings(trainer_nickname="Tai", friends=["192.168.1.42:54545"])
    service = _service(settings)
    payload = {
        "protocol_version": 1,
        "trainer_nickname": "Sora",
        "species_id": "numemon",
        "digimon_name": "Numemon",
        "stage": "champion",
        "age_seconds": 5400,
        "generation_count": 7,
        "collected_species_count": 12,
        "current_generation_species_ids": ["botamon", "koromon", "agumon", "numemon"],
        "current_action": "idle",
        "is_sleeping": False,
        "hp": 9370,
        "mp": 5618,
        "offense": 526,
        "defense": 625,
        "speed": 447,
        "brains": 458,
    }
    service._peers["192.168.1.42:54545"] = PeerStatus(
        address="192.168.1.42:54545",
        online=True,
        payload=payload,
    )

    window = NetworkWindow(settings, service, lambda updated: None)
    window._friends_table.selectRow(0)

    sprite_labels = [
        label for label in window._friend_lineage_content.findChildren(QLabel)
        if label.objectName() == "FriendLineageSprite"
    ]
    name_labels = [
        label for label in window._friend_lineage_content.findChildren(QLabel)
        if label.objectName() == "FriendLineageName"
    ]
    assert window._friend_lineage_scroll.height() == LINEAGE_SCROLL_HEIGHT
    assert all(label.width() == LINEAGE_SPRITE_LABEL_SIZE for label in sprite_labels)
    assert all(label.width() == LINEAGE_NAME_WIDTH for label in name_labels)


def test_network_window_table_shows_self_and_summary_columns():
    app = QApplication.instance() or QApplication([])
    settings = NetworkSettings(trainer_nickname="Tai", friends=["192.168.1.42:54545"])
    service = _service(settings)
    local_payload = {
        "protocol_version": 1,
        "trainer_nickname": "Tai",
        "species_id": "agumon",
        "digimon_name": "Agumon",
        "stage": "rookie",
        "age_seconds": 120,
        "generation_count": 4,
        "collected_species_count": 9,
        "current_generation_species_ids": ["botamon", "koromon", "agumon"],
        "current_action": "idle",
        "is_sleeping": False,
        "hp": 1000,
        "mp": 500,
        "offense": 100,
        "defense": 90,
        "speed": 80,
        "brains": 70,
    }

    window = NetworkWindow(settings, service, lambda updated: None, lambda: local_payload)

    assert window._friends_table.rowCount() == 2
    assert [window._friends_table.horizontalHeaderItem(index).text() for index in range(7)] == [
        "Trainer",
        "Connected",
        "Digimon",
        "Total Stats",
        "Generation",
        "Collected",
        "Sprite",
    ]
    assert window._friends_table.item(0, 0).text() == "Tai"
    assert window._friends_table.item(0, 3).text() == "490"
    assert window._friends_table.item(0, 4).text() == "4"
    assert window._friends_table.item(0, 5).text() == "9"


def test_network_window_sorts_numeric_summary_columns():
    app = QApplication.instance() or QApplication([])
    settings = NetworkSettings(trainer_nickname="Tai", friends=["192.168.1.42:54545", "192.168.1.43:54545"])
    service = _service(settings)
    for address, trainer, generation in [
        ("192.168.1.42:54545", "Sora", 12),
        ("192.168.1.43:54545", "Matt", 3),
    ]:
        service._peers[address] = PeerStatus(
            address=address,
            online=True,
            payload={
                "protocol_version": 1,
                "trainer_nickname": trainer,
                "species_id": "agumon",
                "digimon_name": "Agumon",
                "stage": "rookie",
                "age_seconds": 120,
                "generation_count": generation,
                "collected_species_count": generation,
                "current_generation_species_ids": ["agumon"],
                "current_action": "idle",
                "is_sleeping": False,
                "hp": generation * 1000,
                "mp": 0,
                "offense": 0,
                "defense": 0,
                "speed": 0,
                "brains": 0,
            },
        )
    window = NetworkWindow(settings, service, lambda updated: None)

    window._friends_table.sortItems(4, Qt.SortOrder.AscendingOrder)

    assert [window._friends_table.item(row, 0).text() for row in range(2)] == ["Matt", "Sora"]


def test_network_window_table_shows_animated_idle_sprite(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    sprite_path = tmp_path / "agumon_idle.png"
    _write_two_frame_sprite(sprite_path)
    monkeypatch.setattr(
        network_window,
        "load_species",
        lambda: {"agumon": Species(id="agumon", name="Agumon", stage=GrowthStage.ROOKIE)},
    )
    monkeypatch.setattr(
        network_window,
        "load_runtime_manifest",
        lambda: {
            "entries": {
                "agumon": {
                    "asset_path": str(sprite_path),
                    "metadata": {"frame_count": 2, "fps": 10},
                }
            }
        },
    )
    settings = NetworkSettings(trainer_nickname="Tai", friends=["192.168.1.42:54545"])
    service = _service(settings)
    payload = {
        "protocol_version": 1,
        "trainer_nickname": "Sora",
        "species_id": "agumon",
        "digimon_name": "Agumon",
        "stage": "rookie",
        "age_seconds": 5400,
        "current_generation_species_ids": ["agumon"],
        "current_action": "idle",
        "is_sleeping": False,
        "hp": 9370,
        "mp": 5618,
        "offense": 526,
        "defense": 625,
        "speed": 447,
        "brains": 458,
    }
    service._peers["192.168.1.42:54545"] = PeerStatus(
        address="192.168.1.42:54545",
        online=True,
        payload=payload,
    )

    window = NetworkWindow(settings, service, lambda updated: None)

    label, sprite = window._friend_table_sprite_labels[0]
    assert window._friends_table.horizontalHeaderItem(6).text() == "Sprite"
    assert label.pixmap() is not None
    assert sprite.current_frame_index == 0

    window._advance_idle_sprites()

    assert sprite.current_frame_index == 1


def test_friend_lineage_sprites_use_pixel_art_scaling():
    assert _lineage_sprite_transformation_mode() == Qt.TransformationMode.FastTransformation
