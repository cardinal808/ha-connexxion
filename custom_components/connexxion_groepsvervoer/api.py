"""Async client for the Connexxion Groepsvervoer (Transdev ptflex) API."""

from __future__ import annotations

import base64
import json
import time
from typing import Any
from urllib.parse import quote

import aiohttp

from . import const

TIMEOUT = aiohttp.ClientTimeout(total=30)


class ConnexxionError(Exception):
    """Base error."""


class ConnexxionAuthError(ConnexxionError):
    """Login rejected."""


class ConnexxionConnectionError(ConnexxionError):
    """API unreachable or returned an unexpected answer."""


def _jwt_exp(token: str) -> float:
    try:
        part = token.split(".")[1]
        part += "=" * (-len(part) % 4)
        return float(json.loads(base64.urlsafe_b64decode(part))["exp"])
    except (IndexError, KeyError, ValueError, TypeError):
        return time.time() + 1800


def _tokens_from(resp: Any) -> dict[str, Any] | None:
    try:
        user = resp["Data"]["user"]
        st = user["sessionTokens"]
    except (KeyError, TypeError):
        return None
    access = st.get("accessToken") or st.get("AccessToken")
    if not access:
        return None
    return {
        "access": access,
        "refresh": st.get("refreshToken") or st.get("RefreshToken"),
        "username": user.get("username"),
        "exp": _jwt_exp(access),
    }


class ConnexxionClient:
    """Log in once, keep the token in memory, refresh when it expires."""

    def __init__(
        self, session: aiohttp.ClientSession, username: str, password: str
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._tokens: dict[str, Any] | None = None

    async def _request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: Any = None,
    ) -> tuple[int, Any]:
        try:
            async with self._session.request(
                method,
                url,
                headers={**const.BASE_HEADERS, **(headers or {})},
                json=body,
                timeout=TIMEOUT,
            ) as resp:
                raw = await resp.text()
                try:
                    data = json.loads(raw) if raw.strip() else None
                except ValueError:
                    data = raw[:300]
                return resp.status, data
        except (TimeoutError, aiohttp.ClientError) as err:
            raise ConnexxionConnectionError(str(err) or type(err).__name__) from err

    async def async_login(self) -> None:
        """Log in with e-mail and password."""
        basic = base64.b64encode(f"{self._username}:{self._password}".encode()).decode()
        status, resp = await self._request(
            "POST", const.AUTH_URL + "login", {"Authorization": "Basic " + basic}
        )
        tokens = _tokens_from(resp) if status == 200 else None
        if tokens:
            self._tokens = tokens
            return
        if status in (400, 401, 403) or status == 200:
            raise ConnexxionAuthError(f"Login failed (HTTP {status})")
        raise ConnexxionConnectionError(f"Login failed (HTTP {status})")

    async def _async_refresh(self) -> bool:
        tok = self._tokens
        if not tok or not tok.get("refresh") or not tok.get("username"):
            return False
        status, resp = await self._request(
            "POST",
            const.AUTH_URL + "refreshuser",
            body={"RefreshToken": tok["refresh"], "Username": tok["username"]},
        )
        new = _tokens_from(resp) if status == 200 else None
        if not new:
            return False
        new["refresh"] = new.get("refresh") or tok["refresh"]
        self._tokens = new
        return True

    async def _async_ensure_token(self) -> None:
        if self._tokens and self._tokens["exp"] - 120 > time.time():
            return
        if not await self._async_refresh():
            await self.async_login()

    async def _get(self, path: str) -> tuple[int, Any]:
        await self._async_ensure_token()
        assert self._tokens is not None
        status, data = await self._request(
            "GET",
            const.GT_URL + path,
            {"Authorization": "Bearer " + self._tokens["access"]},
        )
        if status == 401:
            # Token rejected after all: log in again once.
            await self.async_login()
            status, data = await self._request(
                "GET",
                const.GT_URL + path,
                {"Authorization": "Bearer " + self._tokens["access"]},
            )
        return status, data

    async def async_get_linked_travelers(self) -> list[int]:
        """Customer ids of the travellers linked to this account."""
        status, data = await self._get("users/current")
        if status != 200 or not isinstance(data, dict):
            raise ConnexxionConnectionError(f"users/current: HTTP {status}")
        return list(data.get("linkedTravelers") or [])

    async def async_get_trips(
        self, customer_id: int, days: int = const.BUSINESS_DAYS_AHEAD
    ) -> list[dict[str, Any]]:
        """Raw trips from yesterday until `days` business days ahead."""
        status, data = await self._get(
            f"customer/{customer_id}/trips"
            f"?businessDaysInFuture={days}&businessDaysInPast=1"
        )
        if status != 200 or not isinstance(data, dict):
            raise ConnexxionConnectionError(f"trips: HTTP {status}")
        return list(data.get("trips") or [])

    async def async_get_live(
        self, trip_id: Any, business_day: str | None
    ) -> dict[str, Any] | None:
        """Vehicle position and live times; None when not available."""
        status, data = await self._get(
            f"trips/{trip_id}/vehicles-position"
            f"?tripBusinessday={quote(business_day or '')}&includeGeometry=false"
        )
        return data if status == 200 and isinstance(data, dict) else None
