import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from digimon_pet.app.digimon_manager_window import DigimonManagerWindow
from digimon_pet.domain.digimon_catalog import load_digimon_catalog
from tests.test_digimon_catalog import write_catalog_files


def make_window(tmp_path: Path) -> DigimonManagerWindow:
    app = QApplication.instance() or QApplication([])
    species_path, digivolutions_path = write_catalog_files(tmp_path)
    catalog = load_digimon_catalog(species_path, digivolutions_path)
    return DigimonManagerWindow(
        catalog,
        tmp_path,
        species_path=species_path,
        digivolutions_path=digivolutions_path,
    )


def make_window_with_runtime_sprite(tmp_path: Path) -> DigimonManagerWindow:
    sprite_path = tmp_path / "assets" / "sprite_sources" / "digital_monster_color" / "Koromon.png"
    sprite_path.parent.mkdir(parents=True)
    sprite_path.write_bytes(b"not a real png")
    manifest_path = tmp_path / "data" / "dw1_sprite_manifest.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        json.dumps(
            {
                "entries": {
                    "koromon": {
                        "asset_path": "assets/sprite_sources/digital_monster_color/Koromon.png"
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    app = QApplication.instance() or QApplication([])
    species_path, digivolutions_path = write_catalog_files(tmp_path)
    catalog = load_digimon_catalog(species_path, digivolutions_path)
    return DigimonManagerWindow(
        catalog,
        tmp_path,
        species_path=species_path,
        digivolutions_path=digivolutions_path,
        sprite_manifest_path=manifest_path,
    )


def test_digimon_manager_window_opens_with_catalog(tmp_path):
    window = make_window(tmp_path)

    assert window.windowTitle() == "Digimon Manager"
    assert window._species_table.rowCount() == 3


def test_selecting_species_populates_detail_fields(tmp_path):
    window = make_window(tmp_path)

    window._species_table.selectRow(1)

    assert window._selected_species_id() == "agumon"
    assert window._id_input.text() == "agumon"
    assert window._name_input.text() == "Agumon"
    assert window._stage_input.currentText() == "rookie"


def test_editing_species_fields_updates_catalog_and_dirty_state(tmp_path):
    window = make_window(tmp_path)

    window._species_table.selectRow(1)
    window._name_input.setText("Agumon X")
    window._id_input.setText("agumon_x")
    window._stage_input.setCurrentText("champion")

    row = window._catalog.species_by_id()["agumon_x"]
    assert row["name"] == "Agumon X"
    assert row["stage"] == "champion"
    assert window._dirty is True


def test_sprite_path_preview_handles_existing_and_missing_paths(tmp_path):
    sprite_path = tmp_path / "assets" / "sprites" / "agumon" / "idle.png"
    sprite_path.parent.mkdir(parents=True)
    sprite_path.write_bytes(b"not a png")
    window = make_window(tmp_path)

    window._species_table.selectRow(1)
    window._sprite_inputs["idle"].setText("assets/sprites/agumon/idle.png")

    assert window._sprite_preview.text() == "Invalid image"

    window._sprite_inputs["idle"].setText("assets/sprites/agumon/missing.png")

    assert window._sprite_preview.text() == "Missing sprite"


def test_runtime_manifest_sprite_prevents_missing_status_and_preview(tmp_path):
    window = make_window_with_runtime_sprite(tmp_path)

    window._species_table.selectRow(0)

    assert "Missing sprites" not in window._species_table.item(0, 3).text()
    assert window._sprite_preview.text() == "Invalid image"


def test_save_refuses_validation_errors_and_does_not_write_files(tmp_path):
    window = make_window(tmp_path)
    original = window._species_path.read_text(encoding="utf-8")

    window._species_table.selectRow(1)
    window._id_input.setText("koromon")

    assert window.save_catalog() is False
    assert window._species_path.read_text(encoding="utf-8") == original
    assert "Duplicate Digimon id: koromon" in window._validation_output.toPlainText()


def test_save_writes_valid_species_and_digivolution_json(tmp_path):
    window = make_window(tmp_path)

    window._species_table.selectRow(1)
    window._name_input.setText("Agumon X")

    assert window.save_catalog() is True
    raw_species = json.loads(window._species_path.read_text(encoding="utf-8"))
    raw_digivolutions = json.loads(window._digivolutions_path.read_text(encoding="utf-8"))
    assert raw_species[1]["name"] == "Agumon X"
    assert raw_digivolutions["indexes"]["by_source"]["agumon"] == ["agumon__to__greymon"]


def test_delete_confirmation_receives_impact_summary(tmp_path, monkeypatch):
    window = make_window(tmp_path)
    messages = []

    def fake_question(parent, title, text, buttons, default_button):
        messages.append(text)
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", fake_question)

    window._species_table.selectRow(1)
    window.delete_selected_species()

    assert "Natural as source: agumon__to__greymon" in messages[0]
    assert "Natural as target: koromon__to__agumon" in messages[0]
    assert "Special references: special__to__greymon" in messages[0]
    assert "agumon" not in window._catalog.species_by_id()
