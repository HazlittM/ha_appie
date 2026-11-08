"""One number per regular product: how many to add to the list this week (0 = skip)."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AhConfigEntry
from .const import DOMAIN
from .entity import AhEntity
from .model import RegularProduct


async def async_setup_entry(
    hass: HomeAssistant, entry: AhConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    runtime = entry.runtime_data
    known: set[int] = set()

    @callback
    def _sync() -> None:
        current = {r.product_id: r for r in runtime.extra.data.regulars}
        new = [AhRegularNumber(runtime, r) for pid, r in current.items() if pid not in known]
        known.update(current)
        if new:
            async_add_entities(new)
        # products that stopped being regular: remove their entity (also leftovers from before a restart)
        registry = er.async_get(hass)
        prefix = f"{entry.entry_id}_regular_"
        for ent in er.async_entries_for_config_entry(registry, entry.entry_id):
            if ent.domain == "number" and ent.unique_id.startswith(prefix):
                if int(ent.unique_id[len(prefix):]) not in current:
                    registry.async_remove(ent.entity_id)
        known.intersection_update(current)

    _sync()
    entry.async_on_unload(runtime.extra.async_add_listener(_sync))

    async_add_entities([AhRecipePersons(runtime), AhSearchQuantity(runtime), AhDraftPersons(runtime)])


class AhRegularNumber(AhEntity, NumberEntity):
    _attr_has_entity_name = False  # show just the product name, without the device prefix
    _attr_native_min_value = 0
    _attr_native_max_value = 30
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:cart-plus"

    def __init__(self, runtime, regular: RegularProduct) -> None:
        super().__init__(runtime.extra, f"regular_{regular.product_id}")
        self._regulars = runtime.regulars
        self._pid = regular.product_id
        self._attr_translation_key = None
        self._attr_name = regular.title

    @property
    def native_value(self) -> float:
        return self._regulars.quantity(self._pid)

    @property
    def extra_state_attributes(self) -> dict:
        reg = next((r for r in self.coordinator.data.regulars if r.product_id == self._pid), None)
        return {
            "product_id": self._pid,
            "standaard": self._regulars.default(self._pid),
            "besteld_in": f"{reg.orders} van de laatste {reg.of} bestellingen" if reg else None,
        }

    async def async_set_native_value(self, value: float) -> None:
        await self._regulars.async_set_quantity(self._pid, int(value))
        self.async_write_ha_state()


class AhRecipePersons(AhEntity, NumberEntity):
    """Persons for the selected recipe (changing it rescales the ingredients)."""

    _attr_native_min_value = 1
    _attr_native_max_value = 30
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:account-multiple"
    _attr_name = "Recept personen"

    def __init__(self, runtime) -> None:
        super().__init__(runtime.extra, "recipe_persons")
        self._recipes = runtime.recipes
        self._attr_translation_key = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._recipes.async_add_listener(self.async_write_ha_state))

    @property
    def available(self) -> bool:
        return self._recipes.current() is not None

    @property
    def native_value(self) -> float | None:
        r = self._recipes.current()
        return r["persons"] if r else None

    @property
    def extra_state_attributes(self) -> dict:
        r = self._recipes.current() or {}
        return {"recept": r.get("name"), "oorspronkelijk": r.get("base")}

    async def async_set_native_value(self, value: float) -> None:
        await self._recipes.async_set_persons(int(value))


class AhSearchQuantity(AhEntity, NumberEntity):
    """How many of the chosen search result to add."""

    _attr_native_min_value = 1
    _attr_native_max_value = 30
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:numeric"
    _attr_name = "Zoek aantal"

    def __init__(self, runtime) -> None:
        super().__init__(runtime.extra, "search_quantity")
        self._search = runtime.search
        self._attr_translation_key = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._search.async_add_listener(self.async_write_ha_state))

    @property
    def native_value(self) -> float:
        return self._search.quantity

    async def async_set_native_value(self, value: float) -> None:
        self._search.set_quantity(int(value))


class AhDraftPersons(AhEntity, NumberEntity):
    """Number of persons of the recipe being entered."""

    _attr_native_min_value = 1
    _attr_native_max_value = 30
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:account-group"
    _attr_name = "Nieuw recept personen"

    def __init__(self, runtime) -> None:
        super().__init__(runtime.extra, "new_recipe_persons")
        self._recipes = runtime.recipes
        self._attr_translation_key = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._recipes.async_add_listener(self.async_write_ha_state))

    @property
    def native_value(self) -> float:
        return self._recipes.draft["persons"]

    async def async_set_native_value(self, value: float) -> None:
        self._recipes.set_draft(persons=int(value))
