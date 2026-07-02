import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton, QSpinBox

from digimon_pet.app.shop_window import FriendMarketListing, ShopWindow
from digimon_pet.domain.items import ItemCatalog, ItemDefinition, ItemType
from digimon_pet.domain.models import MarketListingState


def _catalog() -> ItemCatalog:
    return ItemCatalog(
        items={
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
        },
        pools={},
    )


def _window(calls: list[tuple]) -> ShopWindow:
    return ShopWindow(
        buy_shop_item=lambda item_id: calls.append(("buy", item_id)),
        create_listing=lambda item_id, price: calls.append(("list", item_id, price)),
        cancel_listing=lambda listing_id: calls.append(("cancel", listing_id)),
        buy_friend_listing=lambda address, listing_id: calls.append(("friend", address, listing_id)),
    )


def test_shop_window_renders_shop_items_and_disables_unaffordable_buy():
    app = QApplication.instance() or QApplication([])
    calls = []
    window = _window(calls)

    window.set_data(bits=300, catalog=_catalog(), inventory={}, listings=[], friend_listings=[])

    assert window._shop_table.rowCount() == 2
    assert window._shop_table.item(0, 0).text() == "DigiMeat"
    assert window._shop_table.item(1, 0).text() == "Auto Clicker"
    assert window._shop_table.cellWidget(0, 3).isEnabled() is True
    assert window._shop_table.cellWidget(1, 3).isEnabled() is False

    window._shop_table.cellWidget(0, 3).click()

    assert calls == [("buy", "digimeat")]


def test_shop_window_creates_listing_with_selected_price():
    app = QApplication.instance() or QApplication([])
    calls = []
    window = _window(calls)

    window.set_data(
        bits=100,
        catalog=_catalog(),
        inventory={"digimeat": 1},
        listings=[],
        friend_listings=[],
    )
    editor = window._inventory_table.cellWidget(0, 3)
    price_input = editor.findChild(QSpinBox)
    button = editor.findChild(QPushButton)
    price_input.setValue(425)
    button.click()

    assert calls == [("list", "digimeat", 425)]


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
    window._listing_table.cellWidget(0, 3).click()

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
    window._friend_table.cellWidget(0, 4).click()

    assert calls == [("friend", "192.168.1.42:54545", "listing-1")]
