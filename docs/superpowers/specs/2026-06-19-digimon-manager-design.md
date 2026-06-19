# Digimon Manager Design

## Goal

Create a standalone Python desktop tool for managing Digimon data without launching the pet app in debug mode.

The tool must make it easy to add, duplicate, edit, delete, validate, and save Digimon and their evolution relationships with a better UI/UX than the current item manager.

## Launch

Primary command:

```powershell
python -m digimon_pet.tools.digimon_manager
```

The tool runs as its own PySide6 application window. It does not require `python -m digimon_pet --debug`.

## Data Scope

The first implementation manages:

- `data/species.json`
- `data/dw1_digivolutions.json`

The manager edits Digimon definitions and evolution links. Derived indexes in `dw1_digivolutions.json` are recalculated by code instead of edited manually.

Out of scope for the first implementation:

- editing item definitions
- packaging a separate executable
- full interactive graph editing
- lifecycle simulation beyond structural validation

## User Experience

Visual direction: compact admin tool with enough visual preview to make Digimon editing comfortable.

Main layout:

- center: sortable/filterable Digimon table
- top controls: search, stage filter, data status filter
- right panel: selected Digimon details
- lower/right tab area: sprite slots and evolution relationships
- bottom/status area: validation summary and save state

Expected actions:

- Add Digimon
- Duplicate selected Digimon
- Delete selected Digimon
- Add natural evolution
- Add special evolution
- Remove evolution
- Validate
- Save

The UI should avoid the current item manager's narrow form-first flow. The table should support fast scanning, while the detail panel handles focused edits.

## Digimon Editing

Editable fields:

- id
- name
- stage
- sprite slots:
  - idle
  - walk
  - sleep
  - eat
  - train

Behavior:

- ids use lowercase snake_case style unless existing data requires otherwise
- name-to-id autocomplete is allowed for new Digimon
- sprite paths are project-relative paths
- sprite preview shows available slot images
- missing sprite paths are surfaced in validation

## Evolution Editing

Natural evolutions:

- source species
- target species
- target stage
- stat requirements:
  - hp
  - mp
  - offense
  - defense
  - speed
  - brains
- chart order where present
- notes where present

Special evolutions:

- target species
- source selector:
  - any
  - stage
  - species ids
- trigger text
- notes

Indexes:

- `indexes.by_source` is regenerated from natural evolution rows.
- manual index editing is not exposed.

## Delete Safety

Deleting a Digimon must show impact before mutating data:

- natural evolutions where it is source
- natural evolutions where it is target
- special evolutions that target it
- special source selectors that reference it
- sprite paths attached to it

Default behavior is to block deletion until the user confirms. Confirmed deletion removes or updates affected evolution rows so saved data remains valid.

## Validation

Validation must run before save and should also update live while editing.

Blocking validation:

- duplicate Digimon ids
- empty id or name
- invalid stage
- evolution source or target references unknown species
- special source selectors reference unknown species
- invalid requirement stat names
- invalid requirement values
- malformed natural evolution ids

Warnings:

- missing sprite files
- Digimon with no outgoing evolution where that is unusual for its stage
- Digimon with no incoming evolution where that is unusual for its stage
- special evolution trigger text is empty

Save is blocked only by blocking validation errors. Warnings remain visible but do not block.

## Architecture

Use PySide6, matching the existing app dependency.

Suggested modules:

- `digimon_pet.tools.digimon_manager`
  - standalone entry point
  - creates `QApplication`
  - loads project data
  - opens the manager window
- `digimon_pet.app.digimon_manager_window`
  - UI composition and widget state
  - no direct JSON parsing details beyond calling service functions
- `digimon_pet.domain.digimon_catalog`
  - dataclasses or typed helpers for editable species/evolution data
  - validation
  - add/duplicate/delete operations
  - index rebuild
- existing loaders remain source of truth where practical

The UI should keep styling centralized. If existing `APP_QSS` is insufficient, add manager-specific QSS or theme tokens without scattering inline styles.

## Save Flow

1. User edits in memory.
2. UI tracks dirty state.
3. User clicks Save.
4. Validation runs.
5. If blocking errors exist, save is refused and errors are shown.
6. If valid, write formatted JSON with stable ordering.
7. Dirty state clears.

## Testing

Unit tests:

- load and serialize species without data loss
- load and serialize digivolutions without data loss
- add Digimon with generated id
- duplicate Digimon with unique id/name
- delete Digimon with referenced evolutions
- rebuild `indexes.by_source`
- validation catches broken references
- validation distinguishes blocking errors from warnings

UI tests:

- window opens standalone
- selecting a Digimon populates detail fields
- editing fields updates in-memory data
- save refuses invalid data
- delete confirmation receives correct impact summary

## Acceptance Criteria

- Running `python -m digimon_pet.tools.digimon_manager` opens the Digimon Manager directly.
- The app can add, duplicate, edit, delete, validate, and save Digimon.
- The app can add, edit, remove, validate, and save natural and special evolutions.
- `data/species.json` and `data/dw1_digivolutions.json` remain valid after save.
- Indexes are regenerated automatically.
- The UI is visibly more usable than the current item manager: searchable table, focused detail panel, sprite previews, impact-aware deletion, and clear validation states.
