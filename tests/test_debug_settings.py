from digimon_pet.storage import debug_settings
from digimon_pet.storage.debug_settings import DebugSettings, load_debug_settings, save_debug_settings


def test_debug_settings_roundtrip(tmp_path):
    path = tmp_path / "debug_settings.json"
    settings = DebugSettings(time_scale=42, auto_rebirth_random=True, auto_lifecycle_events=True)

    save_debug_settings(settings, path)
    loaded = load_debug_settings(path)

    assert loaded == settings


def test_debug_settings_defaults_when_missing(tmp_path):
    loaded = load_debug_settings(tmp_path / "missing.json")

    assert loaded == DebugSettings()


def test_debug_settings_clamps_time_scale(tmp_path):
    path = tmp_path / "debug_settings.json"
    path.write_text(
        """
{
  "time_scale": 99999,
  "auto_rebirth_random": true,
  "auto_lifecycle_events": true
}
""".strip(),
        encoding="utf-8",
    )

    loaded = load_debug_settings(path)

    assert loaded.time_scale == 3600
    assert loaded.auto_rebirth_random is True
    assert loaded.auto_lifecycle_events is True


def test_debug_settings_migrates_legacy_file_when_default_target_missing(tmp_path, monkeypatch):
    settings_path = tmp_path / "user-data" / "debug_settings.json"
    legacy_path = tmp_path / ".local" / "debug_settings.json"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text(
        """
{
  "time_scale": 12,
  "auto_rebirth_random": true,
  "auto_lifecycle_events": true
}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(debug_settings, "DEBUG_SETTINGS_PATH", settings_path)
    monkeypatch.setattr(debug_settings, "LEGACY_DEBUG_SETTINGS_PATH", legacy_path)

    loaded = load_debug_settings()

    assert loaded == DebugSettings(time_scale=12, auto_rebirth_random=True, auto_lifecycle_events=True)
    assert settings_path.read_text(encoding="utf-8") == legacy_path.read_text(encoding="utf-8")


def test_debug_settings_does_not_replace_existing_user_file(tmp_path, monkeypatch):
    settings_path = tmp_path / "user-data" / "debug_settings.json"
    legacy_path = tmp_path / ".local" / "debug_settings.json"
    settings_path.parent.mkdir(parents=True)
    legacy_path.parent.mkdir(parents=True)
    settings_path.write_text('{"time_scale": 3}\n', encoding="utf-8")
    legacy_path.write_text('{"time_scale": 12}\n', encoding="utf-8")
    monkeypatch.setattr(debug_settings, "DEBUG_SETTINGS_PATH", settings_path)
    monkeypatch.setattr(debug_settings, "LEGACY_DEBUG_SETTINGS_PATH", legacy_path)

    loaded = load_debug_settings()

    assert loaded.time_scale == 3
    assert settings_path.read_text(encoding="utf-8") == '{"time_scale": 3}\n'
