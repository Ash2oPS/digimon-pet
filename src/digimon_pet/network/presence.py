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


PresencePayload = dict[str, str | int | bool | list[str]]
MarketListingPayload = dict[str, str | int]
COMBAT_STAT_KEYS = ("hp", "mp", "offense", "defense", "speed", "brains")


@dataclass(frozen=True)
class PeerStatus:
    address: str
    online: bool = False
    payload: PresencePayload | None = None
    last_seen_seconds: float | None = None
    error: str = ""


@dataclass(frozen=True)
class MarketPurchaseResult:
    ok: bool
    item_id: str = ""
    price_bits: int = 0
    reason: str = ""


PeerStatusChangedCallback = Callable[[PeerStatus | None, PeerStatus], None]
MarketListingsProvider = Callable[[], list[MarketListingPayload]]
MarketPurchaseHandler = Callable[[str], MarketPurchaseResult]


def build_presence_payload(nickname: str, state: PetState, species: Species) -> PresencePayload:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "trainer_nickname": str(nickname).strip(),
        "species_id": state.species_id,
        "digimon_name": species.name,
        "stage": state.stage.value,
        "age_seconds": int(state.age_seconds),
        "generation_count": int(state.generation_count),
        "collected_species_count": len(state.discovered_species_ids),
        "current_generation_species_ids": list(state.current_generation_species_ids or [state.species_id]),
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
        market_listings_provider: MarketListingsProvider | None = None,
        market_purchase_handler: MarketPurchaseHandler | None = None,
    ) -> None:
        self._settings = settings
        self._payload_provider = payload_provider
        self._poll_interval_seconds = max(1, int(poll_interval_seconds))
        self._peer_status_changed = peer_status_changed
        self._market_listings_provider = market_listings_provider
        self._market_purchase_handler = market_purchase_handler
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

    def market_listings_for(self, address: str) -> list[MarketListingPayload]:
        host, port = parse_friend_address(address)
        url = f"http://{host}:{port}/market/listings"
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                raise ValueError(f"HTTP {response.status}")
            raw = json.loads(response.read().decode("utf-8"))
        return _market_listings_from_raw(raw)

    def buy_market_listing(self, address: str, listing_id: str) -> MarketPurchaseResult:
        try:
            host, port = parse_friend_address(address)
            url = f"http://{host}:{port}/market/buy"
            body = json.dumps({"listing_id": str(listing_id)}, separators=(",", ":")).encode("utf-8")
            request = urllib.request.Request(
                url,
                data=body,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError, AttributeError, json.JSONDecodeError, urllib.error.URLError) as exc:
            return MarketPurchaseResult(ok=False, reason=_short_error(exc))
        return _market_purchase_result_from_raw(raw)

    def _start_server(self) -> bool:
        service = self

        class PresenceHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/market/listings":
                    service._handle_market_listings(self)
                    return
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

            def do_POST(self) -> None:  # noqa: N802
                if self.path != "/market/buy":
                    self.send_error(404)
                    return
                service._handle_market_buy(self)

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

    def _handle_market_listings(self, handler: BaseHTTPRequestHandler) -> None:
        try:
            listings = self._market_listings_provider() if self._market_listings_provider is not None else []
            body = json.dumps(
                {"protocol_version": PROTOCOL_VERSION, "listings": listings},
                separators=(",", ":"),
            ).encode("utf-8")
        except Exception:
            handler.send_error(500)
            return
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    def _handle_market_buy(self, handler: BaseHTTPRequestHandler) -> None:
        if self._market_purchase_handler is None:
            handler.send_error(404)
            return
        try:
            length = int(handler.headers.get("Content-Length", "0"))
            raw = json.loads(handler.rfile.read(length).decode("utf-8"))
            listing_id = str(raw["listing_id"])
            result = self._market_purchase_handler(listing_id)
            body = json.dumps(
                {
                    "protocol_version": PROTOCOL_VERSION,
                    "ok": result.ok,
                    "item_id": result.item_id,
                    "price_bits": result.price_bits,
                    "reason": result.reason,
                },
                separators=(",", ":"),
            ).encode("utf-8")
        except Exception:
            handler.send_error(400)
            return
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

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
        "generation_count": max(1, int(raw.get("generation_count", 1))),
        "collected_species_count": max(0, int(raw.get("collected_species_count", 0))),
        "current_generation_species_ids": _current_generation_species_ids_from_raw(
            raw.get("current_generation_species_ids"),
            str(raw["species_id"]),
        ),
        "current_action": str(raw["current_action"]),
        "is_sleeping": bool(raw["is_sleeping"]),
        "needs_rebirth_choice": bool(raw.get("needs_rebirth_choice", False)),
    }
    for key in COMBAT_STAT_KEYS:
        payload[key] = int(raw.get(key, 0))
    if not payload["trainer_nickname"] or not payload["species_id"] or not payload["digimon_name"]:
        raise ValueError("Presence response is incomplete.")
    return payload


def _market_listings_from_raw(raw: Any) -> list[MarketListingPayload]:
    if not isinstance(raw, dict):
        raise ValueError("Market response must be an object.")
    if int(raw.get("protocol_version", 0)) != PROTOCOL_VERSION:
        raise ValueError("Unsupported protocol version.")
    raw_listings = raw.get("listings", [])
    if not isinstance(raw_listings, list):
        raise ValueError("Market listings must be a list.")
    listings: list[MarketListingPayload] = []
    for item in raw_listings:
        if not isinstance(item, dict):
            continue
        listing_id = str(item.get("listing_id", "")).strip()
        item_id = str(item.get("item_id", "")).strip()
        item_name = str(item.get("item_name", "")).strip()
        trainer_name = str(item.get("trainer_name", "")).strip()
        price_bits = int(item.get("price_bits", 0))
        if listing_id and item_id and item_name and trainer_name and price_bits > 0:
            listings.append(
                {
                    "listing_id": listing_id,
                    "item_id": item_id,
                    "item_name": item_name,
                    "trainer_name": trainer_name,
                    "price_bits": price_bits,
                }
            )
    return listings


def _market_purchase_result_from_raw(raw: Any) -> MarketPurchaseResult:
    if not isinstance(raw, dict):
        raise ValueError("Market purchase response must be an object.")
    if int(raw.get("protocol_version", 0)) != PROTOCOL_VERSION:
        raise ValueError("Unsupported protocol version.")
    return MarketPurchaseResult(
        ok=bool(raw.get("ok", False)),
        item_id=str(raw.get("item_id", "")),
        price_bits=max(0, int(raw.get("price_bits", 0))),
        reason=str(raw.get("reason", "")),
    )


def _current_generation_species_ids_from_raw(raw: Any, current_species_id: str) -> list[str]:
    if not isinstance(raw, list):
        return [current_species_id]
    cleaned = list(dict.fromkeys(str(item) for item in raw if str(item).strip()))
    return cleaned or [current_species_id]


def _short_error(exc: Exception) -> str:
    text = str(exc).strip()
    return text[:120] if text else exc.__class__.__name__
