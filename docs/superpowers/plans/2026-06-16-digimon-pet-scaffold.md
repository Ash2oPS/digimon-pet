# Digimon Pet Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a launchable PySide6 scaffold for a Windows desktop Digimon-style virtual pet with data-driven growth from Botamon to Koromon to Agumon.

**Architecture:** The app is split into domain logic, JSON data loading, JSON persistence, and PySide UI. Domain modules have no Qt dependency so they can be unit tested quickly. The UI reads and mutates state through small service functions and saves after each action/tick.

**Tech Stack:** Python 3.11+, PySide6, pytest, JSON data files.

---

## File Structure

- Create `pyproject.toml`: package metadata, dependencies, pytest config, console entrypoint.
- Create `README.md`: setup and launch instructions.
- Create `src/digimon_pet/__init__.py`: package marker.
- Create `src/digimon_pet/__main__.py`: `python -m digimon_pet` entrypoint.
- Create `src/digimon_pet/main.py`: console entrypoint.
- Create `src/digimon_pet/paths.py`: project/data/save path helpers.
- Create `src/digimon_pet/domain/models.py`: dataclasses and enums for pet state and species.
- Create `src/digimon_pet/domain/care.py`: care action functions.
- Create `src/digimon_pet/domain/evolution.py`: deterministic rule selection.
- Create `src/digimon_pet/data/loaders.py`: typed JSON loaders.
- Create `src/digimon_pet/storage/save_store.py`: JSON save/load roundtrip.
- Create `src/digimon_pet/app/theme.py`: centralized QSS and color tokens.
- Create `src/digimon_pet/app/pet_widget.py`: animated pet widget with placeholder rendering.
- Create `src/digimon_pet/app/debug_panel.py`: compact debug controls and stat labels.
- Create `src/digimon_pet/app/main_window.py`: window modes, tick loop, movement, menus.
- Create `data/species.json`: Botamon, Koromon, Agumon definitions and sprite slots.
- Create `data/evolution_rules.json`: Botamon -> Koromon and Koromon -> Agumon rules.
- Create `data/default_save.json`: initial pet save.
- Create `assets/sprites/README.md`: expected spritesheet slots.
- Create `tests/test_data_loading.py`: validate JSON parsing.
- Create `tests/test_save_store.py`: validate persistence roundtrip.
- Create `tests/test_evolution.py`: validate evolution priority and thresholds.

## Tasks

### Task 1: Project Metadata and Data Model

- [x] Create package metadata, entrypoints, path helpers, domain dataclasses, JSON data, and tests for loading.
- [x] Run `python -m pytest tests/test_data_loading.py -v`.
- [x] Expected: tests pass.

### Task 2: Care, Persistence, and Evolution

- [x] Add care actions, save/load helpers, and evolution rule evaluation.
- [x] Add tests for save roundtrip and evolution thresholds.
- [x] Run `python -m pytest -v`.
- [x] Expected: all tests pass.

### Task 3: PySide App Scaffold

- [x] Add central theme, pet widget, debug panel, and main desktop window.
- [x] Wire right-click menu actions and debug panel actions to domain functions.
- [x] Add tick loop for stat drift, autonomous movement, saving, and evolution checks.
- [x] Run `python -m pytest -v`.
- [x] Run `python -m digimon_pet --normal --debug`.
- [x] Expected: tests pass and the desktop window launches.

### Task 4: Documentation and Final Commit

- [x] Add setup and usage instructions to `README.md`.
- [x] Verify `git status --short`.
- [x] Commit scaffold with `feat: scaffold digimon desktop pet`.
