"""DataUpdateCoordinator for Havant waste collections."""
from __future__ import annotations

import logging
from datetime import date

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    Collection,
    HavantWasteAuthError,
    HavantWasteClient,
    HavantWasteError,
)
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class HavantWasteCoordinator(DataUpdateCoordinator[list[Collection]]):
    """Fetches the collection schedule on a slow cadence."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({entry.title})",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        session = async_get_clientsession(hass)
        self._client = HavantWasteClient(
            session=session,
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
        )

    async def _async_update_data(self) -> list[Collection]:
        try:
            return await self._client.async_fetch_collections()
        except HavantWasteAuthError as err:
            raise UpdateFailed(f"authentication failed: {err}") from err
        except HavantWasteError as err:
            raise UpdateFailed(str(err)) from err

    def upcoming(self) -> list[Collection]:
        today = date.today()
        return [c for c in (self.data or []) if c.collection_date >= today]

    def next_for(self, waste_type: str) -> Collection | None:
        return next(
            (c for c in self.upcoming() if c.waste_type == waste_type),
            None,
        )

    def next_overall(self) -> Collection | None:
        return next(iter(self.upcoming()), None)

    def waste_types(self) -> list[str]:
        return sorted({c.waste_type for c in (self.data or [])})
