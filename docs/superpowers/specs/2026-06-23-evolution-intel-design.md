# Evolution Intel Design

## Goal

Replace the current Evolution tab with an `Evolution Intel` experience that shows every direct evolution path while hiding digivolution conditions until the player discovers them through event-bubble interactions.

## User Experience

The tab uses a master/detail layout.

Left panel: `Direct evolutions`
- Shows one selectable card per direct natural evolution from the current Digimon.
- Known targets show sprite/artwork, name, target stage, and clue count.
- Unknown targets still appear as `???` with a silhouette or question marker.
- Each card shows six clue slots: `HP`, `MP`, `OFF`, `DEF`, `SPD`, `INT`.
- Slot states are `?` for unknown, a check/threshold hint for known required stats, and `-` for known no-requirement stats.

Right panel: selected evolution detail
- Shows target name if discovered, otherwise `???`.
- Shows `Known evolution intel`.
- For each stat:
  - unknown clue: `???` and `Unknown`
  - discovered required stat: current value, required value, progress bar, and `OK` or `Need X`
  - discovered no-requirement stat: `-` and `No requirement`
- No hidden condition value appears in labels or tooltips before discovery.

## Discovery Rules

By default, no evolution condition clue is known.

On each secondary event-bubble interaction:
- Pick a random direct natural evolution for the current Digimon.
- Pick a random undiscovered stat clue among `hp`, `mp`, `offense`, `defense`, `speed`, `brains`.
- Reveal that stat for that evolution.
- If the stat exists in the evolution requirements, show its threshold.
- If the stat is absent from the requirements, show `-`.
- If all direct evolution clues are already known, do not change state.

Only secondary event-bubble interactions grant clues. Menu actions such as feed/train do not grant clues in this version.

## Data Model

Add persistent clue state to `PetState`:

```python
evolution_condition_discoveries: dict[str, list[str]]
```

Keys are natural evolution ids such as `terriermon__to__galgomon`.
Values are discovered stat ids from the six tracked stats.

Save/load must preserve this field. Legacy saves default to `{}`.

## UI Behavior

The `Evolution Intel` tab should refresh from `PetState` and `dw1_digivolutions.json`.

Direct evolutions are derived from:
- `digivolutions["indexes"]["by_source"][state.species_id]`
- `digivolutions["natural_evolutions"]`

Target identity visibility follows the existing collection/evolution-tree rule:
- target discovered: show name and visual
- target not discovered: show `???`

Condition visibility follows the new clue state:
- target discovery does not automatically reveal conditions
- each stat condition remains hidden until its stat clue is recorded

## Testing

Focused tests should cover:
- default state hides all six condition slots
- discovered target still hides undiscovered condition values
- event-bubble claim reveals exactly one new clue when available
- revealed absent stat displays `-`
- revealed required stat displays threshold and progress
- save/load persists `evolution_condition_discoveries`
- UI lists all direct natural evolutions for the current Digimon

## Out Of Scope

- Revealing non-stat conditions such as weight, care mistakes, or bonus requirements.
- Revealing clues from regular menu actions.
- Changing actual evolution eligibility logic.
- Changing the collection evolution tree.
