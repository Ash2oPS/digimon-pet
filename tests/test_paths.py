from pathlib import Path
import sys

from digimon_pet import platform as desktop_platform
from digimon_pet import paths


def test_user_data_dir_uses_macos_application_support():
    path = desktop_platform.user_data_dir(
        platform_name="darwin",
        home=Path("/Users/tester"),
        environ={},
    )

    assert path == Path("/Users/tester/Library/Application Support/Digimon Pet")


def test_user_data_dir_uses_windows_appdata_when_available():
    path = desktop_platform.user_data_dir(
        platform_name="win32",
        home=Path("C:/Users/tester"),
        environ={"APPDATA": "C:/Users/tester/AppData/Roaming"},
    )

    assert path == Path("C:/Users/tester/AppData/Roaming/Digimon Pet")


def test_legacy_project_save_dir_uses_project_local_folder(tmp_path):
    assert desktop_platform.legacy_project_save_dir(tmp_path) == tmp_path / ".local"


def test_project_root_uses_pyinstaller_meipass_when_frozen(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert paths.project_root() == tmp_path


def test_project_root_finds_macos_bundle_resources(tmp_path, monkeypatch):
    bundle_root = tmp_path / "Digimon Pet.app"
    resources = bundle_root / "Contents" / "Resources"
    executable = bundle_root / "Contents" / "MacOS" / "Digimon Pet"
    (resources / "data").mkdir(parents=True)
    (resources / "assets").mkdir()
    (executable.parent).mkdir(parents=True)
    (resources / "data" / "default_save.json").write_text("{}", encoding="utf-8")
    executable.write_text("", encoding="utf-8")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "missing_meipass"), raising=False)
    monkeypatch.setattr(sys, "executable", str(executable), raising=False)

    assert paths.project_root() == resources
