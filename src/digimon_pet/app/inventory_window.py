from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from digimon_pet.app.theme import APP_QSS, COLORS


@dataclass(frozen=True)
class InventoryItem:
    id: str
    name: str
    quantity: int = 1
    icon_path: str | None = None
    description: str = "Usable item"
    item_type: str = "consumable"
    usable: bool = True
    unavailable_reason: str = ""
    effect_text: str = ""
    dangerous: bool = False


class InventoryWindow(QDialog):
    _DEFAULT_SLOT_COUNT = 24
    _COLUMNS = 4
    _GHOST_SLOT_COUNT = 4
    _MIN_VISIBLE_SLOT_COUNT = 6

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
        self._items: list[InventoryItem] = []
        self._active_filter = "all"
        self._slot_count = slot_count

        self.setWindowTitle("Inventory")
        self.setMinimumSize(600, 360)
        self.setStyleSheet(APP_QSS + _INVENTORY_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        title = QLabel("DIGIVICE STORAGE", self)
        title.setObjectName("Title")
        header.addWidget(title)
        header.addStretch(1)
        self._inventory_count = QLabel(f"0 / {slot_count}", self)
        self._inventory_count.setObjectName("InventoryCount")
        header.addWidget(self._inventory_count)
        layout.addLayout(header)

        filters = QHBoxLayout()
        filters.setContentsMargins(0, 0, 0, 0)
        filters.setSpacing(6)
        self._filter_group = QButtonGroup(self)
        self._filter_group.setExclusive(True)
        for filter_id, label in (
            ("all", "All"),
            ("consumable", "Stats"),
            ("evolution", "Evolution"),
            ("special", "Special"),
        ):
            button = QToolButton(self)
            button.setText(label)
            button.setCheckable(True)
            button.setObjectName("InventoryFilter")
            button.clicked.connect(lambda checked=False, value=filter_id: self.set_filter(value))
            self._filter_group.addButton(button)
            filters.addWidget(button)
            if filter_id == "all":
                button.setChecked(True)
        filters.addStretch(1)
        layout.addLayout(filters)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(8)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setMinimumHeight(224)
        scroll_area.setMaximumHeight(270)

        grid_host = QWidget(self)
        grid_host.setObjectName("InventoryGrid")
        grid_host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

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
        details_layout.setContentsMargins(10, 10, 10, 10)
        details_layout.setSpacing(6)

        scan_title = QLabel("ITEM SCAN", details)
        scan_title.setObjectName("InventoryScanTitle")
        scan_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        details_layout.addWidget(scan_title)

        self._details_icon = QLabel(details)
        self._details_icon.setObjectName("InventoryDetailsIcon")
        self._details_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._details_icon.setFixedSize(QSize(74, 74))
        details_layout.addWidget(self._details_icon, 0, Qt.AlignmentFlag.AlignHCenter)

        self._details_name = QLabel("No item", details)
        self._details_name.setObjectName("InventoryDetailsName")
        self._details_name.setWordWrap(True)
        self._details_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        details_layout.addWidget(self._details_name)

        self._details_status = QLabel("", details)
        self._details_status.setObjectName("InventoryStatus")
        self._details_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._details_status.setWordWrap(True)
        details_layout.addWidget(self._details_status)

        self._details_description = QLabel("", details)
        self._details_description.setObjectName("InventoryDetailsDescription")
        self._details_description.setWordWrap(True)
        self._details_description.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        details_layout.addWidget(self._details_description, 1)

        details_layout.addStretch(1)

        self._use_button = QPushButton("Use", details)
        self._use_button.setEnabled(False)
        self._use_button.clicked.connect(self._use_selected_item)
        details_layout.addWidget(self._use_button)

        body.addWidget(details)
        layout.addLayout(body, 1)
        self._refresh_details()

    def set_items(self, items: list[InventoryItem]) -> None:
        self._items = list(items)
        self._inventory_count.setText(f"{len(self._items)} / {self._slot_count}")
        self._render_slots()

    def set_filter(self, filter_id: str) -> None:
        self._active_filter = filter_id
        for button in self._filter_group.buttons():
            if button.text() == _filter_label(filter_id):
                button.setChecked(True)
        self._render_slots()

    def _render_slots(self) -> None:
        visible_items = [item for item in self._items if _matches_filter(item, self._active_filter)]
        visible_slot_count = _visible_slot_count(len(visible_items), self._slot_count)
        for index, slot in enumerate(self._slots):
            slot.set_item(visible_items[index] if index < len(visible_items) else None)
            slot.setVisible(index < visible_slot_count)
        if self._selected_item_id not in {item.id for item in visible_items}:
            self._selected_item_id = visible_items[0].id if visible_items else None
        self._refresh_selection()

    def _use_item(self, item_id: str) -> None:
        if self._item_used is not None:
            self._item_used(item_id)

    def _select_item(self, item_id: str | None) -> None:
        self._selected_item_id = item_id
        self._refresh_selection()

    def _use_selected_item(self) -> None:
        selected_item = self._selected_item()
        if selected_item is not None and selected_item.usable:
            self._use_item(selected_item.id)

    def _selected_item(self) -> InventoryItem | None:
        return next((item for item in self._items if item.id == self._selected_item_id), None)

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
            self._details_name.setText("No item")
            self._details_status.setText("")
            self._details_status.setProperty("state", "neutral")
            self._details_status.style().unpolish(self._details_status)
            self._details_status.style().polish(self._details_status)
            self._details_description.setText("")
            self._use_button.setText("Use")
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
                    58,
                    58,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        self._details_name.setText(item.name)
        self._details_status.setText(_item_type_label(item))
        self._details_status.setProperty("state", _item_state(item))
        self._details_status.style().unpolish(self._details_status)
        self._details_status.style().polish(self._details_status)
        self._details_description.setText(item.description)
        self._use_button.setText("Confirm" if item.dangerous else "Use")
        self._use_button.setEnabled(item.usable)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._use_selected_item()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            event.accept()
            return
        super().keyPressEvent(event)


class InventorySlotWidget(QWidget):
    _SIZE = QSize(86, 92)

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
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(self._SIZE)
        self.setProperty("empty", True)
        self.setProperty("selected", False)
        self.setProperty("usable", True)
        self.setProperty("dangerous", False)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setToolTip("Empty slot")
        self.setCursor(Qt.CursorShape.ArrowCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(3)

        self._type_label = QLabel("", self)
        self._type_label.setObjectName("InventorySlotType")
        self._type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._type_label.setFixedHeight(15)
        layout.addWidget(self._type_label)

        self._icon_label = QLabel(self)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setFixedHeight(36)
        layout.addWidget(self._icon_label)

        self._name_label = QLabel("", self)
        self._name_label.setObjectName("InventorySlotName")
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name_label.setWordWrap(True)
        self._name_label.setFixedHeight(26)
        layout.addWidget(self._name_label)

        self._quantity_label = QLabel("", self)
        self._quantity_label.setObjectName("InventoryQuantity")
        self._quantity_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._quantity_label.setFixedSize(QSize(20, 20))
        self._quantity_label.hide()

    def set_item(self, item: InventoryItem | None) -> None:
        self.item = item
        self.setProperty("empty", item is None)
        self.setProperty("usable", True if item is None else item.usable)
        self.setProperty("dangerous", False if item is None else item.dangerous)
        self.setCursor(Qt.CursorShape.PointingHandCursor if item is not None else Qt.CursorShape.ArrowCursor)
        self._refresh_style()

        if item is None:
            self._icon_label.clear()
            self._name_label.clear()
            self._type_label.clear()
            self._type_label.setVisible(False)
            self._quantity_label.clear()
            self._quantity_label.setVisible(False)
            self.setToolTip("Empty slot")
            return

        self.setToolTip(_item_tooltip(item))
        self._name_label.setText(_short_item_name(item.name))
        self._type_label.setText(_slot_type_label(item))
        self._type_label.setVisible(True)
        self._quantity_label.setText(str(item.quantity))
        self._quantity_label.setVisible(True)
        self._position_quantity_badge()
        pixmap = _item_pixmap(item)
        if pixmap is None:
            self._icon_label.setPixmap(QPixmap())
            self._icon_label.setText(item.name[:2].upper())
            return
        self._icon_label.setText("")
        self._icon_label.setPixmap(
            pixmap.scaled(
                44,
                36,
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
        if event.button() == Qt.MouseButton.LeftButton and self.item is not None and self.item.usable:
            if self._item_used is not None:
                self._item_used(self.item.id)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _refresh_style(self) -> None:
        self.style().unpolish(self)
        self.style().polish(self)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._position_quantity_badge()

    def _position_quantity_badge(self) -> None:
        margin = 4
        self._quantity_label.move(
            self.width() - self._quantity_label.width() - margin,
            self.height() - self._quantity_label.height() - margin,
        )


def _item_tooltip(item: InventoryItem) -> str:
    suffix = "Double-click to use" if item.usable else ""
    name = f"{item.name} x{item.quantity}" if item.quantity > 1 else item.name
    return f"{name}\n{suffix}" if suffix else name


def _matches_filter(item: InventoryItem, filter_id: str) -> bool:
    if filter_id == "all":
        return True
    if filter_id == "special":
        return item.item_type not in {"consumable", "evolution"} or item.dangerous
    return item.item_type == filter_id


def _filter_label(filter_id: str) -> str:
    return {
        "all": "All",
        "consumable": "Stats",
        "evolution": "Evolution",
        "special": "Special",
    }.get(filter_id, "All")


def _visible_slot_count(item_count: int, slot_count: int) -> int:
    if slot_count <= 0:
        return 0
    if item_count <= 0:
        return min(slot_count, InventoryWindow._MIN_VISIBLE_SLOT_COUNT)
    return min(
        slot_count,
        max(item_count + InventoryWindow._GHOST_SLOT_COUNT, InventoryWindow._MIN_VISIBLE_SLOT_COUNT),
    )


def _slot_type_label(item: InventoryItem) -> str:
    if item.dangerous:
        return "DANGER"
    return {
        "consumable": "STAT",
        "evolution": "EVO",
        "key_item": "KEY",
        "misc": "DATA",
    }.get(item.item_type, "DATA")


def _short_item_name(name: str) -> str:
    return name if len(name) <= 16 else f"{name[:14]}.."


def _item_type_label(item: InventoryItem) -> str:
    prefix = "Danger" if item.dangerous else {
        "consumable": "Stats",
        "evolution": "Evolution",
        "key_item": "Key Item",
        "misc": "Special",
    }.get(item.item_type, "Special")
    if not item.usable and item.unavailable_reason:
        return f"{prefix} - unavailable"
    return prefix


def _item_state(item: InventoryItem) -> str:
    if not item.usable:
        return "blocked"
    if item.dangerous:
        return "danger"
    if item.item_type == "evolution":
        return "evolution"
    return "ready"


def _item_pixmap(item: InventoryItem) -> QPixmap | None:
    if item.icon_path is None:
        return None
    path = Path(item.icon_path)
    if not path.exists():
        return None
    pixmap = QPixmap(str(path))
    return None if pixmap.isNull() else pixmap


_INVENTORY_QSS = f"""
QLabel#InventoryCount {{
    background: {COLORS["surface_alt"]};
    border: 2px solid {COLORS["accent"]};
    border-radius: 2px;
    color: {COLORS["focus"]};
    font-weight: 900;
    padding: 4px 8px;
}}

QToolButton#InventoryFilter {{
    background: {COLORS["surface_alt"]};
    border: 2px solid {COLORS["line"]};
    border-radius: 2px;
    color: {COLORS["muted"]};
    font-weight: 900;
    padding: 6px 10px;
}}

QToolButton#InventoryFilter:hover {{
    border-color: {COLORS["accent"]};
    color: {COLORS["text"]};
}}

QToolButton#InventoryFilter:checked {{
    background: {COLORS["panel_alt"]};
    border-color: {COLORS["accent"]};
    color: {COLORS["focus"]};
}}

QWidget#InventoryGrid {{
    background: {COLORS["surface"]};
    border: 2px solid {COLORS["line_soft"]};
    border-top-color: {COLORS["accent"]};
    border-radius: 2px;
}}

QWidget#InventorySlot {{
    background: {COLORS["panel"]};
    border: 2px solid {COLORS["line"]};
    border-radius: 2px;
}}

QWidget#InventorySlot:hover {{
    border-color: {COLORS["accent"]};
    background: {COLORS["panel_hot"]};
}}

QWidget#InventorySlot:focus {{
    border-color: {COLORS["focus"]};
}}

QWidget#InventorySlot[empty="false"] {{
    background: {COLORS["panel_alt"]};
    border-color: {COLORS["accent_soft"]};
}}

QWidget#InventorySlot[empty="true"] {{
    background: {COLORS["surface_alt"]};
    border: 2px dashed {COLORS["line"]};
}}

QWidget#InventorySlot[usable="false"] {{
    background: {COLORS["surface_alt"]};
    border-color: {COLORS["focus_soft"]};
}}

QWidget#InventorySlot[dangerous="true"] {{
    border-color: {COLORS["danger"]};
}}

QWidget#InventorySlot[selected="true"] {{
    background: {COLORS["panel_hot"]};
    border-color: {COLORS["focus"]};
}}

QLabel#InventorySlotType {{
    background: {COLORS["surface_alt"]};
    border: 2px solid {COLORS["accent_soft"]};
    border-radius: 2px;
    color: {COLORS["accent"]};
    font-size: 9px;
    font-weight: 900;
    padding: 0px 3px;
}}

QLabel#InventorySlotName {{
    color: {COLORS["text"]};
    font-size: 10px;
    font-weight: 800;
}}

QFrame#InventoryDetails {{
    background: {COLORS["panel"]};
    border: 2px solid {COLORS["line"]};
    border-top-color: {COLORS["accent"]};
    border-radius: 2px;
}}

QLabel#InventoryScanTitle {{
    color: {COLORS["accent"]};
    font-size: 10px;
    font-weight: 900;
    letter-spacing: 0px;
}}

QLabel#InventoryDetailsIcon {{
    background: {COLORS["surface_alt"]};
    border: 2px solid {COLORS["accent_soft"]};
    border-radius: 2px;
    color: {COLORS["focus"]};
    font-size: 18px;
    font-weight: 900;
}}

QLabel#InventoryDetailsName {{
    background: transparent;
    color: {COLORS["text"]};
    font-size: 13px;
    font-weight: 800;
}}

QLabel#InventoryStatus {{
    background: {COLORS["surface_alt"]};
    border: 2px solid {COLORS["line"]};
    border-radius: 2px;
    color: {COLORS["muted"]};
    font-weight: 900;
    padding: 4px 7px;
}}

QLabel#InventoryStatus[state="ready"] {{
    color: {COLORS["success"]};
    border-color: #2f7a48;
}}

QLabel#InventoryStatus[state="evolution"] {{
    color: {COLORS["focus"]};
    border-color: #725f2b;
}}

QLabel#InventoryStatus[state="danger"] {{
    color: {COLORS["danger"]};
    border-color: {COLORS["danger_soft"]};
}}

QLabel#InventoryStatus[state="blocked"] {{
    color: {COLORS["muted"]};
    border-color: #5b5140;
}}

QLabel#InventoryEffect {{
    background: {COLORS["surface_alt"]};
    border: 2px solid {COLORS["accent_soft"]};
    border-radius: 2px;
    color: {COLORS["focus"]};
    font-weight: 900;
    padding: 7px 9px;
}}

QLabel#InventoryDetailsDescription {{
    background: transparent;
    color: {COLORS["muted"]};
}}

QLabel#InventoryQuantity {{
    background: {COLORS["surface_alt"]};
    border: 2px solid {COLORS["focus_soft"]};
    border-radius: 10px;
    color: {COLORS["focus"]};
    font-size: 10px;
    font-weight: 900;
    padding: 0px;
}}
"""
