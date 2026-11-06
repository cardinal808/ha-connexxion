"""Config flow for Connexxion Groepsvervoer."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import ConnexxionAuthError, ConnexxionClient, ConnexxionConnectionError
from .const import CONF_CUSTOMER_ID, DOMAIN
from .parser import first_name

_LOGGER = logging.getLogger(__name__)

PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
EMAIL_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL))

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): EMAIL_SELECTOR,
        vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
    }
)


class ConnexxionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Connexxion Groepsvervoer."""

    VERSION = 1

    def __init__(self) -> None:
        self._credentials: dict[str, Any] = {}
        self._travelers: dict[int, str] = {}

    def _client(self, data: dict[str, Any]) -> ConnexxionClient:
        return ConnexxionClient(
            async_get_clientsession(self.hass), data[CONF_USERNAME], data[CONF_PASSWORD]
        )

    async def _async_travelers(self, client: ConnexxionClient) -> dict[int, str]:
        """Linked travellers with a readable name where we can find one."""
        result: dict[int, str] = {}
        for customer_id in await client.async_get_linked_travelers():
            name = None
            try:
                trips = await client.async_get_trips(customer_id)
                name = first_name(trips[0].get("customerName")) if trips else None
            except ConnexxionConnectionError:
                pass
            result[int(customer_id)] = name or str(customer_id)
        return result

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for e-mail and password."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {
                CONF_USERNAME: user_input[CONF_USERNAME].strip(),
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            try:
                client = self._client(data)
                await client.async_login()
                travelers = await self._async_travelers(client)
            except ConnexxionAuthError:
                errors["base"] = "invalid_auth"
            except ConnexxionConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error while validating Connexxion login")
                errors["base"] = "unknown"
            else:
                if not travelers:
                    errors["base"] = "no_travelers"
                else:
                    self._credentials = data
                    self._travelers = travelers
                    if len(travelers) == 1:
                        return await self._async_create(next(iter(travelers)))
                    return await self.async_step_traveler()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA, {CONF_USERNAME: (user_input or {}).get(CONF_USERNAME)}
            ),
            errors=errors,
        )

    async def async_step_traveler(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Several travellers on one account: pick one."""
        if user_input is not None:
            return await self._async_create(int(user_input[CONF_CUSTOMER_ID]))
        options = [
            SelectOptionDict(value=str(cid), label=name)
            for cid, name in self._travelers.items()
        ]
        return self.async_show_form(
            step_id="traveler",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CUSTOMER_ID): SelectSelector(
                        SelectSelectorConfig(options=options)
                    )
                }
            ),
        )

    async def _async_create(self, customer_id: int) -> ConfigFlowResult:
        await self.async_set_unique_id(str(customer_id))
        self._abort_if_unique_id_configured()
        name = self._travelers.get(customer_id, str(customer_id))
        return self.async_create_entry(
            title=f"Connexxion {name}",
            data={**self._credentials, CONF_CUSTOMER_ID: customer_id},
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Login stopped working."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for new credentials."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {
                **entry.data,
                CONF_USERNAME: user_input[CONF_USERNAME].strip(),
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            try:
                await self._client(data).async_login()
            except ConnexxionAuthError:
                errors["base"] = "invalid_auth"
            except ConnexxionConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error while validating Connexxion login")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(entry, data=data)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_USERNAME, default=entry.data.get(CONF_USERNAME, "")
                ): EMAIL_SELECTOR,
                vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
            }
        )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=schema, errors=errors
        )
