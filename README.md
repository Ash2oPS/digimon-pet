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

The app also appears in the Windows background task tray. Use the tray icon menu to show/hide the pet, open the debug panel, or quit.

By default, the pet starts near the bottom-right corner of the primary screen. Drag it with the left mouse button to move it manually, including across monitors. Right-click the pet to open care actions and the collection.

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

Offline Digimon World 1 sprite source manifests are configured in `data/sprite_sources.json`.
Put local PNG exports or source manifests under:

```text
assets/sprite_sources/digital_monster_color/
assets/sprite_sources/digimon_pendulum_color/
assets/sprite_sources/xros_loader_toy/
```

Build the generated DW1 sprite manifest and report with:

```powershell
python -m digimon_pet.data.sprite_pipeline
```

The desktop pet checks this manifest on startup. If any roster sprite is missing, it downloads entries declared in `data/sprite_downloads.json`, then rebuilds the manifest from local files.

Download entries use direct file URLs and project-relative targets:

```json
[
  {
    "species_id": "agumon",
    "source_id": "digital_monster_color",
    "url": "https://example.com/agumon.png",
    "path": "assets/sprite_sources/digital_monster_color/agumon.png"
  }
]
```

Source manifests may use per-Digimon frame metadata:

```json
{
  "sprites": [
    {
      "name": "Agumon",
      "path": "agumon.png",
      "frame_width": 24,
      "frame_height": 24,
      "frame_count": 4,
      "fps": 8
    }
  ]
}
```

For action-specific sheets, put an `animations` object with keys such as `idle`, `sleep`, `eat`, or `train`.
