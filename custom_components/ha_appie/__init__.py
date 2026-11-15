"""HA Appie: your Albert Heijn account in Home Assistant (unofficial)."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.loader import async_get_integration

from .const import DOMAIN, OPT_CARD, PLATFORMS, opt
from .coordinator import AhCoordinator, AhExtraCoordinator, AhInfoCoordinator, ReceiptCache
from .recipes import Recipes
from .regulars import Regulars
from .search import ProductSearch


@dataclass
class AhRuntime:
    deliveries: AhCoordinator
    extra: AhExtraCoordinator
    regulars: Regulars
    recipes: Recipes
    search: ProductSearch
    info: AhInfoCoordinator | None = None
    receipts: ReceiptCache | None = None


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type AhConfigEntry = ConfigEntry[AhRuntime]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    from .services import async_register_services

    async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AhConfigEntry) -> bool:
    if entry.title != "HA Appie":
        hass.config_entries.async_update_entry(entry, title="HA Appie")
    deliveries = AhCoordinator(hass, entry)
    await deliveries.async_config_entry_first_refresh()
    regulars = Regulars(hass, entry.entry_id)
    await regulars.async_load()
    receipts = ReceiptCache(hass, entry.entry_id)
    await receipts.async_load()
    extra = AhExtraCoordinator(hass, entry, deliveries, regulars, receipts)
    await extra.async_config_entry_first_refresh()
    info = AhInfoCoordinator(hass, entry, deliveries.client)
    await info.async_refresh()  # optional data: never blocks setup
    recipes = Recipes(hass, entry.entry_id)
    await recipes.async_load()
    entry.runtime_data = AhRuntime(deliveries, extra, regulars, recipes, ProductSearch(), info, receipts)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = dict(entry.options)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    from .frontend import async_register_frontend

    integration = await async_get_integration(hass, DOMAIN)
    await async_register_frontend(hass, str(integration.version), bool(opt(entry, OPT_CARD)))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: AhConfigEntry) -> None:
    """Options switch features (and so entities) on or off: reload.

    The listener also fires when refreshed tokens are saved in entry.data; that must not reload."""
    if hass.data.get(DOMAIN, {}).get(entry.entry_id) != dict(entry.options):
        await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: AhConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
