"""Constants for the Connexxion Groepsvervoer integration."""

from __future__ import annotations

from datetime import timedelta
from zoneinfo import ZoneInfo

DOMAIN = "connexxion_groepsvervoer"

CONF_CUSTOMER_ID = "customer_id"

AUTH_URL = "https://api.transdev.nl/api/auth/auth/"
GT_URL = "https://grouptransportation-api.ptflex.net/api/gt/"
BASE_HEADERS = {
    "Accept": "application/json, text/plain",
    "Content-Type": "application/json",
    "x-region": "6",
    "x-origin": "GT",
    "x-tenant-id": "ce2538f9-7239-4c2c-b3cb-7f58fb5d5aad",
    "accept-language": "nl",
    "User-Agent": "HomeAssistant-Connexxion-Groepsvervoer",
}

# The API returns local Dutch times without a time zone.
PORTAL_TZ = ZoneInfo("Europe/Amsterdam")

BUSINESS_DAYS_AHEAD = 14
IGNORED_STATUSES = {"cancel", "cancelByGenerator"}

FAST_INTERVAL = timedelta(minutes=5)
MAX_IDLE_INTERVAL = timedelta(hours=3)
WINDOW_BEFORE = timedelta(minutes=45)
WINDOW_AFTER = timedelta(minutes=15)
# Fetch live vehicle data from this long before pickup.
LIVE_BEFORE = timedelta(minutes=60)
MORNING_REFRESH_HOUR = 6
MORNING_REFRESH_MINUTE = 30

DIRECTION_TO_HOME = "to_home"
DIRECTION_FROM_HOME = "from_home"
