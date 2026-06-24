from digimon_pet.network import presence as presence_module
from digimon_pet.domain.models import GrowthStage, PetState, Species
from digimon_pet.network.presence import PresenceService, build_presence_payload
from digimon_pet.storage.network_settings import NetworkSettings


def _state() -> PetState:
    return PetState(
        species_id="agumon",
        stage=GrowthStage.ROOKIE,
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
        "current_action": "idle",
        "is_sleeping": True,
    }
    assert "inventory" not in payload
    assert "hp" not in payload


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
