"""Async client for waste.havant.gov.uk."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import aiohttp

from .const import BASE_URL, LOGIN_PATH

_LOGGER = logging.getLogger(__name__)

_TOKEN_RE = re.compile(
    r'name="__RequestVerificationToken"[^>]*value="([^"]+)"'
    r'|value="([^"]+)"[^>]*name="__RequestVerificationToken"'
)
_EVENTS_RE = re.compile(
    r"eventSettings.*?dataSource.*?isJson\((\[.*?\])\)", re.DOTALL
)


class HavantWasteError(Exception):
    """Base error for the Havant waste client."""


class HavantWasteAuthError(HavantWasteError):
    """Raised when login fails (bad credentials, or login form changed)."""


class HavantWasteParseError(HavantWasteError):
    """Raised when the response does not contain the expected data."""


@dataclass(slots=True)
class Collection:
    """A single waste collection entry."""

    waste_type: str
    collection_date: date
    status: str
    description: str
    is_future: bool
    can_report_missed: bool
    raw: dict[str, Any]


class HavantWasteClient:
    """Talks to waste.havant.gov.uk.

    Each `async_fetch_collections` call starts a fresh session — the upstream
    site uses short-lived cookies, and the integration only polls a few times
    a day, so keeping a long-lived session buys nothing.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
    ) -> None:
        self._session = session
        self._username = username
        self._password = password

    async def async_fetch_collections(self) -> list[Collection]:
        jar = aiohttp.CookieJar(unsafe=False)
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(
            cookie_jar=jar, timeout=timeout, headers={"User-Agent": "ha-vant-waste/0.1"}
        ) as session:
            token = await self._fetch_token(session)
            await self._login(session, token)
            html = await self._fetch_landing(session)
        return self._parse_events(html)

    async def async_validate(self) -> None:
        """Cheap auth check used by the config flow."""
        await self.async_fetch_collections()

    async def _fetch_token(self, session: aiohttp.ClientSession) -> str:
        async with session.get(f"{BASE_URL}{LOGIN_PATH}") as resp:
            resp.raise_for_status()
            body = await resp.text()
        match = _TOKEN_RE.search(body)
        if not match:
            raise HavantWasteParseError("anti-forgery token not found on login page")
        return match.group(1) or match.group(2)

    async def _login(self, session: aiohttp.ClientSession, token: str) -> None:
        payload = {
            "Input.Email": self._username,
            "Input.Password": self._password,
            "__RequestVerificationToken": token,
            "Input.RememberMe": "false",
        }
        async with session.post(
            f"{BASE_URL}{LOGIN_PATH}",
            data=payload,
            allow_redirects=True,
        ) as resp:
            resp.raise_for_status()
            if LOGIN_PATH in str(resp.url):
                raise HavantWasteAuthError("login redirected back to login page")

    async def _fetch_landing(self, session: aiohttp.ClientSession) -> str:
        async with session.get(BASE_URL) as resp:
            resp.raise_for_status()
            return await resp.text()

    @staticmethod
    def _parse_events(html: str) -> list[Collection]:
        match = _EVENTS_RE.search(html)
        if not match:
            raise HavantWasteParseError("collection event block missing from page")
        try:
            raw_events: list[dict[str, Any]] = json.loads(match.group(1))
        except json.JSONDecodeError as err:
            raise HavantWasteParseError("event JSON could not be parsed") from err

        collections: list[Collection] = []
        for ev in raw_events:
            # AppointmentType=="Event" rows are advisories (e.g. "BIN NOT OUT"),
            # not actual collections.
            if ev.get("AppointmentType") != "Job":
                continue
            try:
                dt = datetime.fromisoformat(ev["StartTime"])
            except (KeyError, ValueError):
                continue
            collections.append(
                Collection(
                    waste_type=(ev.get("Subject") or "").strip(),
                    collection_date=dt.date(),
                    status=ev.get("Status") or "",
                    description=ev.get("Description") or "",
                    is_future=bool(ev.get("FutureJob")),
                    can_report_missed=bool(ev.get("CanReportMissedBin")),
                    raw=ev,
                )
            )
        collections.sort(key=lambda c: c.collection_date)
        return collections
