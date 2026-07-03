from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
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
        sell_shop_item: Callable[[str], None],
        create_listing: Callable[[str, int], None],
        cancel_listing: Callable[[str], None],
        buy_friend_listing: Callable[[str, str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._buy_shop_item = buy_shop_item
        self._sell_shop_item = sell_shop_item
        self._create_listing = create_listing
        self._cancel_listing = cancel_listing
        self._buy_friend_listing = buy_friend_listing
        self._catalog: ItemCatalog | None = None
        self._inventory: dict[str, int] = {}
        self._listings: list[MarketListingState] = []
        self._friend_listings: list[FriendMarketListing] = []
        self._bits = 0
        self._selected_listing_item_id: str | None = None
        self._listing_price_item_id: str | None = None

        self._shop_buy_buttons: dict[str, QPushButton] = {}
        self._shop_sell_buttons: dict[str, QPushButton] = {}
        self._sell_item_buttons: dict[str, QPushButton] = {}
        self._sell_value_labels: dict[str, QLabel] = {}
        self._listing_cancel_buttons: dict[str, QPushButton] = {}
        self._friend_buy_buttons: dict[str, QPushButton] = {}
        self._friend_icon_labels: dict[str, QLabel] = {}
        self._friend_price_labels: dict[str, QLabel] = {}

        self.setWindowTitle("Shop")
        self.setMinimumSize(760, 500)
        self.setStyleSheet(APP_QSS + _SHOP_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title_block = QVBoxLayout()
        title = QLabel("DIGI SHOP", self)
        title.setObjectName("Title")
        title_block.addWidget(title)
        self._summary_label = QLabel("Buy, sell, and browse friend listings.", self)
        self._summary_label.setObjectName("Muted")
        title_block.addWidget(self._summary_label)
        header.addLayout(title_block)
        header.addStretch(1)
        self._bits_label = QLabel("100 Bits", self)
        self._bits_label.setObjectName("ShopBits")
        header.addWidget(self._bits_label)
        layout.addLayout(header)

        self._status_label = QLabel("", self)
        self._status_label.setObjectName("Muted")
        layout.addWidget(self._status_label)

        self._tabs = QTabWidget(self)
        self._tabs.addTab(self._build_buy_tab(), "Buy Items")
        self._tabs.addTab(self._build_sell_tab(), "Sell Items")
        self._tabs.addTab(self._build_friends_tab(), "Friend Market")
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
        self._summary_label.setText(
            f"{len(self._buy_items())} shop items - {len(self._sell_items())} owned - "
            f"{len(self._friend_listings)} friend listings"
        )
        self._render_buy_items()
        self._render_sell_items()
        self._render_listing_cards()
        self._render_friend_cards()

    def _build_buy_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        header = QLabel("Buy fixed-price items", tab)
        header.setObjectName("SectionTitle")
        layout.addWidget(header)
        self._buy_items_layout = _card_grid_layout(tab, layout)
        return tab

    def _build_sell_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        owned_panel = _panel(tab, "Owned items")
        self._sell_items_layout = _card_grid_layout(owned_panel, owned_panel.layout())
        layout.addWidget(owned_panel, 2)

        action_panel = QFrame(tab)
        action_panel.setObjectName("ShopPanel")
        action_layout = QVBoxLayout(action_panel)
        action_layout.setSpacing(8)
        action_title = QLabel("Network listing", action_panel)
        action_title.setObjectName("SectionTitle")
        action_layout.addWidget(action_title)
        self._selected_item_name_label = QLabel("Select an item", action_panel)
        self._selected_item_name_label.setObjectName("ShopSelectedName")
        self._selected_item_name_label.setWordWrap(True)
        action_layout.addWidget(self._selected_item_name_label)
        self._selected_item_hint_label = QLabel("Pick one owned item.", action_panel)
        self._selected_item_hint_label.setObjectName("Muted")
        self._selected_item_hint_label.setWordWrap(True)
        action_layout.addWidget(self._selected_item_hint_label)
        price_grid = QGridLayout()
        price_grid.setColumnStretch(1, 1)
        price_grid.addWidget(QLabel("Price", action_panel), 0, 0)
        self._listing_price_input = QSpinBox(action_panel)
        self._listing_price_input.setRange(1, 999999)
        self._listing_price_input.setMinimumWidth(120)
        price_grid.addWidget(self._listing_price_input, 0, 1)
        action_layout.addLayout(price_grid)
        self._list_selected_button = QPushButton("List on market", action_panel)
        self._list_selected_button.setObjectName("PrimaryButton")
        self._list_selected_button.setEnabled(False)
        self._list_selected_button.clicked.connect(self._list_selected_item)
        action_layout.addWidget(self._list_selected_button)
        action_layout.addStretch(1)
        layout.addWidget(action_panel, 1)

        listing_panel = _panel(tab, "Active listings")
        self._listing_cards_layout = _card_grid_layout(listing_panel, listing_panel.layout())
        layout.addWidget(listing_panel, 2)
        return tab

    def _build_friends_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        header = QLabel("Friend Market", tab)
        header.setObjectName("SectionTitle")
        layout.addWidget(header)
        self._friend_grid_layout = _card_grid_layout(tab, layout)
        return tab

    def _render_buy_items(self) -> None:
        self._shop_buy_buttons = {}
        _clear_layout(self._buy_items_layout)
        items = self._buy_items()
        if not items:
            self._buy_items_layout.addWidget(_empty_state("No shop items available."), 0, 0, 1, _GRID_COLUMNS)
            return
        for index, item in enumerate(items):
            card = self._item_card(item)
            content = card.layout()
            price = QLabel(_format_bits(item.shop_price_bits or 0), card)
            price.setObjectName("ShopPrice")
            owned = QLabel(f"Owned: {self._inventory.get(item.id, 0)}", card)
            owned.setObjectName("Muted")
            button = QPushButton("Buy", card)
            button.setObjectName("PrimaryButton")
            can_buy = self._bits >= (item.shop_price_bits or 0)
            button.setEnabled(can_buy)
            button.setToolTip("" if can_buy else "Not enough Bits")
            button.clicked.connect(lambda checked=False, item_id=item.id: self._buy_shop_item(item_id))
            self._shop_buy_buttons[item.id] = button
            content.addWidget(price)
            content.addWidget(owned)
            content.addWidget(button)
            _add_grid_card(self._buy_items_layout, card, index)

    def _render_sell_items(self) -> None:
        self._shop_sell_buttons = {}
        self._sell_item_buttons = {}
        self._sell_value_labels = {}
        _clear_layout(self._sell_items_layout)
        items = self._sell_items()
        if not items:
            self._sell_items_layout.addWidget(_empty_state("No owned items to sell."), 0, 0, 1, _GRID_COLUMNS)
            self._selected_listing_item_id = None
            self._refresh_listing_form()
            return
        if self._selected_listing_item_id not in {item.id for item in items}:
            self._selected_listing_item_id = items[0].id
        for index, item in enumerate(items):
            theoretical_price = _suggested_market_price(item) or 0
            sell_price = max(1, theoretical_price // 3)
            owned = self._inventory.get(item.id, 0)
            card = self._item_card(item, selected=item.id == self._selected_listing_item_id)
            content = card.layout()
            meta = QLabel(f"Owned: {owned}", card)
            meta.setObjectName("Muted")
            sell_value = QLabel(f"Sell now: {_format_bits(sell_price)}", card)
            sell_value.setObjectName("ShopPrice")
            actions = QHBoxLayout()
            sell_button = QPushButton("Sell now", card)
            sell_button.setEnabled(owned > 0)
            sell_button.clicked.connect(lambda checked=False, item_id=item.id: self._sell_shop_item(item_id))
            list_button = QPushButton("List", card)
            list_button.clicked.connect(lambda checked=False, item_id=item.id: self._select_listing_item(item_id))
            actions.addWidget(sell_button)
            actions.addWidget(list_button)
            content.addWidget(meta)
            content.addWidget(sell_value)
            content.addLayout(actions)
            self._shop_sell_buttons[item.id] = sell_button
            self._sell_item_buttons[item.id] = list_button
            self._sell_value_labels[item.id] = sell_value
            _add_grid_card(self._sell_items_layout, card, index)
        self._refresh_listing_form()

    def _render_listing_cards(self) -> None:
        self._listing_cancel_buttons = {}
        _clear_layout(self._listing_cards_layout)
        if not self._listings:
            self._listing_cards_layout.addWidget(_empty_state("No active listings."), 0, 0, 1, _GRID_COLUMNS)
            return
        for index, listing in enumerate(self._listings):
            item = self._catalog.items.get(listing.item_id) if self._catalog is not None else None
            card = self._item_card(item) if item is not None else _market_card(listing.item_id)
            content = card.layout()
            price = QLabel(_format_bits(listing.price_bits), card)
            price.setObjectName("ShopPrice")
            created = QLabel(f"Listed: {listing.created_at}", card)
            created.setObjectName("Muted")
            button = QPushButton("Cancel", card)
            button.clicked.connect(lambda checked=False, listing_id=listing.id: self._cancel_listing(listing_id))
            self._listing_cancel_buttons[listing.id] = button
            content.addWidget(price)
            content.addWidget(created)
            content.addWidget(button)
            _add_grid_card(self._listing_cards_layout, card, index)

    def _render_friend_cards(self) -> None:
        self._friend_buy_buttons = {}
        self._friend_icon_labels = {}
        self._friend_price_labels = {}
        _clear_layout(self._friend_grid_layout)
        if not self._friend_listings:
            self._friend_grid_layout.addWidget(_empty_state("No friend listings available."), 0, 0, 1, _GRID_COLUMNS)
            return
        for index, listing in enumerate(self._friend_listings):
            item = self._catalog.items.get(listing.item_id) if self._catalog is not None else None
            card = self._item_card(item) if item is not None else _market_card(listing.item_name)
            content = card.layout()
            status = QLabel("Online" if listing.online else "Offline", card)
            status.setObjectName("StatusOnline" if listing.online else "StatusOffline")
            status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            trainer = QLabel(listing.trainer_name, card)
            trainer.setObjectName("Muted")
            trainer.setAlignment(Qt.AlignmentFlag.AlignCenter)
            price = QLabel(_format_bits(listing.price_bits), card)
            price.setObjectName("ShopPrice")
            price.setAlignment(Qt.AlignmentFlag.AlignCenter)
            button = QPushButton("Buy", card)
            can_buy = listing.online and self._bits >= listing.price_bits
            button.setObjectName("PrimaryButton")
            button.setEnabled(can_buy)
            button.setToolTip(_friend_buy_disabled_reason(listing, self._bits) if not can_buy else "")
            button.clicked.connect(
                lambda checked=False, address=listing.address, listing_id=listing.listing_id:
                self._buy_friend_listing(address, listing_id)
            )
            content.addWidget(status)
            content.addWidget(trainer)
            content.addWidget(price)
            content.addWidget(button)
            icon_label = card.findChild(QLabel, "ShopIcon")
            if icon_label is not None:
                self._friend_icon_labels[listing.listing_id] = icon_label
            self._friend_price_labels[listing.listing_id] = price
            self._friend_buy_buttons[listing.listing_id] = button
            _add_grid_card(self._friend_grid_layout, card, index)

    def _buy_items(self) -> list[ItemDefinition]:
        if self._catalog is None:
            return []
        return sorted(
            (item for item in self._catalog.items.values() if item.shop_price_bits is not None),
            key=lambda item: (item.shop_price_bits or 0, item.name.casefold()),
        )

    def _sell_items(self) -> list[ItemDefinition]:
        if self._catalog is None:
            return []
        return sorted(
            (
                item for item in self._catalog.items.values()
                if self._inventory.get(item.id, 0) > 0 and _suggested_market_price(item) is not None
            ),
            key=lambda item: (_suggested_market_price(item) or 0, item.name.casefold()),
        )

    def _selected_inventory_item(self) -> ItemDefinition | None:
        if self._catalog is None or self._selected_listing_item_id is None:
            return None
        return self._catalog.items.get(self._selected_listing_item_id)

    def _select_listing_item(self, item_id: str) -> None:
        self._selected_listing_item_id = item_id
        self._render_sell_items()

    def _refresh_listing_form(self) -> None:
        item = self._selected_inventory_item()
        if item is None:
            self._selected_item_name_label.setText("Select an item")
            self._selected_item_hint_label.setText("Pick one owned item.")
            self._listing_price_input.setValue(1)
            self._list_selected_button.setEnabled(False)
            self._listing_price_item_id = None
            return
        suggested = _suggested_market_price(item)
        self._selected_item_name_label.setText(item.name)
        self._selected_item_hint_label.setText(
            f"Default price: {_format_bits(suggested)}." if suggested is not None else "No default price."
        )
        if self._listing_price_item_id != item.id:
            self._listing_price_input.setValue(suggested or 1)
            self._listing_price_item_id = item.id
        self._list_selected_button.setEnabled(True)

    def _list_selected_item(self) -> None:
        item = self._selected_inventory_item()
        if item is None:
            return
        self._create_listing(item.id, self._listing_price_input.value())

    def _item_card(self, item: ItemDefinition, *, selected: bool = False) -> QFrame:
        card = _market_card(item.name)
        if selected:
            card.setProperty("selected", "true")
        content = card.layout()
        icon = QLabel(card)
        icon.setObjectName("ShopIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedHeight(40)
        if item.icon_path:
            pixmap = QPixmap(str(Path(item.icon_path)))
            if not pixmap.isNull():
                icon.setPixmap(
                    pixmap.scaled(
                        48,
                        40,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            else:
                icon.setText(item.name[:2].upper())
        else:
            icon.setText(item.name[:2].upper())
        content.insertWidget(1, icon)
        return card


_GRID_COLUMNS = 4


def _card_grid_layout(parent: QWidget, layout) -> QGridLayout:
    scroll = QScrollArea(parent)
    scroll.setObjectName("ShopScroll")
    scroll.setWidgetResizable(True)
    body = QWidget(scroll)
    body.setObjectName("ShopScrollBody")
    cards = QGridLayout(body)
    cards.setContentsMargins(6, 6, 6, 6)
    cards.setSpacing(8)
    for column in range(_GRID_COLUMNS):
        cards.setColumnStretch(column, 1)
    scroll.setWidget(body)
    layout.addWidget(scroll, 1)
    return cards


def _add_grid_card(layout: QGridLayout, card: QWidget, index: int) -> None:
    layout.addWidget(card, index // _GRID_COLUMNS, index % _GRID_COLUMNS)


def _panel(parent: QWidget, title: str) -> QFrame:
    panel = QFrame(parent)
    panel.setObjectName("ShopPanel")
    layout = QVBoxLayout(panel)
    layout.setSpacing(8)
    label = QLabel(title, panel)
    label.setObjectName("SectionTitle")
    layout.addWidget(label)
    return panel


def _market_card(name: str) -> QFrame:
    card = QFrame()
    card.setObjectName("ShopCard")
    card.setFixedSize(142, 172)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(3)
    tag = QLabel("MARKET", card)
    tag.setObjectName("ShopSlotType")
    tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
    tag.setFixedHeight(15)
    layout.addWidget(tag)
    name_label = QLabel(_short_card_name(name), card)
    name_label.setObjectName("ShopItemTitle")
    name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    name_label.setWordWrap(True)
    name_label.setFixedHeight(30)
    layout.addWidget(name_label)
    return card


def _empty_state(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("ShopEmpty")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setWordWrap(True)
    label.setMinimumHeight(90)
    return label


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
            continue
        child_layout = item.layout()
        if child_layout is not None:
            _clear_layout(child_layout)


def _format_bits(value: int | None) -> str:
    return f"{int(value or 0)} Bits"


def _suggested_market_price(item: ItemDefinition | None) -> int | None:
    if item is None:
        return None
    return item.suggested_market_price_bits or item.shop_price_bits


def _short_card_name(name: str) -> str:
    if len(name) <= 18:
        return name
    return f"{name[:15]}..."


def _friend_buy_disabled_reason(listing: FriendMarketListing, bits: int) -> str:
    if not listing.online:
        return "Friend offline"
    if bits < listing.price_bits:
        return "Not enough Bits"
    return ""


_SHOP_QSS = f"""
QLabel#ShopBits {{
    background: {COLORS["surface_alt"]};
    border: 2px solid {COLORS["focus"]};
    border-radius: 2px;
    color: {COLORS["focus"]};
    font-weight: 900;
    padding: 5px 10px;
}}

QFrame#ShopPanel {{
    background: {COLORS["panel"]};
    border: 1px solid {COLORS["line_soft"]};
    border-radius: 3px;
}}

QFrame#ShopCard {{
    background: {COLORS["panel_alt"]};
    border: 2px solid {COLORS["accent_soft"]};
    border-radius: 2px;
}}

QFrame#ShopCard:hover {{
    background: {COLORS["panel_hot"]};
    border-color: {COLORS["accent"]};
}}

QFrame#ShopCard[selected="true"] {{
    border-color: {COLORS["focus"]};
}}

QScrollArea#ShopScroll,
QWidget#ShopScrollBody {{
    background: transparent;
    border: none;
}}

QLabel#ShopItemTitle {{
    color: {COLORS["text"]};
    font-size: 10px;
    font-weight: 800;
}}

QLabel#ShopSelectedName {{
    color: {COLORS["text"]};
    font-size: 14px;
    font-weight: 900;
}}

QLabel#ShopPrice {{
    color: {COLORS["focus"]};
    font-size: 11px;
    font-weight: 900;
}}

QLabel#ShopIcon {{
    background: {COLORS["surface"]};
    border: none;
    color: {COLORS["focus"]};
    font-size: 16px;
    font-weight: 900;
}}

QLabel#ShopSlotType {{
    background: {COLORS["surface_alt"]};
    border: 2px solid {COLORS["accent_soft"]};
    border-radius: 2px;
    color: {COLORS["accent"]};
    font-size: 9px;
    font-weight: 900;
    padding: 0px 3px;
}}

QLabel#ShopEmpty {{
    color: {COLORS["muted"]};
    border: 1px dashed {COLORS["line"]};
    border-radius: 4px;
    padding: 12px;
}}

QLabel#StatusOnline {{
    color: {COLORS["success"]};
    font-size: 10px;
    font-weight: 900;
}}

QLabel#StatusOffline {{
    color: {COLORS["danger"]};
    font-size: 10px;
    font-weight: 900;
}}
"""
