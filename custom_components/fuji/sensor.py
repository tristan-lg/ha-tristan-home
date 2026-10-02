"""Plateforme sensor pour l'intégration Fuji (litière)."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, VISIT_TYPE_CACA, VISIT_TYPE_PIPI
from .coordinator import FujiLitterCoordinator
from .entity import FujiEntity

VISIT_TYPE_LABELS = {
    VISIT_TYPE_PIPI: "Pipi",
    VISIT_TYPE_CACA: "Caca",
}

LIVE_REFRESH_INTERVAL = timedelta(seconds=5)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: FujiLitterCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            FujiVisitDurationSensor(coordinator),
            FujiLastVisitSensor(coordinator),
            FujiHistorySensor(coordinator),
            FujiDailyCounterSensor(coordinator, VISIT_TYPE_PIPI, "pipis_aujourdhui"),
            FujiDailyCounterSensor(coordinator, VISIT_TYPE_CACA, "cacas_aujourdhui"),
            FujiDailyCounterSensor(coordinator, "visits", "visites_aujourdhui"),
        ]
    )


class FujiVisitDurationSensor(FujiEntity, SensorEntity):
    """Durée (s) de la visite en cours, 0 si Fuji n'est pas à la litière."""

    _attr_translation_key = "current_visit_duration"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator: FujiLitterCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_current_visit_duration"
        self._unsub_interval = None

    @property
    def native_value(self) -> int:
        return self.coordinator.current_visit_duration

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._unsub_interval = async_track_time_interval(
            self.hass, self._async_refresh, LIVE_REFRESH_INTERVAL
        )
        self.async_on_remove(self._cancel_interval)

    def _cancel_interval(self) -> None:
        if self._unsub_interval is not None:
            self._unsub_interval()
            self._unsub_interval = None

    @callback
    def _async_refresh(self, _now) -> None:
        if self.coordinator.is_present:
            self.async_write_ha_state()


class FujiLastVisitSensor(FujiEntity, SensorEntity):
    """Dernier passage validé (Pipi/Caca)."""

    _attr_translation_key = "last_visit"
    _attr_icon = "mdi:cat"

    def __init__(self, coordinator: FujiLitterCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_last_visit"

    @property
    def native_value(self) -> str:
        visit = self.coordinator.last_visit
        if not visit:
            return "Aucun"
        return VISIT_TYPE_LABELS.get(visit["type"], visit["type"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        visit = self.coordinator.last_visit
        if not visit:
            return {}
        return {
            "duration_seconds": visit["duration_seconds"],
            "started_at": visit["started_at"],
            "ended_at": visit["ended_at"],
        }


class FujiHistorySensor(FujiEntity, SensorEntity):
    """Historique des derniers passages à la litière."""

    _attr_translation_key = "history"
    _attr_icon = "mdi:history"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "passages"

    def __init__(self, coordinator: FujiLitterCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_history"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.history)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "visits": [
                {
                    "type": VISIT_TYPE_LABELS.get(visit["type"], visit["type"]),
                    "duration_seconds": visit["duration_seconds"],
                    "started_at": visit["started_at"],
                    "ended_at": visit["ended_at"],
                }
                for visit in self.coordinator.history
            ]
        }


class FujiDailyCounterSensor(FujiEntity, SensorEntity):
    """Compteur journalier (pipis / cacas / visites), remis à zéro à minuit."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = "passages"
    _attr_icon = "mdi:counter"

    def __init__(
        self, coordinator: FujiLitterCoordinator, counter_key: str, translation_key: str
    ) -> None:
        super().__init__(coordinator)
        self._counter_key = counter_key
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{translation_key}"

    @property
    def native_value(self) -> int:
        return self.coordinator.counters.get(self._counter_key, 0)
