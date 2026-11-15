"""Constants for HA Appie."""
DOMAIN = "ha_appie"
PLATFORMS = ["sensor", "event", "todo", "number", "button", "select", "text"]
CONF_CODE = "code"
SCAN_INTERVAL_DELIVERY_DAY = 60  # seconds, while a delivery is due today
SCAN_INTERVAL_IDLE = 900  # seconds, otherwise
SCAN_INTERVAL_EXTRA = 1800  # seconds: basket, receipts, list, bonus
SCAN_INTERVAL_INFO = 3600  # seconds: store, last chance, favourites, cards, free delivery slots

# Options (Settings > Devices & services > HA Appie > Configure). Every v0.5 extra can be switched off.
OPT_RECEIPT_DETAILS = "receipt_details"  # receipt lines, discounts, saved this month
OPT_RECEIPT_IMAGES = "receipt_images"  # product photos for receipt lines
OPT_DELIVERY_DETAILS = "delivery_details"  # ETA, change-until, minimum order value, invoice
OPT_PERSONAL_BONUS = "personal_bonus"  # personal bonus with activation status and prices
OPT_STORE = "store"  # favourite store + opening hours
OPT_BARGAINS = "bargains"  # "Laatste kans" in that store
OPT_FAVORITES = "favorites"  # favourite lists
OPT_MEMBER_CARDS = "member_cards"  # bonus card number (for the barcode in the card)
OPT_ALLERHANDE = "allerhande"  # Allerhande recipe search/import services
OPT_PRODUCT_INFO = "product_info"  # product details / barcode lookup services
OPT_DELIVERY_SLOTS = "delivery_slots"  # free delivery moments (needs an address you enter yourself)
OPT_CARD = "lovelace_card"  # register the built-in dashboard card
OPT_STORE_ID = "store_id"  # 0 = your favourite store in the AH app
OPT_POSTAL_CODE = "postal_code"
OPT_HOUSE_NUMBER = "house_number"
OPT_HOUSE_EXTRA = "house_number_extra"
OPT_STREET = "street"
OPT_CITY = "city"

DEFAULTS = {
    OPT_RECEIPT_DETAILS: True,
    OPT_RECEIPT_IMAGES: True,
    OPT_DELIVERY_DETAILS: True,
    OPT_PERSONAL_BONUS: True,
    OPT_STORE: True,
    OPT_BARGAINS: True,
    OPT_FAVORITES: True,
    OPT_MEMBER_CARDS: False,  # personal: opt-in
    OPT_ALLERHANDE: True,
    OPT_PRODUCT_INFO: True,
    OPT_DELIVERY_SLOTS: False,  # needs an address: opt-in
    OPT_CARD: True,
    OPT_STORE_ID: 0,
}

FRONTEND_URL = "/ha_appie_static/ha-appie-card.js"
CARD_FILENAME = "ha-appie-card.js"


def opt(entry, key: str):
    """An option with its default (entry.options may be empty on existing installs)."""
    return entry.options.get(key, DEFAULTS.get(key))
