from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from digimon_pet.paths import NETWORK_SETTINGS_PATH

DEFAULT_LISTEN_PORT = 54545
MIN_PORT = 1024
MAX_PORT = 65535


@dataclass
class NetworkSettings:
    trainer_nickname: str = ""
    network_enabled: bool = False
    listen_port: int = DEFAULT_LISTEN_PORT
    friends: list[str] = field(default_factory=list)

    def clamp(self) -> None:
        self.trainer_nickname = clean_trainer_nickname(self.trainer_nickname)
        self.network_enabled = bool(self.network_enabled)
        self.listen_port = clean_port(self.listen_port, default=DEFAULT_LISTEN_PORT)
        self.friends = clean_friend_addresses(self.friends)


def clean_trainer_nickname(value: str) -> str:
    return str(value).strip()


def is_valid_trainer_nickname(value: str) -> bool:
    return bool(clean_trainer_nickname(value))


def clean_port(value: int | str, *, default: int = DEFAULT_LISTEN_PORT) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError):
        return default
    return port if MIN_PORT <= port <= MAX_PORT else default


def parse_friend_address(value: str) -> tuple[str, int]:
    raw = str(value).strip()
    if raw.count(":") != 1:
        raise ValueError("Friend address must use host:port.")
    host, port_text = (part.strip() for part in raw.rsplit(":", 1))
    if not host:
        raise ValueError("Friend host is required.")
    try:
        port = int(port_text)
    except ValueError as exc:
        raise ValueError("Friend port must be a number.") from exc
    if not MIN_PORT <= port <= MAX_PORT:
        raise ValueError("Friend port must be between 1024 and 65535.")
    return host, port


def normalize_friend_address(value: str) -> str:
    host, port = parse_friend_address(value)
    return f"{host}:{port}"


def clean_friend_addresses(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        try:
            address = normalize_friend_address(value)
        except ValueError:
            continue
        if address not in cleaned:
            cleaned.append(address)
    return cleaned


def load_network_settings(path: Path | None = None) -> NetworkSettings:
    settings_path = path or NETWORK_SETTINGS_PATH
    if not settings_path.exists():
        return NetworkSettings()
    try:
        with settings_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return NetworkSettings()
    if not isinstance(raw, dict):
        return NetworkSettings()
    return _settings_from_dict(raw)


def save_network_settings(settings: NetworkSettings, path: Path | None = None) -> None:
    settings_path = path or NETWORK_SETTINGS_PATH
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings.clamp()
    with settings_path.open("w", encoding="utf-8") as handle:
        json.dump(asdict(settings), handle, indent=2)
        handle.write("\n")


def _settings_from_dict(raw: dict[str, Any]) -> NetworkSettings:
    friends = raw.get("friends", [])
    settings = NetworkSettings(
        trainer_nickname=str(raw.get("trainer_nickname", "")),
        network_enabled=bool(raw.get("network_enabled", False)),
        listen_port=raw.get("listen_port", DEFAULT_LISTEN_PORT),
        friends=[str(value) for value in friends] if isinstance(friends, list) else [],
    )
    settings.clamp()
    return settings
