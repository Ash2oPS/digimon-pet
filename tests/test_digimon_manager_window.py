import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from digimon_pet.app.digimon_manager_window import DigimonManagerWindow
from digimon_pet.domain.digimon_catalog import load_digimon_catalog
from digimon_pet.domain.items import ItemCatalog, ItemDefinition, ItemType
from tests.test_digimon_catalog import write_catalog_files


def make_window(tmp_path: Path) -> DigimonManagerWindow:
    app = QApplication.instance() or QApplication([])
    species_path, digivolutions_path = write_catalog_files(tmp_path)
    catalog = load_digimon_catalog(species_path, digivolutions_path)
    item_catalog = ItemCatalog(
        items={
            "digimeat": ItemDefinition(
                id="digimeat",
                name="DigiMeat",
                description="Food.",
                type=ItemType.CONSUMABLE,
            )
        },
        pools={"secondary_event": ()},
    )
    return DigimonManagerWindow(
        catalog,
        tmp_path,
        species_path=species_path,
        digivolutions_path=digivolutions_path,
        item_catalog=item_catalog,
        item_save_path=tmp_path / "items.json",
    )


def make_window_with_runtime_sprite(tmp_path: Path) -> DigimonManagerWindow:
    sprite_path = tmp_path / "assets" / "sprite_sources" / "digital_monster_color" / "Koromon.png"
    sprite_path.parent.mkdir(parents=True)
    from PySide6.QtGui import QColor, QImage

    sprite_image = QImage(26, 13, QImage.Format.Format_ARGB32)
    sprite_image.fill(QColor("transparent"))
    sprite_image.setPixelColor(1, 1, QColor("red"))
    sprite_image.setPixelColor(14, 1, QColor("blue"))
    sprite_image.save(str(sprite_path))
    artwork_path = tmp_path / "assets" / "artworks" / "koromon.png"
    artwork_path.parent.mkdir(parents=True)
    artwork_image = QImage(64, 64, QImage.Format.Format_ARGB32)
    artwork_image.fill(QColor("green"))
    artwork_image.save(str(artwork_path))
    manifest_path = tmp_path / "data" / "dw1_sprite_manifest.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        json.dumps(
            {
                "entries": {
                    "koromon": {
                        "asset_path": "assets/sprite_sources/digital_monster_color/Koromon.png",
                        "metadata": {"frame_count": 2, "fps": 8},
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


def test_digimon_manager_has_global_items_tab_with_embedded_item_manager(tmp_path):
    window = make_window(tmp_path)

    tab_labels = [window._main_tabs.tabText(index) for index in range(window._main_tabs.count())]

    assert tab_labels == ["Digimon", "Items"]
    assert window._item_manager_window is not None
    assert window._item_manager_window.isWindow() is False
    assert window._item_manager_window._item_list.count() == 1


def test_species_table_shows_idle_frame_thumbnail_column(tmp_path):
    window = make_window_with_runtime_sprite(tmp_path)

    thumbnail = window._species_table.item(0, 0).data(Qt.ItemDataRole.DecorationRole)

    assert window._species_table.columnCount() == 5
    assert thumbnail is not None
    assert window._species_table.columnWidth(0) >= 44
    assert window._species_table.rowHeight(0) >= 40


def test_species_table_status_surfaces_validation_warnings(tmp_path):
    window = make_window(tmp_path)

    assert "warning" in window._species_table.item(0, 4).text()
    assert "koromon missing sprite file for idle" in window._species_table.item(0, 4).toolTip()


def test_validation_summary_shows_error_and_warning_counts(tmp_path):
    window = make_window(tmp_path)

    assert "0 errors" in window._validation_summary_label.text()
    assert "warnings" in window._validation_summary_label.text()


def test_primary_actions_have_icons_and_tooltips(tmp_path):
    window = make_window(tmp_path)

    for button in (
        window._add_button,
        window._duplicate_button,
        window._delete_button,
        window._validate_button,
        window._save_button,
    ):
        assert not button.icon().isNull()
        assert button.toolTip()


def test_selecting_species_populates_detail_fields(tmp_path):
    window = make_window(tmp_path)

    window._species_table.selectRow(1)

    assert window._selected_species_id() == "agumon"
    assert window._id_input.text() == "agumon"
    assert window._name_input.text() == "Agumon"
    assert window._stage_input.currentText() == "rookie"


def test_right_panel_header_tracks_selected_species(tmp_path):
    window = make_window(tmp_path)

    window._species_table.selectRow(1)

    assert window._selected_title_label.text() == "Agumon"
    assert window._selected_subtitle_label.text() == "agumon · rookie"
    assert "Referenced" in window._selected_status_label.text()


def test_selected_validation_focuses_current_species(tmp_path):
    window = make_window(tmp_path)

    window._species_table.selectRow(1)

    assert "agumon missing sprite file for idle" in window._selected_validation_output.toPlainText()
    assert "koromon missing sprite file for idle" not in window._selected_validation_output.toPlainText()


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

    assert window._runtime_sprite_preview._status_text == "Invalid runtime sprite"

    window._sprite_inputs["idle"].setText("assets/sprites/agumon/missing.png")

    assert window._runtime_sprite_preview._status_text == "No runtime sprite"


def test_runtime_manifest_sprite_prevents_missing_status_and_preview(tmp_path):
    window = make_window_with_runtime_sprite(tmp_path)

    window._species_table.selectRow(0)

    assert "Missing sprites" not in window._species_table.item(0, 4).text()
    assert window._runtime_sprite_preview._pixmap is not None
    assert window._runtime_sprite_preview._frame_count == 2
    assert window._artwork_preview.pixmap() is not None


def test_runtime_sprite_preview_advances_frames(tmp_path):
    window = make_window_with_runtime_sprite(tmp_path)

    window._species_table.selectRow(0)
    assert window._runtime_sprite_preview._frame_index == 0

    window._runtime_sprite_preview._advance_frame()

    assert window._runtime_sprite_preview._frame_index == 1


def test_stage_selector_special_evolution_appears_for_matching_species(tmp_path):
    window = make_window(tmp_path)
    window._catalog.special_evolutions = [
        {
            "id": "special__to__kunemon",
            "type": "special",
            "target_species_id": "agumon",
            "source_selector": {"stage": "in_training"},
            "trigger": "sleep in Kunemon's bed",
        }
    ]
    window._refresh_evolution_tables()

    window._species_table.selectRow(0)

    assert window._selected_species_id() == "koromon"
    assert window._special_table.rowCount() == 1
    assert window._special_table.item(0, 1).text() == "stage: in_training"

    window._species_table.selectRow(1)

    assert window._selected_species_id() == "agumon"
    assert window._special_table.rowCount() == 1
    assert window._special_table.item(0, 0).text() == "agumon"


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
