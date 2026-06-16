from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from digimon_pet.domain.lifecycle import EvolutionSchedule, LifecycleEventPreview
from digimon_pet.domain.models import PetState, Species


class DebugPanel(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        schedule_changed: Callable[[EvolutionSchedule], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._labels: dict[str, QLabel] = {}
        self._schedule_inputs: dict[str, QSpinBox] = {}
        self._schedule_changed = schedule_changed
        self._updating_schedule = False
        self.setWindowTitle("Digimon Pet Debug")
        self.setMinimumWidth(320)

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

        for row, key in enumerate([
            "species",
            "stage",
            "age",
            "next",
            "remaining",
            "hunger",
            "fatigue",
            "discipline",
            "mistakes",
            "training",
        ]):
            label = QLabel(f"{key.title()}:")
            label.setObjectName("Muted")
            value = QLabel("-")
            self._labels[key] = value
            grid.addWidget(label, row, 0)
            grid.addWidget(value, row, 1)

        schedule_grid = QGridLayout()
        schedule_grid.setHorizontalSpacing(12)
        schedule_grid.setVerticalSpacing(5)
        root.addLayout(schedule_grid)

        for row, (key, label_text) in enumerate([
            ("baby_seconds", "Baby1"),
            ("baby_2_seconds", "Baby2"),
            ("rookie_seconds", "Rookie"),
            ("champion_seconds", "Champion"),
            ("ultimate_seconds", "Ultimate"),
        ]):
            label = QLabel(f"{label_text}:")
            label.setObjectName("Muted")
            value = QSpinBox()
            value.setRange(1, 24 * 60 * 60)
            value.setSuffix("s")
            value.valueChanged.connect(self._emit_schedule_changed)
            self._schedule_inputs[key] = value
            schedule_grid.addWidget(label, row, 0)
            schedule_grid.addWidget(value, row, 1)

    def set_schedule_values(self, schedule: EvolutionSchedule) -> None:
        self._updating_schedule = True
        try:
            for key, value in schedule.__dict__.items():
                if key in self._schedule_inputs:
                    self._schedule_inputs[key].setValue(int(value))
        finally:
            self._updating_schedule = False
        if self._schedule_changed is not None:
            self._schedule_changed(schedule)

    def refresh(self, state: PetState, species: Species, next_event: LifecycleEventPreview) -> None:
        self._labels["species"].setText(species.name)
        self._labels["stage"].setText(state.stage.value)
        self._labels["age"].setText(f"{state.age_seconds}s")
        self._labels["next"].setText(next_event.label)
        self._labels["remaining"].setText(f"{next_event.remaining_seconds}s")
        self._labels["hunger"].setText(str(state.hunger))
        self._labels["fatigue"].setText(str(state.fatigue))
        self._labels["discipline"].setText(str(state.discipline))
        self._labels["mistakes"].setText(str(state.care_mistakes))
        self._labels["training"].setText(str(state.training_count))

    def _emit_schedule_changed(self) -> None:
        if self._updating_schedule or self._schedule_changed is None:
            return
        self._schedule_changed(
            EvolutionSchedule(
                baby_seconds=self._schedule_inputs["baby_seconds"].value(),
                baby_2_seconds=self._schedule_inputs["baby_2_seconds"].value(),
                rookie_seconds=self._schedule_inputs["rookie_seconds"].value(),
                champion_seconds=self._schedule_inputs["champion_seconds"].value(),
                ultimate_seconds=self._schedule_inputs["ultimate_seconds"].value(),
            )
        )
