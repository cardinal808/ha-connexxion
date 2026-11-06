"""Vehicle position during a ride."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ConnexxionConfigEntry, ConnexxionCoordinator
from .entity import ConnexxionEntity
from .parser import Ride

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConnexxionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the vehicle tracker."""
    async_add_entities([ConnexxionVehicleTracker(entry.runtime_data)])


class ConnexxionVehicleTracker(ConnexxionEntity, TrackerEntity):
    """GPS position of the vehicle, only while the operator shares it."""

    _attr_icon = "mdi:bus-school"
    _attr_source_type = SourceType.GPS
    # Trackers default to "diagnostic"; this one belongs on the dashboard.
    _attr_entity_category = None

    def __init__(self, coordinator: ConnexxionCoordinator) -> None:
        super().__init__(coordinator, "vehicle")

    @property
    def _ride(self) -> Ride | None:
        ride = self.coordinator.data.current
        if (
            ride
            and ride.vehicle_latitude is not None
            and ride.vehicle_longitude is not None
        ):
            return ride
        return None

    @property
    def latitude(self) -> float | None:
        return self._ride.vehicle_latitude if self._ride else None

    @property
    def longitude(self) -> float | None:
        return self._ride.vehicle_longitude if self._ride else None

    @property
    def location_accuracy(self) -> float:
        return 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        ride = self._ride
        if ride is None:
            return {}
        return {
            "driver": ride.driver,
            "license_plate": ride.license_plate,
            "updated": ride.vehicle_updated.isoformat()
            if ride.vehicle_updated
            else None,
        }
