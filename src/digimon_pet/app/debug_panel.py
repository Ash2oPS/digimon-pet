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
        time_scale_changed: Callable[[int], None] | None = None,
        stat_changed: Callable[[str, int], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._labels: dict[str, QLabel] = {}
        self._schedule_inputs: dict[str, QSpinBox] = {}
        self._stat_inputs: dict[str, QSpinBox] = {}
        self._schedule_changed = schedule_changed
        self._time_scale_changed = time_scale_changed
        self._stat_changed = stat_changed
        self._updating_schedule = False
        self._updating_stats = False
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
            "happiness",
            "mistakes",
            "training",
            "weight",
            "hp",
            "mp",
            "offense",
            "defense",
            "speed",
            "brains",
            "battles",
            "techniques",
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

        time_scale_label = QLabel("Time Scale:")
        time_scale_label.setObjectName("Muted")
        self._time_scale_input = QSpinBox()
        self._time_scale_input.setRange(1, 3600)
        self._time_scale_input.setSuffix("x")
        self._time_scale_input.setValue(1)
        self._time_scale_input.valueChanged.connect(self._emit_time_scale_changed)
        schedule_grid.addWidget(time_scale_label, len(self._schedule_inputs), 0)
        schedule_grid.addWidget(self._time_scale_input, len(self._schedule_inputs), 1)

        stats_grid = QGridLayout()
        stats_grid.setHorizontalSpacing(12)
        stats_grid.setVerticalSpacing(5)
        root.addLayout(stats_grid)

        stat_ranges = {
            "hp": (0, 9999),
            "mp": (0, 9999),
            "offense": (0, 9999),
            "defense": (0, 9999),
            "speed": (0, 9999),
            "brains": (0, 9999),
            "weight": (0, 999),
            "happiness": (0, 100),
            "discipline": (0, 100),
            "care_mistakes": (0, 999),
            "won_battles": (0, 999),
            "techniques_mastered": (0, 999),
        }
        for row, (key, bounds) in enumerate(stat_ranges.items()):
            label = QLabel(f"{key.replace('_', ' ').title()}:")
            label.setObjectName("Muted")
            value = QSpinBox()
            value.setRange(bounds[0], bounds[1])
            value.valueChanged.connect(lambda new_value, name=key: self._emit_stat_changed(name, new_value))
            self._stat_inputs[key] = value
            stats_grid.addWidget(label, row, 0)
            stats_grid.addWidget(value, row, 1)

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
        self._labels["happiness"].setText(str(state.happiness))
        self._labels["mistakes"].setText(str(state.care_mistakes))
        self._labels["training"].setText(str(state.training_count))
        self._labels["weight"].setText(str(state.weight))
        self._labels["hp"].setText(str(state.hp))
        self._labels["mp"].setText(str(state.mp))
        self._labels["offense"].setText(str(state.offense))
        self._labels["defense"].setText(str(state.defense))
        self._labels["speed"].setText(str(state.speed))
        self._labels["brains"].setText(str(state.brains))
        self._labels["battles"].setText(str(state.won_battles))
        self._labels["techniques"].setText(str(state.techniques_mastered))
        self._set_stat_values(state)

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

    def _emit_time_scale_changed(self) -> None:
        if self._time_scale_changed is not None:
            self._time_scale_changed(self._time_scale_input.value())

    def _set_stat_values(self, state: PetState) -> None:
        self._updating_stats = True
        try:
            for key, widget in self._stat_inputs.items():
                widget.setValue(int(getattr(state, key)))
        finally:
            self._updating_stats = False

    def _emit_stat_changed(self, name: str, value: int) -> None:
        if self._updating_stats or self._stat_changed is None:
            return
        self._stat_changed(name, value)
