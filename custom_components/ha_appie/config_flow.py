"""Config flow: log in once with the code from the AH login redirect."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LOGIN_URL, AhApiError, AhAuthError, AhClient, extract_code
from .const import CONF_CODE, DOMAIN


class AhBezorgingConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

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
