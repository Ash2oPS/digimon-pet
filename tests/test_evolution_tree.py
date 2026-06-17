import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QLabel

from digimon_pet.app.collection_dialog import CollectionDialog, CollectionTile, EvolutionTreeDialog
from digimon_pet.domain.evolution_tree import build_evolution_links, family_species_ids
from digimon_pet.domain.models import GrowthStage, Species


def _species(species_id: str, name: str, stage: GrowthStage) -> Species:
    return Species(id=species_id, name=name, stage=stage)


def _species_map() -> dict[str, Species]:
    return {
        "botamon": _species("botamon", "Botamon", GrowthStage.BABY),
        "koromon": _species("koromon", "Koromon", GrowthStage.BABY_2),
        "agumon": _species("agumon", "Agumon", GrowthStage.ROOKIE),
        "greymon": _species("greymon", "Greymon", GrowthStage.CHAMPION),
        "angemon": _species("angemon", "Angemon", GrowthStage.CHAMPION),
        "devimon": _species("devimon", "Devimon", GrowthStage.CHAMPION),
    }


def _digivolutions() -> dict:
    return {
        "natural_evolutions": [
            {
                "source_species_id": "agumon",
                "target_species_id": "greymon",
                "requirements": {
                    "groups": {
                        "stats": {"offense": 100},
                        "weight": {"min": 25, "max": 35},
                        "care_mistakes": {"max": 1},
                    }
                },
            }
        ],
        "special_evolutions": [
            {
                "target_species_id": "devimon",
                "source_selector": {"species_ids": ["angemon"]},
                "trigger": "lose a life with discipline <= 50",
            }
        ],
    }


def test_build_evolution_links_include_baby_natural_and_supported_special_paths():
    links = build_evolution_links(_species_map(), _digivolutions())

    pairs = {(link.source_species_id, link.target_species_id) for link in links}

    assert ("botamon", "koromon") in pairs
    assert ("koromon", "agumon") in pairs
    assert ("agumon", "greymon") in pairs
    assert ("angemon", "devimon") in pairs
    assert family_species_ids("greymon", links) == {"botamon", "koromon", "agumon", "greymon"}


def test_collection_tile_click_opens_tree_only_for_discovered_species():
    app = QApplication.instance() or QApplication([])
    dialog = CollectionDialog(_species_map(), ["agumon"], _digivolutions())
    opened: list[str] = []
    tiles = {tile._species.id: tile for tile in dialog.findChildren(CollectionTile)}
    tiles["agumon"].clicked.connect(opened.append)
    tiles["greymon"].clicked.connect(opened.append)

    for tile in (tiles["agumon"], tiles["greymon"]):
        event = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            QPointF(8, 8),
            QPointF(8, 8),
            QPointF(8, 8),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        tile.mouseReleaseEvent(event)

    assert opened == ["agumon"]


def test_evolution_tree_hides_unknown_species_and_their_conditions():
    app = QApplication.instance() or QApplication([])

    tree = EvolutionTreeDialog(_species_map(), _digivolutions(), {"botamon", "koromon", "agumon"}, "agumon")

    texts = [label.text() for label in tree.findChildren(QLabel)]

    assert "Agumon Evolution Tree" in texts
    assert "???" in texts
    assert not any("OFF >= 100" in text for text in texts)


def test_evolution_tree_shows_conditions_for_discovered_targets():
    app = QApplication.instance() or QApplication([])

    tree = EvolutionTreeDialog(
        _species_map(),
        _digivolutions(),
        {"botamon", "koromon", "agumon", "greymon"},
        "agumon",
    )

    texts = [label.text() for label in tree.findChildren(QLabel)]

    assert any("OFF >= 100" in text for text in texts)
