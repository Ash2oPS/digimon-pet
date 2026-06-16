# Digimon Pet

Small Windows desktop virtual pet scaffold inspired by Digimon World 1.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Run

Development window:

```powershell
python -m digimon_pet --normal --debug
```

Overlay window:

```powershell
python -m digimon_pet --overlay
```

## Test

```powershell
python -m pytest -v
```

## Assets

Sprites are intentionally not bundled. Put manually supplied PNG spritesheets under `assets/sprites/<species_id>/` and update `data/species.json`.

