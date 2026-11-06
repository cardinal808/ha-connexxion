"""Setup, entities and diagnostics."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.connexxion_groepsvervoer.api import (
    ConnexxionAuthError,
    ConnexxionConnectionError,
)
from custom_components.connexxion_groepsvervoer.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .conftest import CLIENT

P = "connexxion_tim"


async def _setup(hass, entry):
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_entities_during_ride(
    hass: HomeAssistant, config_entry, mock_api, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-12T14:00:00+01:00")
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    # Live data was fetched for today's ride only.
    assert mock_api["live"].call_count == 1
    assert mock_api["live"].call_args.args == (1001, "2026-11-12T00:00:00")

    pickup = hass.states.get(f"sensor.{P}_pickup")
    assert pickup.state == "2026-11-12T13:12:00+00:00"  # live 14:12
    assert pickup.attributes["pickup_time"] == "14:05"
    assert pickup.attributes["driver"] == "Piet"
    assert hass.states.get(f"sensor.{P}_arrival").state == "2026-11-12T13:55:00+00:00"
    # Yesterday's ride is not counted.
    assert hass.states.get(f"sensor.{P}_rides").state == "2"
    assert hass.states.get(f"binary_sensor.{P}_ride_window").state == "on"

    vehicle = hass.states.get(f"device_tracker.{P}_vehicle")
    assert vehicle.attributes["latitude"] == 52.1
    assert vehicle.attributes["license_plate"] == "AB-123-C"
    entity = er.async_get(hass).async_get(f"device_tracker.{P}_vehicle")
    assert entity.entity_category is None

    cal = hass.states.get(f"calendar.{P}_schedule")
    assert cal.attributes["message"] == "Taxi naar huis (Gepland)"
    result = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "entity_id": f"calendar.{P}_schedule",
            "start_date_time": "2026-11-12T00:00:00+01:00",
            "end_date_time": "2026-11-20T00:00:00+01:00",
        },
        blocking=True,
        return_response=True,
    )
    events = result[f"calendar.{P}_schedule"]["events"]
    assert len(events) == 2
    assert "Ophalen: 14:12 (gepland 14:05)" in events[0]["description"]
    assert "Kenteken: AB-123-C" in events[0]["description"]

    diag = await async_get_config_entry_diagnostics(hass, config_entry)
    assert diag["entry"]["password"] == "**REDACTED**"
    assert diag["rides"][0]["driver"] == "**REDACTED**"

    # After the ride the window closes and the sensors move to Friday.
    freezer.move_to("2026-11-12T16:00:00+01:00")
    await config_entry.runtime_data.async_refresh()
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(f"binary_sensor.{P}_ride_window").state == "off"
    assert hass.states.get(f"sensor.{P}_pickup").state == "2026-11-13T13:10:00+00:00"
    assert hass.states.get(f"device_tracker.{P}_vehicle").state == "unknown"

    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_no_live_outside_ride(
    hass: HomeAssistant, config_entry, mock_api, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-12T09:00:00+01:00")
    await _setup(hass, config_entry)
    assert mock_api["live"].call_count == 0
    assert hass.states.get(f"sensor.{P}_pickup").state == "2026-11-12T13:05:00+00:00"


async def test_live_error_is_ignored(
    hass: HomeAssistant, config_entry, mock_api, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-12T14:00:00+01:00")
    mock_api["live"].side_effect = ConnexxionConnectionError("boom")
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(f"sensor.{P}_pickup").state == "2026-11-12T13:05:00+00:00"


async def test_auth_failure_starts_reauth(hass: HomeAssistant, config_entry) -> None:
    with patch(f"{CLIENT}.async_get_trips", side_effect=ConnexxionAuthError):
        await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"]["source"] == SOURCE_REAUTH for f in flows)


async def test_connection_error_retries(hass: HomeAssistant, config_entry) -> None:
    with patch(f"{CLIENT}.async_get_trips", side_effect=ConnexxionConnectionError("x")):
        await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
