import json

from digimon_pet.data.sprite_pipeline import (
    DEFAULT_ALIAS_MAP,
    build_sprite_manifest,
    load_roster,
)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_resolution_uses_source_priority_and_reports_conflicts(tmp_path):
    root = tmp_path
    roster_path = root / "data" / "roster.json"
    config_path = root / "data" / "sources.json"
    output_path = root / "data" / "manifest.json"
    report_path = root / "data" / "report.md"

    _write_json(
        roster_path,
        [
            {"id": "agumon", "name": "Agumon"},
            {"id": "penguinmon", "name": "Penguinmon"},
        ],
    )
    _write_json(
        config_path,
        [
            {
                "id": "digital_monster_color",
                "name": "Digital Monster COLOR",
                "priority": 1,
                "manifest": "assets/dmc/manifest.json",
            },
            {
                "id": "digimon_pendulum_color",
                "name": "Digimon Pendulum COLOR",
                "priority": 2,
                "manifest": "assets/pendulum/manifest.json",
            },
            {
                "id": "xros_loader_toy",
                "name": "Digimon Xros Loader Toy",
                "priority": 3,
                "manifest": "assets/xros/manifest.json",
            },
        ],
    )
    _write_json(root / "assets" / "dmc" / "manifest.json", [{"name": "Agumon", "path": "agumon.png"}])
    _write_json(
        root / "assets" / "pendulum" / "manifest.json",
        [{"name": "Agumon", "path": "agumon_alt.png"}],
    )
    _write_json(root / "assets" / "xros" / "manifest.json", [{"name": "Penmon", "path": "penmon.png"}])

    result = build_sprite_manifest(root, roster_path, config_path, output_path, report_path)

    assert result["entries"]["agumon"]["source_id"] == "digital_monster_color"
    assert result["entries"]["penguinmon"]["source_id"] == "xros_loader_toy"
    assert result["entries"]["penguinmon"]["matched_name"] == "Penmon"
    assert result["entries"]["penguinmon"]["aliases_used"] == ["Penmon"]
    assert result["missing"] == []
    assert result["conflicts"] == [
        {
            "species_id": "agumon",
            "name": "Agumon",
            "chosen_source_id": "digital_monster_color",
            "available_source_ids": ["digital_monster_color", "digimon_pendulum_color"],
        }
    ]
    assert output_path.exists()
    report = report_path.read_text(encoding="utf-8")
    assert "Digital Monster COLOR" in report
    assert "Digimon Xros Loader Toy" in report


def test_load_roster_excludes_japanese_promos_when_flagged(tmp_path):
    roster_path = tmp_path / "roster.json"
    _write_json(
        roster_path,
        [
            {"id": "agumon", "name": "Agumon"},
            {"id": "panjyamon", "name": "Panjyamon", "promo_japan": True},
            {"id": "gigadramon", "name": "Gigadramon", "promo_japan": True},
            {"id": "metaletemon", "name": "MetalEtemon", "promo_japan": True},
        ],
    )

    roster = load_roster(roster_path, include_japanese_promos=False)

    assert [entry.id for entry in roster] == ["agumon"]


def test_missing_species_are_reported(tmp_path):
    root = tmp_path
    roster_path = root / "data" / "roster.json"
    config_path = root / "data" / "sources.json"
    output_path = root / "data" / "manifest.json"
    report_path = root / "data" / "report.md"

    _write_json(roster_path, [{"id": "piximon", "name": "Piximon"}])
    _write_json(
        config_path,
        [{"id": "digital_monster_color", "name": "Digital Monster COLOR", "priority": 1, "root": "assets/dmc"}],
    )

    result = build_sprite_manifest(root, roster_path, config_path, output_path, report_path)

    assert result["entries"] == {}
    assert result["missing"] == [{"species_id": "piximon", "name": "Piximon"}]
    assert "Piximon" in report_path.read_text(encoding="utf-8")


def test_alias_map_keeps_distinct_forms_separate():
    assert "WaruMonzaemon" not in DEFAULT_ALIAS_MAP.get("Monzaemon", [])
