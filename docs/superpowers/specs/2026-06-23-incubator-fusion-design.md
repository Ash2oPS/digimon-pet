# Incubator Fusion Design

## Goal

Add a new Incubator feature that lets the player convert the current Digimon into a stored fusion material, then start a new generation. Later, a filled incubator can be used with the current Digimon to produce fusion-only Digimon.

This is not a duplicate of DigiGun. DigiGun kills the current Digimon to start rebirth. Incubator preserves the sacrificed Digimon as an item-like stored entity for future fusion.

## Player Flow

### Empty Incubator

- `incubator` remains a droppable special item.
- It can be used only when the current Digimon is `rookie` stage or later.
- Using it requires the same kind of deliberate confirmation as dangerous lifecycle actions.
- On confirmation:
  - one empty incubator is consumed;
  - the current Digimon is stored as a filled incubator entry;
  - the current Digimon functionally dies;
  - the player starts a new generation through the Baby1 choice flow.
- The rebirth bonus from incubator sacrifice is reduced to 50% of the normal death rebirth bonus.

### Filled Incubator

- A filled incubator represents one stored Digimon.
- Filled incubators appear in inventory as distinct special items, such as `Incubator: Greymon`.
- Filled incubators are not represented by `inventory[item_id]` quantities, because each one has unique contents.
- Using a filled incubator with the current Digimon attempts a fusion.

### Fusion

- Fusion recipes are symmetric: `A + B` is equivalent to `B + A`.
- If the current Digimon and filled incubator contents match a recipe:
  - the filled incubator is consumed;
  - the current Digimon becomes the fusion result;
  - the result is marked discovered.
- If no recipe exists:
  - the action is refused;
  - the filled incubator is not consumed;
  - the current Digimon is unchanged.
- No random fusion failure is included in the first implementation.

## Data Model

### Save Data

Extend `PetState` with a dedicated filled-incubator collection:

```python
filled_incubators: list[FilledIncubatorState]
```

Each filled incubator stores:

- unique id;
- stored `species_id`;
- stored `stage`;
- snapshot of fusion-relevant stats: `hp`, `mp`, `offense`, `defense`, `speed`, `brains`;
- optional display metadata such as stored species name can be derived at runtime.

The saved structure should be backward compatible. Legacy saves without filled incubators load with an empty list.

### Fusion Recipes

Create a dedicated `data/fusions.json` file:

```json
{
  "fusions": [
    {
      "source_species_ids": ["wargreymon", "metalgarurumon"],
      "target_species_id": "omnimon",
      "notes": "Example future fusion"
    }
  ]
}
```

Rules:

- `source_species_ids` always contains exactly two species ids.
- Source order does not matter.
- `target_species_id` must reference an existing species.
- `notes` is optional and designer-facing only.

## Runtime Components

### Domain

Add a small fusion domain module responsible for:

- loading and serializing fusion recipe data;
- validating recipe references;
- normalizing symmetric source pairs;
- finding a fusion target for two species ids.

Add incubator behavior to item usage without turning item definitions into a scripting system. The incubator is a special-case runtime action because it mutates save structure and lifecycle state.

### Inventory

Inventory should combine two sources:

- normal item quantities from `state.inventory`;
- filled incubator entries from `state.filled_incubators`.

Filled incubators should render as special inventory entries with unique runtime ids. The inventory item id passed back to the app must use the stable prefix `filled_incubator:<entry_id>`.

### Lifecycle

Incubating the current Digimon should reuse the existing rebirth choice flow where possible, but must not roll the normal Bakemon natural death evolution. This is a deliberate storage action, not natural death.

The current Digimon's rebirth bonuses should be rolled from the existing stat-bonus logic, then reduced by 50% before being applied as pending generation bonuses.

## Digimon Manager

Digimon Manager must expose fusion recipes so designers can edit them without hand-editing JSON.

Add a `Fusions` tab with:

- recipe list;
- Digimon A selector;
- Digimon B selector;
- result Digimon selector;
- notes field;
- add, duplicate, delete, validate, and save actions matching existing manager behavior.

Validation blocks save when:

- either source species is missing;
- the target species is missing;
- either source references an unknown species;
- the target references an unknown species;
- a symmetric duplicate exists;
- a recipe does not contain exactly two sources.

Warnings may show when:

- source A and source B are the same;
- the target is already obtainable through normal evolution;
- either source is below a late-game stage.

## Implementation Phases

1. Add filled-incubator save data and empty-incubator runtime behavior.
2. Add `data/fusions.json`, fusion domain loading, validation, and tests.
3. Add Digimon Manager fusion editing.
4. Add filled-incubator inventory rendering and fusion execution.

## Tests

Add focused tests for:

- legacy saves load with no filled incubators;
- filled incubators persist through save/load;
- empty incubator is blocked for Baby and Baby2 stages;
- empty incubator stores the current Digimon and starts rebirth;
- incubator rebirth bonus is reduced compared with normal death;
- filled incubator inventory entries render separately;
- no-recipe fusion refuses without consuming the incubator;
- matching recipe consumes the incubator and changes current species;
- fusion recipes are symmetric;
- Digimon Manager blocks invalid or duplicate fusion recipes.

## Out of Scope

- Omnimon, WarGreymon, MetalGarurumon, or other new fusion species.
- fusion animations beyond existing lifecycle feedback.
- multi-Digimon party management.
- random fusion failure.
- reusable incubators after fusion.
