"""Minimal async client for the public MealViewer API."""

from __future__ import annotations

from datetime import date
import re
from typing import Any

import aiohttp

from .models import Menu, School

BASE_URL = "https://api.mealviewer.com/api/v4"
TIMEOUT = aiohttp.ClientTimeout(total=30)

_SCHOOL_URL_RE = re.compile(r"mealviewer\.com/school/([^/?#]+)", re.IGNORECASE)


class MealViewerError(Exception):
    """Base MealViewer error."""


class MealViewerConnectionError(MealViewerError):
    """Request failed or returned unexpected data."""


class MealViewerSchoolNotFoundError(MealViewerError):
    """The school lookup does not exist."""


def parse_school_lookup(value: str) -> str:
    """Accept a school lookup or a schools.mealviewer.com URL."""
    value = value.strip()
    if match := _SCHOOL_URL_RE.search(value):
        return match.group(1)
    return value.strip("/")


def _fmt(day: date) -> str:
    return f"{day.month}-{day.day}-{day.year}"


class MealViewerClient:
    """MealViewer API client bound to one school."""

    def __init__(self, session: aiohttp.ClientSession, school: str) -> None:
        """Initialize the client."""
        self._session = session
        self.school = school
        self.last_menu_payload: dict[str, Any] | None = None

    async def _get(self, path: str) -> dict[str, Any]:
        try:
            async with self._session.get(f"{BASE_URL}/{path}", timeout=TIMEOUT) as resp:
                if resp.status == 404:
                    raise MealViewerSchoolNotFoundError(self.school)
                resp.raise_for_status()
                data = await resp.json()
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise MealViewerConnectionError(str(err)) from err
        if not isinstance(data, dict):
            raise MealViewerConnectionError("Unexpected response")
        return data

    async def get_school(self) -> School:
        """Fetch school metadata; validates the lookup."""
        data = await self._get(f"physicalLocation/{self.school}")
        if not data.get("id"):
            raise MealViewerSchoolNotFoundError(self.school)
        return School.from_dict(data)

    async def get_menu(self, start: date, end: date) -> Menu:
        """Fetch menus for an inclusive date range."""
        data = await self._get(f"school/{self.school}/{_fmt(start)}/{_fmt(end)}/0")
        # Unknown schools still return 200, with a null physicalLocation.
        if not data.get("physicalLocation"):
            raise MealViewerSchoolNotFoundError(self.school)
        self.last_menu_payload = data
        try:
            return Menu.from_dict(data)
        except (KeyError, TypeError, ValueError) as err:
            raise MealViewerConnectionError(f"Unexpected payload: {err}") from err
