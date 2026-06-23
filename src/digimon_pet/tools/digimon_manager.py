from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from digimon_pet.app.digimon_manager_window import DigimonManagerWindow
from digimon_pet.data import load_fusion_catalog, load_item_catalog
from digimon_pet.domain.digimon_catalog import load_digimon_catalog
from digimon_pet.paths import PROJECT_ROOT


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    species_path = PROJECT_ROOT / "data" / "species.json"
    digivolutions_path = PROJECT_ROOT / "data" / "dw1_digivolutions.json"
    item_path = PROJECT_ROOT / "data" / "items.json"
    fusion_path = PROJECT_ROOT / "data" / "fusions.json"
    catalog = load_digimon_catalog(species_path, digivolutions_path)
    item_catalog = load_item_catalog(item_path)
    fusion_catalog = load_fusion_catalog(fusion_path)
    window = DigimonManagerWindow(
        catalog,
        PROJECT_ROOT,
        species_path=species_path,
        digivolutions_path=digivolutions_path,
        item_catalog=item_catalog,
        item_save_path=item_path,
        fusion_catalog=fusion_catalog,
        fusion_save_path=fusion_path,
    )
    window.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
