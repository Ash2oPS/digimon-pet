from __future__ import annotations

from pathlib import Path

from typing import Any

from PySide6.QtCore import QPointF, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QDialog, QGridLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from digimon_pet.app.sprite_runtime import SpriteAnimation, load_runtime_manifest, resolve_sprite_animation
from digimon_pet.app.theme import APP_QSS, COLORS
from digimon_pet.domain.evolution_tree import EvolutionLink, build_evolution_links, graph_links, graph_species_ids
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
        all_graph_ids = graph_species_ids(selected_species_id, species, links)
        graph_ids = _graph_species_until_stage_after_selected(all_graph_ids, species, selected.stage)
        visible_links = _links_within_graph(graph_links(selected_species_id, species, links), graph_ids)
        known_count = len(graph_ids.intersection(self._discovered_species_ids))
        summary = QLabel(f"{known_count}/{len(graph_ids)} graph Digimon discovered")
        summary.setObjectName("Muted")
        layout.addWidget(summary)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        graph = EvolutionGraphWidget(
            species,
            graph_ids,
            visible_links,
            self._discovered_species_ids,
            selected_species_id,
            self._manifest,
            scroll_area,
        )

        scroll_area.setWidget(graph)
        layout.addWidget(scroll_area, 1)


class EvolutionGraphWidget(QWidget):
    NODE_SIZE = QSize(116, 96)
    LEFT_MARGIN = 92
    TOP_MARGIN = 18
    RIGHT_MARGIN = 22
    BOTTOM_MARGIN = 22
    X_GAP = 34
    Y_GAP = 54

    def __init__(
        self,
        species: dict[str, Species],
        graph_species: set[str],
        links: list[EvolutionLink],
        discovered_species_ids: set[str],
        selected_species_id: str,
        manifest: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._species = species
        self._graph_species = graph_species
        self._links = links
        self._drawable_links = _drawable_links_for_graph(species, graph_species, links)
        self._discovered_species_ids = discovered_species_ids
        self._selected_species_id = selected_species_id
        self._manifest = manifest
        self._nodes: dict[str, EvolutionNode] = {}
        self._build_graph()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(COLORS["focus"]), 1))
        painter.setBrush(QColor(COLORS["focus"]))

        for link in self._drawable_links:
            source = self._nodes.get(link.source_species_id)
            target = self._nodes.get(link.target_species_id)
            if source is None or target is None:
                continue
            source_rect = source.geometry()
            target_rect = target.geometry()
            start = QPointF(source_rect.center().x(), source_rect.bottom())
            end = QPointF(target_rect.center().x(), target_rect.top())
            bend_y = start.y() + max(14, (end.y() - start.y()) * 0.45)
            path_points = [
                start,
                QPointF(start.x(), bend_y),
                QPointF(end.x(), bend_y),
                end,
            ]
            for point_index in range(len(path_points) - 1):
                painter.drawLine(path_points[point_index], path_points[point_index + 1])
            painter.drawPolygon(
                QPolygonF(
                    [
                        end,
                        QPointF(end.x() - 4, end.y() - 7),
                        QPointF(end.x() + 4, end.y() - 7),
                    ]
                )
            )

    def _build_graph(self) -> None:
        incoming_requirements = _incoming_requirements(self._links)
        stage_rows = [
            (stage, self._species_for_stage(stage))
            for stage in STAGE_ORDER
            if self._species_for_stage(stage)
        ]

        y = self.TOP_MARGIN
        max_width = self.LEFT_MARGIN + self.NODE_SIZE.width() + self.RIGHT_MARGIN
        for stage, stage_species in stage_rows:
            header = QLabel(STAGE_LABELS[stage], self)
            header.setObjectName("EvolutionGraphStageHeader")
            header.setGeometry(0, y + 34, self.LEFT_MARGIN - 14, 22)
            header.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            for index, species_id in enumerate(stage_species):
                item = self._species[species_id]
                x = self.LEFT_MARGIN + index * (self.NODE_SIZE.width() + self.X_GAP)
                requirements = incoming_requirements.get(species_id, [])
                node = EvolutionNode(
                    item,
                    species_id in self._discovered_species_ids,
                    species_id == self._selected_species_id,
                    _pixmap_for_species(item, self._manifest),
                    requirements,
                    self,
                )
                node.setGeometry(x, y, self.NODE_SIZE.width(), self.NODE_SIZE.height())
                self._nodes[species_id] = node
                max_width = max(max_width, x + self.NODE_SIZE.width() + self.RIGHT_MARGIN)
            y += self.NODE_SIZE.height() + self.Y_GAP

        graph_height = max(self.TOP_MARGIN + self.NODE_SIZE.height() + self.BOTTOM_MARGIN, y - self.Y_GAP + self.BOTTOM_MARGIN)
        self.setMinimumSize(max_width, graph_height)

    def _species_for_stage(self, stage: GrowthStage) -> list[str]:
        return sorted(
            (species_id for species_id in self._graph_species if self._species[species_id].stage == stage),
            key=lambda species_id: (
                0 if species_id == self._selected_species_id else 1,
                self._species[species_id].name,
            ),
        )


class EvolutionNode(QWidget):
    def __init__(
        self,
        species: Species,
        discovered: bool,
        selected: bool,
        pixmap: QPixmap | None,
        requirements: list[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._species = species
        self.setObjectName("EvolutionNode")
        self.setProperty("selected", selected)
        self.setFixedSize(QSize(116, 96))
        self.setToolTip(_node_tooltip(species, discovered, requirements or []))

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


def _incoming_requirements(links: list[EvolutionLink]) -> dict[str, list[str]]:
    requirements: dict[str, list[str]] = {}
    for link in links:
        requirements.setdefault(link.target_species_id, []).append(link.description)
    return requirements


def _node_tooltip(species: Species, discovered: bool, requirements: list[str]) -> str:
    if not discovered:
        return "Unknown"
    if not requirements:
        return species.name
    return "\n".join([species.name, "Requirements:", *requirements])


def _stage_index(stage: GrowthStage) -> int:
    return STAGE_ORDER.index(stage)


def _drawable_links_for_graph(
    species: dict[str, Species],
    graph_species: set[str],
    links: list[EvolutionLink],
) -> list[EvolutionLink]:
    drawable_links: list[EvolutionLink] = []
    for link in links:
        if link.source_species_id is not None:
            if _is_forward_link(species, link.source_species_id, link.target_species_id):
                drawable_links.append(link)
            continue

        drawable_links.extend(_concrete_links_for_global_link(species, graph_species, link))
    return drawable_links


def _concrete_links_for_global_link(
    species: dict[str, Species],
    graph_species: set[str],
    link: EvolutionLink,
) -> list[EvolutionLink]:
    source_ids = sorted(
        (
            species_id
            for species_id in graph_species
            if species_id != link.target_species_id
            and species_id not in link.excluded_source_species_ids
            and (link.source_stage is None or species[species_id].stage == link.source_stage)
            and _is_forward_link(species, species_id, link.target_species_id)
        ),
        key=lambda species_id: (_stage_index(species[species_id].stage), species[species_id].name),
    )
    return [
        EvolutionLink(
            source_id,
            link.target_species_id,
            link.kind,
            link.description,
            link.order,
            link.source_stage,
            link.excluded_source_species_ids,
        )
        for source_id in source_ids
    ]


def _is_forward_link(species: dict[str, Species], source_species_id: str, target_species_id: str) -> bool:
    return _stage_index(species[target_species_id].stage) > _stage_index(species[source_species_id].stage)


def _graph_species_until_stage_after_selected(
    graph_species_ids: set[str],
    species: dict[str, Species],
    selected_stage: GrowthStage,
) -> set[str]:
    max_visible_stage = min(_stage_index(selected_stage) + 1, len(STAGE_ORDER) - 1)
    return {
        species_id
        for species_id in graph_species_ids
        if _stage_index(species[species_id].stage) <= max_visible_stage
    }


def _links_within_graph(links: list[EvolutionLink], graph_species_ids: set[str]) -> list[EvolutionLink]:
    return [
        link
        for link in links
        if link.target_species_id in graph_species_ids
        and (link.source_species_id is None or link.source_species_id in graph_species_ids)
    ]
