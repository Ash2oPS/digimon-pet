from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QScrollArea,
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
        auto_rebirth_changed: Callable[[bool], None] | None = None,
        auto_lifecycle_changed: Callable[[bool], None] | None = None,
        reset_stats_requested: Callable[[], None] | None = None,
        reset_collection_requested: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._labels: dict[str, QLabel] = {}
        self._schedule_inputs: dict[str, QSpinBox] = {}
        self._stat_inputs: dict[str, QSpinBox] = {}
        self._schedule_changed = schedule_changed
        self._time_scale_changed = time_scale_changed
        self._stat_changed = stat_changed
        self._auto_rebirth_changed = auto_rebirth_changed
        self._auto_lifecycle_changed = auto_lifecycle_changed
        self._reset_stats_requested = reset_stats_requested
        self._reset_collection_requested = reset_collection_requested
        self._updating_schedule = False
        self._updating_stats = False
        self.setWindowTitle("Digimon Pet Debug")
        self.setMinimumSize(420, 560)
        self.resize(460, 680)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget(self)
        header.setObjectName("DebugHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(16, 14, 16, 12)
        header_layout.setSpacing(3)
        title = QLabel("Pet Debug", header)
        title.setObjectName("Title")
        subtitle = QLabel("Live state and tuning", header)
        subtitle.setObjectName("Muted")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        root.addWidget(header)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(scroll_area, 1)

        content = QWidget(scroll_area)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(14, 14, 14, 14)
        content_layout.setSpacing(12)
        scroll_area.setWidget(content)

        overview_grid = self._section_grid(content_layout, "Current")
        self._add_readout(overview_grid, 0, "species", "Species")
        self._add_readout(overview_grid, 1, "stage", "Stage")
        self._add_readout(overview_grid, 2, "age", "Age")
        self._add_readout(overview_grid, 3, "next", "Next")
        self._add_readout(overview_grid, 4, "remaining", "Remaining")

        care_grid = self._section_grid(content_layout, "Care")
        for row, (key, label_text) in enumerate([
            ("hunger", "Hunger"),
            ("fatigue", "Fatigue"),
            ("discipline", "Discipline"),
            ("happiness", "Happiness"),
            ("mistakes", "Care Mistakes"),
            ("training", "Training"),
            ("weight", "Weight"),
        ]):
            self._add_readout(care_grid, row, key, label_text)

        stats_grid = self._section_grid(content_layout, "Stats")
        for index, (key, label_text) in enumerate([
            ("hp", "HP"),
            ("mp", "MP"),
            ("offense", "Offense"),
            ("defense", "Defense"),
            ("speed", "Speed"),
            ("brains", "Brains"),
            ("battles", "Battles"),
            ("techniques", "Techniques"),
        ]):
            row = index // 2
            column = (index % 2) * 2
            self._add_readout(stats_grid, row, key, label_text, column)

        schedule_grid = self._section_grid(content_layout, "Timing")

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

        automation_group = QGroupBox("Automation")
        automation_layout = QVBoxLayout(automation_group)
        automation_layout.setContentsMargins(12, 14, 12, 12)
        self._auto_rebirth_checkbox = QCheckBox("Auto-pick random Baby1 on death")
        self._auto_rebirth_checkbox.toggled.connect(self._emit_auto_rebirth_changed)
        automation_layout.addWidget(self._auto_rebirth_checkbox)
        self._auto_lifecycle_checkbox = QCheckBox("Auto-resolve evolution and death")
        self._auto_lifecycle_checkbox.toggled.connect(self._emit_auto_lifecycle_changed)
        automation_layout.addWidget(self._auto_lifecycle_checkbox)
        content_layout.addWidget(automation_group)

        reset_group = QGroupBox("Reset")
        reset_layout = QVBoxLayout(reset_group)
        reset_layout.setContentsMargins(12, 14, 12, 12)
        reset_layout.setSpacing(8)
        self._reset_stats_button = QPushButton("Reset Stats")
        self._reset_stats_button.clicked.connect(self._emit_reset_stats_requested)
        self._reset_collection_button = QPushButton("Reset Collection")
        self._reset_collection_button.clicked.connect(self._emit_reset_collection_requested)
        reset_layout.addWidget(self._reset_stats_button)
        reset_layout.addWidget(self._reset_collection_button)
        content_layout.addWidget(reset_group)

        editor_grid = self._section_grid(content_layout, "Edit Stats")

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
            editor_grid.addWidget(label, row, 0)
            editor_grid.addWidget(value, row, 1)

        content_layout.addStretch(1)

    def set_auto_rebirth_enabled(self, enabled: bool) -> None:
        self._auto_rebirth_checkbox.setChecked(enabled)

    def set_auto_lifecycle_enabled(self, enabled: bool) -> None:
        self._auto_lifecycle_checkbox.setChecked(enabled)

    def _section_grid(self, parent_layout: QVBoxLayout, title: str) -> QGridLayout:
        group = QGroupBox(title)
        layout = QGridLayout(group)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setHorizontalSpacing(14)
        layout.setVerticalSpacing(7)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)
        parent_layout.addWidget(group)
        return layout

    def _add_readout(self, layout: QGridLayout, row: int, key: str, label_text: str, column: int = 0) -> None:
        label = QLabel(f"{label_text}:")
        label.setObjectName("Muted")
        value = QLabel("-")
        value.setObjectName("DebugValue")
        value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        value.setWordWrap(True)
        self._labels[key] = value
        layout.addWidget(label, row, column)
        layout.addWidget(value, row, column + 1)

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

    def _emit_auto_rebirth_changed(self, enabled: bool) -> None:
        if self._auto_rebirth_changed is not None:
            self._auto_rebirth_changed(enabled)

    def _emit_auto_lifecycle_changed(self, enabled: bool) -> None:
        if self._auto_lifecycle_changed is not None:
            self._auto_lifecycle_changed(enabled)

    def _emit_reset_stats_requested(self) -> None:
        if self._reset_stats_requested is not None:
            self._reset_stats_requested()

    def _emit_reset_collection_requested(self) -> None:
        if self._reset_collection_requested is not None:
            self._reset_collection_requested()

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
