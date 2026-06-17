import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QLabel

from digimon_pet.app.collection_dialog import CollectionDialog, CollectionTile, EvolutionNode, EvolutionTreeDialog
from digimon_pet.domain.evolution_tree import build_evolution_links, family_species_ids, graph_species_ids
from digimon_pet.domain.models import GrowthStage, Species


def _species(species_id: str, name: str, stage: GrowthStage) -> Species:
    return Species(id=species_id, name=name, stage=stage)


def _species_map() -> dict[str, Species]:
    return {
        "botamon": _species("botamon", "Botamon", GrowthStage.BABY),
        "koromon": _species("koromon", "Koromon", GrowthStage.BABY_2),
        "agumon": _species("agumon", "Agumon", GrowthStage.ROOKIE),
        "gabumon": _species("gabumon", "Gabumon", GrowthStage.ROOKIE),
        "kunemon": _species("kunemon", "Kunemon", GrowthStage.ROOKIE),
        "greymon": _species("greymon", "Greymon", GrowthStage.CHAMPION),
        "angemon": _species("angemon", "Angemon", GrowthStage.CHAMPION),
        "devimon": _species("devimon", "Devimon", GrowthStage.CHAMPION),
        "numemon": _species("numemon", "Numemon", GrowthStage.CHAMPION),
        "sukamon": _species("sukamon", "Sukamon", GrowthStage.CHAMPION),
        "vademon": _species("vademon", "Vademon", GrowthStage.ULTIMATE),
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
                "target_species_id": "numemon",
                "source_selector": {"stage": "rookie"},
                "trigger": "after 96h on Rookie level without natural evolution",
            },
            {
                "target_species_id": "sukamon",
                "source_selector": {"scope": "any"},
                "trigger": "full Virus Bar",
            },
            {
                "target_species_id": "kunemon",
                "source_selector": {"stage": "in_training"},
                "trigger": "sleep in Kunemon's bed",
            },
            {
                "target_species_id": "vademon",
                "source_selector": {"stage": "champion"},
                "trigger": "praise or scold with evolution counter at least 240h",
            },
            {
                "target_species_id": "devimon",
                "source_selector": {"species_ids": ["angemon"]},
                "trigger": "lose a life with discipline <= 50",
            },
        ],
    }


def _cross_family_digivolutions() -> dict:
    return {
        "natural_evolutions": [
            {
                "source_species_id": "gabumon",
                "target_species_id": "angemon",
                "requirements": {"groups": {"stats": {"brains": 100}}},
            }
        ],
        "special_evolutions": [
            {
                "target_species_id": "numemon",
                "source_selector": {"stage": "rookie"},
                "trigger": "after 96h on Rookie level without natural evolution",
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


def test_broad_special_evolutions_are_hidden_from_non_baby_family_trees():
    links = build_evolution_links(_species_map(), _digivolutions())
    broad_specials = {
        link.target_species_id: link
        for link in links
        if link.target_species_id in {"kunemon", "numemon", "sukamon", "vademon"}
    }

    assert broad_specials["kunemon"].source_species_id is None
    assert broad_specials["numemon"].source_species_id is None
    assert broad_specials["sukamon"].source_species_id is None
    assert broad_specials["vademon"].source_species_id is None

    polluted_links = build_evolution_links(_species_map(), _cross_family_digivolutions())

    assert family_species_ids("agumon", polluted_links) == {"botamon", "koromon", "agumon"}
    assert graph_species_ids("agumon", _species_map(), polluted_links) == {"botamon", "koromon", "agumon"}
    assert graph_species_ids("patamon", _species_map(), links).isdisjoint({"kunemon", "numemon", "sukamon", "vademon"})
    assert graph_species_ids("numemon", _species_map(), links) == {"numemon"}


def test_kunemon_is_visible_in_baby_1_and_baby_2_trees():
    links = build_evolution_links(_species_map(), _digivolutions())

    assert "kunemon" in graph_species_ids("botamon", _species_map(), links)
    assert "kunemon" in graph_species_ids("koromon", _species_map(), links)


def test_family_uses_selected_ancestors_and_descendants_without_sibling_branches():
    species = {
        "poyomon": _species("poyomon", "Poyomon", GrowthStage.BABY),
        "tokomon": _species("tokomon", "Tokomon", GrowthStage.BABY_2),
        "patamon": _species("patamon", "Patamon", GrowthStage.ROOKIE),
        "biyomon": _species("biyomon", "Biyomon", GrowthStage.ROOKIE),
        "angemon": _species("angemon", "Angemon", GrowthStage.CHAMPION),
        "birdramon": _species("birdramon", "Birdramon", GrowthStage.CHAMPION),
    }
    digivolutions = {
        "natural_evolutions": [
            {"source_species_id": "tokomon", "target_species_id": "patamon", "requirements": {}},
            {"source_species_id": "tokomon", "target_species_id": "biyomon", "requirements": {}},
            {"source_species_id": "patamon", "target_species_id": "angemon", "requirements": {}},
            {"source_species_id": "biyomon", "target_species_id": "birdramon", "requirements": {}},
        ],
        "special_evolutions": [],
    }

    links = build_evolution_links(species, digivolutions)

    assert family_species_ids("patamon", links) == {"poyomon", "tokomon", "patamon", "angemon"}


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

    labels = tree.findChildren(QLabel)
    nodes = {node._species.id: node for node in tree.findChildren(EvolutionNode)}

    assert not any("OFF >= 100" in label.text() for label in labels)
    assert "OFF >= 100" in nodes["greymon"].toolTip()


def test_evolution_tree_groups_nodes_by_growth_stage_from_top_to_bottom():
    app = QApplication.instance() or QApplication([])

    tree = EvolutionTreeDialog(
        _species_map(),
        _digivolutions(),
        {"botamon", "koromon", "agumon", "greymon", "numemon", "sukamon"},
        "agumon",
    )

    headers = [
        label.text()
        for label in tree.findChildren(QLabel)
        if label.objectName() == "EvolutionGraphStageHeader"
    ]

    assert headers == ["Baby1", "Baby2", "Rookie", "Champion"]
