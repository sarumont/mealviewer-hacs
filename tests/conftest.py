"""Fixtures for MealViewer tests."""

import json
from pathlib import Path
import re
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.mealviewer.const import CONF_SCHOOL, DOMAIN

FIXTURES = Path(__file__).parent / "fixtures"
SCHOOL_URL = re.compile(r"https://api\.mealviewer\.com/api/v4/physicalLocation/.*")
MENU_URL = re.compile(r"https://api\.mealviewer\.com/api/v4/school/.*")


def load_json(name: str) -> dict[str, Any]:
    """Load a JSON fixture."""
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations."""


@pytest.fixture
def menu_payload() -> dict[str, Any]:
    """Raw menu response (Thu 2026-10-22 .. Mon 2026-10-26)."""
    return load_json("menu.json")


@pytest.fixture
def mock_api(aioclient_mock: AiohttpClientMocker, menu_payload) -> AiohttpClientMocker:
    """Mock the MealViewer API."""
    aioclient_mock.get(SCHOOL_URL, json=load_json("school.json"))
    aioclient_mock.get(MENU_URL, json=menu_payload)
    return aioclient_mock


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """A config entry for Appleton."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Appleton Elementary School",
        unique_id="9003",
        data={CONF_SCHOOL: "AppletonElementarySchool"},
    )
