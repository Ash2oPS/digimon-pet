# Digimon Pet

Small desktop virtual pet scaffold inspired by Digimon World 1.

## Setup

Windows:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"
```

## Run

Double-click launcher files:

```text
Windows: Digimon Pet.bat
macOS: Digimon Pet.command
```

These launchers create `.venv` if needed, install the app dependencies, and start the pet in normal overlay mode without `--debug`.

Overlay desktop pet:

```powershell
python -m digimon_pet
```

The app also appears in the Windows task tray or macOS menu bar. Use that menu to show/hide the pet, open the debug panel, or quit.

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

On macOS, use `python3 -m pytest -v`.

## Saves

User saves and debug settings are stored in the OS user data folder:

```text
Windows: %APPDATA%\Digimon Pet\
macOS: ~/Library/Application Support/Digimon Pet/
```

Older project-local saves in `.local/` are copied to the user data folder on first launch if no newer user save exists.

## macOS App Build

Builds must be produced on macOS with the target Python architecture:

```bash
python3 -m pip install -e ".[build]"
pyinstaller packaging/macos/digimon_pet.spec --noconfirm
```

For maximum compatibility, build once with arm64 Python and once with x86_64 Python, then rename the outputs to `Digimon Pet-arm64.app` and `Digimon Pet-x86_64.app`.

The local `.app` is not signed or notarized. Gatekeeper may require opening it manually from Finder or System Settings before first launch.

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
