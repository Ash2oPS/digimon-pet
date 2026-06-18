# Item Manager Design

## Goal

Build a debug-only item management tool for the Digimon Pet app. The tool lets the designer add, edit, delete, and tune game items without changing Python code. It also prepares the item drop pool used by a future secondary event that grants a random item according to configurable appearance weights.

## Scope

- Add a dedicated `Item Manager` window available only from debug mode.
- Move item definitions from hard-coded Python data to `data/items.json`.
- Support editing item identity, display metadata, sprite, type, evolution behavior, and drop weights.
- Keep the first random item pool focused on the secondary event: `secondary_event`.
- Make `evolution` items functional in runtime. Other item types are editable but do not need gameplay effects yet.

Out of scope:

- Implementing the secondary event reward flow itself.
- Implementing gameplay effects for non-evolution item types.
- Building a general-purpose scripting system for item effects.

## Data Model

Create `data/items.json` with two top-level sections:

- `items`: list of item definitions.
- `pools`: named random pools, starting with `secondary_event`.

Each item definition stores:

- `id`: stable unique id, snake_case.
- `name`: display name.
- `description`: inventory/tool text.
- `type`: one of `evolution`, `consumable`, `key_item`, `misc`.
- `icon_path`: path under `assets/items/`.
- `evolution`: optional object used when `type` is `evolution`.

Evolution item data stores:

- `target_species_id`: species reached after item use.
- `required_species_ids`: allowed current Digimon ids.
- `required_stages`: allowed current growth stages.

Pool entries store:

- `item_id`: referenced item id.
- `weight`: non-negative integer weight.

The runtime should calculate the visible percentage from the active pool's total weight instead of storing percentages.

## UX

The Item Manager is a separate PySide dialog opened from debug mode only.

Layout:

- Left panel: searchable item list with add/delete controls.
- Right panel: detail editor for the selected item.
- Detail fields: id, name, description, type, sprite selector with preview.
- Evolution section: visible for `evolution` type, with target species, required species, and required stages.
- Pool section: `secondary_event` weights table showing item name, raw weight, and calculated chance percentage.
- Footer actions: save, reload, and validation summary.

Sprite workflow:

- User selects an image file.
- The tool copies it into `assets/items/`.
- The stored `icon_path` points to the copied asset.
- The preview updates immediately.

Deletion workflow:

- Deleting an item removes it from `data/items.json` and from pools.
- Old saves may still contain the removed id, but inventory UI should ignore unknown item ids.

## Validation

Saving is blocked when:

- An item id is empty or duplicated.
- An item id is not stable/snake_case compatible.
- A referenced sprite path does not exist.
- An evolution target species does not exist.
- A required species id does not exist.
- A required stage is unknown.
- A pool references an unknown item id.
- A pool weight is negative.

The tool should show actionable validation messages near the save area. Warnings may be used for non-blocking issues, such as an item with zero drop weight.

## Runtime Integration

Item runtime behavior should load definitions from `data/items.json` through the app data loading layer. Existing Monzaemon Head behavior should be represented as an item definition in the JSON file and remain functional.

Inventory rendering should use item definitions for display name, icon, and description. Unknown item ids should be skipped so deleted items in old saves do not break the inventory.

The random pool helper should expose a deterministic function that receives a pool name and RNG, then returns an item id based on weights. This prepares the future secondary event without wiring the reward event yet.

## Testing

Add focused tests for:

- Loading and validating `data/items.json`.
- Existing Monzaemon Head evolution item behavior after moving data to JSON.
- Inventory display skipping unknown item ids.
- Weighted random selection ignoring zero-weight entries and rejecting empty/invalid pools.
- Item Manager validation rules for duplicate ids, missing sprites, unknown species, and invalid weights.

UI tests should cover the PySide widgets at the smallest practical level: create the dialog, populate fields, validate edits, and confirm no save occurs when blocking errors exist.
