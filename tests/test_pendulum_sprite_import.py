import json
from pathlib import Path

from PySide6.QtGui import QColor, QImage

from digimon_pet.data import pendulum_sprite_import
from digimon_pet.data.pendulum_sprite_import import (
    AnimationSheet,
    PendulumSheetSource,
    SpriteImportOption,
    discover_sprite_import_options,
    import_pendulum_color_sprite,
    import_sprite_option,
    sprite_import_option_preview_image,
)


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


def test_discover_sprite_import_options_includes_wikimon_virtual_pets_without_pendulum(monkeypatch):
    html = """
    <h2><span class="mw-headline" id="Virtual_Pets_2">Virtual Pets</span></h2>
    <table>
      <tr>
        <td><img alt="Terriermon vpet darc.gif" src="/images/d/d5/Terriermon_vpet_darc.gif" /></td>
        <td><img alt="Terriermon vpet_power_euv1.gif" src="/images/e/ee/Terriermon_vpet_power_euv1.gif" /></td>
        <td><img alt="Terriermon vpet pen.gif" src="/images/1/11/Terriermon_vpet_pen.gif" /></td>
      </tr>
      <tr>
        <td><a>D-Ark</a></td>
        <td><a>D-Power</a> (EU/AS, V1)</td>
        <td><a>Digimon Pendulum Ver.20th</a></td>
      </tr>
      <tr>
        <td><img alt="Terriermon vpet vb.png" src="/images/a/a8/Terriermon_vpet_vb.png" /></td>
      </tr>
      <tr>
        <td><a>Vital Bracelet Digital Monster</a></td>
      </tr>
    </table>
    <h2><span class="mw-headline" id="Other">Other</span></h2>
    """

    monkeypatch.setattr(pendulum_sprite_import, "PENDULUM_SHEET_SOURCES", ())
    monkeypatch.setattr(pendulum_sprite_import, "_load_remote_text", lambda url, timeout_seconds: html)

    options = discover_sprite_import_options("terriermon", "Terriermon")

    assert [option.label for option in options] == ["D-Ark", "D-Power (EU/AS, V1)", "Vital Bracelet Digital Monster"]
    assert options[0].image_url == "https://wikimon.net/images/d/d5/Terriermon_vpet_darc.gif"
    assert options[0].provider_id == "wikimon_virtual_pets"


def test_sprite_import_option_preview_image_returns_first_pendulum_frame(tmp_path, monkeypatch):
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

    option = discover_sprite_import_options("weregarurumon", "WereGarurumon")[0]
    preview = sprite_import_option_preview_image(option)

    assert preview.width() == 64
    assert preview.height() == 64
    assert preview.pixelColor(8, 8) == QColor(10, 20, 30)
    assert preview.pixelColor(63, 0).alpha() == 0


def test_wikimon_import_becomes_preferred_sprite_when_lower_priority_source_exists(tmp_path, monkeypatch):
    _write_json(
        tmp_path / "data" / "sprite_sources.json",
        [
            {
                "id": "digimon_pendulum_color",
                "name": "Digimon Pendulum COLOR",
                "priority": 1,
                "manifest": "assets/sprite_sources/digimon_pendulum_color/manifest.json",
            },
            {
                "id": "wikimon_virtual_pets",
                "name": "Wikimon Virtual Pets",
                "priority": 4,
                "manifest": "assets/sprite_sources/wikimon_virtual_pets/manifest.json",
            },
        ],
    )
    _write_json(tmp_path / "data" / "dw1_roster.json", [{"id": "ninjamon", "name": "Ninjamon"}])
    _write_json(
        tmp_path / "assets" / "sprite_sources" / "digimon_pendulum_color" / "manifest.json",
        {"sprites": [{"name": "Ninjamon", "path": "assets/sprite_sources/digimon_pendulum_color/Ignamon.png"}]},
    )
    imported_image = QImage(16, 16, QImage.Format.Format_ARGB32)
    imported_image.fill(QColor("red"))
    monkeypatch.setattr(
        pendulum_sprite_import,
        "_load_remote_animation_sheet",
        lambda url, fps=6, timeout_seconds=10, **kwargs: AnimationSheet(imported_image, 1, fps, 16, 16),
    )
    option = SpriteImportOption(
        provider_id="wikimon_virtual_pets",
        label="D-3 -25th COLOR EVOLUTION-",
        detail="Igamon vpet d3 color.png",
        species_id="ninjamon",
        name="Ninjamon",
        source_url="https://wikimon.net/Ninjamon",
        image_url="https://wikimon.net/images/igamon.png",
    )

    result = import_sprite_option(
        option,
        tmp_path,
        source_config_path=Path("data/sprite_sources.json"),
        roster_path=Path("data/dw1_roster.json"),
        runtime_manifest_path=Path("data/dw1_sprite_manifest.json"),
        report_path=Path("data/dw1_sprite_report.md"),
    )

    assert result is not None
    roster = json.loads((tmp_path / "data" / "dw1_roster.json").read_text(encoding="utf-8"))
    assert roster == [
        {
            "id": "ninjamon",
            "name": "Ninjamon",
            "preferred_source_id": "wikimon_virtual_pets",
        }
    ]
    manifest = json.loads((tmp_path / "data" / "dw1_sprite_manifest.json").read_text(encoding="utf-8"))
    entry = manifest["entries"]["ninjamon"]
    assert entry["source_id"] == "wikimon_virtual_pets"
    assert entry["asset_path"] == "assets/sprite_sources/wikimon_virtual_pets/ninjamon_d_3_25th_color_evolution.png"


def test_download_manifest_import_adds_digital_monster_color_vertical_sheet(tmp_path, monkeypatch):
    monkeypatch.setattr(pendulum_sprite_import, "PENDULUM_SHEET_SOURCES", ())
    monkeypatch.setattr(pendulum_sprite_import, "_discover_wikimon_virtual_pet_options", lambda *args, **kwargs: [])
    _write_json(
        tmp_path / "data" / "sprite_sources.json",
        [
            {
                "id": "digital_monster_color",
                "name": "Digital Monster COLOR",
                "priority": 1,
                "manifest": "assets/sprite_sources/digital_monster_color/manifest.json",
            }
        ],
    )
    _write_json(tmp_path / "data" / "dw1_roster.json", [])
    remote_path = tmp_path / "remote" / "Testmon.png"
    _save_vertical_sheet(remote_path)
    _write_json(
        tmp_path / "data" / "sprite_downloads.json",
        [
            {
                "species_id": "testmon",
                "name": "Testmon",
                "source_id": "digital_monster_color",
                "url": remote_path.as_uri(),
                "path": "assets/sprite_sources/digital_monster_color/Testmon.png",
                "frame_count": 3,
                "fps": 8,
            }
        ],
    )

    options = discover_sprite_import_options(
        "testmon",
        "Testmon",
        tmp_path,
        download_manifest_path=Path("data/sprite_downloads.json"),
        source_config_path=Path("data/sprite_sources.json"),
    )
    result = import_sprite_option(
        options[0],
        tmp_path,
        source_config_path=Path("data/sprite_sources.json"),
        roster_path=Path("data/dw1_roster.json"),
        runtime_manifest_path=Path("data/dw1_sprite_manifest.json"),
        report_path=Path("data/dw1_sprite_report.md"),
    )

    assert options[0].label == "Digital Monster COLOR (3 frames)"
    assert result is not None
    assert result.frame_count == 3
    output = QImage(str(result.path))
    assert output.width() == 48
    assert output.height() == 16
    assert output.pixelColor(0, 0) == QColor("red")
    assert output.pixelColor(16, 0) == QColor("green")
    assert output.pixelColor(32, 0) == QColor("blue")
    manifest = json.loads((tmp_path / "assets" / "sprite_sources" / "digital_monster_color" / "manifest.json").read_text())
    assert manifest["sprites"][0]["frame_width"] == 16
    assert manifest["sprites"][0]["frame_height"] == 16
    runtime = json.loads((tmp_path / "data" / "dw1_sprite_manifest.json").read_text(encoding="utf-8"))
    assert runtime["entries"]["testmon"]["source_id"] == "digital_monster_color"


def test_wikimon_white_background_keeps_internal_white_pixels():
    image = QImage(5, 5, QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    for y in range(1, 4):
        for x in range(1, 4):
            image.setPixelColor(x, y, QColor("black"))
    image.setPixelColor(2, 2, QColor("white"))

    result = pendulum_sprite_import._transparent_white_background(image)

    assert result.pixelColor(0, 0).alpha() == 0
    assert result.pixelColor(4, 4).alpha() == 0
    assert result.pixelColor(2, 2) == QColor("white")


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


def _save_vertical_sheet(path):
    path.parent.mkdir(parents=True)
    image = QImage(16, 48, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))
    for index, color in enumerate((QColor("red"), QColor("green"), QColor("blue"))):
        for y in range(16):
            for x in range(16):
                image.setPixelColor(x, index * 16 + y, color)
    image.save(str(path))


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
