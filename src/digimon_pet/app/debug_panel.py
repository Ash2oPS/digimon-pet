from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from digimon_pet.domain.models import PetState, Species


class DebugPanel(QWidget):
    def __init__(self, on_action: Callable[[str], None], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._on_action = on_action
        self._labels: dict[str, QLabel] = {}
        self.setWindowTitle("Digimon Pet Debug")
        self.setMinimumWidth(260)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        title = QLabel("Pet Debug")
        title.setObjectName("Title")
        root.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(5)
        root.addLayout(grid)

        for row, key in enumerate(
            ["species", "stage", "age", "hunger", "fatigue", "discipline", "mistakes", "training"]
        ):
            label = QLabel(f"{key.title()}:")
            label.setObjectName("Muted")
            value = QLabel("-")
            self._labels[key] = value
            grid.addWidget(label, row, 0)
            grid.addWidget(value, row, 1)

        for action in ["feed", "train", "sleep", "wake", "clean", "scold"]:
            button = QPushButton(action.title())
            button.clicked.connect(lambda checked=False, name=action: self._on_action(name))
            root.addWidget(button)

    def refresh(self, state: PetState, species: Species) -> None:
        self._labels["species"].setText(species.name)
        self._labels["stage"].setText(state.stage.value)
        self._labels["age"].setText(f"{state.age_seconds}s")
        self._labels["hunger"].setText(str(state.hunger))
        self._labels["fatigue"].setText(str(state.fatigue))
        self._labels["discipline"].setText(str(state.discipline))
        self._labels["mistakes"].setText(str(state.care_mistakes))
        self._labels["training"].setText(str(state.training_count))

