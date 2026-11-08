"""Recipes: stored locally, scaled to a number of persons, added to the AH list in one press."""
from __future__ import annotations

import logging
import uuid
from collections.abc import Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import slugify

from .api import AhClient, AhError
from .const import DOMAIN
from .model import (
    apply_aliases,
    best_product_match,
    parse_ingredient,
    format_amount,
    list_payload,
    packs_needed,
    parse_recipe_text,
    search_variants,
    scale_amount,
)

_LOGGER = logging.getLogger(__name__)
MATCHER_VERSION = 3


class Recipes:
    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store = Store(hass, 1, f"{DOMAIN}_recipes_{entry_id}")
        self.recipes: dict[str, dict] = {}
        self.selected: str | None = None
        self.pin_target: str | None = None  # line id chosen in the "pin product" dropdown
        self._migrated = False
        self.aliases: dict[str, str] = {}  # your own translations: "creme fraise" -> "creme fraiche"
        self._listeners: list[Callable[[], None]] = []
        self.draft = {"name": "", "persons": 4, "ingredients": ""}  # the 'new recipe' form in the dashboard

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self.recipes = data.get("recipes") or {}
        for r in self.recipes.values():
            for line in r["lines"]:
                line.setdefault("id", uuid.uuid4().hex)
        self.selected = data.get("selected")
        self.aliases = dict(data.get("aliases") or {})
        if data.get("matcher") != MATCHER_VERSION:  # old automatic product picks were worse: choose again
            for r in self.recipes.values():
                for line in r["lines"]:
                    if not line.get("pinned"):
                        for k in ("pid", "title", "size"):
                            line.pop(k, None)
            self._migrated = True
        self._fix_selected()

    def _fix_selected(self) -> None:
        if self.selected not in self.recipes:
            self.selected = next(iter(sorted(self.recipes)), None)

    def current(self) -> dict | None:
        return self.recipes.get(self.selected) if self.selected else None

    async def _async_save(self) -> None:
        self._fix_selected()
        await self._store.async_save({"recipes": self.recipes, "selected": self.selected, "matcher": MATCHER_VERSION, "aliases": self.aliases})
        for cb in list(self._listeners):
            cb()

    @callback
    def async_add_listener(self, cb: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(cb)
        return lambda: self._listeners.remove(cb)

    @callback
    def set_draft(self, **fields) -> None:
        self.draft.update(fields)
        for cb in list(self._listeners):
            cb()

    async def async_save_draft(self) -> tuple[str, int]:
        """Save the form as a recipe (ingredients separated by ';' or new lines) and empty the form."""
        d = self.draft
        if not d["name"].strip():
            raise ValueError("Geef het recept eerst een naam")
        text = d["ingredients"].replace(";", "\n")
        result = await self.async_save_recipe(d["name"], d["persons"], text)
        self.draft = {"name": "", "persons": d["persons"], "ingredients": ""}
        for cb in list(self._listeners):
            cb()
        return result

    def find(self, name: str) -> str | None:
        rid = slugify(name)
        if rid in self.recipes:
            return rid
        return next((k for k, r in self.recipes.items() if r["name"].lower() == name.strip().lower()), None)

    async def async_save_recipe(self, name: str, persons: int, ingredients: str) -> tuple[str, int]:
        lines = parse_recipe_text(ingredients)
        if not lines:
            raise ValueError("Geen ingrediënten herkend")
        rid = self.find(name) or slugify(name)
        old = self.recipes.get(rid, {})
        self.recipes[rid] = {
            "name": name.strip(),
            "base": max(1, int(persons)),
            "persons": int(old.get("persons") or persons),
            "lines": [
                {"id": uuid.uuid4().hex, "name": i.name, "amount": i.amount, "unit": i.unit, "raw": i.raw}
                for i in lines
            ],
        }
        if old:  # recipe text changed: forget cached product choices only for changed ingredients
            cache = {l["name"]: l for l in old.get("lines", []) if l.get("pid")}
            for l in self.recipes[rid]["lines"]:
                if (c := cache.get(l["name"])):
                    l.update(pid=c["pid"], title=c["title"], size=c.get("size"), pinned=c.get("pinned", False))
        self.selected = rid
        await self._async_save()
        return rid, len(lines)

    async def async_select(self, name: str) -> None:
        if (rid := self.find(name)) is not None:
            self.selected = rid
            await self._async_save()

    async def async_set_persons(self, persons: int) -> None:
        if (r := self.current()) is not None:
            r["persons"] = max(1, int(persons))
            await self._async_save()

    # one ingredient line at a time (used by the editor to-do list)
    async def async_add_line(self, rid: str, text: str) -> None:
        if (i := parse_ingredient(text)) is not None:
            self.recipes[rid]["lines"].append(
                {"id": uuid.uuid4().hex, "name": i.name, "amount": i.amount, "unit": i.unit, "raw": i.raw}
            )
            await self._async_save()

    async def async_update_line(self, rid: str, lid: str, text: str) -> None:
        if (i := parse_ingredient(text)) is None:
            return
        for line in self.recipes[rid]["lines"]:
            if line["id"] == lid:
                if line["name"] != i.name:  # other ingredient: choose its product again
                    for k in ("pid", "title", "size", "pinned"):
                        line.pop(k, None)
                line.update(name=i.name, amount=i.amount, unit=i.unit, raw=i.raw)
        await self._async_save()

    async def async_remove_line(self, rid: str, lid: str) -> None:
        self.recipes[rid]["lines"] = [l for l in self.recipes[rid]["lines"] if l["id"] != lid]
        await self._async_save()

    async def async_delete(self, rid: str) -> None:
        self.recipes.pop(rid, None)
        await self._async_save()

    async def _resolve(self, client: AhClient, known: dict, line: dict) -> None:
        if line.get("pid"):
            return
        hits: list[dict] = []
        match = None
        name = apply_aliases(line["name"], self.aliases)
        for variant in search_variants(name):
            try:
                hits = await client.async_search_products(variant)
            except AhError as err:
                _LOGGER.debug("Search failed for %r: %s", variant, err)
                continue
            match = best_product_match(name, known, hits, strict=True)
            if match:
                break
        if not match:
            return
        pid, title = match
        size = next((h.get("salesUnitSize") for h in hits if str(h.get("webshopId")) == str(pid)), None)
        line.update(pid=pid, title=title, size=size)

    async def async_set_alias(self, key: str, value: str) -> None:
        self.aliases[key] = value
        await self._async_save()

    async def async_remove_alias(self, key: str) -> None:
        self.aliases.pop(key, None)
        await self._async_save()

    async def async_pin(self, rid: str, lid: str, pid: int, title: str, size: str | None) -> None:
        """Fix the product for one ingredient (used instead of the automatic choice)."""
        for line in self.recipes[rid]["lines"]:
            if line["id"] == lid:
                line.update(pid=int(pid), title=title, size=size, pinned=True)
        await self._async_save()

    async def async_unpin(self, rid: str, lid: str) -> None:
        for line in self.recipes[rid]["lines"]:
            if line["id"] == lid:
                for k in ("pid", "title", "size", "pinned"):
                    line.pop(k, None)
        await self._async_save()

    async def async_add_to_list(self, extra, rid: str, persons: int | None = None) -> str:
        """Put the recipe on the AH list (scaled). Returns a short summary."""
        recipe = self.recipes[rid]
        n = int(persons or recipe["persons"])
        client, data = extra.client, extra.data
        on_list = {i.product_id: i.quantity for i in await client.async_get_list() if i.product_id is not None}  # live, not the 30-min cache
        wanted: dict[int, list] = {}  # pid -> [title, packs]
        texts: list[str] = []
        for line in recipe["lines"]:
            await self._resolve(client, data.known, line)
            amount = scale_amount(line["amount"], recipe["base"], n)
            if line.get("pid"):
                packs = packs_needed(amount, line["unit"], line.get("size"))
                entry = wanted.setdefault(line["pid"], [line["title"], 0])
                entry[1] += packs
            else:
                texts.append(f"{format_amount(amount, line['unit'])} {line['name']}".strip())
        await client.async_add_list_items(
            [list_payload(title, packs + on_list.get(pid, 0), pid) for pid, (title, packs) in wanted.items()]
        )
        for text in texts:  # one by one: AH answers 409 "cannot be duplicate" for a text it already holds
            try:
                await client.async_add_list_item(text, 1)
            except AhError as err:
                if getattr(err, "status", None) != 409:
                    raise
        await self._async_save()  # keep the resolved products for next time
        await extra.async_request_refresh()
        return f"{recipe['name']} voor {n} personen: {len(wanted)} producten, {len(texts)} als tekst"
