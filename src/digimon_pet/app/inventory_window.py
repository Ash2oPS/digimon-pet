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
    description: str = "Objet utilisable"
    item_type: str = "consumable"
    usable: bool = True
    unavailable_reason: str = ""
    effect_text: str = ""
    dangerous: bool = False


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
        self._items: list[InventoryItem] = []
        self._active_filter = "all"
        self._slot_count = slot_count

        self.setWindowTitle("Inventaire")
        self.setMinimumSize(700, 460)
        self.setStyleSheet(APP_QSS + _INVENTORY_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Inventaire", self)
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
            ("all", "Tous"),
            ("consumable", "Stats"),
            ("evolution", "Evolution"),
            ("special", "Speciaux"),
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
        body.setSpacing(12)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        grid_host = QWidget(self)
        grid_host.setObjectName("InventoryGrid")
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(14, 14, 14, 14)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        for index in range(slot_count):
            slot = InventorySlotWidget(self._select_item, self._use_item, grid_host)
            self._slots.append(slot)
            grid.addWidget(slot, index // self._COLUMNS, index % self._COLUMNS)

        scroll_area.setWidget(grid_host)
        body.addWidget(scroll_area, 1)

        details = QFrame(self)
        details.setObjectName("InventoryDetails")
        details.setFixedWidth(220)
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

        self._details_status = QLabel("", details)
        self._details_status.setObjectName("InventoryStatus")
        self._details_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._details_status.setWordWrap(True)
        details_layout.addWidget(self._details_status)

        self._details_effect = QLabel("", details)
        self._details_effect.setObjectName("InventoryEffect")
        self._details_effect.setWordWrap(True)
        self._details_effect.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        details_layout.addWidget(self._details_effect)

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
        for index, slot in enumerate(self._slots):
            slot.set_item(visible_items[index] if index < len(visible_items) else None)
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
            self._details_name.setText("Aucun objet")
            self._details_quantity.setText("")
            self._details_status.setText("")
            self._details_status.setProperty("state", "neutral")
            self._details_status.style().unpolish(self._details_status)
            self._details_status.style().polish(self._details_status)
            self._details_effect.setText("")
            self._details_description.setText("Les objets disponibles apparaissent dans la grille.")
            self._use_button.setText("Utiliser")
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
        self._details_status.setText(_item_type_label(item))
        self._details_status.setProperty("state", _item_state(item))
        self._details_status.style().unpolish(self._details_status)
        self._details_status.style().polish(self._details_status)
        self._details_effect.setText(item.unavailable_reason or item.effect_text)
        self._details_description.setText(item.description)
        self._use_button.setText("Confirmer" if item.dangerous else "Utiliser")
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
    _SIZE = QSize(78, 78)

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
        self.setProperty("usable", True)
        self.setProperty("dangerous", False)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setToolTip("Emplacement vide")
        self.setCursor(Qt.CursorShape.ArrowCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(7, 7, 7, 7)
        layout.setSpacing(2)

        self._icon_label = QLabel(self)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setFixedHeight(48)
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
        self.setProperty("usable", True if item is None else item.usable)
        self.setProperty("dangerous", False if item is None else item.dangerous)
        self.setCursor(Qt.CursorShape.PointingHandCursor if item is not None else Qt.CursorShape.ArrowCursor)
        self._refresh_style()

        if item is None:
            self._icon_label.clear()
            self._quantity_label.clear()
            self._quantity_label.setVisible(False)
            self.setToolTip("Emplacement vide")
            return

        self.setToolTip(_item_tooltip(item))
        self._quantity_label.setText(str(item.quantity) if item.quantity > 1 else "")
        self._quantity_label.setVisible(item.quantity > 1)
        pixmap = _item_pixmap(item)
        if pixmap is None:
            self._icon_label.setText(item.name[:2].upper())
            return
        self._icon_label.setPixmap(
            pixmap.scaled(
                48,
                48,
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


def _item_tooltip(item: InventoryItem) -> str:
    suffix = "Double-clic pour utiliser" if item.usable else item.unavailable_reason
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
        "all": "Tous",
        "consumable": "Stats",
        "evolution": "Evolution",
        "special": "Speciaux",
    }.get(filter_id, "Tous")


def _item_type_label(item: InventoryItem) -> str:
    prefix = "Dangereux" if item.dangerous else {
        "consumable": "Stats",
        "evolution": "Evolution",
        "key_item": "Objet cle",
        "misc": "Special",
    }.get(item.item_type, "Special")
    if not item.usable and item.unavailable_reason:
        return f"{prefix} - indisponible"
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
    border: 1px solid {COLORS["accent_soft"]};
    border-radius: 7px;
    color: {COLORS["focus"]};
    font-weight: 800;
    padding: 5px 9px;
}}

QToolButton#InventoryFilter {{
    background: {COLORS["surface_alt"]};
    border: 1px solid {COLORS["line"]};
    border-radius: 7px;
    color: {COLORS["muted"]};
    font-weight: 800;
    padding: 7px 12px;
}}

QToolButton#InventoryFilter:hover {{
    border-color: {COLORS["accent"]};
    color: {COLORS["text"]};
}}

QToolButton#InventoryFilter:checked {{
    background: {COLORS["panel_hot"]};
    border-color: {COLORS["focus"]};
    color: {COLORS["focus"]};
}}

QWidget#InventoryGrid {{
    background: {COLORS["surface_alt"]};
    border: 1px solid {COLORS["line"]};
    border-top-color: {COLORS["accent_soft"]};
    border-radius: 9px;
}}

QWidget#InventorySlot {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["line_soft"]};
    border-radius: 8px;
}}

QWidget#InventorySlot:hover {{
    border-color: {COLORS["accent"]};
    background: {COLORS["panel"]};
}}

QWidget#InventorySlot:focus {{
    border-color: {COLORS["focus"]};
}}

QWidget#InventorySlot[empty="false"] {{
    background: {COLORS["panel_alt"]};
    border-color: {COLORS["line"]};
}}

QWidget#InventorySlot[usable="false"] {{
    background: #101722;
    border-color: {COLORS["focus_soft"]};
}}

QWidget#InventorySlot[dangerous="true"] {{
    border-color: {COLORS["danger"]};
}}

QWidget#InventorySlot[selected="true"] {{
    background: {COLORS["panel_hot"]};
    border-color: {COLORS["focus"]};
}}

QFrame#InventoryDetails {{
    background: {COLORS["panel"]};
    border: 1px solid {COLORS["line"]};
    border-top-color: {COLORS["accent"]};
    border-radius: 9px;
}}

QLabel#InventoryDetailsIcon {{
    background: {COLORS["surface_alt"]};
    border: 1px solid {COLORS["accent_soft"]};
    border-radius: 8px;
    color: {COLORS["focus"]};
    font-size: 18px;
    font-weight: 800;
}}

QLabel#InventoryDetailsName {{
    background: transparent;
    color: {COLORS["text"]};
    font-size: 14px;
    font-weight: 700;
}}

QLabel#InventoryStatus {{
    background: {COLORS["surface_alt"]};
    border: 1px solid {COLORS["line"]};
    border-radius: 7px;
    color: {COLORS["muted"]};
    font-weight: 800;
    padding: 5px 8px;
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
    border: 1px solid {COLORS["accent_soft"]};
    border-radius: 7px;
    color: {COLORS["focus"]};
    font-weight: 800;
    padding: 7px 9px;
}}

QLabel#InventoryDetailsDescription {{
    background: transparent;
    color: {COLORS["muted"]};
}}

QLabel#InventoryQuantity {{
    background: {COLORS["surface_alt"]};
    border: 1px solid {COLORS["focus_soft"]};
    border-radius: 6px;
    color: {COLORS["focus"]};
    font-size: 10px;
    font-weight: 900;
    padding: 1px 5px;
}}
"""
