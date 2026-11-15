"""The built-in dashboard card and the PDF downloads.

The card JS is registered as a real Lovelace resource (the same storage the
"Add resource" dialog uses), not with add_extra_js_url, which re-injects a
script tag on every page load and is known to leave stale copies after an
update. Two details matter (both bit other integrations before):

- `hass.data["lovelace"]` is a `LovelaceData` dataclass whose field is
  `resource_mode` (not `mode`);
- `resources.async_items()` reads an empty list until the collection is
  loaded, so `_async_ensure_loaded()` is awaited first (otherwise a restart
  could create a duplicate resource instead of updating ours).

Anything unexpected falls back to add_extra_js_url instead of failing.
The file itself is served with caching disabled, so a wall tablet that stays
open for days still gets the new card after an update. The card JS handles
HA 2026.8's scoped custom-element registry race itself (defineElement).
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .api import AhError
from .const import CARD_FILENAME, DOMAIN, FRONTEND_URL

_LOGGER = logging.getLogger(__name__)
RESOURCE_TYPE = "module"


class AhCardView(HomeAssistantView):
    """Serves the card JS with Cache-Control: no-store."""

    name = "ha_appie:card_js"
    url = FRONTEND_URL
    requires_auth = False  # a static script, like any Lovelace resource; contains no data

    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path

    async def get(self, request: web.Request) -> web.StreamResponse:
        response = web.FileResponse(self._file_path)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


def _runtime(hass: HomeAssistant):
    for entry in hass.config_entries.async_entries(DOMAIN):
        if getattr(entry, "runtime_data", None):
            return entry.runtime_data
    return None


class AhPdfView(HomeAssistantView):
    """GET /api/ha_appie/pdf/{kind}/{ref}: a receipt (kind=receipt) or invoice (kind=invoice) PDF.

    Logged-in HA users only (the card fetches it with the user's token); nothing is stored."""

    name = "ha_appie:pdf"
    url = "/api/ha_appie/pdf/{kind}/{ref}"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request, kind: str, ref: str) -> web.Response:
        rt = _runtime(self.hass)
        if rt is None:
            return web.Response(status=503)
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", ref):
            return web.Response(status=400)
        from .pdfs import async_fetch_pdf  # local import: pdfs imports this module's siblings

        try:
            name, pdf = await async_fetch_pdf(rt, kind, ref)
        except (AhError, ValueError) as err:
            _LOGGER.debug("PDF %s not available: %s", kind, err)
            return web.Response(status=404, text="Niet beschikbaar")
        return web.Response(
            body=pdf,
            content_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{name}"', "Cache-Control": "no-store"},
        )


async def async_register_frontend(hass: HomeAssistant, version: str, card: bool) -> None:
    """Views once per HA run; the Lovelace resource on every setup (it carries the version)."""
    if not hass.data.get(f"{DOMAIN}_views"):
        hass.data[f"{DOMAIN}_views"] = True
        hass.http.register_view(AhCardView(Path(__file__).parent / "www" / CARD_FILENAME))
        hass.http.register_view(AhPdfView(hass))
    if not card or hass.data.get(f"{DOMAIN}_resource") == version:
        return
    hass.data[f"{DOMAIN}_resource"] = version
    if not await LovelaceResourceRegistration(hass, FRONTEND_URL).async_try_register(version):
        try:
            from homeassistant.components.frontend import add_extra_js_url

            add_extra_js_url(hass, f"{FRONTEND_URL}?v={version}")
            _LOGGER.debug("Card registered via add_extra_js_url fallback")
        except ImportError:
            pass


class LovelaceResourceRegistration:
    def __init__(self, hass: HomeAssistant, js_path: str) -> None:
        self.hass = hass
        self._js_path = js_path  # without ?v=

    async def async_try_register(self, version: str) -> bool:
        """Create/update our resource. False (never raises) means: use the fallback."""
        lovelace = self.hass.data.get("lovelace")
        if lovelace is None:
            return False
        try:
            if lovelace.resource_mode != "storage":
                _LOGGER.debug("Lovelace resources are in %s mode, not storage", lovelace.resource_mode)
                return False
            await self._async_create_or_update(lovelace.resources, version)
            return True
        except Exception as err:  # noqa: BLE001 - any shape mismatch: fall back
            _LOGGER.debug("Could not register the card as a Lovelace resource: %s", err)
            return False

    async def _async_create_or_update(self, resources, version: str) -> None:
        ensure_loaded = getattr(resources, "_async_ensure_loaded", None)
        if ensure_loaded is not None:
            await ensure_loaded()  # async_items() is empty until loaded
        url = f"{self._js_path}?v={version}"
        existing = [r for r in resources.async_items() if str(r.get("url", "")).split("?")[0] == self._js_path]
        if not existing:
            await resources.async_create_item({"res_type": RESOURCE_TYPE, "url": url})
        elif existing[0]["url"] != url:
            await resources.async_update_item(existing[0]["id"], {"res_type": RESOURCE_TYPE, "url": url})
