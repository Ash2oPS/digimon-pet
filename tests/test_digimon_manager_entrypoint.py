import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_digimon_manager_entrypoint_opens_without_debug_mode(monkeypatch, tmp_path):
    from PySide6.QtWidgets import QApplication

    from digimon_pet.tools import digimon_manager

    windows = []

    class FakeWindow:
        def __init__(self, *args, **kwargs):
            windows.append((args, kwargs))

        def show(self):
            windows.append("shown")

    monkeypatch.setattr(digimon_manager, "PROJECT_ROOT", tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "species.json").write_text("[]\n", encoding="utf-8")
    (data_dir / "dw1_digivolutions.json").write_text(
        '{"natural_evolutions": [], "special_evolutions": [], "indexes": {}}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(digimon_manager, "DigimonManagerWindow", FakeWindow)
    monkeypatch.setattr(QApplication, "exec", lambda self: 0)

    assert digimon_manager.main() == 0
    assert "shown" in windows
