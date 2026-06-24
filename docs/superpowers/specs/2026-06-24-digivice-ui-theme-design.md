# Digivice UI Theme Design

## Goal

Restyle the desktop UI around the selected **D2-A Clean Digivice Shell** direction: a readable pixel-terminal Digivice interface with dark device surfaces, cyan/yellow borders, segmented gauges, and data-slot panels.

The pet overlay and sprite rendering stay functionally unchanged. The first implementation pass targets the app windows and dialogs that already use `APP_QSS`.

## Visual Direction

- Base surface: deep navy/black device shell.
- Panels: dark blue screen surfaces with subtle pixel-grid texture where Qt styling allows it.
- Borders: cyan primary frame, yellow focus/info accent, orange action/selection accent.
- Typography: terminal/pixel display feel for short titles, buttons, tabs, counters, and labels; standard readable UI font for long descriptions and dense copy.
- Geometry: squarer controls, lower radius, heavier borders, clipped/device-like emphasis where feasible in QSS.
- Gauges: segmented or hard-edged bars instead of soft rounded progress.

## Scope

Primary surfaces:

- Global theme in `src/digimon_pet/app/theme.py`.
- Stats window panels, tabs, portrait frame, metric cards, progress bars.
- Inventory window filters, slots, details panel, count badge.
- Baby choice cards and standard dialogs that inherit `APP_QSS`.
- Debug panel and manager windows through shared widget styles.

Out of scope for this pass:

- Changing pet sprite animations or overlay behavior.
- Rebuilding layouts.
- Adding custom painted widgets unless QSS cannot express an essential part of the style.
- Downloading or bundling external fonts before deciding whether PySide packaging should include them.

## Component Rules

- Buttons use hard borders, compact padding, and clear hover/pressed/focus colors.
- Inputs and combo boxes remain readable first; pixel styling should not reduce form usability.
- Tabs should look like device navigation keys, not browser tabs.
- Inventory slots should read as data cartridges: clear empty state, selected state, unusable state, and danger state.
- Progress bars should use hard-edged chunks with no soft radius.
- Tooltip, menu, list, and table styling should stay consistent with the new palette.

## Palette Draft

- `surface`: near-black navy.
- `surface_alt`: dark screen blue.
- `panel`: device panel blue.
- `panel_alt`: raised panel blue.
- `line`: muted steel/cyan frame.
- `accent`: electric cyan.
- `accent_alt`: warm orange for active actions.
- `focus`: Digivice yellow.
- `success`: digital green.
- `danger`: warning red.

Exact values should be tuned in `COLORS` and verified visually in the running app.

## Validation

- Run the existing focused UI tests where available.
- Start the app locally and inspect at least Stats and Inventory windows.
- Verify text remains readable, buttons retain visible focus, and progress bars/slots show all important states.
- If visual verification cannot be automated, record the unchecked areas in the final summary.
