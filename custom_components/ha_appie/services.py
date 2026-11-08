"""Services: save/delete a recipe, put a recipe on the AH list."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

SAVE = vol.Schema(
    {
        vol.Required("name"): cv.string,
        vol.Required("persons"): vol.All(vol.Coerce(int), vol.Range(min=1, max=30)),
        vol.Required("ingredients"): cv.string,
    }
)
NAME = vol.Schema({vol.Required("name"): cv.string})
ADD = vol.Schema(
    {vol.Required("name"): cv.string, vol.Optional("persons"): vol.All(vol.Coerce(int), vol.Range(min=1, max=30))}
)


def _runtime(hass: HomeAssistant):
    for entry in hass.config_entries.async_entries(DOMAIN):
        if getattr(entry, "runtime_data", None):
            return entry.runtime_data
    raise HomeAssistantError("HA Appie is niet geladen")


def async_register_services(hass: HomeAssistant) -> None:
    async def save_recipe(call: ServiceCall) -> dict:
        rt = _runtime(hass)
        try:
            rid, n = await rt.recipes.async_save_recipe(
                call.data["name"], call.data["persons"], call.data["ingredients"]
            )
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        return {"recipe": rt.recipes.recipes[rid]["name"], "ingredients": n}

    async def delete_recipe(call: ServiceCall) -> None:
        rt = _runtime(hass)
        if (rid := rt.recipes.find(call.data["name"])) is None:
            raise HomeAssistantError("Recept niet gevonden")
        await rt.recipes.async_delete(rid)

    async def add_recipe(call: ServiceCall) -> dict:
        rt = _runtime(hass)
        if (rid := rt.recipes.find(call.data["name"])) is None:
            raise HomeAssistantError("Recept niet gevonden")
        return {"result": await rt.recipes.async_add_to_list(rt.extra, rid, call.data.get("persons"))}

    hass.services.async_register(DOMAIN, "save_recipe", save_recipe, SAVE, supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, "delete_recipe", delete_recipe, NAME)
    hass.services.async_register(DOMAIN, "add_recipe_to_list", add_recipe, ADD, supports_response=SupportsResponse.OPTIONAL)
