import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from digimon_pet.app.network_window import NetworkWindow
from digimon_pet.network.presence import PeerStatus
from digimon_pet.network.presence import PresenceService, build_presence_payload
from digimon_pet.storage.network_settings import NetworkSettings
from digimon_pet.domain.models import GrowthStage, PetState, Species


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

    window._friend_input.setText("192.168.1.42:54545")
    window._add_friend_button.click()

    assert settings.friends == ["192.168.1.42:54545"]
    assert saved[-1] == ["192.168.1.42:54545"]
    assert window._friends_table.rowCount() == 1

    window._friends_table.selectRow(0)
    window._remove_friend_button.click()

    assert settings.friends == []
    assert saved[-1] == []


def test_network_window_saves_nickname_and_enabled_state():
    app = QApplication.instance() or QApplication([])
    settings = NetworkSettings(trainer_nickname="Tai")
    saved = []
    service = _service(settings)
    window = NetworkWindow(settings, service, lambda updated: saved.append(updated.network_enabled))

    window._nickname_input.setText("  Sora  ")
    window._enabled_checkbox.setChecked(True)
    window._save_button.click()

    assert settings.trainer_nickname == "Sora"
    assert settings.network_enabled is True
    assert saved[-1] is True
    service.stop()


def test_network_window_opens_friend_combat_stats_from_context_action():
    app = QApplication.instance() or QApplication([])
    settings = NetworkSettings(trainer_nickname="Tai", friends=["192.168.1.42:54545"])
    service = _service(settings)
    payload = {
        "protocol_version": 1,
        "trainer_nickname": "Sora",
        "species_id": "numemon",
        "digimon_name": "Numemon",
        "stage": "champion",
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

    assert window._friends_table.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu

    window._open_friend_details_for_row(0)

    dialog = window._friend_details_dialog
    assert dialog is not None
    assert dialog.windowTitle() == "Numemon - Sora"
    assert dialog._labels["hp"].text() == "9370"
    assert dialog._labels["mp"].text() == "5618"
    assert dialog._labels["offense"].text() == "526"
    assert dialog._labels["defense"].text() == "625"
    assert dialog._labels["speed"].text() == "447"
    assert dialog._labels["brains"].text() == "458"
