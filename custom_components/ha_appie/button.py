"""Buttons: add the regular products to the list in one press; reset the quantities."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AhConfigEntry
from .entity import AhEntity
from .model import list_payload


async def async_setup_entry(
    hass: HomeAssistant, entry: AhConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    runtime = entry.runtime_data
    async_add_entities([AhAddRegularsButton(runtime), AhResetQuantitiesButton(runtime)])

    async_add_entities([AhRecipeButton(runtime), AhSearchAddButton(runtime), AhPinButton(runtime, pin=True), AhPinButton(runtime, pin=False), AhSaveDraftButton(runtime)])


class AhAddRegularsButton(AhEntity, ButtonEntity):
    _attr_icon = "mdi:cart-arrow-down"

    def __init__(self, runtime) -> None:
        super().__init__(runtime.extra, "add_regulars")
        self._runtime = runtime

    async def async_press(self) -> None:
        extra = self._runtime.extra
        # skip what is already on the list, so pressing twice never doubles anything
        on_list = {i.product_id for i in await extra.client.async_get_list() if i.product_id is not None}  # live list
        payloads = [
            list_payload(r.title, qty, r.product_id)
            for r in extra.data.regulars
            if (qty := self._runtime.regulars.quantity(r.product_id)) > 0 and r.product_id not in on_list
        ]
        await extra.client.async_add_list_items(payloads)
        await extra.async_request_refresh()


class AhResetQuantitiesButton(AhEntity, ButtonEntity):
    _attr_icon = "mdi:restore"

    def __init__(self, runtime) -> None:
        super().__init__(runtime.extra, "reset_quantities")
        self._runtime = runtime

    async def async_press(self) -> None:
        await self._runtime.regulars.async_reset_quantities()
        self._runtime.extra.async_update_listeners()


class AhRecipeButton(AhEntity, ButtonEntity):
    """Put the selected recipe, scaled to its persons, on the AH shopping list."""

    _attr_icon = "mdi:chef-hat"
    _attr_name = "Recept op boodschappenlijst"

    def __init__(self, runtime) -> None:
        super().__init__(runtime.extra, "recipe_add")
        self._runtime = runtime
        self._attr_translation_key = None
        self._last: str | None = None

    @property
    def available(self) -> bool:
        return self._runtime.recipes.current() is not None

    @property
    def extra_state_attributes(self) -> dict:
        return {"laatste_keer": self._last}

    async def async_press(self) -> None:
        rt = self._runtime
        if rt.recipes.selected is None:
            return
        self._last = await rt.recipes.async_add_to_list(rt.extra, rt.recipes.selected)
        self.async_write_ha_state()


class AhSearchAddButton(AhEntity, ButtonEntity):
    """Add the chosen search result (times the chosen quantity) to the AH list."""

    _attr_icon = "mdi:cart-plus"
    _attr_name = "Zoekresultaat toevoegen"

    def __init__(self, runtime) -> None:
        super().__init__(runtime.extra, "search_add")
        self._runtime = runtime
        self._attr_translation_key = None
        self._last: str | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.search.async_add_listener(self.async_write_ha_state))

    @property
    def available(self) -> bool:
        return self._runtime.search.current() is not None

    @property
    def extra_state_attributes(self) -> dict:
        return {"laatste_keer": self._last}

    async def async_press(self) -> None:
        rt = self._runtime
        choice = rt.search.current()
        if choice is None:
            return
        current = await rt.extra.client.async_get_list()  # live, not the 30-min cache
        existing = next((i.quantity for i in current if i.product_id == choice["pid"]), 0)
        qty = rt.search.quantity + existing
        await rt.extra.client.async_add_list_item(choice["title"], qty, choice["pid"])
        await rt.extra.async_request_refresh()
        self._last = f"{rt.search.quantity}x {choice['title']}"
        self.async_write_ha_state()


class AhPinButton(AhEntity, ButtonEntity):
    """Pin the chosen search result to the chosen ingredient (or clear the pin)."""

    def __init__(self, runtime, pin: bool) -> None:
        super().__init__(runtime.extra, "recipe_pin" if pin else "recipe_unpin")
        self._runtime = runtime
        self._pin = pin
        self._attr_translation_key = None
        self._attr_icon = "mdi:pin" if pin else "mdi:pin-off"
        self._attr_name = "Zoekresultaat vastzetten bij ingrediënt" if pin else "Ingrediënt weer automatisch kiezen"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.search.async_add_listener(self.async_write_ha_state))
        self.async_on_remove(self._runtime.recipes.async_add_listener(self.async_write_ha_state))

    @property
    def available(self) -> bool:
        rt = self._runtime
        ready = rt.recipes.current() is not None and rt.recipes.pin_target is not None
        return ready and (rt.search.current() is not None if self._pin else True)

    async def async_press(self) -> None:
        rt = self._runtime
        rid, lid = rt.recipes.selected, rt.recipes.pin_target
        if rid is None or lid is None:
            return
        if self._pin:
            choice = rt.search.current()
            if choice is not None:
                await rt.recipes.async_pin(rid, lid, choice["pid"], choice["title"], choice["size"])
        else:
            await rt.recipes.async_unpin(rid, lid)


class AhSaveDraftButton(AhEntity, ButtonEntity):
    """Save the 'new recipe' form as a recipe and select it."""

    _attr_icon = "mdi:content-save"
    _attr_name = "Nieuw recept opslaan"

    def __init__(self, runtime) -> None:
        super().__init__(runtime.extra, "new_recipe_save")
        self._recipes = runtime.recipes
        self._attr_translation_key = None

    async def async_press(self) -> None:
        try:
            await self._recipes.async_save_draft()
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
