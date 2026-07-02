from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from digimon_pet.app.theme import APP_QSS, COLORS
from digimon_pet.domain.items import ItemCatalog, ItemDefinition
from digimon_pet.domain.models import MarketListingState


@dataclass(frozen=True)
class FriendMarketListing:
    address: str
    trainer_name: str
    listing_id: str
    item_id: str
    item_name: str
    price_bits: int
    online: bool = True


class ShopWindow(QDialog):
    def __init__(
        self,
        *,
        buy_shop_item: Callable[[str], None],
        create_listing: Callable[[str, int], None],
        cancel_listing: Callable[[str], None],
        buy_friend_listing: Callable[[str, str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._buy_shop_item = buy_shop_item
        self._create_listing = create_listing
        self._cancel_listing = cancel_listing
        self._buy_friend_listing = buy_friend_listing
        self._catalog: ItemCatalog | None = None
        self._inventory: dict[str, int] = {}
        self._listings: list[MarketListingState] = []
        self._friend_listings: list[FriendMarketListing] = []
        self._bits = 0
        self._selected_listing_item_id: str | None = None

        self.setWindowTitle("Shop")
        self.setMinimumSize(680, 430)
        self.setStyleSheet(APP_QSS + _SHOP_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("DIGI SHOP", self)
        title.setObjectName("Title")
        header.addWidget(title)
        header.addStretch(1)
        self._bits_label = QLabel("100 Bits", self)
        self._bits_label.setObjectName("ShopBits")
        header.addWidget(self._bits_label)
        layout.addLayout(header)

        self._status_label = QLabel("", self)
        self._status_label.setObjectName("Muted")
        layout.addWidget(self._status_label)

        self._tabs = QTabWidget(self)
        self._tabs.addTab(self._build_shop_tab(), "Shop")
        self._tabs.addTab(self._build_my_listings_tab(), "My Listings")
        self._tabs.addTab(self._build_friends_tab(), "Friends")
        layout.addWidget(self._tabs, 1)

    def set_status(self, text: str) -> None:
        self._status_label.setText(text)

    def set_data(
        self,
        *,
        bits: int,
        catalog: ItemCatalog,
        inventory: dict[str, int],
        listings: list[MarketListingState],
        friend_listings: list[FriendMarketListing],
    ) -> None:
        self._bits = int(bits)
        self._catalog = catalog
        self._inventory = dict(inventory)
        self._listings = list(listings)
        self._friend_listings = list(friend_listings)
        self._bits_label.setText(f"{self._bits} Bits")
        self._render_shop_table()
        self._render_inventory_table()
        self._render_listing_table()
        self._render_friend_table()

    def _build_shop_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        self._shop_table = QTableWidget(0, 4, tab)
        self._shop_table.setHorizontalHeaderLabels(["Item", "Price", "Owned", "Buy"])
        self._shop_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._shop_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._shop_table)
        return tab

    def _build_my_listings_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QHBoxLayout(tab)
        layout.setSpacing(8)

        inventory_panel = QFrame(tab)
        inventory_panel.setObjectName("StatsPanel")
        inventory_layout = QVBoxLayout(inventory_panel)
        inventory_title = QLabel("Choose Item To Sell", inventory_panel)
        inventory_title.setObjectName("SectionTitle")
        inventory_layout.addWidget(inventory_title)
        self._inventory_table = QTableWidget(0, 3, inventory_panel)
        self._inventory_table.setHorizontalHeaderLabels(["Item", "Owned", "Suggested"])
        self._inventory_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._inventory_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._inventory_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._inventory_table.itemSelectionChanged.connect(self._refresh_listing_form)
        self._inventory_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._inventory_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._inventory_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        inventory_layout.addWidget(self._inventory_table)
        layout.addWidget(inventory_panel, 1)

        action_panel = QFrame(tab)
        action_panel.setObjectName("StatsPanel")
        action_layout = QVBoxLayout(action_panel)
        action_title = QLabel("Selected Item", action_panel)
        action_title.setObjectName("SectionTitle")
        action_layout.addWidget(action_title)
        self._selected_item_name_label = QLabel("Select an item", action_panel)
        self._selected_item_name_label.setObjectName("ShopSelectedName")
        self._selected_item_name_label.setWordWrap(True)
        action_layout.addWidget(self._selected_item_name_label)
        self._selected_item_hint_label = QLabel("Pick one owned item on the left.", action_panel)
        self._selected_item_hint_label.setObjectName("Muted")
        self._selected_item_hint_label.setWordWrap(True)
        action_layout.addWidget(self._selected_item_hint_label)
        price_grid = QGridLayout()
        price_grid.setColumnStretch(1, 1)
        price_grid.addWidget(QLabel("Price", action_panel), 0, 0)
        self._listing_price_input = QSpinBox(action_panel)
        self._listing_price_input.setRange(1, 999999)
        self._listing_price_input.setMinimumWidth(110)
        price_grid.addWidget(self._listing_price_input, 0, 1)
        action_layout.addLayout(price_grid)
        self._list_selected_button = QPushButton("List item", action_panel)
        self._list_selected_button.setObjectName("PrimaryButton")
        self._list_selected_button.setEnabled(False)
        self._list_selected_button.clicked.connect(self._list_selected_item)
        action_layout.addWidget(self._list_selected_button)
        action_layout.addStretch(1)
        layout.addWidget(action_panel)

        listing_panel = QFrame(tab)
        listing_panel.setObjectName("StatsPanel")
        listing_layout = QVBoxLayout(listing_panel)
        listing_layout.addWidget(QLabel("Active Listings", listing_panel))
        self._listing_table = QTableWidget(0, 4, listing_panel)
        self._listing_table.setHorizontalHeaderLabels(["Item", "Price", "Created", "Cancel"])
        self._listing_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        listing_layout.addWidget(self._listing_table)
        layout.addWidget(listing_panel, 1)
        return tab

    def _build_friends_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        self._friend_table = QTableWidget(0, 5, tab)
        self._friend_table.setHorizontalHeaderLabels(["Trainer", "Item", "Price", "Status", "Buy"])
        self._friend_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._friend_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._friend_table)
        return tab

    def _render_shop_table(self) -> None:
        items = self._shop_items()
        self._shop_table.setRowCount(len(items))
        for row, item in enumerate(items):
            self._set_item(self._shop_table, row, 0, item.name, item.icon_path)
            self._shop_table.setItem(row, 1, _table_item(f"{item.shop_price_bits} Bits", item.shop_price_bits or 0))
            self._shop_table.setItem(row, 2, _table_item(str(self._inventory.get(item.id, 0)), self._inventory.get(item.id, 0)))
            button = QPushButton("Buy", self._shop_table)
            button.setEnabled(item.shop_price_bits is not None and self._bits >= item.shop_price_bits)
            button.clicked.connect(lambda checked=False, item_id=item.id: self._buy_shop_item(item_id))
            self._shop_table.setCellWidget(row, 3, button)
        self._shop_table.resizeColumnsToContents()

    def _render_inventory_table(self) -> None:
        items = [
            item for item in self._known_inventory_items()
            if self._inventory.get(item.id, 0) > 0
        ]
        self._inventory_table.setRowCount(len(items))
        for row, item in enumerate(items):
            suggested = _suggested_market_price(item)
            self._set_item(self._inventory_table, row, 0, item.name, item.icon_path)
            self._inventory_table.item(row, 0).setData(Qt.ItemDataRole.UserRole + 1, item.id)
            self._inventory_table.setItem(row, 1, _table_item(str(self._inventory.get(item.id, 0)), self._inventory.get(item.id, 0)))
            self._inventory_table.setItem(
                row,
                2,
                _table_item(f"{suggested} Bits" if suggested is not None else "No suggestion", suggested or 0),
            )
        if self._selected_listing_item_id not in {item.id for item in items}:
            self._selected_listing_item_id = items[0].id if items else None
        self._restore_inventory_selection()
        self._refresh_listing_form()
        self._inventory_table.resizeColumnsToContents()

    def _render_listing_table(self) -> None:
        self._listing_table.setRowCount(len(self._listings))
        for row, listing in enumerate(self._listings):
            item = self._catalog.items.get(listing.item_id) if self._catalog is not None else None
            self._listing_table.setItem(row, 0, _table_item(item.name if item else listing.item_id))
            self._listing_table.setItem(row, 1, _table_item(f"{listing.price_bits} Bits", listing.price_bits))
            self._listing_table.setItem(row, 2, _table_item(str(listing.created_at), listing.created_at))
            button = QPushButton("Cancel", self._listing_table)
            button.clicked.connect(lambda checked=False, listing_id=listing.id: self._cancel_listing(listing_id))
            self._listing_table.setCellWidget(row, 3, button)
        self._listing_table.resizeColumnsToContents()

    def _render_friend_table(self) -> None:
        self._friend_table.setRowCount(len(self._friend_listings))
        for row, listing in enumerate(self._friend_listings):
            self._friend_table.setItem(row, 0, _table_item(listing.trainer_name))
            self._friend_table.setItem(row, 1, _table_item(listing.item_name))
            self._friend_table.setItem(row, 2, _table_item(f"{listing.price_bits} Bits", listing.price_bits))
            self._friend_table.setItem(row, 3, _table_item("Online" if listing.online else "Offline"))
            button = QPushButton("Buy", self._friend_table)
            button.setEnabled(listing.online and self._bits >= listing.price_bits)
            button.clicked.connect(
                lambda checked=False, address=listing.address, listing_id=listing.listing_id:
                self._buy_friend_listing(address, listing_id)
            )
            self._friend_table.setCellWidget(row, 4, button)
        self._friend_table.resizeColumnsToContents()

    def _shop_items(self) -> list[ItemDefinition]:
        if self._catalog is None:
            return []
        return sorted(
            (item for item in self._catalog.items.values() if item.shop_price_bits is not None),
            key=lambda item: (item.shop_price_bits or 0, item.name.casefold()),
        )

    def _known_inventory_items(self) -> list[ItemDefinition]:
        if self._catalog is None:
            return []
        return sorted(
            (
                item for item in self._catalog.items.values()
                if self._inventory.get(item.id, 0) > 0
            ),
            key=lambda item: item.name.casefold(),
        )

    def _selected_inventory_item(self) -> ItemDefinition | None:
        if self._catalog is None:
            return None
        selected_rows = {index.row() for index in self._inventory_table.selectedIndexes()}
        if selected_rows:
            row = min(selected_rows)
            item = self._inventory_table.item(row, 0)
            if item is not None:
                item_id = str(item.data(Qt.ItemDataRole.UserRole + 1) or "")
                self._selected_listing_item_id = item_id or None
        if self._selected_listing_item_id is None:
            return None
        return self._catalog.items.get(self._selected_listing_item_id)

    def _restore_inventory_selection(self) -> None:
        if self._selected_listing_item_id is None:
            self._inventory_table.clearSelection()
            return
        for row in range(self._inventory_table.rowCount()):
            item = self._inventory_table.item(row, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole + 1) == self._selected_listing_item_id:
                self._inventory_table.selectRow(row)
                return

    def _refresh_listing_form(self) -> None:
        item = self._selected_inventory_item()
        if item is None:
            self._selected_item_name_label.setText("Select an item")
            self._selected_item_hint_label.setText("Pick one owned item on the left.")
            self._listing_price_input.setValue(1)
            self._list_selected_button.setEnabled(False)
            return
        suggested = _suggested_market_price(item)
        self._selected_item_name_label.setText(item.name)
        self._selected_item_hint_label.setText(
            f"Suggested price: {suggested} Bits." if suggested is not None else "No suggested price for this item."
        )
        self._listing_price_input.setValue(suggested or 1)
        self._list_selected_button.setEnabled(True)

    def _list_selected_item(self) -> None:
        item = self._selected_inventory_item()
        if item is None:
            return
        self._create_listing(item.id, self._listing_price_input.value())

    def _set_item(self, table: QTableWidget, row: int, column: int, text: str, icon_path: str | None = None) -> None:
        item = _table_item(text)
        if icon_path:
            pixmap = QPixmap(str(Path(icon_path)))
            if not pixmap.isNull():
                item.setIcon(QIcon(pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio)))
        table.setItem(row, column, item)


def _table_item(text: str, sort_value: int | str | None = None) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setData(Qt.ItemDataRole.UserRole, text if sort_value is None else sort_value)
    return item


def _suggested_market_price(item: ItemDefinition) -> int | None:
    return item.suggested_market_price_bits or item.shop_price_bits


_SHOP_QSS = f"""
QLabel#ShopBits {{
    background: {COLORS["surface_alt"]};
    border: 2px solid {COLORS["focus"]};
    border-radius: 2px;
    color: {COLORS["focus"]};
    font-weight: 900;
    padding: 5px 10px;
}}

QLabel#ShopSelectedName {{
    color: {COLORS["text"]};
    font-size: 14px;
    font-weight: 900;
}}
"""
