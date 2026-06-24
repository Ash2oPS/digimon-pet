import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from digimon_pet.app.network_window import NetworkWindow
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
