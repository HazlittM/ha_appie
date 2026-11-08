"""Constants for HA Appie."""
DOMAIN = "ha_appie"
PLATFORMS = ["sensor", "event", "todo", "number", "button", "select", "text"]
CONF_CODE = "code"
SCAN_INTERVAL_DELIVERY_DAY = 60  # seconds, while a delivery is due today
SCAN_INTERVAL_IDLE = 900  # seconds, otherwise
SCAN_INTERVAL_EXTRA = 1800  # seconds: basket, receipts, list, bonus
