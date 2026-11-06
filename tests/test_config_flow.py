"""Config flow tests."""

from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.connexxion_groepsvervoer.api import (
    ConnexxionAuthError,
    ConnexxionConnectionError,
)
from custom_components.connexxion_groepsvervoer.const import CONF_CUSTOMER_ID, DOMAIN

from .conftest import CLIENT, CREDENTIALS


@pytest.fixture(autouse=True)
def no_setup():
    with patch(
        "custom_components.connexxion_groepsvervoer.async_setup_entry",
        return_value=True,
    ):
        yield


async def _start(hass):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_single_traveler(hass: HomeAssistant, mock_api) -> None:
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CREDENTIALS
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Connexxion Tim"
    assert result["data"] == {**CREDENTIALS, CONF_CUSTOMER_ID: 4711}
    assert result["result"].unique_id == "4711"


async def test_pick_traveler(hass: HomeAssistant, mock_api, trips) -> None:
    mock_api["travelers"].return_value = [4711, 4712]

    async def trips_for(customer_id, *args):
        if customer_id == 4712:
            return [{**trips[1], "customerName": "Jansen, Sanne"}]
        return trips

    mock_api["trips"].side_effect = trips_for
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CREDENTIALS
    )
    assert result["step_id"] == "traveler"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CUSTOMER_ID: "4712"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Connexxion Sanne"
    assert result["data"][CONF_CUSTOMER_ID] == 4712


@pytest.mark.parametrize(
    ("patch_target", "error", "key"),
    [
        ("async_login", ConnexxionAuthError, "invalid_auth"),
        ("async_login", ConnexxionConnectionError, "cannot_connect"),
        ("async_get_linked_travelers", RuntimeError, "unknown"),
    ],
)
async def test_errors(hass: HomeAssistant, mock_api, patch_target, error, key) -> None:
    result = await _start(hass)
    with patch(f"{CLIENT}.{patch_target}", side_effect=error):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CREDENTIALS
        )
    assert result["errors"] == {"base": key}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CREDENTIALS
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_no_travelers(hass: HomeAssistant, mock_api) -> None:
    mock_api["travelers"].return_value = []
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CREDENTIALS
    )
    assert result["errors"] == {"base": "no_travelers"}


async def test_already_configured(hass: HomeAssistant, mock_api, config_entry) -> None:
    config_entry.add_to_hass(hass)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CREDENTIALS
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(hass: HomeAssistant, mock_api, config_entry) -> None:
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    with patch(f"{CLIENT}.async_login", side_effect=ConnexxionAuthError):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "ouder@example.com", CONF_PASSWORD: "fout"},
        )
    assert result["errors"] == {"base": "invalid_auth"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "ouder@example.com", CONF_PASSWORD: "nieuw"}
    )
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_PASSWORD] == "nieuw"
