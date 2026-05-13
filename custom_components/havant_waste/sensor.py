"""Sensor platform for Havant waste collections."""
from __future__ import annotations

import re
from datetime import date

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Collection
from .const import DEFAULT_ICON, DOMAIN, ICON_MAP
from .coordinator import HavantWasteCoordinator


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: HavantWasteCoordinator = hass.data[DOMAIN][entry.entry_id]

    device = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Havant Waste Collection",
        manufacturer="Havant Borough Council",
        entry_type=DeviceEntryType.SERVICE,
        configuration_url="https://waste.havant.gov.uk/",
    )

    entities: list[SensorEntity] = [NextCollectionSensor(coordinator, entry, device)]
    seen: set[str] = set()

    @callback
    def _add_for_new_types() -> None:
        new: list[SensorEntity] = []
        for wt in coordinator.waste_types():
            if wt in seen:
                continue
            seen.add(wt)
            new.append(WasteTypeSensor(coordinator, entry, device, wt))
        if new:
            async_add_entities(new)

    _add_for_new_types()
    async_add_entities(entities)

    entry.async_on_unload(coordinator.async_add_listener(_add_for_new_types))


class _BaseSensor(CoordinatorEntity[HavantWasteCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(
        self,
        coordinator: HavantWasteCoordinator,
        entry: ConfigEntry,
        device: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = device


class NextCollectionSensor(_BaseSensor):
    _attr_translation_key = "next_collection"
    _attr_name = "Next collection"

    def __init__(
        self,
        coordinator: HavantWasteCoordinator,
        entry: ConfigEntry,
        device: DeviceInfo,
    ) -> None:
        super().__init__(coordinator, entry, device)
        self._attr_unique_id = f"{entry.entry_id}_next_collection"

    @property
    def native_value(self) -> date | None:
        nxt = self.coordinator.next_overall()
        return nxt.collection_date if nxt else None

    @property
    def icon(self) -> str:
        nxt = self.coordinator.next_overall()
        if nxt is None:
            return DEFAULT_ICON
        return ICON_MAP.get(nxt.waste_type, DEFAULT_ICON)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        nxt = self.coordinator.next_overall()
        upcoming = self.coordinator.upcoming()
        today = date.today()
        attrs: dict[str, object] = {
            "upcoming": [
                {
                    "date": c.collection_date.isoformat(),
                    "type": c.waste_type,
                    "status": c.status,
                    "days_until": (c.collection_date - today).days,
                }
                for c in upcoming[:10]
            ],
        }
        if nxt is not None:
            attrs.update(
                {
                    "type": nxt.waste_type,
                    "status": nxt.status,
                    "description": nxt.description,
                    "days_until": (nxt.collection_date - today).days,
                    "is_today": nxt.collection_date == today,
                    "can_report_missed": nxt.can_report_missed,
                }
            )
        return attrs


class WasteTypeSensor(_BaseSensor):
    def __init__(
        self,
        coordinator: HavantWasteCoordinator,
        entry: ConfigEntry,
        device: DeviceInfo,
        waste_type: str,
    ) -> None:
        super().__init__(coordinator, entry, device)
        self._waste_type = waste_type
        self._attr_unique_id = f"{entry.entry_id}_{_slug(waste_type)}"
        self._attr_name = f"Next {waste_type}"
        self._attr_icon = ICON_MAP.get(waste_type, DEFAULT_ICON)

    def _current(self) -> Collection | None:
        return self.coordinator.next_for(self._waste_type)

    @property
    def native_value(self) -> date | None:
        cur = self._current()
        return cur.collection_date if cur else None

    @property
    def available(self) -> bool:
        return super().available and self._waste_type in self.coordinator.waste_types()

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        cur = self._current()
        if cur is None:
            return {"type": self._waste_type}
        today = date.today()
        return {
            "type": cur.waste_type,
            "status": cur.status,
            "description": cur.description,
            "days_until": (cur.collection_date - today).days,
            "is_today": cur.collection_date == today,
            "can_report_missed": cur.can_report_missed,
        }
