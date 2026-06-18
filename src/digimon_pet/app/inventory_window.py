from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QGridLayout, QLabel, QVBoxLayout, QWidget

from digimon_pet.app.theme import APP_QSS, COLORS


@dataclass(frozen=True)
class InventoryItem:
    id: str
    name: str
    quantity: int = 1
    icon_path: str | None = None


class InventoryWindow(QDialog):
    _DEFAULT_SLOT_COUNT = 24
    _COLUMNS = 6

    def __init__(
        self,
        slot_count: int = _DEFAULT_SLOT_COUNT,
        item_used: Callable[[str], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._slots: list[InventorySlotWidget] = []
        self._item_used = item_used

        self.setWindowTitle("Inventaire")
        self.setMinimumSize(430, 320)
        self.setStyleSheet(APP_QSS + _INVENTORY_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("Inventaire", self)
        title.setObjectName("Title")
        layout.addWidget(title)

        grid_host = QWidget(self)
        grid_host.setObjectName("InventoryGrid")
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        for index in range(slot_count):
            slot = InventorySlotWidget(self._use_item, grid_host)
            self._slots.append(slot)
            grid.addWidget(slot, index // self._COLUMNS, index % self._COLUMNS)

        layout.addWidget(grid_host)
        layout.addStretch(1)

    def set_items(self, items: list[InventoryItem]) -> None:
        for index, slot in enumerate(self._slots):
            slot.set_item(items[index] if index < len(items) else None)

    def _use_item(self, item_id: str) -> None:
        if self._item_used is not None:
            self._item_used(item_id)


class InventorySlotWidget(QWidget):
    _SIZE = QSize(58, 58)

    def __init__(
        self,
        item_used: Callable[[str], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.item: InventoryItem | None = None
        self._item_used = item_used
        self.setObjectName("InventorySlot")
        self.setFixedSize(self._SIZE)
        self.setProperty("empty", True)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setToolTip("Emplacement vide")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        self._icon_label = QLabel(self)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setFixedHeight(30)
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
        self.style().unpolish(self)
        self.style().polish(self)

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
                30,
                30,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.item is not None:
            if self._item_used is not None:
                self._item_used(self.item.id)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


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
    background: transparent;
}}

QWidget#InventorySlot {{
    background: #111113;
    border: 1px solid #3a3938;
    border-radius: 6px;
}}

QWidget#InventorySlot:hover {{
    border-color: {COLORS["accent"]};
}}

QWidget#InventorySlot:focus {{
    border-color: {COLORS["focus"]};
}}

QWidget#InventorySlot[empty="false"] {{
    background: {COLORS["panel"]};
}}

QLabel#InventoryQuantity {{
    background: transparent;
    color: {COLORS["focus"]};
    font-size: 10px;
    font-weight: 700;
}}
"""
