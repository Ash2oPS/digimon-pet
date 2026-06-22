import json
from pathlib import Path

from PySide6.QtGui import QColor, QImage

from digimon_pet.data import pendulum_sprite_import
from digimon_pet.data.pendulum_sprite_import import PendulumSheetSource, import_pendulum_color_sprite


def test_import_pendulum_color_sprite_slices_named_row_without_separator_bleed(tmp_path, monkeypatch):
    sheet_path = tmp_path / "remote" / "virus_busters.png"
    sheet_path.parent.mkdir(parents=True)
    _save_test_sheet(sheet_path)
    source = PendulumSheetSource(
        name="Test Virus Busters",
        url=sheet_path.as_uri(),
        row_names=("Othermon", "WereGarurumon"),
        grid_x=10,
        grid_y=8,
        cell_size=16,
        cell_step=17,
        frame_count=12,
        fps=6,
    )
    monkeypatch.setattr(pendulum_sprite_import, "PENDULUM_SHEET_SOURCES", (source,))
    _write_json(
        tmp_path / "data" / "sprite_sources.json",
        [
            {
                "id": "digimon_pendulum_color",
                "name": "Digimon Pendulum COLOR",
                "priority": 1,
                "manifest": "assets/sprite_sources/digimon_pendulum_color/manifest.json",
            }
        ],
    )
    _write_json(tmp_path / "data" / "dw1_roster.json", [])

    result = import_pendulum_color_sprite(
        "weregarurumon",
        "WereGarurumon",
        tmp_path,
        source_config_path=Path("data/sprite_sources.json"),
        roster_path=Path("data/dw1_roster.json"),
        runtime_manifest_path=Path("data/dw1_sprite_manifest.json"),
        report_path=Path("data/dw1_sprite_report.md"),
    )

    assert result is not None
    assert result.frame_count == 12
    image = QImage(str(result.path))
    assert image.width() == 768
    assert image.height() == 64
    assert image.pixelColor(63, 0).alpha() == 0
    assert image.pixelColor(64, 0).alpha() == 0
    manifest = json.loads((tmp_path / "data" / "dw1_sprite_manifest.json").read_text(encoding="utf-8"))
    entry = manifest["entries"]["weregarurumon"]
    assert entry["asset_path"] == "assets/sprite_sources/digimon_pendulum_color/WereGarurumon.png"
    assert entry["metadata"]["frame_count"] == 12


def _save_test_sheet(path):
    image = QImage(240, 48, QImage.Format.Format_ARGB32)
    image.fill(QColor(255, 0, 255))
    y = 8 + 17
    for frame in range(12):
        x = 10 + frame * 17
        for yy in range(16):
            for xx in range(16):
                image.setPixelColor(x + xx, y + yy, QColor(8, 4, 33))
        image.setPixelColor(x + 2, y + 2, QColor(10 + frame, 20, 30))
        image.setPixelColor(x + 3, y + 2, QColor(200, 210, 255))
    image.save(str(path))


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
