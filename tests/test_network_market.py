from digimon_pet.domain.models import GrowthStage, PetState, Species
from digimon_pet.network import presence as presence_module
from digimon_pet.network.presence import (
    MarketPurchaseResult,
    PresenceService,
    _market_listings_from_raw,
    build_presence_payload,
)
from digimon_pet.storage.network_settings import NetworkSettings


def _payload_provider():
    return build_presence_payload(
        "Tai",
        PetState(species_id="agumon", stage=GrowthStage.ROOKIE),
        Species(id="agumon", name="Agumon", stage=GrowthStage.ROOKIE),
    )


def test_market_listing_parser_accepts_valid_listings_and_skips_malformed_entries():
    listings = _market_listings_from_raw(
        {
            "protocol_version": 1,
            "listings": [
                {
                    "listing_id": "listing-1",
                    "item_id": "digimeat",
                    "item_name": "DigiMeat",
                    "trainer_name": "Tai",
                    "price_bits": 300,
                },
                {
                    "listing_id": "free",
                    "item_id": "digifish",
                    "item_name": "DigiFish",
                    "trainer_name": "Tai",
                    "price_bits": 0,
                },
                "bad",
            ],
        }
    )

    assert listings == [
        {
            "listing_id": "listing-1",
            "item_id": "digimeat",
            "item_name": "DigiMeat",
            "trainer_name": "Tai",
            "price_bits": 300,
        }
    ]


def test_market_listing_endpoint_returns_provider_data():
    seller = PresenceService(
        settings=NetworkSettings(trainer_nickname="Tai", network_enabled=True, listen_port=0),
        payload_provider=_payload_provider,
        market_listings_provider=lambda: [
            {
                "listing_id": "listing-1",
                "item_id": "digimeat",
                "item_name": "DigiMeat",
                "trainer_name": "Tai",
                "price_bits": 300,
            }
        ],
    )

    try:
        assert seller.start() is True
        port = seller._server.server_port
        buyer = PresenceService(
            settings=NetworkSettings(network_enabled=False),
            payload_provider=_payload_provider,
        )

        listings = buyer.market_listings_for(f"127.0.0.1:{port}")
    finally:
        seller.stop()

    assert listings[0]["listing_id"] == "listing-1"
    assert listings[0]["price_bits"] == 300


def test_market_buy_endpoint_returns_successful_purchase():
    seller = PresenceService(
        settings=NetworkSettings(trainer_nickname="Tai", network_enabled=True, listen_port=0),
        payload_provider=_payload_provider,
        market_purchase_handler=lambda listing_id: MarketPurchaseResult(
            ok=True,
            item_id="digimeat",
            price_bits=300,
        )
        if listing_id == "listing-1"
        else MarketPurchaseResult(ok=False, reason="listing_not_found"),
    )

    try:
        assert seller.start() is True
        port = seller._server.server_port
        buyer = PresenceService(
            settings=NetworkSettings(network_enabled=False),
            payload_provider=_payload_provider,
        )

        result = buyer.buy_market_listing(f"127.0.0.1:{port}", "listing-1")
        missing = buyer.buy_market_listing(f"127.0.0.1:{port}", "missing")
    finally:
        seller.stop()

    assert result == MarketPurchaseResult(ok=True, item_id="digimeat", price_bits=300)
    assert missing == MarketPurchaseResult(ok=False, reason="listing_not_found")
