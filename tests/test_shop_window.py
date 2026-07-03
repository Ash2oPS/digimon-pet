import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton, QSpinBox

from digimon_pet.app.shop_window import FriendMarketListing, ShopWindow
from digimon_pet.domain.items import ItemCatalog, ItemDefinition, ItemType
from digimon_pet.domain.models import MarketListingState


def _catalog() -> ItemCatalog:
    return ItemCatalog(
        items={
            "black_wings": ItemDefinition(
                id="black_wings",
                name="Black Wings",
                description="Makes Angemon digivolve into Devimon.",
                type=ItemType.EVOLUTION,
                suggested_market_price_bits=900,
            ),
            "digimeat": ItemDefinition(
                id="digimeat",
                name="DigiMeat",
                description="Increases OFF by 25.",
                type=ItemType.CONSUMABLE,
                shop_price_bits=300,
                suggested_market_price_bits=300,
            ),
            "auto_clicker": ItemDefinition(
                id="auto_clicker",
                name="Auto Clicker",
                description="Auto triggers Secondary Events for 1h.",
                type=ItemType.CONSUMABLE,
                shop_price_bits=1500,
                suggested_market_price_bits=1500,
            ),
            "digialcohol": ItemDefinition(
                id="digialcohol",
                name="DigiAlcohol",
                description="Makes your Digimon drunk.",
                type=ItemType.CONSUMABLE,
                icon_path="assets/items/beer.png",
                shop_price_bits=1000,
                suggested_market_price_bits=1000,
            ),
        },
        pools={},
    )


def _window(calls: list[tuple]) -> ShopWindow:
    return ShopWindow(
        buy_shop_item=lambda item_id: calls.append(("buy", item_id)),
        sell_shop_item=lambda item_id: calls.append(("sell", item_id)),
        create_listing=lambda item_id, price: calls.append(("list", item_id, price)),
        cancel_listing=lambda listing_id: calls.append(("cancel", listing_id)),
        buy_friend_listing=lambda address, listing_id: calls.append(("friend", address, listing_id)),
    )


def test_shop_window_renders_shop_items_and_disables_unaffordable_buy():
    app = QApplication.instance() or QApplication([])
    calls = []
    window = _window(calls)

    window.set_data(bits=300, catalog=_catalog(), inventory={}, listings=[], friend_listings=[])

    assert window._tabs.tabText(0) == "Buy Items"
    assert window._tabs.tabText(1) == "Sell Items"
    assert window._tabs.tabText(2) == "Friend Market"
    assert len(window._shop_buy_buttons) == 3
    assert window._shop_buy_buttons["digimeat"].isEnabled() is True
    assert window._shop_buy_buttons["auto_clicker"].isEnabled() is False
    assert window._shop_buy_buttons["auto_clicker"].toolTip() == "Not enough Bits"

    window._shop_buy_buttons["digimeat"].click()

    assert calls == [("buy", "digimeat")]


def test_shop_window_sells_owned_items_for_one_third_value():
    app = QApplication.instance() or QApplication([])
    calls = []
    window = _window(calls)

    window.set_data(
        bits=300,
        catalog=_catalog(),
        inventory={"black_wings": 1},
        listings=[],
        friend_listings=[],
    )

    assert window._sell_value_labels["black_wings"].text() == "Sell now: 300 Bits"
    assert window._shop_sell_buttons["black_wings"].isEnabled() is True

    window._shop_sell_buttons["black_wings"].click()

    assert calls == [("sell", "black_wings")]


def test_shop_window_uses_separate_listing_form_instead_of_inline_table_controls():
    app = QApplication.instance() or QApplication([])
    calls = []
    window = _window(calls)

    window.set_data(
        bits=100,
        catalog=_catalog(),
        inventory={"digimeat": 1, "black_wings": 1},
        listings=[],
        friend_listings=[],
    )
    assert window._sell_item_buttons["black_wings"].text() == "List"

    window._select_listing_item("digimeat")
    window._listing_price_input.setValue(425)
    window._list_selected_button.click()

    assert calls == [("list", "digimeat", 425)]


def test_shop_window_preserves_typed_listing_price_across_refreshes():
    app = QApplication.instance() or QApplication([])
    calls = []
    window = _window(calls)

    window.set_data(
        bits=100,
        catalog=_catalog(),
        inventory={"digimeat": 1, "black_wings": 1},
        listings=[],
        friend_listings=[],
    )
    window._select_listing_item("digimeat")
    window._listing_price_input.setValue(425)

    window.set_data(
        bits=125,
        catalog=_catalog(),
        inventory={"digimeat": 1, "black_wings": 1},
        listings=[],
        friend_listings=[],
    )

    assert window._selected_item_name_label.text() == "DigiMeat"
    assert window._listing_price_input.value() == 425


def test_shop_window_cancels_listing():
    app = QApplication.instance() or QApplication([])
    calls = []
    window = _window(calls)

    window.set_data(
        bits=100,
        catalog=_catalog(),
        inventory={},
        listings=[
            MarketListingState(id="listing-1", item_id="digimeat", price_bits=425, created_at=12345)
        ],
        friend_listings=[],
    )
    window._listing_cancel_buttons["listing-1"].click()

    assert calls == [("cancel", "listing-1")]


def test_shop_window_buys_online_friend_listing():
    app = QApplication.instance() or QApplication([])
    calls = []
    window = _window(calls)

    window.set_data(
        bits=500,
        catalog=_catalog(),
        inventory={},
        listings=[],
        friend_listings=[
            FriendMarketListing(
                address="192.168.1.42:54545",
                trainer_name="Sora",
                listing_id="listing-1",
                item_id="digimeat",
                item_name="DigiMeat",
                price_bits=425,
            )
        ],
    )
    window._friend_buy_buttons["listing-1"].click()

    assert calls == [("friend", "192.168.1.42:54545", "listing-1")]


def test_friend_market_cards_use_inventory_like_grid_without_price_advice():
    app = QApplication.instance() or QApplication([])
    calls = []
    window = _window(calls)

    window.set_data(
        bits=1661,
        catalog=_catalog(),
        inventory={},
        listings=[],
        friend_listings=[
            FriendMarketListing(
                address="192.168.1.42:54545",
                trainer_name="Joris Joestar",
                listing_id="listing-1",
                item_id="digialcohol",
                item_name="DigiAlcohol",
                price_bits=100000,
            )
        ],
    )

    labels = [label.text() for label in window.findChildren(type(window._friend_price_labels["listing-1"]))]
    assert window._friend_grid_layout.columnCount() >= 4
    assert window._friend_icon_labels["listing-1"].pixmap() is not None
    assert window._friend_price_labels["listing-1"].text() == "100000 Bits"
    assert not any("Suggested" in text for text in labels)
    assert not any("suggested" in text for text in labels)
    assert window._friend_buy_buttons["listing-1"].isEnabled() is False
    assert window._friend_buy_buttons["listing-1"].toolTip() == "Not enough Bits"
