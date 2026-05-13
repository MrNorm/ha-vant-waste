"""Config flow for Havant Waste."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HavantWasteAuthError, HavantWasteClient, HavantWasteError
from .const import DOMAIN

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class HavantWasteConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()

            client = HavantWasteClient(
                session=async_get_clientsession(self.hass),
                username=username,
                password=user_input[CONF_PASSWORD],
            )
            try:
                await client.async_validate()
            except HavantWasteAuthError:
                errors["base"] = "invalid_auth"
            except HavantWasteError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 — surface as generic unknown
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=username,
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )
