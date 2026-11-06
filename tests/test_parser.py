"""Parser and polling tests."""

from datetime import date, datetime, timedelta

import pytest

from custom_components.connexxion_groepsvervoer.const import PORTAL_TZ
from custom_components.connexxion_groepsvervoer.coordinator import (
    next_interval,
    wants_live,
)
from custom_components.connexxion_groepsvervoer.parser import (
    apply_live,
    first_name,
    next_ride,
    parse_trips,
)


def at(d, h, m):
    return datetime(2026, 11, d, h, m, tzinfo=PORTAL_TZ)


def test_parse_trips(trips) -> None:
    rides = parse_trips(trips)
    # Cancelled trip dropped, sorted by pickup time.
    assert [r.trip_id for r in rides] == [900, 1001, 1002]
    ride = rides[1]
    assert ride.date == date(2026, 11, 12)
    assert ride.day == "Donderdag"
    assert ride.pickup == at(12, 14, 5)
    assert ride.arrival == at(12, 14, 45)
    assert ride.origin == "BSO De Vlinder"
    assert ride.destination == "Thuis"
    assert ride.origin_address == "Schoolweg 2, Ergens"
    assert ride.direction == "to_home"
    assert ride.as_dict()["status"] == "Gepland"


def test_apply_live(trips, live) -> None:
    ride = parse_trips(trips)[1]
    apply_live(ride, live)
    assert ride.expected_pickup == at(12, 14, 12)
    assert ride.expected_arrival == at(12, 14, 55)
    assert ride.driver == "Piet"
    assert ride.license_plate == "AB-123-C"
    assert (ride.vehicle_latitude, ride.vehicle_longitude) == (52.1, 5.1)
    assert ride.as_dict()["pickup_time"] == "14:05"
    assert ride.as_dict()["expected_pickup_time"] == "14:12"


def test_first_name() -> None:
    assert first_name("Jansen, Tim") == "Tim"
    assert first_name("Tim") == "Tim"
    assert first_name(None) is None


def test_next_ride(trips) -> None:
    rides = parse_trips(trips)
    assert next_ride(rides, at(12, 10, 0)).trip_id == 1001
    assert next_ride(rides, at(12, 14, 59)).trip_id == 1001
    assert next_ride(rides, at(12, 15, 1)).trip_id == 1002
    assert next_ride(rides, at(13, 16, 0)) is None


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (at(12, 14, 0), timedelta(minutes=5)),
        (at(12, 12, 20), timedelta(hours=1)),  # window opens 13:20
        (at(12, 9, 0), timedelta(hours=3)),
        (at(12, 5, 0), timedelta(minutes=90)),  # 06:30 refresh
    ],
)
def test_next_interval(trips, now, expected) -> None:
    assert next_interval(parse_trips(trips), now) == expected


def test_wants_live(trips) -> None:
    ride = parse_trips(trips)[1]
    assert not wants_live(ride, at(12, 13, 0))
    assert wants_live(ride, at(12, 13, 5))
    assert wants_live(ride, at(12, 15, 0))
    assert not wants_live(ride, at(12, 15, 1))
