"""Config flow: log in once with the code from the AH login redirect."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LOGIN_URL, AhApiError, AhAuthError, AhClient, extract_code
from .const import (
    CONF_CODE,
    DEFAULTS,
    DOMAIN,
    OPT_ALLERHANDE,
    OPT_BARGAINS,
    OPT_CARD,
    OPT_CITY,
    OPT_DELIVERY_DETAILS,
    OPT_DELIVERY_SLOTS,
    OPT_FAVORITES,
    OPT_HOUSE_EXTRA,
    OPT_HOUSE_NUMBER,
    OPT_MEMBER_CARDS,
    OPT_PERSONAL_BONUS,
    OPT_POSTAL_CODE,
    OPT_PRODUCT_INFO,
    OPT_RECEIPT_DETAILS,
    OPT_RECEIPT_IMAGES,
    OPT_STORE,
    OPT_STORE_ID,
    OPT_STREET,
)

FEATURES = [
    OPT_RECEIPT_DETAILS, OPT_RECEIPT_IMAGES, OPT_DELIVERY_DETAILS, OPT_PERSONAL_BONUS, OPT_STORE,
    OPT_BARGAINS, OPT_FAVORITES, OPT_MEMBER_CARDS, OPT_ALLERHANDE, OPT_PRODUCT_INFO, OPT_CARD,
]
ADDRESS = [OPT_STREET, OPT_HOUSE_NUMBER, OPT_HOUSE_EXTRA, OPT_POSTAL_CODE, OPT_CITY]


class AhBezorgingConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "AhOptionsFlow":
        return AhOptionsFlow()

    async def _login(self, step_id: str, user_input: dict[str, Any] | None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            try:
                tokens = await AhClient.exchange_code(session, extract_code(user_input[CONF_CODE]))
                member = await AhClient(
                    session, tokens["access_token"], tokens["refresh_token"]
                ).async_member_id()
            except AhAuthError:
                errors["base"] = "invalid_code"
            except AhApiError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(member)
                if self.source == "reauth":
                    self._abort_if_unique_id_mismatch(reason="wrong_account")
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data_updates=tokens
                    )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="HA Appie", data=tokens)
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema({vol.Required(CONF_CODE): str}),
            errors=errors,
            description_placeholders={"login_url": LOGIN_URL},
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._login("user", user_input)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._login("reauth_confirm", user_input)


class AhOptionsFlow(OptionsFlow):
    """Switch every optional part on or off. Saving reloads the integration."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        cur = {**DEFAULTS, **self.config_entry.options}
        if user_input is not None:
            flat: dict[str, Any] = {}
            for value in user_input.values():
                if isinstance(value, dict):
                    flat.update(value)
            flat = {**{k: v for k, v in user_input.items() if not isinstance(v, dict)}, **flat}
            flat[OPT_STORE_ID] = int(flat.get(OPT_STORE_ID) or 0)
            return self.async_create_entry(data=flat)

        def toggle(key: str):
            return vol.Optional(key, default=bool(cur.get(key)))

        def text(key: str):
            return vol.Optional(key, description={"suggested_value": cur.get(key) or ""})

        schema = vol.Schema({
            vol.Required("features"): section(vol.Schema({toggle(k): bool for k in FEATURES}), {"collapsed": False}),
            vol.Required("store_section"): section(vol.Schema({
                vol.Optional(OPT_STORE_ID, default=int(cur.get(OPT_STORE_ID) or 0)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=99999, step=1, mode=selector.NumberSelectorMode.BOX)),
            }), {"collapsed": True}),
            vol.Required("slots_section"): section(vol.Schema({
                toggle(OPT_DELIVERY_SLOTS): bool,
                **{text(k): str for k in ADDRESS},
            }), {"collapsed": True}),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
