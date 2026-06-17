from __future__ import annotations

from pathlib import Path

from typing import Any

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QDialog, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from digimon_pet.app.sprite_runtime import SpriteAnimation, load_runtime_manifest, resolve_sprite_animation
from digimon_pet.app.theme import APP_QSS, COLORS
from digimon_pet.domain.evolution_tree import EvolutionLink, build_evolution_links, family_species_ids
from digimon_pet.domain.models import GrowthStage, PetState, Species
from digimon_pet.paths import PROJECT_ROOT

STAGE_LABELS = {
    GrowthStage.BABY: "Baby1",
    GrowthStage.BABY_2: "Baby2",
    GrowthStage.ROOKIE: "Rookie",
    GrowthStage.CHAMPION: "Champion",
    GrowthStage.ULTIMATE: "Ultimate",
}

STAGE_ORDER = (
    GrowthStage.BABY,
    GrowthStage.BABY_2,
    GrowthStage.ROOKIE,
    GrowthStage.CHAMPION,
    GrowthStage.ULTIMATE,
)


class CollectionDialog(QDialog):
    def __init__(
        self,
        species: dict[str, Species],
        discovered_species_ids: list[str],
        digivolutions: dict[str, Any] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._species = species
        self._discovered_species_ids = set(discovered_species_ids)
        self._digivolutions = digivolutions or {}
        self._manifest = load_runtime_manifest()
        self._tree_dialog: EvolutionTreeDialog | None = None

        self.setWindowTitle("Collection")
        self.setMinimumSize(560, 460)
        self.setStyleSheet(APP_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("Collection")
        title.setObjectName("Title")
        layout.addWidget(title)

        count = len(self._discovered_species_ids.intersection(self._species))
        summary = QLabel(f"{count}/{len(self._species)} Digimon discovered")
        summary.setObjectName("Muted")
        layout.addWidget(summary)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget(scroll_area)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(14)

        for stage in STAGE_ORDER:
            items = [item for item in self._species.values() if item.stage == stage]
            if not items:
                continue
            section = CollectionStageSection(
                STAGE_LABELS[stage],
                items,
                self._discovered_species_ids,
                self,
                content,
            )
            content_layout.addWidget(section)
        content_layout.addStretch(1)

        scroll_area.setWidget(content)
        layout.addWidget(scroll_area, 1)

    def _pixmap_for_species(self, species: Species) -> QPixmap | None:
        return _pixmap_for_species(species, self._manifest)

    def _open_evolution_tree(self, species_id: str) -> None:
        if species_id not in self._discovered_species_ids or species_id not in self._species:
            return
        self._tree_dialog = EvolutionTreeDialog(
            self._species,
            self._digivolutions,
            self._discovered_species_ids,
            species_id,
            self,
        )
        self._tree_dialog.show()
        self._tree_dialog.raise_()
        self._tree_dialog.activateWindow()


class CollectionStageSection(QWidget):
    def __init__(
        self,
        label: str,
        species: list[Species],
        discovered_species_ids: set[str],
        dialog: CollectionDialog,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        discovered_count = sum(1 for item in species if item.id in discovered_species_ids)
        header = QLabel(f"{label}  {discovered_count}/{len(species)}")
        header.setObjectName("StageHeader")
        layout.addWidget(header)

        grid_host = QWidget(self)
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        for index, item in enumerate(species):
            tile = CollectionTile(
                item,
                item.id in discovered_species_ids,
                dialog._pixmap_for_species(item),
                grid_host,
            )
            tile.clicked.connect(dialog._open_evolution_tree)
            grid.addWidget(tile, index // 5, index % 5)

        layout.addWidget(grid_host)


class CollectionTile(QWidget):
    clicked = Signal(str)

    def __init__(
        self,
        species: Species,
        discovered: bool,
        pixmap: QPixmap | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._species = species
        self._discovered = discovered
        self._pixmap = pixmap
        self.setFixedSize(QSize(96, 108))
        self.setToolTip(species.name if discovered else "Unknown")
        if discovered:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._discovered:
            self.clicked.emit(self._species.id)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(QColor("#3a3938"))
        painter.setBrush(QColor(COLORS["panel"]))
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 6, 6)

        sprite_rect = QRect(16, 8, 64, 64)
        if self._pixmap is not None:
            if self._discovered:
                painter.drawPixmap(sprite_rect, self._pixmap)
            else:
                painter.drawPixmap(sprite_rect, _silhouette(self._pixmap))
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#050506"))
            painter.drawEllipse(sprite_rect.adjusted(10, 10, -10, -10))

        if not self._discovered:
            painter.setPen(QColor(COLORS["focus"]))
            font = QFont()
            font.setPointSize(24)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(sprite_rect, Qt.AlignmentFlag.AlignCenter, "?")

        painter.setPen(QColor(COLORS["text"] if self._discovered else COLORS["muted"]))
        font = QFont()
        font.setPointSize(8)
        font.setBold(self._discovered)
        painter.setFont(font)
        label = self._species.name if self._discovered else "???"
        painter.drawText(QRect(6, 78, 84, 24), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, label)


class EvolutionTreeDialog(QDialog):
    def __init__(
        self,
        species: dict[str, Species],
        digivolutions: dict[str, Any],
        discovered_species_ids: set[str] | list[str],
        selected_species_id: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._species = species
        self._discovered_species_ids = set(discovered_species_ids)
        self._selected_species_id = selected_species_id
        self._manifest = load_runtime_manifest()

        selected = species[selected_species_id]
        self.setWindowTitle(f"{selected.name} Evolution Tree")
        self.setMinimumSize(700, 460)
        self.setStyleSheet(APP_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel(f"{selected.name} Evolution Tree")
        title.setObjectName("Title")
        layout.addWidget(title)

        links = build_evolution_links(species, digivolutions)
        family_ids = family_species_ids(selected_species_id, links)
        family_links = _sort_links([link for link in links if _is_family_link(link, family_ids)], species)
        known_count = len(family_ids.intersection(self._discovered_species_ids))
        summary = QLabel(f"{known_count}/{len(family_ids)} family Digimon discovered")
        summary.setObjectName("Muted")
        layout.addWidget(summary)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget(scroll_area)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)

        if family_links:
            for link in family_links:
                content_layout.addWidget(self._link_row(link))
        else:
            empty = QLabel("No known evolution links.")
            empty.setObjectName("Muted")
            content_layout.addWidget(empty)
        content_layout.addStretch(1)

        scroll_area.setWidget(content)
        layout.addWidget(scroll_area, 1)

    def _link_row(self, link: EvolutionLink) -> QWidget:
        row = QWidget(self)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(10)

        row_layout.addWidget(self._node(link.source_species_id))
        row_layout.addWidget(self._link_details(link), 1)
        row_layout.addWidget(self._node(link.target_species_id))
        return row

    def _node(self, species_id: str) -> QWidget:
        species = self._species[species_id]
        return EvolutionNode(
            species,
            species_id in self._discovered_species_ids,
            species_id == self._selected_species_id,
            _pixmap_for_species(species, self._manifest),
            self,
        )

    def _link_details(self, link: EvolutionLink) -> QWidget:
        details = QWidget(self)
        layout = QVBoxLayout(details)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        arrow = QLabel("->")
        arrow.setObjectName("TreeArrow")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(arrow)

        if link.target_species_id in self._discovered_species_ids:
            condition = QLabel(link.description)
            condition.setObjectName("ConditionLabel")
            condition.setAlignment(Qt.AlignmentFlag.AlignCenter)
            condition.setWordWrap(True)
            layout.addWidget(condition)
        return details


class EvolutionNode(QWidget):
    def __init__(
        self,
        species: Species,
        discovered: bool,
        selected: bool,
        pixmap: QPixmap | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("EvolutionNode")
        self.setProperty("selected", selected)
        self.setFixedSize(QSize(116, 96))
        self.setToolTip(species.name if discovered else "Unknown")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 7)
        layout.setSpacing(4)

        sprite = QLabel(self)
        sprite.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sprite.setPixmap(_tree_node_pixmap(pixmap, discovered))
        layout.addWidget(sprite)

        name = QLabel(species.name if discovered else "???")
        name.setObjectName("EvolutionNodeName")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setWordWrap(True)
        layout.addWidget(name)


def _first_frame_rect(pixmap: QPixmap, animation: SpriteAnimation) -> QRect | None:
    if animation.frame_count <= 1:
        return None
    frame_width = animation.frame_width or pixmap.width() // animation.frame_count
    frame_height = animation.frame_height or pixmap.height()
    if frame_width <= 0 or frame_height <= 0:
        return None
    return QRect(0, 0, frame_width, frame_height)


def _pixmap_for_species(species: Species, manifest: dict[str, Any]) -> QPixmap | None:
    state = PetState(species_id=species.id, stage=species.stage)
    animation = resolve_sprite_animation(state, species, manifest)
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


def _silhouette(pixmap: QPixmap) -> QPixmap:
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            if color.alpha() > 0:
                image.setPixelColor(x, y, QColor(5, 5, 6, color.alpha()))
    return QPixmap.fromImage(image)


def _tree_node_pixmap(pixmap: QPixmap | None, discovered: bool) -> QPixmap:
    if pixmap is not None:
        display = pixmap if discovered else _silhouette(pixmap)
        return display.scaled(52, 52, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)

    placeholder = QPixmap(52, 52)
    placeholder.fill(Qt.GlobalColor.transparent)
    painter = QPainter(placeholder)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#050506"))
    painter.drawEllipse(QRect(8, 8, 36, 36))
    painter.end()
    return placeholder


def _is_family_link(link: EvolutionLink, family_ids: set[str]) -> bool:
    return link.source_species_id in family_ids and link.target_species_id in family_ids


def _sort_links(links: list[EvolutionLink], species: dict[str, Species]) -> list[EvolutionLink]:
    stage_index = {stage: index for index, stage in enumerate(STAGE_ORDER)}
    return sorted(
        links,
        key=lambda link: (
            stage_index.get(species[link.source_species_id].stage, 99),
            species[link.source_species_id].name,
            link.order,
            stage_index.get(species[link.target_species_id].stage, 99),
            species[link.target_species_id].name,
        ),
    )
