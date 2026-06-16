from digimon_pet.storage.debug_settings import DebugSettings, load_debug_settings, save_debug_settings


def test_debug_settings_roundtrip(tmp_path):
    path = tmp_path / "debug_settings.json"
    settings = DebugSettings(time_scale=42, auto_rebirth_random=True)

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
  "auto_rebirth_random": true
}
""".strip(),
        encoding="utf-8",
    )

    loaded = load_debug_settings(path)

    assert loaded.time_scale == 3600
    assert loaded.auto_rebirth_random is True
