from __future__ import annotations

from pathlib import Path
import threading

from PySide6.QtCore import QObject, QRect, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QGridLayout, QLabel, QVBoxLayout, QWidget

from digimon_pet.app.artwork_runtime import download_artwork_for_species, resolve_artwork_path
from digimon_pet.app.sprite_runtime import SpriteAnimation, load_runtime_manifest, resolve_sprite_animation
from digimon_pet.app.theme import APP_QSS
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
        self._artwork_downloads_in_progress: set[str] = set()
        self._artwork_downloads_attempted: set[str] = set()
        self._artwork_download_signals = _ArtworkDownloadSignals(self)
        self._artwork_download_signals.finished.connect(self._handle_artwork_download_finished)
        self._labels: dict[str, QLabel] = {}

        self.setWindowTitle("Stats")
        self.setMinimumSize(280, 340)
        self.setStyleSheet(APP_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self._sprite_label = QLabel(self)
        self._sprite_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sprite_label.setMinimumHeight(150)
        layout.addWidget(self._sprite_label)

        self._name_label = QLabel("-", self)
        self._name_label.setObjectName("Title")
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._name_label)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(7)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        for row, (key, label_text) in enumerate(
            [
                ("age", "Age"),
                ("hp", "HP"),
                ("mp", "MP"),
                ("offense", "OFF"),
                ("defense", "DEF"),
                ("speed", "SPD"),
                ("brains", "INT"),
            ]
        ):
            label = QLabel(f"{label_text}:", self)
            label.setObjectName("Muted")
            value = QLabel("-", self)
            value.setObjectName("DebugValue")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._labels[key] = value
            grid.addWidget(label, row, 0)
            grid.addWidget(value, row, 1)

        layout.addStretch(1)

    def refresh(self, state: PetState, species: Species) -> None:
        self._state = state
        self._species = species
        self._name_label.setText(species.name)
        self._labels["age"].setText(_format_age(state.age_seconds))
        self._labels["hp"].setText(str(state.hp))
        self._labels["mp"].setText(str(state.mp))
        self._labels["offense"].setText(str(state.offense))
        self._labels["defense"].setText(str(state.defense))
        self._labels["speed"].setText(str(state.speed))
        self._labels["brains"].setText(str(state.brains))
        self._set_sprite(state, species)

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
