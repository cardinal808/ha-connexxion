"""Fixtures for Connexxion tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.connexxion_groepsvervoer.const import CONF_CUSTOMER_ID, DOMAIN

FIXTURES = Path(__file__).parent / "fixtures"
CLIENT = "custom_components.connexxion_groepsvervoer.api.ConnexxionClient"

CREDENTIALS = {CONF_USERNAME: "ouder@example.com", CONF_PASSWORD: "geheim"}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def trips() -> list[dict]:
    return json.loads((FIXTURES / "trips.json").read_text())["trips"]


@pytest.fixture
def live() -> dict:
    return json.loads((FIXTURES / "live.json").read_text())


@pytest.fixture
def mock_api(trips, live):
    with (
        patch(f"{CLIENT}.async_login", return_value=None) as login,
        patch(f"{CLIENT}.async_get_linked_travelers", return_value=[4711]) as travelers,
        patch(f"{CLIENT}.async_get_trips", return_value=trips) as get_trips,
        patch(f"{CLIENT}.async_get_live", return_value=live) as get_live,
    ):
        yield {
            "login": login,
            "travelers": travelers,
            "trips": get_trips,
            "live": get_live,
        }


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Connexxion Tim",
        unique_id="4711",
        data={**CREDENTIALS, CONF_CUSTOMER_ID: 4711},
    )
