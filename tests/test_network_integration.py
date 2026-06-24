import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from digimon_pet.app.main_window import PetWindow
from digimon_pet.domain.models import GrowthStage, PetState
from digimon_pet.storage import debug_settings, network_settings, save_store
from digimon_pet.storage import save_pet_state


def test_pet_window_prompts_for_missing_trainer_nickname_on_show(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    save_path = tmp_path / "pet_save.json"
    monkeypatch.setattr(save_store, "SAVE_PATH", save_path)
    monkeypatch.setattr(save_store, "LEGACY_SAVE_PATH", tmp_path / ".local" / "pet_save.json")
    monkeypatch.setattr(debug_settings, "DEBUG_SETTINGS_PATH", tmp_path / "debug_settings.json")
    settings_path = tmp_path / "network_settings.json"
    monkeypatch.setattr(network_settings, "NETWORK_SETTINGS_PATH", settings_path)
    save_pet_state(PetState(species_id="agumon", stage=GrowthStage.ROOKIE), save_path)
    calls = []
    monkeypatch.setattr(PetWindow, "_get_trainer_nickname", lambda self: calls.append("prompt") or ("Tai", True))

    window = PetWindow(overlay=False, debug=False)
    window.show()
    app.processEvents()

    loaded = network_settings.load_network_settings(settings_path)
    assert calls == ["prompt"]
    assert loaded.trainer_nickname == "Tai"
    window.shutdown()
