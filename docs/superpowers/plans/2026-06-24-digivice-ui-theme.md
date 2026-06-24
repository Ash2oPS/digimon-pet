# Digivice UI Theme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the approved D2-A Clean Digivice Shell visual direction to the desktop app UI.

**Architecture:** Keep the change mostly in the shared QSS theme so all existing PySide windows inherit the new look without layout rewrites. Add only small inventory-specific QSS changes where the window already has local slot/detail styles.

**Tech Stack:** Python, PySide6, Qt Style Sheets, pytest.

---

## File Structure

- Modify `src/digimon_pet/app/theme.py`: replace the global palette and shared widget QSS with the D2-A Digivice style.
- Modify `src/digimon_pet/app/inventory_window.py`: align inventory filters, slots, detail panel, and count badge with the new data-cartridge style.
- Modify `tests/test_inventory_window.py`: add focused assertions for existing item state behavior if missing; avoid brittle visual color tests.
- Modify or use existing UI tests: run `tests/test_stats_window.py`, `tests/test_inventory_window.py`, `tests/test_main_window.py`.
- No new font file in this pass. Use a fallback stack that prefers terminal-style fonts when installed and stays readable without packaging changes.

### Task 1: Shared Theme Palette And Global Controls

**Files:**
- Modify: `src/digimon_pet/app/theme.py`
- Test: existing UI tests only

- [ ] **Step 1: Update the shared color map**

Replace `COLORS` in `src/digimon_pet/app/theme.py` with:

```python
COLORS = {
    "surface": "#050b13",
    "surface_alt": "#091827",
    "panel": "#0d1a29",
    "panel_alt": "#12263b",
    "panel_hot": "#173653",
    "line": "#2e5876",
    "line_soft": "#18324a",
    "text": "#f6fbff",
    "muted": "#9ec5d8",
    "subtle": "#5f7f95",
    "accent": "#00d8ff",
    "accent_soft": "#0b6680",
    "accent_pressed": "#0b9ec0",
    "accent_alt": "#ff5a2f",
    "focus": "#ffdf4a",
    "focus_soft": "#725f20",
    "success": "#7dff8a",
    "danger": "#ff5f73",
    "danger_soft": "#5b2632",
}
```

- [ ] **Step 2: Update the global QWidget typography**

In `APP_QSS`, set the root widget block to:

```css
QWidget {
    background: #050b13;
    color: #f6fbff;
    font-family: "VT323", "Cascadia Mono", "Consolas", "Segoe UI", Arial, sans-serif;
    font-size: 13px;
    selection-background-color: #0b6680;
    selection-color: #f6fbff;
}
```

Use `COLORS[...]` interpolation in the real code rather than hard-coded values inside the f-string.

- [ ] **Step 3: Square off shared panels and buttons**

In `APP_QSS`, lower shared `border-radius` values from `7px`/`8px`/`9px` to `2px` or `3px` for panels, buttons, inputs, list widgets, tabs, and progress bars. Keep circular badges such as inventory quantity badges round if they rely on fixed square sizing.

Use this button style as the target:

```css
QPushButton {
    background: #0d1a29;
    border: 2px solid #2e5876;
    border-radius: 2px;
    padding: 7px 11px;
    color: #ffdf4a;
    font-weight: 800;
}

QPushButton:hover {
    background: #12263b;
    border-color: #00d8ff;
}

QPushButton:pressed {
    background: #0b6680;
    border-color: #00d8ff;
}

QPushButton:focus {
    border-color: #ffdf4a;
}
```

- [ ] **Step 4: Update progress bars to hard-edged Digivice gauges**

Change the shared `QProgressBar` and `QProgressBar::chunk` rules to:

```css
QProgressBar {
    background: #091827;
    border: 2px solid #2e5876;
    border-radius: 1px;
    height: 12px;
    text-align: center;
}

QProgressBar::chunk {
    background: #00d8ff;
    border-radius: 0px;
}
```

- [ ] **Step 5: Run focused smoke tests**

Run:

```powershell
uv run pytest tests/test_stats_window.py tests/test_main_window.py -q
```

Expected: both files pass. If failures are caused by QSS parsing or widget construction, fix the QSS before continuing.

### Task 2: Stats, Dialog, And Shared Card Polish

**Files:**
- Modify: `src/digimon_pet/app/theme.py`
- Test: `tests/test_stats_window.py`

- [ ] **Step 1: Restyle stats and shared card frames**

Update rules for `QFrame#StatsHeader`, `QFrame#StatsPanel`, `QFrame#StatsMetricCard`, `QFrame#EvolutionRequirementCard`, `QFrame#SelectedDigimonHeader`, `QFrame#EditorSection`, `QFrame#EvolutionEditorSection`, `QWidget#StageHeaderPanel`, and `QWidget#EvolutionNode` to use:

```css
background: #0d1a29;
border: 2px solid #2e5876;
border-radius: 2px;
```

For header-like blocks, keep a yellow or cyan top border:

```css
border-top-color: #00d8ff;
```

- [ ] **Step 2: Restyle section labels and titles**

Keep title text readable with:

```css
QLabel#Title {
    color: #f6fbff;
    font-size: 16px;
    font-weight: 900;
}

QLabel#SectionTitle,
QLabel#StageHeader,
QLabel#EvolutionGraphStageHeader {
    color: #ffdf4a;
    background: transparent;
    font-weight: 900;
}
```

- [ ] **Step 3: Restyle tabs as device keys**

Change tab rules to:

```css
QTabWidget::pane {
    border: 2px solid #2e5876;
    border-radius: 2px;
    background: #0d1a29;
}

QTabBar::tab {
    background: #091827;
    color: #9ec5d8;
    border: 2px solid #2e5876;
    border-bottom: none;
    padding: 6px 10px;
    margin-right: 2px;
    border-top-left-radius: 2px;
    border-top-right-radius: 2px;
    font-weight: 800;
}

QTabBar::tab:selected {
    background: #12263b;
    color: #ffdf4a;
    border-color: #00d8ff;
}
```

- [ ] **Step 4: Run stats tests**

Run:

```powershell
uv run pytest tests/test_stats_window.py -q
```

Expected: pass.

### Task 3: Inventory Data-Cartridge Styling

**Files:**
- Modify: `src/digimon_pet/app/inventory_window.py`
- Test: `tests/test_inventory_window.py`

- [ ] **Step 1: Update inventory count and filters**

In `_INVENTORY_QSS`, change `QLabel#InventoryCount` and `QToolButton#InventoryFilter` rules to use dark screen surfaces, 2px borders, 2px radius, cyan/yellow accents:

```css
QLabel#InventoryCount {
    background: #091827;
    border: 2px solid #00d8ff;
    border-radius: 2px;
    color: #ffdf4a;
    font-weight: 900;
    padding: 4px 8px;
}

QToolButton#InventoryFilter {
    background: #091827;
    border: 2px solid #2e5876;
    border-radius: 2px;
    color: #9ec5d8;
    font-weight: 900;
    padding: 6px 10px;
}

QToolButton#InventoryFilter:checked {
    background: #12263b;
    border-color: #00d8ff;
    color: #ffdf4a;
}
```

- [ ] **Step 2: Update grid and slot styling**

Restyle `QWidget#InventoryGrid` and `QWidget#InventorySlot` as data cartridges:

```css
QWidget#InventoryGrid {
    background: #050b13;
    border: 2px solid #18324a;
    border-top-color: #00d8ff;
    border-radius: 2px;
}

QWidget#InventorySlot {
    background: #0d1a29;
    border: 2px solid #2e5876;
    border-radius: 2px;
}

QWidget#InventorySlot[empty="false"] {
    background: #12263b;
    border-color: #0b6680;
}

QWidget#InventorySlot[selected="true"] {
    background: #173653;
    border-color: #ffdf4a;
}
```

Keep `dangerous="true"` using the danger color and `usable="false"` visibly muted.

- [ ] **Step 3: Update detail panel and item labels**

Restyle `QFrame#InventoryDetails`, `QLabel#InventorySlotType`, `QLabel#InventoryDetailsIcon`, and `QLabel#InventoryStatus` to match the global 2px-border style. Use orange (`accent_alt`) only for dangerous or primary action highlights, not all labels.

- [ ] **Step 4: Run inventory tests**

Run:

```powershell
uv run pytest tests/test_inventory_window.py -q
```

Expected: pass.

### Task 4: Runtime Visual Verification

**Files:**
- No required code changes unless visual issues are found

- [ ] **Step 1: Start the app**

Run:

```powershell
uv run python -m digimon_pet --debug
```

Expected: the pet starts and debug panel opens without QSS warnings in the terminal.

- [ ] **Step 2: Inspect windows**

Open the app UI surfaces manually:

- Stats
- Inventory
- Collection if reachable
- Item manager from debug panel
- Baby choice only if lifecycle flow makes it available without corrupting save state

Check:

- Text is readable in title, body, button, table, and tooltip contexts.
- Focus outlines are visible.
- Inventory selected/unusable/danger states are distinguishable.
- Progress bars remain legible.
- The pet overlay is not visually affected.

- [ ] **Step 3: Fix visual defects found during inspection**

If text is clipped, reduce font size only for the affected selector. If a color state is ambiguous, tune the selector-specific color without changing the whole palette.

### Task 5: Final Test And Commit

**Files:**
- Modify only files changed by Tasks 1-4

- [ ] **Step 1: Run focused test set**

Run:

```powershell
uv run pytest tests/test_stats_window.py tests/test_inventory_window.py tests/test_main_window.py tests/test_debug_settings.py -q
```

Expected: pass.

- [ ] **Step 2: Review git diff**

Run:

```powershell
git diff -- src/digimon_pet/app/theme.py src/digimon_pet/app/inventory_window.py tests/test_inventory_window.py
git status --short
```

Expected: only intended UI theme files are modified in the implementation diff. Pre-existing unrelated asset/data changes may still appear unstaged.

- [ ] **Step 3: Commit implementation**

Stage only implementation files:

```powershell
git add -- src/digimon_pet/app/theme.py src/digimon_pet/app/inventory_window.py tests/test_inventory_window.py
git commit -m "improve(ui): apply Digivice theme"
```

Expected: one scoped commit. Do not stage unrelated asset/data changes.

## Self-Review

- Spec coverage: global theme, stats, inventory, dialogs, typography fallback, colors, component rules, and validation are covered.
- Scope control: no layout rebuild, no pet overlay changes, no external font packaging.
- Test strategy: focused existing UI tests plus manual runtime visual verification.
