from digimon_pet.storage.network_settings import (
    DEFAULT_LISTEN_PORT,
    NetworkSettings,
    clean_trainer_nickname,
    load_network_settings,
    normalize_friend_address,
    parse_friend_address,
    save_network_settings,
)


def test_network_settings_defaults_when_missing(tmp_path):
    loaded = load_network_settings(tmp_path / "missing.json")

    assert loaded == NetworkSettings(network_enabled=True)


def test_network_settings_roundtrip(tmp_path):
    path = tmp_path / "network_settings.json"
    settings = NetworkSettings(
        trainer_nickname="Tai",
        network_enabled=False,
        listen_port=54546,
        friends=["192.168.1.42:54545"],
        notify_friend_death=False,
        notify_friend_ultimate=False,
        notify_friend_numemon=False,
    )

    save_network_settings(settings, path)
    loaded = load_network_settings(path)

    assert loaded.network_enabled is False
    assert loaded.listen_port == DEFAULT_LISTEN_PORT
    assert loaded.friends == settings.friends
    assert loaded.notify_friend_death is False
    assert loaded.notify_friend_ultimate is False
    assert loaded.notify_friend_numemon is False


def test_network_settings_clamps_invalid_values(tmp_path):
    path = tmp_path / "network_settings.json"
    path.write_text(
        """
{
  "trainer_nickname": "  Sora  ",
  "network_enabled": true,
  "listen_port": 80,
  "friends": ["192.168.1.10:54545", "bad", "192.168.1.10:54545"]
}
""".strip(),
        encoding="utf-8",
    )

    loaded = load_network_settings(path)

    assert loaded.trainer_nickname == "Sora"
    assert loaded.network_enabled is True
    assert loaded.listen_port == DEFAULT_LISTEN_PORT
    assert loaded.friends == ["192.168.1.10:54545"]
    assert loaded.notify_friend_death is True
    assert loaded.notify_friend_ultimate is True
    assert loaded.notify_friend_numemon is True


def test_trainer_nickname_is_trimmed():
    assert clean_trainer_nickname("  Mimi  ") == "Mimi"


def test_parse_friend_address_requires_host_and_valid_port():
    assert parse_friend_address("192.168.1.42:54545") == ("192.168.1.42", 54545)
    assert normalize_friend_address("  192.168.1.42 ") == "192.168.1.42:54545"

    for value in ("", "192.168.1.42", ":54545", "192.168.1.42:80", "192.168.1.42:nope"):
        try:
            parse_friend_address(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{value!r} should be invalid")


def test_friend_input_requires_ip_only():
    for value in ("192.168.1.42:54545", "192.168.1.42:12345"):
        try:
            normalize_friend_address(value)
        except ValueError as exc:
            assert str(exc) == "Enter the IP only."
        else:
            raise AssertionError(f"{value!r} should be invalid")
