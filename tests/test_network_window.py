import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QScrollArea

from digimon_pet.app.network_window import NetworkWindow
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
    assert window._friends_table.columnCount() == 3

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
        "age_seconds": 7800,
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
        "age_seconds": 7800,
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
    assert window._friend_detail_age_label.text() == "2 h 10 min"
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
