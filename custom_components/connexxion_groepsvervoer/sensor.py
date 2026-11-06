"""Sensors for Connexxion Groepsvervoer."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ConnexxionConfigEntry, ConnexxionCoordinator
from .entity import ConnexxionEntity
from .parser import Ride

PARALLEL_UPDATES = 0


def ride_attributes(ride: Ride | None) -> dict[str, Any]:
    """Attributes shared by the ride sensors."""
    if ride is None:
        return {}
    return {
        **ride.as_dict(),
        "vehicle_updated": ride.vehicle_updated.isoformat()
        if ride.vehicle_updated
        else None,
    }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConnexxionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            ConnexxionPickupSensor(coordinator),
            ConnexxionArrivalSensor(coordinator),
            ConnexxionRidesSensor(coordinator),
        ]
    )


class _RideSensor(ConnexxionEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def _ride(self) -> Ride | None:
        return self.coordinator.data.current

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return ride_attributes(self._ride)


class ConnexxionPickupSensor(_RideSensor):
    """Expected pickup time of the current or next ride (live when known)."""

    _attr_icon = "mdi:car-clock"

    def __init__(self, coordinator: ConnexxionCoordinator) -> None:
        super().__init__(coordinator, "pickup")

    @property
    def native_value(self) -> datetime | None:
        return self._ride.expected_pickup if self._ride else None


class ConnexxionArrivalSensor(_RideSensor):
    """Expected arrival time of the current or next ride (live when known)."""

    _attr_icon = "mdi:home-clock"

    def __init__(self, coordinator: ConnexxionCoordinator) -> None:
        super().__init__(coordinator, "arrival")

    @property
    def native_value(self) -> datetime | None:
        return self._ride.expected_arrival if self._ride else None


class ConnexxionRidesSensor(ConnexxionEntity, SensorEntity):
    """Number of upcoming rides, with the list as attribute."""

    _attr_icon = "mdi:calendar-clock"
    _unrecorded_attributes = frozenset({"rides"})

    def __init__(self, coordinator: ConnexxionCoordinator) -> None:
        super().__init__(coordinator, "rides")

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.rides)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"rides": [r.as_dict() for r in self.coordinator.data.rides]}
