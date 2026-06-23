from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_launcher_installs_when_cryptography_is_missing():
    launcher = (ROOT / "Digimon Pet.bat").read_text(encoding="utf-8")

    assert "import PySide6, cryptography" in launcher


def test_macos_launcher_installs_when_cryptography_is_missing():
    launcher = (ROOT / "Digimon Pet.command").read_text(encoding="utf-8")

    assert "import PySide6, cryptography" in launcher
