import json
import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import QApplication, QMessageBox, QScrollArea

from digimon_pet.app.digimon_manager_window import DigimonManagerWindow, RuntimeSpritePreview
from digimon_pet.data.pendulum_sprite_import import SpriteImportOption
from digimon_pet.domain.digimon_catalog import load_digimon_catalog
from digimon_pet.domain.fusions import FusionCatalog, FusionRecipe
from digimon_pet.domain.items import (
    EvolutionItemEffect,
    ItemCatalog,
    ItemDefinition,
    ItemPoolEntry,
    ItemType,
    item_catalog_to_dict,
)
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
        fusion_catalog=FusionCatalog(),
        fusion_save_path=tmp_path / "fusions.json",
    )


def test_runtime_sprite_preview_slices_multi_row_google_drive_sheet(tmp_path):
    app = QApplication.instance() or QApplication([])
    path = tmp_path / "punimon.png"
    pixmap = QPixmap(48, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.save(str(path))

    preview = RuntimeSpritePreview()
    preview.set_sprite(path, frame_count=12, fps=6, frame_width=16, frame_height=16)
    preview._frame_index = 7

    assert preview._source_rect() == QRect(16, 32, 16, 16)


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

    assert tab_labels == ["Digimon", "Items", "Fusions"]
    assert window._item_manager_window is not None
    assert window._item_manager_window.isWindow() is False
    assert window._item_manager_window._item_list.count() == 1


def test_digimon_manager_has_global_fusions_tab(tmp_path):
    window = make_window(tmp_path)

    assert window._fusion_manager_window is not None
    assert window._fusion_manager_window.isWindow() is False
    assert window._fusion_manager_window._recipe_list.count() == 0


def test_fusion_manager_adds_edits_deletes_and_saves_recipe(tmp_path):
    window = make_window(tmp_path)
    manager = window._fusion_manager_window
    assert manager is not None

    manager.add_recipe()
    manager._source_a_input.setCurrentText("koromon")
    manager._source_b_input.setCurrentText("agumon")
    manager._target_input.setCurrentText("greymon")
    manager._notes_input.setPlainText("Jogress test")
    manager.apply_selected_recipe()

    assert manager._recipe_list.count() == 1
    assert window.save_catalog() is True
    raw = json.loads((tmp_path / "fusions.json").read_text(encoding="utf-8"))
    assert raw == {
        "fusions": [
            {
                "source_species_ids": ["koromon", "agumon"],
                "target_species_id": "greymon",
                "notes": "Jogress test",
            }
        ]
    }

    manager.delete_selected_recipe()
    assert manager._recipe_list.count() == 0


def test_fusion_manager_blocks_symmetric_duplicate_save(tmp_path):
    window = make_window(tmp_path)
    manager = window._fusion_manager_window
    assert manager is not None
    manager._catalog.recipes = (
        FusionRecipe(("koromon", "agumon"), "greymon"),
        FusionRecipe(("agumon", "koromon"), "greymon"),
    )

    assert window.save_catalog() is False
    assert "Duplicate fusion recipe" in manager._validation_output.toPlainText()


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


def test_validation_loads_existing_items_when_item_catalog_not_provided(tmp_path):
    app = QApplication.instance() or QApplication([])
    species_path, digivolutions_path = write_catalog_files(tmp_path)
    catalog = load_digimon_catalog(species_path, digivolutions_path)
    catalog.species_rows.extend(
        [
            {"id": "angemon", "name": "Angemon", "stage": "champion", "sprite_slots": {}},
            {"id": "devimon", "name": "Devimon", "stage": "champion", "sprite_slots": {}},
        ]
    )
    item_path = tmp_path / "items.json"
    item_catalog = ItemCatalog(
        items={
            "black_wings": ItemDefinition(
                id="black_wings",
                name="Black Wings",
                description="Makes Angemon digivolve into Devimon.",
                type=ItemType.EVOLUTION,
                evolution=EvolutionItemEffect(
                    target_species_id="devimon",
                    required_species_ids=("angemon",),
                ),
            )
        },
        pools={},
    )
    item_path.write_text(json.dumps(item_catalog_to_dict(item_catalog)), encoding="utf-8")

    window = DigimonManagerWindow(
        catalog,
        tmp_path,
        species_path=species_path,
        digivolutions_path=digivolutions_path,
        item_save_path=item_path,
    )

    output = window._validation_output.toPlainText()
    assert "devimon has no incoming natural evolution" not in output
    assert "angemon has no outgoing natural evolution" not in output


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


def test_visual_import_buttons_have_icons_and_status(tmp_path):
    window = make_window(tmp_path)

    assert window._import_sprite_button.text() == "Fetch sprite"
    assert not window._import_sprite_button.icon().isNull()
    assert window._import_sprite_button.toolTip()
    assert "Google Drive" in window._import_sprite_button.toolTip()
    assert window._import_artwork_button.text() == "Fetch artwork"
    assert not window._import_artwork_button.icon().isNull()
    assert window._import_artwork_button.toolTip()
    assert window._visual_import_status.text()


def test_fetch_sprite_uses_selected_digimon_name_and_refreshes_runtime(tmp_path, monkeypatch):
    window = make_window(tmp_path)
    calls = []
    option = SpriteImportOption(
        provider_id="wikimon_virtual_pets",
        label="D-Ark",
        detail="Terriermon vpet darc.gif",
        species_id="agumon",
        name="Agumon",
        source_url="https://wikimon.net/Agumon",
        image_url="https://wikimon.net/images/agumon.gif",
        source_name="Wikimon Virtual Pets",
    )

    def fake_discover(species_id, name, project_root, stage=""):
        calls.append(("discover", species_id, name, project_root, stage))
        return [option]

    def fake_import(selected_option, project_root):
        calls.append(("import", selected_option, project_root))
        return SimpleNamespace(source_name="Test Pendulum", frame_count=12)

    monkeypatch.setattr("digimon_pet.app.digimon_manager_window.discover_sprite_import_options", fake_discover)
    monkeypatch.setattr("digimon_pet.app.digimon_manager_window.import_sprite_option", fake_import)
    monkeypatch.setattr(window, "_choose_sprite_import_option", lambda options: calls.append(("choose", options)) or options[0])
    monkeypatch.setattr(window, "_load_runtime_sprite_entries", lambda: {"agumon": {"asset_path": "sprite.png"}})
    window._species_table.selectRow(1)

    window.import_selected_sprite()

    assert calls == [
        ("discover", "agumon", "Agumon", tmp_path, "rookie"),
        ("choose", [option]),
        ("import", option, tmp_path),
    ]
    assert "Sprite imported" in window._visual_import_status.text()
    assert window._runtime_sprite_entries == {"agumon": {"asset_path": "sprite.png"}}


def test_fetch_sprite_searches_aliases_after_selected_digimon_name(tmp_path, monkeypatch):
    window = make_window(tmp_path)
    window._species_table.selectRow(1)
    window._aliases_input.setText("Agumon X, Agu")
    calls = []
    alias_option = SpriteImportOption(
        provider_id="google_drive_sprites",
        label="Google Drive Sprites - Child",
        detail="Agumon_X.png",
        species_id="agumon",
        name="Agumon X",
        source_url="https://drive.google.com/file/d/file1/view",
        image_url="https://drive.google.com/uc?export=download&id=file1",
        source_name="Google Drive Sprites",
    )

    def fake_discover(species_id, name, project_root, stage=""):
        calls.append(("discover", species_id, name, stage))
        return [alias_option] if name == "Agumon X" else []

    def fake_import(selected_option, project_root):
        calls.append(("import", selected_option.name))
        return SimpleNamespace(source_name="Google Drive Sprites - Child", frame_count=12)

    monkeypatch.setattr("digimon_pet.app.digimon_manager_window.discover_sprite_import_options", fake_discover)
    monkeypatch.setattr("digimon_pet.app.digimon_manager_window.import_sprite_option", fake_import)
    monkeypatch.setattr(window, "_choose_sprite_import_option", lambda options: calls.append(("choose", [option.name for option in options])) or options[0])
    monkeypatch.setattr(window, "_load_runtime_sprite_entries", lambda: {"agumon": {"asset_path": "sprite.png"}})

    window.import_selected_sprite()

    assert calls == [
        ("discover", "agumon", "Agumon", "rookie"),
        ("discover", "agumon", "Agumon X", "rookie"),
        ("discover", "agumon", "Agu", "rookie"),
        ("choose", ["Agumon X"]),
        ("import", "Agumon X"),
    ]


def test_sprite_source_list_item_shows_preview_icon(tmp_path, monkeypatch):
    window = make_window(tmp_path)
    option = SpriteImportOption(
        provider_id="wikimon_virtual_pets",
        label="D-Ark",
        detail="Terriermon vpet darc.gif",
        species_id="terriermon",
        name="Terriermon",
        source_url="https://wikimon.net/Terriermon",
        image_url="https://wikimon.net/images/terriermon.gif",
    )
    preview = QImage(16, 16, QImage.Format_ARGB32)
    preview.fill(QColor("red"))
    monkeypatch.setattr("digimon_pet.app.digimon_manager_window.sprite_import_option_preview_image", lambda selected: preview)

    item = window._sprite_source_list_item(option)

    assert not item.icon().isNull()
    assert item.sizeHint().height() >= 60
    assert item.data(Qt.ItemDataRole.UserRole) == option


def test_fetch_artwork_uses_selected_digimon_name_and_refreshes_preview(tmp_path, monkeypatch):
    window = make_window(tmp_path)
    calls = []
    refreshed = []

    def fake_import(species_id, name, project_root):
        calls.append((species_id, name, project_root))
        return tmp_path / "assets" / "artworks" / f"{species_id}.png"

    monkeypatch.setattr("digimon_pet.app.digimon_manager_window.discover_and_download_artwork_for_species", fake_import)
    monkeypatch.setattr(window, "_refresh_artwork_preview", lambda: refreshed.append(True))
    window._species_table.selectRow(1)
    refreshed.clear()

    window.import_selected_artwork()

    assert calls == [("agumon", "Agumon", tmp_path)]
    assert refreshed == [True]
    assert "Artwork imported" in window._visual_import_status.text()


def test_fetch_artwork_searches_aliases_after_selected_digimon_name(tmp_path, monkeypatch):
    window = make_window(tmp_path)
    calls = []
    refreshed = []

    def fake_import(species_id, name, project_root):
        calls.append((species_id, name, project_root))
        return tmp_path / "assets" / "artworks" / f"{species_id}.png" if name == "Agumon X" else None

    monkeypatch.setattr("digimon_pet.app.digimon_manager_window.discover_and_download_artwork_for_species", fake_import)
    monkeypatch.setattr(window, "_refresh_artwork_preview", lambda: refreshed.append(True))
    window._species_table.selectRow(1)
    window._aliases_input.setText("Agumon X")
    refreshed.clear()

    window.import_selected_artwork()

    assert calls == [
        ("agumon", "Agumon", tmp_path),
        ("agumon", "Agumon X", tmp_path),
    ]
    assert refreshed == [True]


def test_selecting_species_populates_detail_fields(tmp_path):
    window = make_window(tmp_path)

    window._species_table.selectRow(1)

    assert window._selected_species_id() == "agumon"
    assert window._id_input.text() == "agumon"
    assert window._name_input.text() == "Agumon"
    assert window._aliases_input.text() == ""
    assert window._stage_input.currentText() == "rookie"


def test_right_panel_header_tracks_selected_species(tmp_path):
    window = make_window(tmp_path)

    window._species_table.selectRow(1)

    assert window._selected_title_label.text() == "Agumon"
    assert window._selected_subtitle_label.text() == "agumon - rookie"
    assert "Referenced" in window._selected_status_label.text()


def test_selected_validation_focuses_current_species(tmp_path):
    window = make_window(tmp_path)

    window._species_table.selectRow(1)

    assert "agumon missing sprite file for idle" in window._selected_validation_output.toPlainText()
    assert "koromon missing sprite file for idle" not in window._selected_validation_output.toPlainText()


def test_validation_lives_in_right_panel_tab_to_preserve_editor_space(tmp_path):
    window = make_window(tmp_path)

    tab_labels = [window._tabs.tabText(index) for index in range(window._tabs.count())]

    assert tab_labels == ["Sprites", "Evolutions", "Validation"]
    assert 280 <= window._tabs.minimumHeight() <= 320


def test_combo_boxes_ignore_mouse_wheel_changes(tmp_path):
    window = make_window(tmp_path)
    window._stage_input.setCurrentIndex(0)

    class FakeWheelEvent:
        ignored = False

        def ignore(self):
            self.ignored = True

    event = FakeWheelEvent()
    window._stage_input.wheelEvent(event)

    assert window._stage_input.currentIndex() == 0
    assert event.ignored is True


def test_evolution_editor_uses_compact_tables_to_keep_controls_visible(tmp_path):
    window = make_window(tmp_path)

    assert window._natural_table.maximumHeight() <= 108
    assert window._special_table.maximumHeight() <= 108
    assert window._natural_add_button.text() == "Add"
    assert window._special_trigger_input.placeholderText() == "ex: full Virus Bar"


def test_splitter_protects_species_table_width(tmp_path):
    window = make_window(tmp_path)
    window.resize(1280, 760)
    window.show()
    QApplication.processEvents()

    left_width, right_width = window._content_splitter.sizes()

    assert window._species_panel.minimumWidth() >= 520
    assert left_width >= 520
    assert right_width >= 560
    assert left_width / (left_width + right_width) >= 0.42


def test_right_editor_uses_scroll_area_for_short_windows(tmp_path):
    window = make_window(tmp_path)

    assert isinstance(window._right_scroll_area, QScrollArea)
    assert window._right_scroll_area.widgetResizable() is True
    assert window._right_editor_content.minimumWidth() >= 560

def test_editing_species_fields_updates_catalog_and_dirty_state(tmp_path):
    window = make_window(tmp_path)

    window._species_table.selectRow(1)
    window._name_input.setText("Agumon X")
    window._aliases_input.setText("Agu, Agumon 2006")
    window._id_input.setText("agumon_x")
    window._stage_input.setCurrentText("champion")

    row = window._catalog.species_by_id()["agumon_x"]
    assert row["name"] == "Agumon X"
    assert row["aliases"] == ["Agu", "Agumon 2006"]
    assert row["stage"] == "champion"
    assert window._dirty is True


def test_editing_species_id_can_be_temporarily_blank_without_losing_editor_state(tmp_path):
    window = make_window(tmp_path)

    window.add_species()
    window._name_input.setText("Gaomon")
    window._id_input.clear()
    window._id_input.setText("gaomon")

    row = window._catalog.species_by_id()["gaomon"]
    assert row["name"] == "Gaomon"
    assert window._name_input.text() == "Gaomon"
    assert window._selected_species_id() == "gaomon"


def test_save_failure_updates_status_when_validation_blocks_write(tmp_path):
    window = make_window(tmp_path)

    window.add_species()
    window._id_input.clear()

    assert window.save_catalog() is False
    assert "Save failed" in window._status_label.text()


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


def test_evolution_species_selectors_are_searchable_and_show_sprite_icons(tmp_path):
    window = make_window_with_runtime_sprite(tmp_path)

    koromon_index = window._natural_source_input.findData("koromon")

    assert window._natural_source_input.isEditable() is True
    assert window._natural_source_input.lineEdit().placeholderText() == "Search Digimon"
    assert window._natural_source_input.completer().filterMode() == Qt.MatchFlag.MatchContains
    assert koromon_index >= 0
    assert window._natural_source_input.itemIcon(koromon_index).isNull() is False
    assert window._natural_target_input.isEditable() is True
    assert window._special_target_input.isEditable() is True


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
    assert window._special_table.item(0, 0).text() == "Agumon (agumon)"


def test_evolution_editor_defaults_natural_source_to_selected_species(tmp_path):
    window = make_window(tmp_path)

    window._species_table.selectRow(1)

    assert window._natural_source_input.currentData() == "agumon"


def test_add_natural_evolution_blocks_duplicate_and_selects_created_row(tmp_path):
    window = make_window(tmp_path)

    window._species_table.selectRow(0)
    window._set_combo_data(window._natural_source_input, "koromon")
    window._set_combo_data(window._natural_target_input, "agumon")

    before_count = len(window._catalog.natural_evolutions)
    assert window._natural_add_button.isEnabled() is False
    window.add_natural_evolution()
    assert len(window._catalog.natural_evolutions) == before_count

    window._set_combo_data(window._natural_target_input, "greymon")
    assert window._natural_add_button.isEnabled() is True
    window.add_natural_evolution()

    assert window._catalog.natural_evolutions[-1]["id"] == "koromon__to__greymon"
    assert window._natural_table.selectedItems()[0].data(Qt.ItemDataRole.UserRole) == len(window._catalog.natural_evolutions) - 1


def test_add_natural_evolution_uses_entered_conditions(tmp_path):
    window = make_window(tmp_path)

    window._species_table.selectRow(0)
    window._set_combo_data(window._natural_source_input, "koromon")
    window._set_combo_data(window._natural_target_input, "greymon")
    window._natural_stat_inputs["hp"].setText("250")
    window._natural_stat_inputs["offense"].setText("50")
    window._natural_weight_min_input.setText("10")
    window._natural_weight_max_input.setText("20")
    window._natural_care_max_input.setText("1")

    window.add_natural_evolution()

    assert window._catalog.natural_evolutions[-1]["requirements"] == {
        "mode": "stats_only",
        "groups": {
            "stats": {"hp": 250, "offense": 50},
            "weight": {"min": 10, "max": 20},
            "care_mistakes": {"max": 1},
        },
    }
    assert "HP 250" in window._natural_table.selectedItems()[3].text()


def test_selected_natural_evolution_conditions_can_be_edited(tmp_path):
    window = make_window(tmp_path)

    window._species_table.selectRow(1)
    window._natural_table.selectRow(1)

    assert window._natural_stat_inputs["offense"].text().strip() == "100"

    window._natural_stat_inputs["offense"].setText("350")
    window._natural_weight_min_input.setText("25")
    window._natural_weight_max_input.setText("35")
    window._natural_care_max_input.setText("0")
    window.save_selected_natural_conditions()

    row = window._catalog.natural_evolutions[1]
    assert row["requirements"]["groups"]["stats"] == {"offense": 350}
    assert row["requirements"]["groups"]["weight"] == {"min": 25, "max": 35}
    assert row["requirements"]["groups"]["care_mistakes"] == {"max": 0}
    assert "weight 25-35" in window._natural_table.selectedItems()[3].text()


def test_add_special_evolution_requires_trigger_and_blocks_duplicate(tmp_path):
    window = make_window(tmp_path)

    window._species_table.selectRow(1)
    window._set_combo_data(window._special_target_input, "greymon")
    window._special_selector_input.setCurrentIndex(window._special_selector_input.findData("selected"))

    before_count = len(window._catalog.special_evolutions)
    assert window._special_add_button.isEnabled() is False
    window.add_special_evolution()
    assert len(window._catalog.special_evolutions) == before_count

    window._special_trigger_input.setText("new event")
    assert window._special_add_button.isEnabled() is True
    window.add_special_evolution()

    assert window._catalog.special_evolutions[-1]["source_selector"] == {"species_ids": ["agumon"]}
    assert window._catalog.special_evolutions[-1]["trigger"] == "new event"
    assert window._special_table.selectedItems()[0].data(Qt.ItemDataRole.UserRole) == len(window._catalog.special_evolutions) - 1

    before_duplicate = len(window._catalog.special_evolutions)
    assert window._special_add_button.isEnabled() is False
    window.add_special_evolution()
    assert len(window._catalog.special_evolutions) == before_duplicate


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


def test_save_reports_file_write_errors(tmp_path, monkeypatch):
    window = make_window(tmp_path)
    path_type = type(window._digivolutions_path)
    original_write_text = path_type.write_text

    def raise_for_digivolutions(path, *args, **kwargs):
        if path == window._digivolutions_path:
            raise OSError(22, "Invalid argument", str(path))
        return original_write_text(path, *args, **kwargs)

    monkeypatch.setattr(path_type, "write_text", raise_for_digivolutions)

    assert window.save_catalog() is False
    assert "Save failed:" in window._status_label.text()
    assert str(window._digivolutions_path) in window._status_label.text()


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


def test_deleting_species_removes_referencing_fusion_recipes(tmp_path, monkeypatch):
    window = make_window(tmp_path)
    manager = window._fusion_manager_window
    assert manager is not None
    manager._catalog.recipes = (
        FusionRecipe(("agumon", "koromon"), "greymon"),
        FusionRecipe(("koromon", "greymon"), "agumon"),
    )
    manager.refresh()

    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)

    window._species_table.selectRow(1)
    window.delete_selected_species()

    assert manager._catalog.recipes == ()
    assert manager._recipe_list.count() == 0
    assert window.save_catalog() is True
    assert json.loads((tmp_path / "fusions.json").read_text(encoding="utf-8")) == {"fusions": []}


def test_deleting_species_removes_referencing_evolution_items_and_pool_entries(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    species_path, digivolutions_path = write_catalog_files(tmp_path)
    catalog = load_digimon_catalog(species_path, digivolutions_path)
    item_catalog = ItemCatalog(
        items={
            "grey_claws": ItemDefinition(
                id="grey_claws",
                name="Grey Claws",
                description="Makes Agumon digivolve into Greymon.",
                type=ItemType.EVOLUTION,
                evolution=EvolutionItemEffect(
                    target_species_id="greymon",
                    required_species_ids=("agumon",),
                ),
            ),
            "digimeat": ItemDefinition(
                id="digimeat",
                name="DigiMeat",
                description="Food.",
                type=ItemType.CONSUMABLE,
            ),
        },
        pools={
            "secondary_event": (
                ItemPoolEntry(item_id="grey_claws", weight=1),
                ItemPoolEntry(item_id="digimeat", weight=4),
            )
        },
    )
    window = DigimonManagerWindow(
        catalog,
        tmp_path,
        species_path=species_path,
        digivolutions_path=digivolutions_path,
        item_catalog=item_catalog,
        item_save_path=tmp_path / "items.json",
        fusion_catalog=FusionCatalog(),
        fusion_save_path=tmp_path / "fusions.json",
    )

    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)

    window._species_table.selectRow(1)
    window.delete_selected_species()

    assert "grey_claws" not in item_catalog.items
    assert "digimeat" in item_catalog.items
    assert [entry.item_id for entry in item_catalog.pools["secondary_event"]] == ["digimeat"]
    assert window.save_catalog() is True
