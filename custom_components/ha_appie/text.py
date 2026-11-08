"""Search box for AH products."""
from __future__ import annotations

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AhConfigEntry
from .entity import AhEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: AhConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    rt = entry.runtime_data
    async_add_entities([AhSearchBox(rt), AhDraftText(rt, "name"), AhDraftText(rt, "ingredients")])


class AhSearchBox(AhEntity, TextEntity):
    _attr_icon = "mdi:magnify"
    _attr_name = "Zoek product"
    _attr_native_max = 100
    _attr_mode = TextMode.TEXT

    def __init__(self, runtime) -> None:
        super().__init__(runtime.extra, "product_search")
        self._runtime = runtime
        self._attr_translation_key = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.search.async_add_listener(self.async_write_ha_state))

    @property
    def native_value(self) -> str:
        return self._runtime.search.query

    @property
    def extra_state_attributes(self) -> dict:
        return {"resultaten": len(self._runtime.search.results)}

    async def async_set_value(self, value: str) -> None:
        await self._runtime.search.async_search(self._runtime.extra.client, value)


class AhDraftText(AhEntity, TextEntity):
    """Fields of the 'new recipe' form."""

    _attr_mode = TextMode.TEXT

    def __init__(self, runtime, field: str) -> None:
        super().__init__(runtime.extra, f"new_recipe_{field}")
        self._recipes = runtime.recipes
        self._field = field
        self._attr_translation_key = None
        self._attr_name = "Nieuw recept naam" if field == "name" else "Nieuw recept ingrediënten"
        self._attr_icon = "mdi:book-plus" if field == "name" else "mdi:format-list-bulleted"
        self._attr_native_max = 100 if field == "name" else 255

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._recipes.async_add_listener(self.async_write_ha_state))

    @property
    def native_value(self) -> str:
        return self._recipes.draft[self._field]

    async def async_set_value(self, value: str) -> None:
        self._recipes.set_draft(**{self._field: value.strip()})
