"""Run the real HTTP calls against a fake Connexxion API."""

import base64
import json

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from custom_components.connexxion_groepsvervoer import const
from custom_components.connexxion_groepsvervoer.api import (
    ConnexxionAuthError,
    ConnexxionClient,
)


def _jwt(exp: int) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode()
    return f"h.{payload.rstrip('=')}.s"


@pytest.fixture
async def api(socket_enabled, trips, live, monkeypatch):
    state = {"logins": 0, "valid": set(), "reject_next": False}

    async def login(request: web.Request) -> web.Response:
        auth = request.headers.get("Authorization", "")
        user, _, pw = (
            base64.b64decode(auth.removeprefix("Basic ")).decode().partition(":")
        )
        if (user, pw) != ("ouder@example.com", "geheim"):
            return web.json_response({"Message": "nope"}, status=401)
        assert request.headers["x-tenant-id"] == const.BASE_HEADERS["x-tenant-id"]
        state["logins"] += 1
        token = _jwt(4_000_000_000) + str(state["logins"])
        state["valid"].add(token)
        return web.json_response(
            {
                "Data": {
                    "user": {
                        "username": user,
                        "sessionTokens": {"accessToken": token, "refreshToken": "r"},
                    }
                }
            }
        )

    def authed(request: web.Request) -> bool:
        token = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if state["reject_next"]:
            state["reject_next"] = False
            state["valid"].discard(token)
        return token in state["valid"]

    async def gt(request: web.Request) -> web.Response:
        if not authed(request):
            return web.json_response({}, status=401)
        path = request.match_info["path"]
        if path == "users/current":
            return web.json_response({"linkedTravelers": [4711]})
        if path == "customer/4711/trips":
            assert request.query["businessDaysInFuture"] == "14"
            return web.json_response({"trips": trips})
        if path == "trips/1001/vehicles-position":
            assert request.query["tripBusinessday"] == "2026-11-12T00:00:00"
            return web.json_response(live)
        return web.json_response({}, status=404)

    app = web.Application()
    app.router.add_post("/auth/login", login)
    app.router.add_get("/gt/{path:.*}", gt)
    server = TestServer(app)
    await server.start_server()
    monkeypatch.setattr(const, "AUTH_URL", str(server.make_url("/auth/")))
    monkeypatch.setattr(const, "GT_URL", str(server.make_url("/gt/")))
    yield state
    await server.close()


async def test_full_flow(api) -> None:
    async with aiohttp.ClientSession() as session:
        client = ConnexxionClient(session, "ouder@example.com", "geheim")
        assert await client.async_get_linked_travelers() == [4711]
        assert len(await client.async_get_trips(4711)) == 4
        live = await client.async_get_live(1001, "2026-11-12T00:00:00")
        assert live["vehicleLocation"]["licensePlate"] == "AB-123-C"
        # Token is reused, not a login per call.
        assert api["logins"] == 1

        # Server rejects the token: client logs in again once and carries on.
        api["reject_next"] = True
        assert len(await client.async_get_trips(4711)) == 4
        assert api["logins"] == 2


async def test_wrong_password(api) -> None:
    async with aiohttp.ClientSession() as session:
        with pytest.raises(ConnexxionAuthError):
            await ConnexxionClient(session, "ouder@example.com", "fout").async_login()
