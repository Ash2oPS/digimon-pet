from digimon_pet.domain.economy import (
    award_bits,
    buy_shop_item,
    cancel_market_listing,
    create_market_listing,
    sell_market_listing,
)
from digimon_pet.domain.items import ItemDefinition, ItemType
from digimon_pet.domain.models import GrowthStage, MarketListingState, PetState


def _state(**kwargs) -> PetState:
    return PetState(species_id="agumon", stage=GrowthStage.ROOKIE, **kwargs)


def _shop_item(price_bits: int | None = 300) -> ItemDefinition:
    return ItemDefinition(
        id="digimeat",
        name="DigiMeat",
        description="Increases OFF by 25.",
        type=ItemType.CONSUMABLE,
        shop_price_bits=price_bits,
        suggested_market_price_bits=price_bits,
    )


def test_award_bits_adds_positive_amount():
    state = _state(bits=100)

    result = award_bits(state, 75)

    assert result.ok is True
    assert state.bits == 175


def test_award_bits_rejects_non_positive_amount():
    state = _state(bits=100)

    result = award_bits(state, 0)

    assert result.ok is False
    assert result.reason == "invalid_amount"
    assert state.bits == 100


def test_buy_shop_item_debits_bits_and_adds_inventory():
    state = _state(bits=350)

    result = buy_shop_item(state, _shop_item())

    assert result.ok is True
    assert state.bits == 50
    assert state.inventory == {"digimeat": 1}


def test_buy_shop_item_rejects_insufficient_bits_without_mutation():
    state = _state(bits=299)

    result = buy_shop_item(state, _shop_item())

    assert result.ok is False
    assert result.reason == "insufficient_bits"
    assert state.bits == 299
    assert state.inventory == {}


def test_buy_shop_item_rejects_item_without_shop_price():
    state = _state(bits=999)

    result = buy_shop_item(state, _shop_item(None))

    assert result.ok is False
    assert result.reason == "item_not_sold"
    assert state.bits == 999
    assert state.inventory == {}


def test_create_market_listing_removes_inventory_and_saves_listing():
    state = _state(inventory={"digimeat": 2})

    result = create_market_listing(
        state,
        "digimeat",
        425,
        id_factory=lambda: "listing-1",
        time_provider=lambda: 12345,
    )

    assert result.ok is True
    assert state.inventory == {"digimeat": 1}
    assert state.market_listings == [
        MarketListingState(id="listing-1", item_id="digimeat", price_bits=425, created_at=12345)
    ]


def test_create_market_listing_rejects_invalid_price_without_mutation():
    state = _state(inventory={"digimeat": 1})

    result = create_market_listing(state, "digimeat", 0)

    assert result.ok is False
    assert result.reason == "invalid_listing_price"
    assert state.inventory == {"digimeat": 1}
    assert state.market_listings == []


def test_create_market_listing_rejects_missing_inventory_without_mutation():
    state = _state(inventory={})

    result = create_market_listing(state, "digimeat", 300)

    assert result.ok is False
    assert result.reason == "missing_inventory_item"
    assert state.inventory == {}
    assert state.market_listings == []


def test_cancel_market_listing_restores_inventory():
    state = _state(
        market_listings=[
            MarketListingState(id="listing-1", item_id="digimeat", price_bits=425, created_at=12345)
        ]
    )

    result = cancel_market_listing(state, "listing-1")

    assert result.ok is True
    assert state.inventory == {"digimeat": 1}
    assert state.market_listings == []


def test_sell_market_listing_credits_bits_and_removes_listing():
    state = _state(
        bits=100,
        market_listings=[
            MarketListingState(id="listing-1", item_id="digimeat", price_bits=425, created_at=12345)
        ],
    )

    result = sell_market_listing(state, "listing-1")

    assert result.ok is True
    assert result.item_id == "digimeat"
    assert state.bits == 525
    assert state.market_listings == []
