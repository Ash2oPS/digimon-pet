from __future__ import annotations

from pathlib import Path
import threading

from PySide6.QtCore import QObject, QRect, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from digimon_pet.app.artwork_runtime import download_artwork_for_species, resolve_artwork_path
from digimon_pet.app.sprite_runtime import SpriteAnimation, load_runtime_manifest, resolve_sprite_animation
from digimon_pet.app.theme import APP_QSS
from digimon_pet.data import load_dw1_digivolutions
from digimon_pet.domain.models import PetState, Species
from digimon_pet.paths import PROJECT_ROOT


class _ArtworkDownloadSignals(QObject):
    finished = Signal(str)


class StatsWindow(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._manifest = load_runtime_manifest()
        self._state: PetState | None = None
        self._species: Species | None = None
        self._digivolutions = load_dw1_digivolutions()
        self._artwork_downloads_in_progress: set[str] = set()
        self._artwork_downloads_attempted: set[str] = set()
        self._artwork_download_signals = _ArtworkDownloadSignals(self)
        self._artwork_download_signals.finished.connect(self._handle_artwork_download_finished)
        self._labels: dict[str, QLabel] = {}
        self._label_groups: dict[str, list[QLabel]] = {}
        self._bars: dict[str, QProgressBar] = {}
        self._bar_groups: dict[str, list[QProgressBar]] = {}
        self._evolution_grid: QGridLayout | None = None

        self.setWindowTitle("Stats")
        self.setMinimumSize(640, 520)
        self.setStyleSheet(APP_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        header = QFrame(self)
        header.setObjectName("StatsHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 12, 12, 12)
        header_layout.setSpacing(14)

        self._sprite_label = QLabel(self)
        self._sprite_label.setObjectName("StatsPortrait")
        self._sprite_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sprite_label.setMinimumSize(142, 142)
        header_layout.addWidget(self._sprite_label)

        identity_layout = QVBoxLayout()
        identity_layout.setSpacing(6)
        self._name_label = QLabel("-", self)
        self._name_label.setObjectName("Title")
        self._stage_label = QLabel("-", self)
        self._stage_label.setObjectName("StatsStage")
        self._summary_label = QLabel("-", self)
        self._summary_label.setObjectName("Muted")
        self._summary_label.setWordWrap(True)
        identity_layout.addWidget(self._name_label)
        identity_layout.addWidget(self._stage_label)
        identity_layout.addWidget(self._summary_label)
        identity_layout.addStretch(1)
        header_layout.addLayout(identity_layout, 1)
        layout.addWidget(header)

        self._tabs = QTabWidget(self)
        self._tabs.setObjectName("StatsTabs")
        self._tabs.addTab(self._build_overview_tab(), "Vue")
        self._tabs.addTab(self._build_combat_tab(), "Combat")
        self._tabs.addTab(self._build_care_tab(), "Soin")
        self._tabs.addTab(self._build_evolution_tab(), "Evolution")
        self._tabs.addTab(self._build_bonus_tab(), "Bonus")
        layout.addWidget(self._tabs, 1)

    def refresh(self, state: PetState, species: Species) -> None:
        self._state = state
        self._species = species
        self._name_label.setText(species.name)
        self._stage_label.setText(_format_stage(species.stage.value))
        self._summary_label.setText(
            f"{_format_age(state.age_seconds)} - {_format_action(state.current_action)}"
            f" - {'endormi' if state.is_sleeping else 'eveille'}"
        )
        self._set_label("age", _format_age(state.age_seconds))
        self._set_label("stage", _format_stage(species.stage.value))
        self._set_label("action", _format_action(state.current_action))
        self._set_label("sleeping", _format_bool(state.is_sleeping))
        self._set_label("weight", str(state.weight))
        self._set_label("care_mistakes", str(state.care_mistakes))
        self._set_label("training_count", str(state.training_count))
        self._set_label("won_battles", str(state.won_battles))
        self._set_label("techniques_mastered", str(state.techniques_mastered))
        self._set_label("hp", str(state.hp))
        self._set_label("mp", str(state.mp))
        self._set_label("offense", str(state.offense))
        self._set_label("defense", str(state.defense))
        self._set_label("speed", str(state.speed))
        self._set_label("brains", str(state.brains))
        self._set_label("discovered_species", str(len(state.discovered_species_ids)))
        self._set_label("generation_bonuses", _format_bonus_summary(state.generation_stat_bonuses))
        self._set_label("pending_bonuses", _format_bonus_summary(state.pending_rebirth_stat_bonuses))
        self._set_label("incubators", str(len(state.filled_incubators)))
        self._set_bar("hunger", state.hunger)
        self._set_bar("fatigue", state.fatigue)
        self._set_bar("discipline", state.discipline)
        self._set_bar("happiness", state.happiness)
        self._refresh_evolution(state, species)
        self._set_sprite(state, species)

    def _build_overview_tab(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        summary_grid = QGridLayout()
        summary_grid.setHorizontalSpacing(8)
        summary_grid.setVerticalSpacing(8)
        layout.addLayout(summary_grid)
        for index, (key, title) in enumerate(
            [
                ("age", "Age"),
                ("stage", "Niveau"),
                ("action", "Action"),
                ("sleeping", "Sommeil"),
                ("weight", "Poids"),
                ("care_mistakes", "Erreurs soin"),
                ("training_count", "Entrainements"),
                ("won_battles", "Combats gagnes"),
            ]
        ):
            summary_grid.addWidget(self._metric_card(key, title), index // 4, index % 4)

        content = QHBoxLayout()
        content.setSpacing(12)
        content.addWidget(self._care_panel(), 1)
        content.addWidget(self._combat_panel(), 1)
        layout.addLayout(content)
        layout.addStretch(1)
        return page

    def _build_combat_tab(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        layout.addWidget(self._combat_panel())
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        layout.addLayout(grid)
        for index, (key, title) in enumerate(
            [
                ("won_battles", "Combats gagnes"),
                ("techniques_mastered", "Techniques"),
                ("training_count", "Entrainements"),
            ]
        ):
            grid.addWidget(self._metric_card(key, title), 0, index)
        layout.addStretch(1)
        return page

    def _build_care_tab(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        layout.addWidget(self._care_panel())
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        layout.addLayout(grid)
        for index, (key, title) in enumerate(
            [
                ("care_mistakes", "Erreurs soin"),
                ("weight", "Poids"),
                ("action", "Action actuelle"),
                ("sleeping", "Sommeil"),
            ]
        ):
            grid.addWidget(self._metric_card(key, title), index // 2, index % 2)
        layout.addStretch(1)
        return page

    def _build_evolution_tab(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        title = QLabel("Projection evolution", self)
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        hint = QLabel("Compare les stats actuelles aux prerequis des evolutions naturelles connues.", self)
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        self._evolution_grid = grid
        layout.addLayout(grid)
        layout.addStretch(1)
        return page

    def _build_bonus_tab(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        layout.addLayout(grid)
        for index, (key, title) in enumerate(
            [
                ("discovered_species", "Especes decouvertes"),
                ("generation_bonuses", "Bonus generation"),
                ("pending_bonuses", "Bonus renaissance"),
                ("incubators", "Incubateurs remplis"),
            ]
        ):
            grid.addWidget(self._metric_card(key, title), index // 2, index % 2)
        layout.addStretch(1)
        return page

    def _metric_card(self, key: str, title: str) -> QFrame:
        card = QFrame(self)
        card.setObjectName("StatsMetricCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        label = QLabel(title, self)
        label.setObjectName("Muted")
        value = QLabel("-", self)
        value.setObjectName("StatsMetricValue")
        value.setWordWrap(True)
        value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._register_label(key, value)
        layout.addWidget(label)
        layout.addWidget(value)
        return card

    def _care_panel(self) -> QFrame:
        panel = QFrame(self)
        panel.setObjectName("StatsPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        title = QLabel("Jauges de soin", self)
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        for key, label in [
            ("hunger", "Faim"),
            ("happiness", "Bonheur"),
            ("discipline", "Discipline"),
            ("fatigue", "Fatigue"),
        ]:
            layout.addLayout(self._bar_row(key, label))
        return panel

    def _combat_panel(self) -> QFrame:
        panel = QFrame(self)
        panel.setObjectName("StatsPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        title = QLabel("Combat", self)
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(10)
        layout.addLayout(grid)
        for index, (key, label) in enumerate(
            [
                ("hp", "HP"),
                ("mp", "MP"),
                ("offense", "OFF"),
                ("defense", "DEF"),
                ("speed", "SPD"),
                ("brains", "INT"),
            ]
        ):
            title_label = QLabel(label, self)
            title_label.setObjectName("Muted")
            value = QLabel("-", self)
            value.setObjectName("StatsMetricValue")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._register_label(key, value)
            cell = QVBoxLayout()
            cell.setSpacing(2)
            cell.addWidget(title_label)
            cell.addWidget(value)
            grid.addLayout(cell, index // 2, index % 2)
        return panel

    def _bar_row(self, key: str, title: str) -> QVBoxLayout:
        row = QVBoxLayout()
        row.setSpacing(3)
        header = QHBoxLayout()
        label = QLabel(title, self)
        value = QLabel("- / 100", self)
        value.setObjectName("StatsBarValue")
        self._register_label(f"{key}_bar_value", value)
        header.addWidget(label)
        header.addStretch(1)
        header.addWidget(value)
        bar = QProgressBar(self)
        bar.setRange(0, 100)
        bar.setTextVisible(False)
        bar.setObjectName(f"StatsBar_{key}")
        self._bar_groups.setdefault(key, []).append(bar)
        self._bars.setdefault(key, bar)
        row.addLayout(header)
        row.addWidget(bar)
        return row

    def _register_label(self, key: str, label: QLabel) -> None:
        self._label_groups.setdefault(key, []).append(label)
        self._labels.setdefault(key, label)

    def _set_label(self, key: str, text: str) -> None:
        for label in self._label_groups.get(key, []):
            label.setText(text)

    def _set_bar(self, key: str, value: int) -> None:
        clamped = max(0, min(100, int(value)))
        for bar in self._bar_groups.get(key, []):
            bar.setValue(clamped)
        self._set_label(f"{key}_bar_value", f"{clamped} / 100")

    def _refresh_evolution(self, state: PetState, species: Species) -> None:
        if self._evolution_grid is None:
            return
        _clear_layout(self._evolution_grid)
        options = _evolution_options_for_species(self._digivolutions, species.id)
        if not options:
            empty = QLabel("Aucune evolution naturelle connue pour cette espece.", self)
            empty.setObjectName("Muted")
            self._evolution_grid.addWidget(empty, 0, 0)
            return
        for row, option in enumerate(options):
            target = QLabel(str(option.get("target_name") or option.get("target_species_id") or "-"), self)
            target.setObjectName("StatsMetricValue")
            self._evolution_grid.addWidget(target, row, 0)
            stats = _requirement_stats(option)
            if not stats:
                detail = QLabel("Aucun prerequis de stat.", self)
                detail.setObjectName("Muted")
                self._evolution_grid.addWidget(detail, row, 1)
                continue
            detail = QLabel(_format_requirements_progress(state, stats), self)
            detail.setObjectName("Muted")
            detail.setWordWrap(True)
            self._evolution_grid.addWidget(detail, row, 1)

    def _set_sprite(self, state: PetState, species: Species) -> None:
        pixmap = self._pixmap_for_species(state, species)
        if pixmap is None:
            self._sprite_label.clear()
            return
        self._sprite_label.setPixmap(
            pixmap.scaled(
                148,
                148,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _pixmap_for_species(self, state: PetState, species: Species) -> QPixmap | None:
        artwork = self._artwork_pixmap_for_species(species)
        if artwork is not None:
            return artwork
        return self._sprite_pixmap_for_species(state, species)

    def _artwork_pixmap_for_species(self, species: Species) -> QPixmap | None:
        path = resolve_artwork_path(species.id)
        if path is None:
            self._queue_artwork_download(species.id)
            return None
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return None
        return pixmap

    def _queue_artwork_download(self, species_id: str) -> None:
        if species_id in self._artwork_downloads_in_progress or species_id in self._artwork_downloads_attempted:
            return
        self._artwork_downloads_attempted.add(species_id)
        self._artwork_downloads_in_progress.add(species_id)

        def worker() -> None:
            try:
                download_artwork_for_species(species_id)
            finally:
                self._artwork_download_signals.finished.emit(species_id)

        threading.Thread(target=worker, daemon=True).start()

    def _handle_artwork_download_finished(self, species_id: str) -> None:
        self._artwork_downloads_in_progress.discard(species_id)
        if self._state is None or self._species is None:
            return
        if self._species.id == species_id:
            self._set_sprite(self._state, self._species)

    def _sprite_pixmap_for_species(self, state: PetState, species: Species) -> QPixmap | None:
        animation = resolve_sprite_animation(state, species, self._manifest)
        if animation is None:
            return None
        path = PROJECT_ROOT / Path(animation.path)
        if not path.exists():
            return None
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return None
        frame = _first_frame_rect(pixmap, animation)
        return pixmap.copy(frame) if frame is not None else pixmap


def _first_frame_rect(pixmap: QPixmap, animation: SpriteAnimation) -> QRect | None:
    if animation.frame_count <= 1:
        return None
    frame_width = animation.frame_width or pixmap.width() // animation.frame_count
    frame_height = animation.frame_height or pixmap.height()
    if frame_width <= 0 or frame_height <= 0:
        return None
    return QRect(0, 0, frame_width, frame_height)


def _format_age(age_seconds: int) -> str:
    total_minutes = max(0, age_seconds) // 60
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours} h {minutes:02d} min"


def _format_stage(stage: str) -> str:
    return stage.replace("_", " ").title()


def _format_action(action: str) -> str:
    return action.replace("_", " ").title()


def _format_bool(value: bool) -> str:
    return "Oui" if value else "Non"


def _format_bonus_summary(bonuses: dict[str, int]) -> str:
    if not bonuses:
        return "Aucun"
    return ", ".join(f"{_stat_label(stat)} +{value}" for stat, value in sorted(bonuses.items()))


def _evolution_options_for_species(digivolutions: dict, species_id: str) -> list[dict]:
    transitions = {str(item.get("id")): item for item in digivolutions.get("natural_evolutions", [])}
    source_index = digivolutions.get("indexes", {}).get("by_source", {})
    transition_ids = source_index.get(species_id, [])
    return [transitions[transition_id] for transition_id in transition_ids if transition_id in transitions]


def _requirement_stats(option: dict) -> dict[str, int]:
    groups = option.get("requirements", {}).get("groups", {})
    stats = groups.get("stats", {})
    return {str(stat): int(value) for stat, value in stats.items()}


def _format_requirements_progress(state: PetState, stats: dict[str, int]) -> str:
    parts: list[str] = []
    for stat, required in stats.items():
        current = int(getattr(state, stat, 0))
        missing = max(0, required - current)
        status = "OK" if missing == 0 else f"manque {missing}"
        parts.append(f"{_stat_label(stat)} {current}/{required} ({status})")
    return " - ".join(parts)


def _stat_label(stat: str) -> str:
    labels = {
        "hp": "HP",
        "mp": "MP",
        "offense": "OFF",
        "defense": "DEF",
        "speed": "SPD",
        "brains": "INT",
    }
    return labels.get(stat, stat.replace("_", " ").upper())


def _clear_layout(layout: QGridLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child_layout is not None:
            _clear_layout(child_layout)  # type: ignore[arg-type]
