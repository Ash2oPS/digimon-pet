from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from collections.abc import Callable

from digimon_pet.domain.items import ItemDefinition
from digimon_pet.domain.models import MarketListingState, PetState


@dataclass(frozen=True)
class EconomyResult:
    ok: bool
    reason: str | None = None
    item_id: str | None = None
    listing: MarketListingState | None = None


def award_bits(state: PetState, amount: int) -> EconomyResult:
    amount = int(amount)
    if amount <= 0:
        return EconomyResult(ok=False, reason="invalid_amount")
    state.bits += amount
    state.clamp()
    return EconomyResult(ok=True)


def buy_shop_item(state: PetState, item: ItemDefinition, quantity: int = 1) -> EconomyResult:
    quantity = int(quantity)
    if quantity < 1:
        return EconomyResult(ok=False, reason="invalid_quantity")
    if item.shop_price_bits is None:
        return EconomyResult(ok=False, reason="item_not_sold")
    total_price = item.shop_price_bits * quantity
    if state.bits < total_price:
        return EconomyResult(ok=False, reason="insufficient_bits")
    state.bits -= total_price
    state.inventory[item.id] = state.inventory.get(item.id, 0) + quantity
    state.clamp()
    return EconomyResult(ok=True, item_id=item.id)


def sell_inventory_item(state: PetState, item: ItemDefinition, quantity: int = 1) -> EconomyResult:
    quantity = int(quantity)
    if quantity < 1:
        return EconomyResult(ok=False, reason="invalid_quantity")
    theoretical_price = theoretical_item_price_bits(item)
    if theoretical_price is None:
        return EconomyResult(ok=False, reason="item_not_valued")
    if state.inventory.get(item.id, 0) < quantity:
        return EconomyResult(ok=False, reason="missing_inventory_item")
    sell_price = max(1, theoretical_price // 3) * quantity
    remaining = state.inventory.get(item.id, 0) - quantity
    if remaining <= 0:
        state.inventory.pop(item.id, None)
    else:
        state.inventory[item.id] = remaining
    state.bits += sell_price
    state.clamp()
    return EconomyResult(ok=True, item_id=item.id)


def theoretical_item_price_bits(item: ItemDefinition) -> int | None:
    return item.suggested_market_price_bits or item.shop_price_bits


def create_market_listing(
    state: PetState,
    item_id: str,
    price_bits: int,
    id_factory: Callable[[], str] | None = None,
    time_provider: Callable[[], float] | None = None,
) -> EconomyResult:
    item_id = str(item_id).strip()
    price_bits = int(price_bits)
    if not item_id:
        return EconomyResult(ok=False, reason="unknown_item")
    if price_bits < 1:
        return EconomyResult(ok=False, reason="invalid_listing_price")
    if state.inventory.get(item_id, 0) <= 0:
        return EconomyResult(ok=False, reason="missing_inventory_item")

    quantity = state.inventory.get(item_id, 0) - 1
    if quantity <= 0:
        state.inventory.pop(item_id, None)
    else:
        state.inventory[item_id] = quantity

    listing = MarketListingState(
        id=(id_factory or _new_listing_id)(),
        item_id=item_id,
        price_bits=price_bits,
        created_at=int((time_provider or time.time)()),
    )
    state.market_listings.append(listing)
    state.clamp()
    return EconomyResult(ok=True, listing=listing)


def cancel_market_listing(state: PetState, listing_id: str) -> EconomyResult:
    listing = _pop_listing(state, listing_id)
    if listing is None:
        return EconomyResult(ok=False, reason="listing_not_found")
    state.inventory[listing.item_id] = state.inventory.get(listing.item_id, 0) + 1
    state.clamp()
    return EconomyResult(ok=True, item_id=listing.item_id, listing=listing)


def sell_market_listing(state: PetState, listing_id: str) -> EconomyResult:
    listing = _pop_listing(state, listing_id)
    if listing is None:
        return EconomyResult(ok=False, reason="listing_not_found")
    state.bits += listing.price_bits
    state.clamp()
    return EconomyResult(ok=True, item_id=listing.item_id, listing=listing)


def _pop_listing(state: PetState, listing_id: str) -> MarketListingState | None:
    listing_id = str(listing_id).strip()
    for index, listing in enumerate(state.market_listings):
        if listing.id == listing_id:
            return state.market_listings.pop(index)
    return None


def _new_listing_id() -> str:
    return uuid.uuid4().hex
