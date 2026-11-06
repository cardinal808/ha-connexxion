"""Turn Connexxion API trips into rides. No Home Assistant imports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from .const import (
    DIRECTION_FROM_HOME,
    DIRECTION_TO_HOME,
    IGNORED_STATUSES,
    PORTAL_TZ,
    WINDOW_AFTER,
    WINDOW_BEFORE,
)

DAYS = ["Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag", "Zaterdag", "Zondag"]


def parse_local(value: str | None) -> datetime | None:
    """API time (local, no zone) -> aware datetime."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value[:19]).replace(tzinfo=PORTAL_TZ)
    except ValueError:
        return None


def parse_any(value: str | None) -> datetime | None:
    """Timestamp that may or may not carry a zone."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return parse_local(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=PORTAL_TZ)


def _hm(value: datetime | None) -> str | None:
    return value.astimezone(PORTAL_TZ).strftime("%H:%M") if value else None


def _address(loc: Any) -> str | None:
    if not isinstance(loc, dict):
        return None
    street = " ".join(x for x in (loc.get("street"), loc.get("housenumber")) if x)
    return ", ".join(x for x in (street, loc.get("place")) if x) or None


def first_name(customer_name: str | None) -> str | None:
    """ "Achternaam, Voornaam" -> "Voornaam"."""
    if customer_name and "," in customer_name:
        return customer_name.split(",", 1)[1].strip()
    return customer_name


@dataclass
class Ride:
    """One trip from the schedule, plus live data when available."""

    trip_id: Any
    business_day: str | None
    date: date
    pickup: datetime | None
    arrival: datetime | None
    origin: str | None
    destination: str | None
    origin_address: str | None
    destination_address: str | None
    direction: str | None
    status: str | None
    status_text: str | None
    # Live data, only around the ride.
    driver: str | None = None
    license_plate: str | None = None
    vehicle_latitude: float | None = None
    vehicle_longitude: float | None = None
    vehicle_updated: datetime | None = None
    live_pickup: datetime | None = None
    live_arrival: datetime | None = None

    @property
    def day(self) -> str:
        return DAYS[self.date.weekday()]

    @property
    def expected_pickup(self) -> datetime | None:
        return self.live_pickup or self.pickup

    @property
    def expected_arrival(self) -> datetime | None:
        return self.live_arrival or self.arrival

    def as_dict(self) -> dict[str, Any]:
        """JSON-serialisable summary."""
        return {
            "date": self.date.isoformat(),
            "day": self.day,
            "pickup_time": _hm(self.pickup),
            "arrival_time": _hm(self.arrival),
            "expected_pickup_time": _hm(self.expected_pickup),
            "expected_arrival_time": _hm(self.expected_arrival),
            "origin": self.origin,
            "destination": self.destination,
            "direction": self.direction,
            "status": self.status_text or self.status,
            "driver": self.driver,
            "license_plate": self.license_plate,
        }


def parse_trips(trips: list[dict[str, Any]]) -> list[Ride]:
    """Active, non-cancelled trips sorted by pickup time."""
    active = [
        t
        for t in trips
        if t.get("tripStatus") not in IGNORED_STATUSES
        and t.get("tripRecStatus", "active") == "active"
    ]
    active.sort(key=lambda t: t.get("pickupTime") or "")
    rides: list[Ride] = []
    for t in active:
        pickup = parse_local(t.get("pickupTime"))
        raw_day = (t.get("tripBusinessDay") or t.get("pickupTime") or "")[:10]
        try:
            day = date.fromisoformat(raw_day)
        except ValueError:
            if pickup is None:
                continue
            day = pickup.date()
        if t.get("customerLocationTo"):
            direction = DIRECTION_TO_HOME
        elif t.get("customerLocationFrom"):
            direction = DIRECTION_FROM_HOME
        else:
            direction = None
        rides.append(
            Ride(
                trip_id=t.get("tripId"),
                business_day=t.get("tripBusinessDay"),
                date=day,
                pickup=pickup,
                arrival=parse_local(t.get("deliveryTime")),
                origin=t.get("institutionLocationFrom")
                or t.get("customerLocationFrom")
                or _address(t.get("locationFrom")),
                destination=t.get("institutionLocationTo")
                or t.get("customerLocationTo")
                or _address(t.get("locationTo")),
                origin_address=_address(t.get("locationFrom")),
                destination_address=_address(t.get("locationTo")),
                direction=direction,
                status=t.get("tripStatus"),
                status_text=t.get("tripStatusDisplayText"),
            )
        )
    return rides


def apply_live(ride: Ride, data: dict[str, Any]) -> None:
    """Merge a vehicles-position response into a ride."""
    vehicle = data.get("vehicleLocation") or {}
    ride.driver = vehicle.get("driverName") or None
    ride.license_plate = vehicle.get("licensePlate") or None
    ride.vehicle_latitude = vehicle.get("latitude")
    ride.vehicle_longitude = vehicle.get("longitude")
    ride.vehicle_updated = parse_any(vehicle.get("lastGPSTimeStamp"))
    ride.live_pickup = parse_local(data.get("estimatedPickupTime"))
    ride.live_arrival = parse_local(data.get("estimatedDeliveryTime"))
    if data.get("tripStatus"):
        ride.status = data["tripStatus"]


def ride_window(ride: Ride) -> tuple[datetime, datetime] | None:
    """Span around a ride: 45 min before pickup until 15 min after arrival."""
    start, end = ride.expected_pickup, ride.expected_arrival or ride.expected_pickup
    if start is None or end is None:
        return None
    return start - WINDOW_BEFORE, end + WINDOW_AFTER


def ride_end(ride: Ride) -> datetime:
    """Moment after which a ride counts as done."""
    end = ride.expected_arrival or ride.expected_pickup
    if end is None:
        return datetime.combine(ride.date + timedelta(days=1), time.min, PORTAL_TZ)
    return end + WINDOW_AFTER


def next_ride(rides: list[Ride], now: datetime) -> Ride | None:
    """Current or next ride."""
    for ride in rides:
        if ride_end(ride) > now:
            return ride
    return None
