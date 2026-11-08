"""Dropdown to pick a recipe."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AhConfigEntry
from .entity import AhEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: AhConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([AhRecipeSelect(entry.runtime_data), AhSearchResultSelect(entry.runtime_data), AhIngredientSelect(entry.runtime_data)])


class AhRecipeSelect(AhEntity, SelectEntity):
    _attr_icon = "mdi:book-open-variant"
    _attr_name = "Recept"

    def __init__(self, runtime) -> None:
        super().__init__(runtime.extra, "recipe_select")
        self._recipes = runtime.recipes
        self._attr_translation_key = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._recipes.async_add_listener(self.async_write_ha_state))

    @property
    def options(self) -> list[str]:
        return sorted((r["name"] for r in self._recipes.recipes.values()), key=str.lower)

    @property
    def current_option(self) -> str | None:
        r = self._recipes.current()
        return r["name"] if r else None

    async def async_select_option(self, option: str) -> None:
        await self._recipes.async_select(option)


class AhSearchResultSelect(AhEntity, SelectEntity):
    """The AH products found for the search box."""

    _attr_icon = "mdi:cart-search"
    _attr_name = "Zoekresultaat"

    def __init__(self, runtime) -> None:
        super().__init__(runtime.extra, "search_result")
        self._search = runtime.search
        self._attr_translation_key = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._search.async_add_listener(self.async_write_ha_state))

    @property
    def options(self) -> list[str]:
        return list(self._search.results)

    @property
    def current_option(self) -> str | None:
        return self._search.selected

    async def async_select_option(self, option: str) -> None:
        self._search.select(option)


def ingredient_labels(recipes) -> dict[str, str]:
    """label -> line id for the current recipe; the label shows the chosen product."""
    r = recipes.current()
    out: dict[str, str] = {}
    for line in (r or {}).get("lines", []):
        label = line["raw"] + (f" → {line['title']}" if line.get("title") else "")
        if line.get("pinned"):
            label += " 📌"
        out[label] = line["id"]
    return out


class AhIngredientSelect(AhEntity, SelectEntity):
    """Which ingredient of the recipe gets the product chosen in the search results."""

    _attr_icon = "mdi:pin"
    _attr_name = "Recept ingrediënt kiezen"

    def __init__(self, runtime) -> None:
        super().__init__(runtime.extra, "recipe_ingredient_pick")
        self._recipes = runtime.recipes
        self._attr_translation_key = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._recipes.async_add_listener(self.async_write_ha_state))

    @property
    def options(self) -> list[str]:
        return list(ingredient_labels(self._recipes))

    @property
    def current_option(self) -> str | None:
        labels = ingredient_labels(self._recipes)
        return next((lab for lab, lid in labels.items() if lid == self._recipes.pin_target), None)

    async def async_select_option(self, option: str) -> None:
        self._recipes.pin_target = ingredient_labels(self._recipes).get(option)
        self.async_write_ha_state()
