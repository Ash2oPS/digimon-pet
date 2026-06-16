# Digimon Pet Scaffold Design

## Goal

Create an initial scaffold for a Windows desktop virtual pet inspired by Digimon World 1. The first slice must launch a small desktop pet, persist its state locally, expose simple care actions, and support data-driven growth from baby to rookie.

## Initial Scope

- Target platform: Windows.
- Runtime: Python with PySide6.
- Pet line: Botamon -> Koromon -> Agumon.
- Growth stages: baby, baby 2, rookie.
- Later stages, champion and ultimate, are represented in the data model but not fully implemented in the first slice.
- Evolution rules are approximate, data-driven, and inspired by Digimon World 1 requirements.
- Assets are not downloaded automatically. The project provides slots and manifests for manually supplied PNG spritesheets.

## User Experience

- The pet appears in a small desktop window.
- The app supports two window modes:
  - normal mode for development and debugging;
  - overlay mode with transparent, borderless, always-on-top behavior.
- The pet can move autonomously inside the available desktop area.
- Right-click opens a compact action menu.
- A small debug panel shows current stats and exposes testing controls.

## Gameplay Model

The pet has persistent state stored as JSON:

- species id;
- growth stage;
- age and lifecycle timers;
- hunger;
- fatigue;
- discipline;
- care mistakes;
- training count;
- sleep state;
- current animation/action.

The first care actions are:

- feed;
- train;
- sleep or wake;
- clean;
- scold.

Time advances through a configurable tick loop. Debug mode uses accelerated timing so evolution can be tested quickly.

## Evolution Model

Evolution rules live in JSON data files. Each rule defines:

- source species;
- target species;
- minimum age or elapsed time;
- stat thresholds;
- care mistake limits;
- priority for conflict resolution.

The initial rules cover Botamon -> Koromon -> Agumon. The rule engine is designed so champion and ultimate requirements can be added without changing app code.

## Assets

Assets use PNG spritesheets. Each Digimon can define sprites per action such as idle, walk, sleep, eat, and train.

The scaffold includes:

- asset directories;
- placeholder manifests;
- fallback placeholder rendering when sprite files are missing.

## Project Structure

- `src/digimon_pet/`: application package.
- `src/digimon_pet/app/`: PySide app, windows, menus, debug panel.
- `src/digimon_pet/domain/`: pet state, care actions, evolution logic.
- `src/digimon_pet/data/`: loaders for species and evolution JSON.
- `data/`: editable game data and default save seed.
- `assets/`: spritesheet slots and manifests.
- `tests/`: pytest tests for data loading, persistence, and evolution.
- `docs/`: project documentation.

## Validation

Initial validation should include:

- unit tests for JSON loading;
- unit tests for save/load roundtrip;
- unit tests for evolution rule selection;
- manual launch check for the desktop window.

## Out of Scope

- Automatic asset scraping or downloading.
- Exact full Digimon World 1 requirement parity.
- Champion and ultimate gameplay completion.
- Cross-platform window behavior.
- Installer/package distribution.
