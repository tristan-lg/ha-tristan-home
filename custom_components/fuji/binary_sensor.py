"""Plateforme binary_sensor pour l'intégration Fuji (litière)."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import FujiLitterCoordinator
from .entity import FujiEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: FujiLitterCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FujiPresenceBinarySensor(coordinator)])


class FujiPresenceBinarySensor(FujiEntity, BinarySensorEntity):
    """Présence (débouncée) à la litière."""

    _attr_translation_key = "presence"
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY
    _attr_entity_category = None

    def __init__(self, coordinator: FujiLitterCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_presence"

    @property
    def is_on(self) -> bool:
        return self.coordinator.is_present
