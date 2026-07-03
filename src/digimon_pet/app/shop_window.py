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
        self._friend_price_labels: dict[str, QLabel] = {}
        self._friend_suggestion_labels: dict[str, QLabel] = {}
        self._friend_price_flags: dict[str, QLabel] = {}

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
            f"{len(self._buy_items())} shop items · {len(self._sell_items())} owned · "
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
        self._buy_items_layout = _card_list_layout(tab, layout)
        return tab

    def _build_sell_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        owned_panel = _panel(tab, "Owned items")
        self._sell_items_layout = _card_list_layout(owned_panel, owned_panel.layout())
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
        self._listing_cards_layout = _card_list_layout(listing_panel, listing_panel.layout())
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
        self._friend_cards_layout = _card_list_layout(tab, layout)
        return tab

    def _render_buy_items(self) -> None:
        self._shop_buy_buttons = {}
        _clear_layout(self._buy_items_layout)
        items = self._buy_items()
        if not items:
            self._buy_items_layout.addWidget(_empty_state("No shop items available."))
            return
        for item in items:
            card = self._item_card(item)
            content = card.layout()
            price = QLabel(f"Buy: {_format_bits(item.shop_price_bits or 0)}", card)
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
            self._buy_items_layout.addWidget(card)
        self._buy_items_layout.addStretch(1)

    def _render_sell_items(self) -> None:
        self._shop_sell_buttons = {}
        self._sell_item_buttons = {}
        self._sell_value_labels = {}
        _clear_layout(self._sell_items_layout)
        items = self._sell_items()
        if not items:
            self._sell_items_layout.addWidget(_empty_state("No owned items to sell."))
            self._selected_listing_item_id = None
            self._refresh_listing_form()
            return
        if self._selected_listing_item_id not in {item.id for item in items}:
            self._selected_listing_item_id = items[0].id
        for item in items:
            theoretical_price = _suggested_market_price(item) or 0
            sell_price = max(1, theoretical_price // 3)
            owned = self._inventory.get(item.id, 0)
            card = self._item_card(item, selected=item.id == self._selected_listing_item_id)
            content = card.layout()
            meta = QLabel(f"Owned: {owned} · Value: {_format_bits(theoretical_price)}", card)
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
            self._sell_items_layout.addWidget(card)
        self._sell_items_layout.addStretch(1)
        self._refresh_listing_form()

    def _render_listing_cards(self) -> None:
        self._listing_cancel_buttons = {}
        _clear_layout(self._listing_cards_layout)
        if not self._listings:
            self._listing_cards_layout.addWidget(_empty_state("No active listings."))
            return
        for listing in self._listings:
            item = self._catalog.items.get(listing.item_id) if self._catalog is not None else None
            card = _card()
            content = card.layout()
            title = QLabel(item.name if item else listing.item_id, card)
            title.setObjectName("ShopItemTitle")
            price = QLabel(_format_bits(listing.price_bits), card)
            price.setObjectName("ShopPrice")
            created = QLabel(f"Created: {listing.created_at}", card)
            created.setObjectName("Muted")
            button = QPushButton("Cancel", card)
            button.clicked.connect(lambda checked=False, listing_id=listing.id: self._cancel_listing(listing_id))
            self._listing_cancel_buttons[listing.id] = button
            content.addWidget(title)
            content.addWidget(price)
            content.addWidget(created)
            content.addWidget(button)
            self._listing_cards_layout.addWidget(card)
        self._listing_cards_layout.addStretch(1)

    def _render_friend_cards(self) -> None:
        self._friend_buy_buttons = {}
        self._friend_price_labels = {}
        self._friend_suggestion_labels = {}
        self._friend_price_flags = {}
        _clear_layout(self._friend_cards_layout)
        if not self._friend_listings:
            self._friend_cards_layout.addWidget(_empty_state("No friend listings available."))
            return
        for listing in self._friend_listings:
            item = self._catalog.items.get(listing.item_id) if self._catalog is not None else None
            suggested = _suggested_market_price(item) if item is not None else None
            card = _card()
            content = card.layout()
            top = QHBoxLayout()
            item_name = QLabel(listing.item_name, card)
            item_name.setObjectName("ShopItemTitle")
            status = QLabel("Online" if listing.online else "Offline", card)
            status.setObjectName("StatusOnline" if listing.online else "StatusOffline")
            top.addWidget(item_name, 1)
            top.addWidget(status)
            trainer = QLabel(f"Seller: {listing.trainer_name}", card)
            trainer.setObjectName("Muted")
            price = QLabel(_format_bits(listing.price_bits), card)
            price.setObjectName("ShopPrice")
            suggestion = QLabel(
                f"Suggested: {_format_bits(suggested)}" if suggested is not None else "No suggested price",
                card,
            )
            suggestion.setObjectName("Muted")
            flag = QLabel(_price_flag(listing.price_bits, suggested), card)
            flag.setObjectName(_price_flag_state(listing.price_bits, suggested))
            button = QPushButton("Buy", card)
            can_buy = listing.online and self._bits >= listing.price_bits
            button.setObjectName("PrimaryButton")
            button.setEnabled(can_buy)
            button.setToolTip(_friend_buy_disabled_reason(listing, self._bits) if not can_buy else "")
            button.clicked.connect(
                lambda checked=False, address=listing.address, listing_id=listing.listing_id:
                self._buy_friend_listing(address, listing_id)
            )
            content.addLayout(top)
            content.addWidget(trainer)
            content.addWidget(price)
            content.addWidget(suggestion)
            content.addWidget(flag)
            content.addWidget(button)
            self._friend_price_labels[listing.listing_id] = price
            self._friend_suggestion_labels[listing.listing_id] = suggestion
            self._friend_price_flags[listing.listing_id] = flag
            self._friend_buy_buttons[listing.listing_id] = button
            self._friend_cards_layout.addWidget(card)
        self._friend_cards_layout.addStretch(1)

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
            f"Suggested price: {_format_bits(suggested)}." if suggested is not None else "No suggested price."
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
        card = _card()
        if selected:
            card.setProperty("selected", "true")
        content = card.layout()
        top = QHBoxLayout()
        icon = QLabel(card)
        icon.setObjectName("ShopIcon")
        icon.setFixedSize(34, 34)
        if item.icon_path:
            pixmap = QPixmap(str(Path(item.icon_path)))
            if not pixmap.isNull():
                icon.setPixmap(pixmap.scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio))
        name = QLabel(item.name, card)
        name.setObjectName("ShopItemTitle")
        name.setWordWrap(True)
        top.addWidget(icon)
        top.addWidget(name, 1)
        content.addLayout(top)
        return card


def _card_list_layout(parent: QWidget, layout) -> QVBoxLayout:
    scroll = QScrollArea(parent)
    scroll.setObjectName("ShopScroll")
    scroll.setWidgetResizable(True)
    body = QWidget(scroll)
    body.setObjectName("ShopScrollBody")
    cards = QVBoxLayout(body)
    cards.setContentsMargins(6, 6, 6, 6)
    cards.setSpacing(8)
    scroll.setWidget(body)
    layout.addWidget(scroll, 1)
    return cards


def _panel(parent: QWidget, title: str) -> QFrame:
    panel = QFrame(parent)
    panel.setObjectName("ShopPanel")
    layout = QVBoxLayout(panel)
    layout.setSpacing(8)
    label = QLabel(title, panel)
    label.setObjectName("SectionTitle")
    layout.addWidget(label)
    return panel


def _card() -> QFrame:
    card = QFrame()
    card.setObjectName("ShopCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(5)
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


def _price_flag(price: int, suggested: int | None) -> str:
    if suggested is None or suggested <= 0:
        return "No benchmark"
    ratio = price / suggested
    if ratio >= 2:
        return f"{ratio:.0f}x suggested"
    if ratio <= 0.75:
        return "Below suggested"
    return "Near suggested"


def _price_flag_state(price: int, suggested: int | None) -> str:
    if suggested is None or suggested <= 0:
        return "PriceNeutral"
    ratio = price / suggested
    if ratio >= 2:
        return "PriceWarning"
    if ratio <= 0.75:
        return "PriceGood"
    return "PriceNeutral"


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
    background: {COLORS["surface_alt"]};
    border: 1px solid {COLORS["line_soft"]};
    border-radius: 4px;
}}

QFrame#ShopCard:hover {{
    background: {COLORS["panel_alt"]};
    border-color: {COLORS["accent_soft"]};
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
    font-weight: 900;
}}

QLabel#ShopSelectedName {{
    color: {COLORS["text"]};
    font-size: 14px;
    font-weight: 900;
}}

QLabel#ShopPrice {{
    color: {COLORS["focus"]};
    font-weight: 900;
}}

QLabel#ShopIcon {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["line_soft"]};
    border-radius: 3px;
}}

QLabel#ShopEmpty {{
    color: {COLORS["muted"]};
    border: 1px dashed {COLORS["line"]};
    border-radius: 4px;
    padding: 12px;
}}

QLabel#StatusOnline {{
    color: {COLORS["success"]};
    font-weight: 900;
}}

QLabel#StatusOffline {{
    color: {COLORS["danger"]};
    font-weight: 900;
}}

QLabel#PriceWarning {{
    color: {COLORS["danger"]};
    font-weight: 900;
}}

QLabel#PriceGood {{
    color: {COLORS["success"]};
    font-weight: 900;
}}

QLabel#PriceNeutral {{
    color: {COLORS["muted"]};
    font-weight: 800;
}}
"""
