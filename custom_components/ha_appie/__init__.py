"""HA Appie: delivery status of your AH online orders (unofficial)."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, PLATFORMS
from dataclasses import dataclass

from .coordinator import AhCoordinator, AhExtraCoordinator
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
    extra = AhExtraCoordinator(hass, entry, deliveries, regulars)
    await extra.async_config_entry_first_refresh()
    recipes = Recipes(hass, entry.entry_id)
    await recipes.async_load()
    entry.runtime_data = AhRuntime(deliveries, extra, regulars, recipes, ProductSearch())
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AhConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
