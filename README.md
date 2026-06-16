# Digimon Pet

Small Windows desktop virtual pet scaffold inspired by Digimon World 1.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Run

Overlay desktop pet:

```powershell
python -m digimon_pet
```

Development mode with accelerated time:

```powershell
python -m digimon_pet --debug
```

Normal framed window for Qt debugging:

```powershell
python -m digimon_pet --normal --debug
```

## Test

```powershell
python -m pytest -v
```

## Assets

Sprites are intentionally not bundled. Put manually supplied PNG spritesheets under `assets/sprites/<species_id>/` and update `data/species.json`.
