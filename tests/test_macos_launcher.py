from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_macos_launcher_requires_python_311_or_newer():
    launcher = (ROOT / "Digimon Pet.command").read_text(encoding="utf-8")

    assert "python3.12 python3.11 python3" in launcher
    assert "sys.version_info >= (3, 11)" in launcher
    assert "Install Python 3.11 or newer" in launcher


def test_macos_launcher_rejects_stale_virtualenv_python():
    launcher = (ROOT / "Digimon Pet.command").read_text(encoding="utf-8")

    assert 'if ! "$VENV_PY" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"' in launcher
    assert "The existing .venv uses Python older than 3.11" in launcher


def test_macos_app_launcher_logs_to_project_local_log():
    launcher = (ROOT / "Digimon Pet.app" / "Contents" / "MacOS" / "Digimon Pet").read_text(encoding="utf-8")

    assert "PROJECT_ROOT=" in launcher
    assert "DIGIMON_PET_SILENT=1" in launcher
    assert ".local/launcher-macos.log" in launcher
