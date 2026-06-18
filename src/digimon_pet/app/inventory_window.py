from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from digimon_pet.app.theme import APP_QSS, COLORS


@dataclass(frozen=True)
class InventoryItem:
    id: str
    name: str
    quantity: int = 1
    icon_path: str | None = None
    description: str = "Objet utilisable"


class InventoryWindow(QDialog):
    _DEFAULT_SLOT_COUNT = 24
    _COLUMNS = 5

    def __init__(
        self,
        slot_count: int = _DEFAULT_SLOT_COUNT,
        item_used: Callable[[str], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._slots: list[InventorySlotWidget] = []
        self._item_used = item_used
        self._selected_item_id: str | None = None

        self.setWindowTitle("Inventaire")
        self.setMinimumSize(640, 420)
        self.setStyleSheet(APP_QSS + _INVENTORY_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        title = QLabel("Inventaire", self)
        title.setObjectName("Title")
        layout.addWidget(title)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        grid_host = QWidget(self)
        grid_host.setObjectName("InventoryGrid")
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        for index in range(slot_count):
            slot = InventorySlotWidget(self._select_item, self._use_item, grid_host)
            self._slots.append(slot)
            grid.addWidget(slot, index // self._COLUMNS, index % self._COLUMNS)

        scroll_area.setWidget(grid_host)
        body.addWidget(scroll_area, 1)

        details = QFrame(self)
        details.setObjectName("InventoryDetails")
        details.setFixedWidth(190)
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(12, 12, 12, 12)
        details_layout.setSpacing(8)

        self._details_icon = QLabel(details)
        self._details_icon.setObjectName("InventoryDetailsIcon")
        self._details_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._details_icon.setFixedSize(QSize(92, 92))
        details_layout.addWidget(self._details_icon, 0, Qt.AlignmentFlag.AlignHCenter)

        self._details_name = QLabel("Aucun objet", details)
        self._details_name.setObjectName("InventoryDetailsName")
        self._details_name.setWordWrap(True)
        self._details_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        details_layout.addWidget(self._details_name)

        self._details_quantity = QLabel("", details)
        self._details_quantity.setObjectName("Muted")
        self._details_quantity.setAlignment(Qt.AlignmentFlag.AlignCenter)
        details_layout.addWidget(self._details_quantity)

        self._details_description = QLabel("Les objets disponibles apparaissent dans la grille.", details)
        self._details_description.setObjectName("InventoryDetailsDescription")
        self._details_description.setWordWrap(True)
        self._details_description.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        details_layout.addWidget(self._details_description, 1)

        self._use_button = QPushButton("Utiliser", details)
        self._use_button.setEnabled(False)
        self._use_button.clicked.connect(self._use_selected_item)
        details_layout.addWidget(self._use_button)

        body.addWidget(details)
        layout.addLayout(body, 1)
        self._refresh_details()

    def set_items(self, items: list[InventoryItem]) -> None:
        for index, slot in enumerate(self._slots):
            slot.set_item(items[index] if index < len(items) else None)
        if self._selected_item_id not in {item.id for item in items}:
            self._selected_item_id = items[0].id if items else None
        self._refresh_selection()

    def _use_item(self, item_id: str) -> None:
        if self._item_used is not None:
            self._item_used(item_id)

    def _select_item(self, item_id: str | None) -> None:
        self._selected_item_id = item_id
        self._refresh_selection()

    def _use_selected_item(self) -> None:
        if self._selected_item_id is not None:
            self._use_item(self._selected_item_id)

    def _refresh_selection(self) -> None:
        selected_item: InventoryItem | None = None
        for slot in self._slots:
            is_selected = slot.item is not None and slot.item.id == self._selected_item_id
            slot.set_selected(is_selected)
            if is_selected:
                selected_item = slot.item
        self._refresh_details(selected_item)

    def _refresh_details(self, item: InventoryItem | None = None) -> None:
        if item is None:
            self._details_icon.clear()
            self._details_name.setText("Aucun objet")
            self._details_quantity.setText("")
            self._details_description.setText("Les objets disponibles apparaissent dans la grille.")
            self._use_button.setEnabled(False)
            return

        pixmap = _item_pixmap(item)
        if pixmap is None:
            self._details_icon.setPixmap(QPixmap())
            self._details_icon.setText(item.name[:2].upper())
        else:
            self._details_icon.setText("")
            self._details_icon.setPixmap(
                pixmap.scaled(
                    72,
                    72,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        self._details_name.setText(item.name)
        self._details_quantity.setText(f"Quantite : {item.quantity}")
        self._details_description.setText(item.description)
        self._use_button.setEnabled(True)


class InventorySlotWidget(QWidget):
    _SIZE = QSize(72, 78)

    def __init__(
        self,
        item_selected: Callable[[str | None], None] | None = None,
        item_used: Callable[[str], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.item: InventoryItem | None = None
        self._item_selected = item_selected
        self._item_used = item_used
        self.setObjectName("InventorySlot")
        self.setFixedSize(self._SIZE)
        self.setProperty("empty", True)
        self.setProperty("selected", False)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setToolTip("Emplacement vide")
        self.setCursor(Qt.CursorShape.ArrowCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(3)

        self._icon_label = QLabel(self)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setFixedHeight(42)
        layout.addWidget(self._icon_label)

        self._quantity_label = QLabel("", self)
        self._quantity_label.setObjectName("InventoryQuantity")
        self._quantity_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self._quantity_label)

    def set_item(self, item: InventoryItem | None) -> None:
        self.item = item
        self.setProperty("empty", item is None)
        self.setCursor(Qt.CursorShape.PointingHandCursor if item is not None else Qt.CursorShape.ArrowCursor)
        self._refresh_style()

        if item is None:
            self._icon_label.clear()
            self._quantity_label.clear()
            self.setToolTip("Emplacement vide")
            return

        self.setToolTip(_item_tooltip(item))
        self._quantity_label.setText(str(item.quantity) if item.quantity > 1 else "")
        pixmap = _item_pixmap(item)
        if pixmap is None:
            self._icon_label.setText(item.name[:2].upper())
            return
        self._icon_label.setPixmap(
            pixmap.scaled(
                42,
                42,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self._refresh_style()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            if self._item_selected is not None:
                self._item_selected(self.item.id if self.item is not None else None)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.item is not None:
            if self._item_used is not None:
                self._item_used(self.item.id)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _refresh_style(self) -> None:
        self.style().unpolish(self)
        self.style().polish(self)


def _item_tooltip(item: InventoryItem) -> str:
    if item.quantity > 1:
        return f"{item.name} x{item.quantity}"
    return item.name


def _item_pixmap(item: InventoryItem) -> QPixmap | None:
    if item.icon_path is None:
        return None
    path = Path(item.icon_path)
    if not path.exists():
        return None
    pixmap = QPixmap(str(path))
    return None if pixmap.isNull() else pixmap


_INVENTORY_QSS = f"""
QWidget#InventoryGrid {{
    background: #111113;
    border: 1px solid #343337;
    border-radius: 6px;
}}

QWidget#InventorySlot {{
    background: #171719;
    border: 1px solid #343337;
    border-radius: 6px;
}}

QWidget#InventorySlot:hover {{
    border-color: {COLORS["accent"]};
    background: #1d1d20;
}}

QWidget#InventorySlot:focus {{
    border-color: {COLORS["focus"]};
}}

QWidget#InventorySlot[empty="false"] {{
    background: {COLORS["panel"]};
}}

QWidget#InventorySlot[selected="true"] {{
    background: {COLORS["panel_alt"]};
    border-color: {COLORS["focus"]};
}}

QFrame#InventoryDetails {{
    background: {COLORS["panel"]};
    border: 1px solid #3a3938;
    border-radius: 6px;
}}

QLabel#InventoryDetailsIcon {{
    background: #111113;
    border: 1px solid #3a3938;
    border-radius: 6px;
    color: {COLORS["focus"]};
    font-size: 18px;
    font-weight: 700;
}}

QLabel#InventoryDetailsName {{
    background: transparent;
    color: {COLORS["text"]};
    font-size: 13px;
    font-weight: 700;
}}

QLabel#InventoryDetailsDescription {{
    background: transparent;
    color: {COLORS["muted"]};
}}

QLabel#InventoryQuantity {{
    background: transparent;
    color: {COLORS["focus"]};
    font-size: 10px;
    font-weight: 700;
}}
"""
