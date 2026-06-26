import pytest
import threading

from digimon_pet.network import presence as presence_module
from digimon_pet.domain.models import GrowthStage, PetState, Species
from digimon_pet.network.presence import (
    PEER_POLL_INTERVAL_SECONDS,
    PresenceService,
    _presence_payload_from_raw,
    build_presence_payload,
)
from digimon_pet.storage.network_settings import NetworkSettings


def _state() -> PetState:
    return PetState(
        species_id="agumon",
        stage=GrowthStage.ROOKIE,
        age_seconds=5400,
        total_age_seconds=7800,
        current_generation_species_ids=["botamon", "koromon", "agumon"],
        current_action="idle",
        is_sleeping=True,
        inventory={"meat": 99},
        hp=777,
    )


def _species() -> Species:
    return Species(id="agumon", name="Agumon", stage=GrowthStage.ROOKIE)


def test_presence_payload_exposes_only_public_fields():
    payload = build_presence_payload("Tai", _state(), _species())

    assert payload == {
        "protocol_version": 1,
        "trainer_nickname": "Tai",
        "species_id": "agumon",
        "digimon_name": "Agumon",
        "stage": "rookie",
        "age_seconds": 5400,
        "current_generation_species_ids": ["botamon", "koromon", "agumon"],
        "current_action": "idle",
        "is_sleeping": True,
        "needs_rebirth_choice": False,
        "hp": 777,
        "mp": 300,
        "offense": 30,
        "defense": 30,
        "speed": 30,
        "brains": 30,
    }
    assert "inventory" not in payload


def test_default_peer_poll_interval_is_fast_enough_for_interactive_status():
    assert PEER_POLL_INTERVAL_SECONDS <= 2


def test_presence_payload_parser_accepts_legacy_payload_without_combat_stats():
    payload = _presence_payload_from_raw(
        {
            "protocol_version": 1,
            "trainer_nickname": "Tai",
            "species_id": "agumon",
            "digimon_name": "Agumon",
            "stage": "rookie",
            "current_action": "idle",
            "is_sleeping": False,
        }
    )

    assert payload["trainer_nickname"] == "Tai"
    assert payload["digimon_name"] == "Agumon"
    assert payload["needs_rebirth_choice"] is False
    assert payload["age_seconds"] == 0
    assert payload["current_generation_species_ids"] == ["agumon"]
    assert payload["hp"] == 0
    assert payload["mp"] == 0


def test_disabled_service_does_not_start_or_poll():
    calls = []
    service = PresenceService(
        settings=NetworkSettings(network_enabled=False, friends=["127.0.0.1:54545"]),
        payload_provider=lambda: calls.append("payload") or build_presence_payload("Tai", _state(), _species()),
        poll_interval_seconds=1,
    )

    assert service.start() is False
    service.poll_once()

    assert service.is_running() is False
    assert calls == []


def test_peer_poll_failure_marks_peer_offline():
    service = PresenceService(
        settings=NetworkSettings(network_enabled=True, friends=["127.0.0.1:65535"]),
        payload_provider=lambda: build_presence_payload("Tai", _state(), _species()),
        poll_interval_seconds=1,
    )

    service.poll_once()

    statuses = service.peer_statuses()
    assert len(statuses) == 1
    assert statuses[0].address == "127.0.0.1:65535"
    assert statuses[0].online is False
    assert statuses[0].error


def test_unexpected_peer_poll_failure_marks_peer_offline(monkeypatch):
    service = PresenceService(
        settings=NetworkSettings(network_enabled=True, friends=["127.0.0.1:54545"]),
        payload_provider=lambda: build_presence_payload("Tai", _state(), _species()),
        poll_interval_seconds=1,
    )

    def raise_attribute_error(request, timeout):
        raise AttributeError("fake socket missing settimeout")

    monkeypatch.setattr(presence_module.urllib.request, "urlopen", raise_attribute_error)

    service.poll_once()

    statuses = service.peer_statuses()
    assert statuses[0].online is False
    assert "fake socket missing settimeout" in statuses[0].error


def test_peer_poll_failure_keeps_last_payload_for_later_transition_detection(monkeypatch):
    payload = build_presence_payload(
        "Sora",
        PetState("gabumon", GrowthStage.ROOKIE),
        Species("gabumon", "Gabumon", GrowthStage.ROOKIE),
    )
    service = PresenceService(
        settings=NetworkSettings(network_enabled=True, friends=["127.0.0.1:54545"]),
        payload_provider=lambda: build_presence_payload("Tai", _state(), _species()),
        poll_interval_seconds=1,
    )
    service._peers["127.0.0.1:54545"] = presence_module.PeerStatus(
        address="127.0.0.1:54545",
        online=True,
        payload=payload,
    )

    def raise_url_error(request, timeout):
        raise presence_module.urllib.error.URLError("offline")

    monkeypatch.setattr(presence_module.urllib.request, "urlopen", raise_url_error)

    service.poll_once()

    status = service.peer_statuses()[0]
    assert status.online is False
    assert status.payload == payload
    assert status.error


def test_peer_status_changed_callback_receives_previous_and_current(monkeypatch):
    service = PresenceService(
        settings=NetworkSettings(network_enabled=True, friends=["127.0.0.1:54545"]),
        payload_provider=lambda: build_presence_payload("Tai", _state(), _species()),
        poll_interval_seconds=1,
        peer_status_changed=lambda previous, current: calls.append((previous, current)),
    )
    calls = []
    payload = build_presence_payload("Sora", PetState("gabumon", GrowthStage.ROOKIE), Species("gabumon", "Gabumon", GrowthStage.ROOKIE))

    def fake_urlopen(request, timeout):
        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return None

            def read(self):
                return presence_module.json.dumps(payload).encode("utf-8")

        return Response()

    monkeypatch.setattr(presence_module.urllib.request, "urlopen", fake_urlopen)

    service.poll_once()
    service.poll_once()

    assert calls[0][0].online is False
    assert calls[0][1].payload == payload
    assert calls[1][0].payload == payload
    assert calls[1][1].payload == payload


def test_port_bind_failure_keeps_service_stopped(monkeypatch):
    def raise_os_error(*args, **kwargs):
        raise OSError("port busy")

    monkeypatch.setattr(presence_module, "ThreadingHTTPServer", raise_os_error)
    service = PresenceService(
        settings=NetworkSettings(trainer_nickname="Tai", network_enabled=True),
        payload_provider=lambda: build_presence_payload("Tai", _state(), _species()),
        poll_interval_seconds=1,
    )

    assert service.start() is False
    assert service.is_running() is False
    assert "port busy" in service.last_error


def test_start_polls_configured_friends_immediately(monkeypatch):
    polled = []
    polled_event = threading.Event()
    service = PresenceService(
        settings=NetworkSettings(network_enabled=True, listen_port=0, friends=["127.0.0.1:54545"]),
        payload_provider=lambda: build_presence_payload("Tai", _state(), _species()),
        poll_interval_seconds=60,
    )

    def poll_peer(address):
        polled.append(address)
        polled_event.set()

    monkeypatch.setattr(service, "_poll_peer", poll_peer)

    assert service.start() is True
    assert polled_event.wait(1)
    service.stop()

    assert polled == ["127.0.0.1:54545"]


def test_local_ip_addresses_includes_all_lan_candidates(monkeypatch):
    class FakeSocket:
        def __init__(self, *args, **kwargs):
            self.connected_to = None

        def connect(self, address):
            self.connected_to = address

        def getsockname(self):
            return ("192.168.0.254", 50000)

        def close(self):
            return None

    monkeypatch.setattr(presence_module.socket, "socket", FakeSocket)
    monkeypatch.setattr(presence_module.socket, "gethostname", lambda: "digimon-pet")
    monkeypatch.setattr(
        presence_module.socket,
        "gethostbyname_ex",
        lambda hostname: ("digimon-pet", [], ["192.168.0.134", "127.0.0.1", "192.168.0.254"]),
    )

    assert presence_module.local_ip_addresses() == ["192.168.0.134", "192.168.0.254"]
