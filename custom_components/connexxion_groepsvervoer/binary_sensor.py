"""Binary sensor: is a ride happening around now?"""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .coordinator import ConnexxionConfigEntry, ConnexxionCoordinator
from .entity import ConnexxionEntity
from .parser import ride_window

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConnexxionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor."""
    async_add_entities([ConnexxionRideWindowSensor(entry.runtime_data)])


class ConnexxionRideWindowSensor(ConnexxionEntity, BinarySensorEntity):
    """On from 45 min before pickup until 15 min after (live) arrival."""

    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator: ConnexxionCoordinator) -> None:
        super().__init__(coordinator, "ride_window")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_time_interval(self.hass, self._tick, timedelta(minutes=1))
        )

    @callback
    def _tick(self, _now: datetime) -> None:
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        now = dt_util.now()
        for ride in self.coordinator.data.rides:
            window = ride_window(ride)
            if window and window[0] <= now < window[1]:
                return True
        return False
