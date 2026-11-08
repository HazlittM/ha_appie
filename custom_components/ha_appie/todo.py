"""To-do list: the Albert Heijn shopping list (read, add, tick off = remove)."""
from __future__ import annotations

import logging

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AhConfigEntry
from .api import AhError
from .coordinator import AhExtraCoordinator
from .entity import AhEntity
from .model import apply_aliases, best_product_match, parse_alias, parse_quantity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: AhConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([AhShoppingList(entry.runtime_data.extra, entry.runtime_data.recipes), AhRecipeIngredients(entry.runtime_data), AhAliasList(entry.runtime_data)])


class AhShoppingList(AhEntity, TodoListEntity):
    _attr_icon = "mdi:cart"
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
    )

    def __init__(self, extra: AhExtraCoordinator, recipes=None) -> None:
        super().__init__(extra, "shopping_list")
        self._recipes = recipes

    @property
    def todo_items(self) -> list[TodoItem]:
        return [
            TodoItem(
                uid=i.uid,
                summary=i.description if i.quantity <= 1 else f"{i.description} ({i.quantity}x)",
                status=TodoItemStatus.NEEDS_ACTION,
            )
            for i in self.coordinator.data.shopping_list
        ]

    async def _resolve(self, text: str) -> tuple[str, int | None]:
        """Turn what the user typed into the AH product they most likely mean."""
        client = self.coordinator.client
        known = self.coordinator.data.known
        query = apply_aliases(text, self._recipes.aliases) if self._recipes else text  # your own translations
        try:
            hits = await client.async_search_products(query)
        except AhError as err:
            _LOGGER.debug("Product search failed for %r: %s", text, err)
            hits = []
        match = best_product_match(query, known, hits)
        return (match[1], match[0]) if match else (text, None)

    async def async_create_todo_item(self, item: TodoItem) -> None:
        # "2 courgette" / "courgette 2x" -> quantity 2; "courgette" -> "AH Courgette"
        quantity, text = parse_quantity((item.summary or "").strip())
        if not text:
            return
        title, product_id = await self._resolve(text)
        await self.coordinator.client.async_add_list_item(title, quantity, product_id)
        await self.coordinator.async_request_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        for uid in uids:
            await self.coordinator.client.async_remove_list_item(uid)
        await self.coordinator.async_request_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        # AH has no "done" state: ticking an item off removes it from the list.
        if item.uid is None:
            return
        old = next((i for i in self.coordinator.data.shopping_list if i.uid == item.uid), None)
        if item.status == TodoItemStatus.COMPLETED:
            await self.coordinator.client.async_remove_list_item(item.uid)
        elif old is not None and item.summary and item.summary != old.description:
            quantity, text = parse_quantity(item.summary.strip())
            title, product_id = await self._resolve(text)
            await self.coordinator.client.async_remove_list_item(item.uid)
            await self.coordinator.client.async_add_list_item(
                title, quantity if quantity > 1 else old.quantity, product_id
            )
        await self.coordinator.async_request_refresh()


class AhRecipeIngredients(AhEntity, TodoListEntity):
    """Ingredients of the selected recipe: add, edit (rename) and delete lines."""

    _attr_icon = "mdi:format-list-bulleted"
    _attr_name = "Recept ingrediënten"
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
    )

    def __init__(self, runtime) -> None:
        super().__init__(runtime.extra, "recipe_ingredients")
        self._recipes = runtime.recipes
        self._attr_translation_key = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._recipes.async_add_listener(self.async_write_ha_state))

    @property
    def todo_items(self) -> list[TodoItem]:
        r = self._recipes.current()
        if not r:
            return []
        return [
            TodoItem(uid=l["id"], summary=l["raw"], status=TodoItemStatus.NEEDS_ACTION)
            for l in r["lines"]
        ]

    @property
    def extra_state_attributes(self) -> dict:
        r = self._recipes.current() or {}
        return {"recept": r.get("name"), "hoeveelheden_voor_personen": r.get("base")}

    async def async_create_todo_item(self, item: TodoItem) -> None:
        if self._recipes.selected:
            await self._recipes.async_add_line(self._recipes.selected, item.summary or "")

    async def async_update_todo_item(self, item: TodoItem) -> None:
        if self._recipes.selected and item.uid and item.summary:
            await self._recipes.async_update_line(self._recipes.selected, item.uid, item.summary)

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        if self._recipes.selected:
            for uid in uids:
                await self._recipes.async_remove_line(self._recipes.selected, uid)


class AhAliasList(AhEntity, TodoListEntity):
    """Your own translations as a last resort: 'cremé fraise = creme fraiche'."""

    _attr_icon = "mdi:translate"
    _attr_name = "Vertaallijst"
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
    )

    def __init__(self, runtime) -> None:
        super().__init__(runtime.extra, "alias_list")
        self._recipes = runtime.recipes
        self._attr_translation_key = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._recipes.async_add_listener(self.async_write_ha_state))

    @property
    def todo_items(self) -> list[TodoItem]:
        return [
            TodoItem(uid=k, summary=f"{k} = {v}", status=TodoItemStatus.NEEDS_ACTION)
            for k, v in sorted(self._recipes.aliases.items())
        ]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        if (pair := parse_alias(item.summary or "")) is not None:
            await self._recipes.async_set_alias(*pair)

    async def async_update_todo_item(self, item: TodoItem) -> None:
        if item.uid and (pair := parse_alias(item.summary or "")) is not None:
            await self._recipes.async_remove_alias(item.uid)
            await self._recipes.async_set_alias(*pair)

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        for uid in uids:
            await self._recipes.async_remove_alias(uid)
