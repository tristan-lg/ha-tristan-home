"""Entité de base pour l'intégration Fuji (litière)."""
from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .coordinator import FujiLitterCoordinator


class FujiEntity(Entity):
    """Entité liée au device Fuji et notifiée via le coordinator."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator: FujiLitterCoordinator) -> None:
        self.coordinator = coordinator
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.title,
            manufacturer="Tristan Home",
            model="Litière connectée",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.coordinator.signal, self._handle_update
            )
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()
