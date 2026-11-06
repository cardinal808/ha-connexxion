"""Diagnostics for Connexxion Groepsvervoer."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_CUSTOMER_ID
from .coordinator import ConnexxionConfigEntry

TO_REDACT = {
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_CUSTOMER_ID,
    "driver",
    "license_plate",
    "origin",
    "destination",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConnexxionConfigEntry
) -> dict[str, Any]:
    """Return diagnostics with personal details removed."""
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "update_interval": str(coordinator.update_interval),
        "updated": data.updated.isoformat() if data.updated else None,
        "rides": [async_redact_data(r.as_dict(), TO_REDACT) for r in data.rides],
    }
