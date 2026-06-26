from __future__ import annotations

import json
import ipaddress
import socket
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from digimon_pet.domain.models import PetState, Species
from digimon_pet.storage.network_settings import NetworkSettings, parse_friend_address

PROTOCOL_VERSION = 1
PEER_POLL_INTERVAL_SECONDS = 2
REQUEST_TIMEOUT_SECONDS = 2


PresencePayload = dict[str, str | int | bool]
COMBAT_STAT_KEYS = ("hp", "mp", "offense", "defense", "speed", "brains")


@dataclass(frozen=True)
class PeerStatus:
    address: str
    online: bool = False
    payload: PresencePayload | None = None
    last_seen_seconds: float | None = None
    error: str = ""


PeerStatusChangedCallback = Callable[[PeerStatus | None, PeerStatus], None]


def build_presence_payload(nickname: str, state: PetState, species: Species) -> PresencePayload:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "trainer_nickname": str(nickname).strip(),
        "species_id": state.species_id,
        "digimon_name": species.name,
        "stage": state.stage.value,
        "age_seconds": int(state.age_seconds),
        "current_action": state.current_action,
        "is_sleeping": bool(state.is_sleeping),
        "needs_rebirth_choice": bool(state.needs_rebirth_choice),
        "hp": int(state.hp),
        "mp": int(state.mp),
        "offense": int(state.offense),
        "defense": int(state.defense),
        "speed": int(state.speed),
        "brains": int(state.brains),
    }


def local_ip_address() -> str:
    return local_ip_addresses()[0]


def local_ip_addresses() -> list[str]:
    addresses: list[str] = []
    try:
        _, _, host_addresses = socket.gethostbyname_ex(socket.gethostname())
    except OSError:
        host_addresses = []
    for address in host_addresses:
        _append_lan_address(addresses, address)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        _append_lan_address(addresses, str(sock.getsockname()[0]))
    except OSError:
        pass
    finally:
        sock.close()
    return addresses or ["127.0.0.1"]


def _append_lan_address(addresses: list[str], value: str) -> None:
    try:
        parsed = ipaddress.ip_address(value)
    except ValueError:
        return
    if parsed.version != 4 or parsed.is_loopback or parsed.is_link_local:
        return
    address = str(parsed)
    if address not in addresses:
        addresses.append(address)


class PresenceService:
    def __init__(
        self,
        *,
        settings: NetworkSettings,
        payload_provider: Callable[[], PresencePayload],
        poll_interval_seconds: int = PEER_POLL_INTERVAL_SECONDS,
        peer_status_changed: PeerStatusChangedCallback | None = None,
    ) -> None:
        self._settings = settings
        self._payload_provider = payload_provider
        self._poll_interval_seconds = max(1, int(poll_interval_seconds))
        self._peer_status_changed = peer_status_changed
        self._server: ThreadingHTTPServer | None = None
        self._server_thread: threading.Thread | None = None
        self._poll_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._peers: dict[str, PeerStatus] = {
            address: PeerStatus(address=address) for address in self._settings.friends
        }
        self._last_error = ""

    @property
    def last_error(self) -> str:
        return self._last_error

    def is_running(self) -> bool:
        return self._server is not None or (self._poll_thread is not None and self._poll_thread.is_alive())

    def apply_settings(self, settings: NetworkSettings) -> bool:
        was_running = self.is_running()
        if was_running:
            self.stop()
        self._settings = settings
        with self._lock:
            self._peers = {address: self._peers.get(address, PeerStatus(address=address)) for address in settings.friends}
        if settings.network_enabled:
            return self.start()
        return False

    def start(self) -> bool:
        self.stop()
        self._stop_event.clear()
        self._last_error = ""
        if not self._settings.network_enabled:
            return False
        if not self._start_server():
            return False
        self._poll_thread = threading.Thread(target=self._poll_loop, name="DigimonPetPresencePoll", daemon=True)
        self._poll_thread.start()
        return True

    def stop(self) -> None:
        self._stop_event.set()
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._server_thread is not None and self._server_thread.is_alive():
            self._server_thread.join(timeout=1)
        self._server_thread = None
        if self._poll_thread is not None and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=1)
        self._poll_thread = None

    def peer_statuses(self) -> list[PeerStatus]:
        with self._lock:
            return [self._peers[address] for address in self._settings.friends if address in self._peers]

    def poll_once(self) -> None:
        if not self._settings.network_enabled:
            return
        for address in self._settings.friends:
            self._poll_peer(address)

    def _start_server(self) -> bool:
        service = self

        class PresenceHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.path != "/presence":
                    self.send_error(404)
                    return
                try:
                    payload = service._payload_provider()
                    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
                except Exception:
                    self.send_error(500)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: Any) -> None:
                return

        try:
            self._server = ThreadingHTTPServer(("", self._settings.listen_port), PresenceHandler)
        except OSError as exc:
            self._last_error = f"Port unavailable: {exc}"
            self._server = None
            return False
        self._server_thread = threading.Thread(
            target=self._server.serve_forever,
            name="DigimonPetPresenceServer",
            daemon=True,
        )
        self._server_thread.start()
        return True

    def _poll_loop(self) -> None:
        self.poll_once()
        while not self._stop_event.wait(self._poll_interval_seconds):
            self.poll_once()

    def _poll_peer(self, address: str) -> None:
        try:
            host, port = parse_friend_address(address)
            url = f"http://{host}:{port}/presence"
            request = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                if response.status != 200:
                    raise ValueError(f"HTTP {response.status}")
                raw = json.loads(response.read().decode("utf-8"))
            payload = _presence_payload_from_raw(raw)
            status = PeerStatus(address=address, online=True, payload=payload, last_seen_seconds=time.time())
        except (OSError, ValueError, AttributeError, json.JSONDecodeError, urllib.error.URLError) as exc:
            with self._lock:
                previous_status = self._peers.get(address)
            status = PeerStatus(
                address=address,
                online=False,
                payload=previous_status.payload if previous_status is not None else None,
                last_seen_seconds=previous_status.last_seen_seconds if previous_status is not None else None,
                error=_short_error(exc),
            )
        with self._lock:
            previous_status = self._peers.get(address)
            self._peers[address] = status
        if self._peer_status_changed is not None:
            self._peer_status_changed(previous_status, status)


def _presence_payload_from_raw(raw: Any) -> PresencePayload:
    if not isinstance(raw, dict):
        raise ValueError("Presence response must be an object.")
    if int(raw.get("protocol_version", 0)) != PROTOCOL_VERSION:
        raise ValueError("Unsupported protocol version.")
    payload = {
        "protocol_version": PROTOCOL_VERSION,
        "trainer_nickname": str(raw["trainer_nickname"]),
        "species_id": str(raw["species_id"]),
        "digimon_name": str(raw["digimon_name"]),
        "stage": str(raw["stage"]),
        "age_seconds": int(raw.get("age_seconds", 0)),
        "current_action": str(raw["current_action"]),
        "is_sleeping": bool(raw["is_sleeping"]),
        "needs_rebirth_choice": bool(raw.get("needs_rebirth_choice", False)),
    }
    for key in COMBAT_STAT_KEYS:
        payload[key] = int(raw.get(key, 0))
    if not payload["trainer_nickname"] or not payload["species_id"] or not payload["digimon_name"]:
        raise ValueError("Presence response is incomplete.")
    return payload


def _short_error(exc: Exception) -> str:
    text = str(exc).strip()
    return text[:120] if text else exc.__class__.__name__
