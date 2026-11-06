"""Calendar with every ride on the schedule."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DIRECTION_FROM_HOME, DIRECTION_TO_HOME
from .coordinator import ConnexxionConfigEntry, ConnexxionCoordinator
from .entity import ConnexxionEntity
from .parser import Ride, ride_end

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConnexxionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the calendar."""
    async_add_entities([ConnexxionCalendar(entry.runtime_data)])


def ride_event(ride: Ride) -> CalendarEvent | None:
    """Turn a ride into a calendar event (live times when known)."""
    start = ride.expected_pickup
    if start is None:
        return None
    end = ride.expected_arrival
    if end is None or end <= start:
        end = start + timedelta(minutes=30)
    if ride.direction == DIRECTION_TO_HOME:
        summary = "Taxi naar huis"
    elif ride.direction == DIRECTION_FROM_HOME:
        summary = f"Taxi → {ride.destination}" if ride.destination else "Taxi ophalen"
    else:
        summary = f"Taxi → {ride.destination}" if ride.destination else "Taxi"
    status = ride.status_text or ride.status
    if status:
        summary += f" ({status})"
    info = ride.as_dict()
    lines = [
        f"Ophalen: {info['expected_pickup_time']}"
        + (
            f" (gepland {info['pickup_time']})"
            if info["pickup_time"] != info["expected_pickup_time"]
            else ""
        ),
        f"Aankomst: {info['expected_arrival_time']}"
        + (
            f" (gepland {info['arrival_time']})"
            if info["arrival_time"] != info["expected_arrival_time"]
            else ""
        ),
        f"Van: {ride.origin or '-'}",
        f"Naar: {ride.destination or '-'}",
    ]
    if status:
        lines.append(f"Status: {status}")
    if ride.driver:
        lines.append(f"Chauffeur: {ride.driver}")
    if ride.license_plate:
        lines.append(f"Kenteken: {ride.license_plate}")
    return CalendarEvent(
        start=start,
        end=end,
        summary=summary,
        description="\n".join(lines),
        location=ride.origin_address or ride.origin,
        uid=str(ride.trip_id) if ride.trip_id is not None else None,
    )


class ConnexxionCalendar(ConnexxionEntity, CalendarEntity):
    """All rides on the schedule."""

    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: ConnexxionCoordinator) -> None:
        super().__init__(coordinator, "schedule")

    def _events(self) -> list[CalendarEvent]:
        return [e for r in self.coordinator.data.rides if (e := ride_event(r))]

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        for ride in self.coordinator.data.rides:
            if ride_end(ride) > now and (e := ride_event(ride)):
                return e
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        return [e for e in self._events() if e.end > start_date and e.start < end_date]
