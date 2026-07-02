# Currency, Shop, and Network Market Design

## Goal

Add a simple player economy to Digimon Pet with Bits, a fixed in-game item shop, and a local-network player market where friends can buy items listed by other players.

## Scope

- Add a global `bits` wallet saved with the player state.
- Award Bits from every secondary event.
- Add fixed shop prices to item data.
- Add a dedicated Shop window opened from the pet right-click radial menu.
- Let players list owned items for sale with a custom price.
- Let online friends view and buy listed items over the existing local network system.

Out of scope:

- Server-backed online marketplace.
- Strong anti-cheat or cryptographic transaction protection.
- Extra earning sources from training, care, battles, or evolution.
- Donations or zero-price listings.

## Currency Rules

The currency is named `Bits`.

New and migrated saves start with `100` Bits. Bits are global to the player and survive death, rebirth, and generation changes.

Every secondary event grants a random amount of Bits in addition to its current effect. The MVP reward range is `50` to `120` Bits inclusive.

The wallet must never go below `0`. Buying requires enough Bits before inventory changes are applied.

## Shop Catalog

Shop pricing lives in `data/items.json` on each item definition. The first shop catalog is fixed and includes:

| Item | Price |
| --- | ---: |
| DigiMeat | 300 Bits |
| DigiFish | 300 Bits |
| DigiWeed | 300 Bits |
| DigiMushroom | 300 Bits |
| DigiVeggie | 300 Bits |
| DigiBerry | 300 Bits |
| DigiGun | 1000 Bits |
| DigiAlcohol | 1000 Bits |
| Auto Clicker | 1500 Bits |

Each listed item also has a suggested market price. For the MVP, the suggested market price should match the fixed shop price.

## Local Shop UX

Add a `Shop` action to the existing pet right-click radial menu. It opens a dedicated PySide dialog.

The dialog has three tabs:

- `Shop`: fixed in-game catalog, current Bits balance, item details, and buy action.
- `My Listings`: owned items eligible for sale, suggested price, custom price input, active listings, and cancel action.
- `Friends`: online friends' listings, seller name, item details, price, online status, and buy action.

The UI should follow the existing Digivice theme used by inventory and network windows.

## Listing Rules

Only owned items can be listed.

When a player lists an item:

- Price must be at least `1` Bit.
- One quantity is removed from inventory immediately.
- A listing entry is saved locally.
- The listing appears to online friends through the local network payload.

When a player cancels a listing:

- The listing is removed.
- The item returns to inventory.

Listings survive app restart.

## Network Market Rules

The network market uses the existing local network model. Friends must be online for purchases.

Friend listings are advertised through a small market endpoint on the same local service as presence. Buying an item is a direct request to the seller app through that endpoint.

When a buyer purchases a listing:

- Buyer must have enough Bits.
- Seller must still be online.
- Seller must still have the listing.
- Buyer loses Bits and receives the item.
- Seller receives Bits and the listing is removed.

This is a local fun feature, not a secure economy. Basic validation is enough to prevent accidental invalid transactions, but deliberate local tampering is out of scope.

If the seller is offline, the listing may remain visible from the last known data, but the buy button is disabled.

## Data Model

Extend `PetState` with:

- `bits: int`
- `market_listings: list[MarketListingState]`

`MarketListingState` stores:

- `id`: stable unique listing id.
- `item_id`: listed item.
- `price_bits`: custom seller price.
- `created_at`: Unix timestamp for stable ordering.

Extend item definitions in `data/items.json` with:

- `shop_price_bits`: optional fixed shop price. Items without this value are not sold by the system shop.
- `suggested_market_price_bits`: optional suggested listing price.

Save loading should tolerate missing fields and old saves.

## Architecture

Add domain helpers for economy operations:

- award Bits.
- buy from fixed shop.
- create listing.
- cancel listing.
- complete network purchase.

These helpers mutate `PetState` and return small result objects with success/failure reasons. UI and network code should not duplicate transaction logic.

Add a Shop window under `src/digimon_pet/app/` and wire it from `main_window.py` and `radial_menu.py`.

Extend the network service with a market endpoint for listing reads and purchase requests while preserving the current presence behavior for existing tests.

## Error Handling

Expected failure reasons:

- unknown item.
- item not sold by shop.
- insufficient Bits.
- missing inventory item.
- invalid listing price.
- listing not found.
- seller offline.
- seller rejected purchase.

The UI should show concise status text and leave state unchanged on failed transactions.

## Testing

Add focused tests for:

- save migration defaults Bits to `100` and empty listings.
- Bits clamp to non-negative values.
- secondary events award `50-120` Bits.
- fixed shop purchase succeeds and fails correctly.
- listing removes one inventory item and cancellation restores it.
- market purchase transfers Bits and item.
- item JSON shop price fields load and serialize.
- Shop window can render the catalog and listing data.
- network market payload parsing accepts valid listings and rejects malformed listings.
