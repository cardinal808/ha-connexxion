"""Data update coordinator for Connexxion Groepsvervoer."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import ConnexxionAuthError, ConnexxionClient, ConnexxionError
from .const import (
    CONF_CUSTOMER_ID,
    DOMAIN,
    FAST_INTERVAL,
    LIVE_BEFORE,
    MAX_IDLE_INTERVAL,
    MORNING_REFRESH_HOUR,
    MORNING_REFRESH_MINUTE,
    PORTAL_TZ,
    WINDOW_AFTER,
)
from .parser import Ride, apply_live, next_ride, parse_trips, ride_window

_LOGGER = logging.getLogger(__name__)

type ConnexxionConfigEntry = ConfigEntry[ConnexxionCoordinator]


@dataclass
class ConnexxionData:
    """Latest schedule."""

    rides: list[Ride] = field(default_factory=list)
    current: Ride | None = None
    updated: datetime | None = None


def next_interval(rides: list[Ride], now: datetime) -> timedelta:
    """Every few minutes around a ride, otherwise sleep until the next one."""
    windows = [w for ride in rides if (w := ride_window(ride))]
    if any(start <= now < end for start, end in windows):
        return FAST_INTERVAL
    local = now.astimezone(PORTAL_TZ)
    morning = local.replace(
        hour=MORNING_REFRESH_HOUR,
        minute=MORNING_REFRESH_MINUTE,
        second=0,
        microsecond=0,
    )
    if morning <= local:
        morning += timedelta(days=1)
    candidates = [morning] + [start for start, _ in windows if start > now]
    wait = min(candidates) - now
    return max(timedelta(minutes=1), min(wait, MAX_IDLE_INTERVAL))


def wants_live(ride: Ride, now: datetime) -> bool:
    """Ask for live data from an hour before pickup until 15 min after arrival."""
    if ride.pickup is None:
        return False
    end = (ride.arrival or ride.pickup) + WINDOW_AFTER
    return ride.pickup - LIVE_BEFORE <= now <= end


class ConnexxionCoordinator(DataUpdateCoordinator[ConnexxionData]):
    """Fetch the schedule with an adaptive interval."""

    config_entry: ConnexxionConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConnexxionConfigEntry,
        client: ConnexxionClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=FAST_INTERVAL,
        )
        self.client = client
        self.customer_id = int(entry.data[CONF_CUSTOMER_ID])

    async def _async_update_data(self) -> ConnexxionData:
        now = dt_util.now()
        try:
            rides = parse_trips(await self.client.async_get_trips(self.customer_id))
            for ride in rides:
                if wants_live(ride, now) and ride.trip_id is not None:
                    try:
                        live = await self.client.async_get_live(
                            ride.trip_id, ride.business_day
                        )
                    except ConnexxionAuthError:
                        raise
                    except ConnexxionError as err:
                        _LOGGER.debug("No live data for %s: %s", ride.trip_id, err)
                        continue
                    if live:
                        apply_live(ride, live)
        except ConnexxionAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="auth_failed"
            ) from err
        except ConnexxionError as err:
            self.update_interval = FAST_INTERVAL
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        # Drop rides from before today (the API also returns yesterday).
        today = now.astimezone(PORTAL_TZ).date()
        rides = [r for r in rides if r.date >= today]
        self.update_interval = next_interval(rides, now)
        _LOGGER.debug(
            "Fetched %d rides, next update in %s", len(rides), self.update_interval
        )
        return ConnexxionData(rides=rides, current=next_ride(rides, now), updated=now)
