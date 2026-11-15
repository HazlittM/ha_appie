"""Services: save/delete a recipe, put a recipe on the AH list."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .api import AhError
from .const import (
    DOMAIN,
    OPT_ALLERHANDE,
    OPT_DELIVERY_DETAILS,
    OPT_FAVORITES,
    OPT_PRODUCT_INFO,
    OPT_RECEIPT_DETAILS,
    opt,
)
from .model import search_hit
from .pdfs import async_save_pdf

_LOGGER = logging.getLogger(__name__)

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
    async_register_v05_services(hass)


# ------------------------------------------------------------------ v0.5 services
# Read-only, except: putting products on the shopping list (as the to-do already does),
# saving an Allerhande recipe as your own recipe, and adding to a favourite list.

PDF = vol.Schema({vol.Optional("id", default="latest"): cv.string,
                  vol.Optional("folder", default="/media/ha_appie"): cv.string})
PRODUCT = vol.Schema({vol.Exclusive("product_id", "p"): vol.Coerce(int), vol.Exclusive("barcode", "p"): cv.string})
SEARCH = vol.Schema({vol.Required("query"): cv.string,
                     vol.Optional("limit", default=12): vol.All(vol.Coerce(int), vol.Range(min=1, max=30))})
ADD_PRODUCT = vol.Schema({vol.Required("product_id"): vol.Coerce(int), vol.Optional("title"): cv.string,
                          vol.Optional("quantity", default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=50))})
RECIPE_ID = vol.Schema({vol.Required("recipe_id"): vol.Coerce(int)})
IMPORT = vol.Schema({vol.Required("recipe_id"): vol.Coerce(int), vol.Optional("name"): cv.string})
RECEIPT = vol.Schema({vol.Optional("id", default="latest"): cv.string})
FAVORITE = vol.Schema({vol.Required("product_id"): vol.Coerce(int), vol.Optional("list"): cv.string})


def _need(rt, key: str) -> None:
    if not opt(rt.extra.config_entry, key):
        raise HomeAssistantError("Dit onderdeel staat uit in de opties van HA Appie")


async def _ah(coro):
    try:
        return await coro
    except AhError as err:
        raise HomeAssistantError(f"Albert Heijn gaf geen antwoord: {err}") from err
    except (AttributeError, KeyError, TypeError, ValueError) as err:  # AH changed the shape of an answer
        _LOGGER.debug("Unexpected answer from AH: %r", err)
        raise HomeAssistantError("Albert Heijn gaf een onverwacht antwoord") from err


def async_register_v05_services(hass: HomeAssistant) -> None:
    async def save_receipt_pdf(call: ServiceCall) -> dict:
        rt = _runtime(hass)
        return {"path": await _ah(async_save_pdf(hass, rt, "receipt", call.data["id"], call.data["folder"]))}

    async def save_invoice_pdf(call: ServiceCall) -> dict:
        rt = _runtime(hass)
        _need(rt, OPT_DELIVERY_DETAILS)
        return {"path": await _ah(async_save_pdf(hass, rt, "invoice", call.data["id"], call.data["folder"]))}

    async def get_receipt(call: ServiceCall) -> dict:
        rt = _runtime(hass)
        _need(rt, OPT_RECEIPT_DETAILS)
        ref = call.data["id"]
        if ref == "latest":
            ref = next((r.id for r in rt.extra.data.receipts if r.amount > 0), None)
            if ref is None:
                raise HomeAssistantError("Geen kassabon gevonden")
        cache = rt.receipts
        d = cache.details.get(ref) or await _ah(rt.extra.client.async_get_receipt_details(ref))
        if d is None:
            raise HomeAssistantError("Kassabon niet gevonden")
        return {"id": d.id, "saved": d.discount_total,
                "lines": [{"name": l.name, "quantity": l.quantity, "price": l.price, "amount": l.amount,
                           "product_id": cache.webshop_for(l.pos_id), "image": cache.image_for(l.pos_id)}
                          for l in d.lines],
                "discounts": [{"name": n, "amount": a} for n, a in d.discounts],
                "payments": [{"method": m, "amount": a} for m, a in d.payments]}

    async def product_details(call: ServiceCall) -> dict:
        rt = _runtime(hass)
        _need(rt, OPT_PRODUCT_INFO)
        client = rt.extra.client
        pid = call.data.get("product_id")
        if pid is None:
            if not call.data.get("barcode"):
                raise HomeAssistantError("Geef product_id of barcode")
            hit = await _ah(client.async_get_product_by_gtin(call.data["barcode"].strip()))
            if not hit:
                raise HomeAssistantError("Geen AH-product met deze barcode")
            pid = hit["product_id"]
        details = await _ah(client.async_get_product_details(pid))
        if not details:
            raise HomeAssistantError("Product niet gevonden")
        return details

    async def search_products(call: ServiceCall) -> dict:
        rt = _runtime(hass)
        hits = await _ah(rt.extra.client.async_search_products(call.data["query"], limit=call.data["limit"]))
        return {"products": [h for x in hits if (h := search_hit(x))]}

    async def add_product(call: ServiceCall) -> dict:
        rt = _runtime(hass)
        client = rt.extra.client
        pid, qty = call.data["product_id"], call.data["quantity"]
        title = call.data.get("title")
        current = await _ah(client.async_get_list())  # live, so the quantity adds up
        existing = next((i for i in current if i.product_id == pid), None)
        if not title:
            title = existing.description if existing else None
        if not title:
            products = await _ah(client.async_get_products([pid]))
            title = str(products[0].get("title")) if products else f"Product {pid}"
        await _ah(client.async_add_list_item(title, qty + (existing.quantity if existing else 0), pid))
        await rt.extra.async_request_refresh()
        return {"added": f"{qty}x {title}"}

    async def search_recipes(call: ServiceCall) -> dict:
        rt = _runtime(hass)
        _need(rt, OPT_ALLERHANDE)
        return {"recipes": await _ah(rt.extra.client.async_search_recipes(call.data["query"], call.data["limit"]))}

    async def get_recipe(call: ServiceCall) -> dict:
        rt = _runtime(hass)
        _need(rt, OPT_ALLERHANDE)
        recipe = await _ah(rt.extra.client.async_get_recipe(call.data["recipe_id"]))
        if not recipe:
            raise HomeAssistantError("Recept niet gevonden")
        return recipe

    async def import_recipe(call: ServiceCall) -> dict:
        """An Allerhande recipe becomes one of your own recipes, with the products AH proposes pinned."""
        rt = _runtime(hass)
        _need(rt, OPT_ALLERHANDE)
        client = rt.extra.client
        recipe = await _ah(client.async_get_recipe(call.data["recipe_id"]))
        if not recipe or not recipe["ingredients"]:
            raise HomeAssistantError("Recept niet gevonden of zonder ingrediënten")
        name = call.data.get("name") or recipe["title"]
        try:
            rid, n = await rt.recipes.async_save_recipe(name, recipe["persons"], "\n".join(recipe["ingredients"]))
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        suggestions = await _ah(client.async_get_recipe_suggestions(call.data["recipe_id"])) or {}
        pinned = 0
        for line in list(rt.recipes.recipes[rid]["lines"]):
            if (s := suggestions.get(line["raw"].strip())) and not line.get("pinned"):
                await rt.recipes.async_pin(rid, line["id"], s[0], s[1], s[2])
                pinned += 1
        return {"recipe": rt.recipes.recipes[rid]["name"], "ingredients": n, "products_from_ah": pinned}

    async def add_to_favorites(call: ServiceCall) -> dict:
        rt = _runtime(hass)
        _need(rt, OPT_FAVORITES)
        client = rt.extra.client
        lists = await _ah(client.async_get_favorite_lists())
        if not lists:
            raise HomeAssistantError("Geen favorietenlijst gevonden")
        wanted = (call.data.get("list") or "").strip().lower()
        target = next((f for f in lists if wanted and wanted in (f.name.lower(), f.id.lower())), lists[0])
        await _ah(client.async_add_to_favorite_list(target.id, call.data["product_id"]))
        if rt.info is not None:
            await rt.info.async_request_refresh()
        return {"list": target.name}

    def reg(name, func, schema):
        hass.services.async_register(DOMAIN, name, func, schema, supports_response=SupportsResponse.OPTIONAL)

    reg("save_receipt_pdf", save_receipt_pdf, PDF)
    reg("save_invoice_pdf", save_invoice_pdf, PDF)
    reg("get_receipt", get_receipt, RECEIPT)
    reg("product_details", product_details, PRODUCT)
    reg("search_products", search_products, SEARCH)
    reg("add_product", add_product, ADD_PRODUCT)
    reg("search_recipes", search_recipes, SEARCH)
    reg("get_recipe", get_recipe, RECIPE_ID)
    reg("import_recipe", import_recipe, IMPORT)
    reg("add_to_favorites", add_to_favorites, FAVORITE)
