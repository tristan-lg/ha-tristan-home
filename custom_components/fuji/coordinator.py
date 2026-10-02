"""Coordinateur de logique métier pour l'intégration Fuji (litière)."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable

from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CACA_THRESHOLD,
    CONF_DEBOUNCE_OFF,
    CONF_PIPI_THRESHOLD,
    CONF_PRESENCE_SENSOR,
    DEFAULT_CACA_THRESHOLD,
    DEFAULT_DEBOUNCE_OFF,
    DEFAULT_PIPI_THRESHOLD,
    DOMAIN,
    EVENT_VISIT_COMPLETED,
    HISTORY_SIZE,
    SIGNAL_UPDATE,
    VISIT_TYPE_CACA,
    VISIT_TYPE_PIPI,
)

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1


class FujiLitterCoordinator:
    """Suit les passages à la litière et maintient historique/compteurs."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.hass = hass
        self.entry = entry
        self.presence_entity_id: str = entry.data[CONF_PRESENCE_SENSOR]

        self._store: Store = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}_{entry.entry_id}"
        )

        self.is_present: bool = False
        self.visit_started_at: datetime | None = None
        self.last_visit: dict[str, Any] | None = None
        self.history: list[dict[str, Any]] = []
        self.counters: dict[str, Any] = {
            "date": dt_util.now().date().isoformat(),
            "pipi": 0,
            "caca": 0,
            "visits": 0,
        }

        self._unsub_state_change: Callable[[], None] | None = None
        self._unsub_midnight: Callable[[], None] | None = None
        self._cancel_end_timer: Callable[[], None] | None = None
        # Instant (pre-debounce) où le capteur brut est repassé à "off".
        self._pending_off_at: datetime | None = None

    # ------------------------------------------------------------------
    # Options (lues dynamiquement pour prendre en compte les changements
    # effectués via l'OptionsFlow sans recharger l'entrée).
    # ------------------------------------------------------------------
    @property
    def pipi_threshold(self) -> int:
        return self.entry.options.get(CONF_PIPI_THRESHOLD, DEFAULT_PIPI_THRESHOLD)

    @property
    def caca_threshold(self) -> int:
        return self.entry.options.get(CONF_CACA_THRESHOLD, DEFAULT_CACA_THRESHOLD)

    @property
    def debounce_off(self) -> int:
        return self.entry.options.get(CONF_DEBOUNCE_OFF, DEFAULT_DEBOUNCE_OFF)

    @property
    def signal(self) -> str:
        return SIGNAL_UPDATE.format(entry_id=self.entry.entry_id)

    @property
    def current_visit_duration(self) -> int:
        """Durée (s) de la visite en cours, 0 si absent."""
        if self.visit_started_at is None:
            return 0
        return max(0, int((dt_util.utcnow() - self.visit_started_at).total_seconds()))

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------
    async def async_setup(self) -> None:
        """Charge l'état persisté et démarre l'écoute du capteur."""
        await self._async_load()
        self._maybe_reset_daily_counters()

        # Initialise l'état de présence à partir de l'état actuel du capteur.
        current = self.hass.states.get(self.presence_entity_id)
        if current is not None and current.state == "on":
            self.is_present = True
            self.visit_started_at = dt_util.utcnow()

        self._unsub_state_change = async_track_state_change_event(
            self.hass, [self.presence_entity_id], self._async_presence_changed
        )
        self._unsub_midnight = async_track_time_change(
            self.hass, self._async_midnight_reset, hour=0, minute=0, second=0
        )

    async def async_unload(self) -> None:
        """Arrête les écouteurs et timers en cours."""
        if self._unsub_state_change is not None:
            self._unsub_state_change()
            self._unsub_state_change = None
        if self._unsub_midnight is not None:
            self._unsub_midnight()
            self._unsub_midnight = None
        self._cancel_pending_end()

    # ------------------------------------------------------------------
    # Persistance
    # ------------------------------------------------------------------
    async def _async_load(self) -> None:
        data = await self._store.async_load()
        if not data:
            return
        self.history = data.get("history", [])
        self.last_visit = data.get("last_visit")
        self.counters = data.get("counters", self.counters)

    async def _async_save(self) -> None:
        await self._store.async_save(
            {
                "history": self.history,
                "last_visit": self.last_visit,
                "counters": self.counters,
            }
        )

    # ------------------------------------------------------------------
    # Gestion des compteurs journaliers
    # ------------------------------------------------------------------
    def _maybe_reset_daily_counters(self) -> None:
        today = dt_util.now().date().isoformat()
        if self.counters.get("date") != today:
            self.counters = {"date": today, "pipi": 0, "caca": 0, "visits": 0}

    @callback
    def _async_midnight_reset(self, _now: datetime) -> None:
        self._maybe_reset_daily_counters()
        self.hass.async_create_task(self._async_save())
        self._notify()

    # ------------------------------------------------------------------
    # Détection de présence / debounce
    # ------------------------------------------------------------------
    @callback
    def _async_presence_changed(self, event: Event[EventStateChangedData]) -> None:
        new_state = event.data["new_state"]
        if new_state is None:
            return

        if new_state.state == "on":
            self._handle_raw_on()
        elif new_state.state == "off":
            self._handle_raw_off()

    def _handle_raw_on(self) -> None:
        if self._cancel_end_timer is not None:
            # Coupure courte absorbée : on annule la fin de visite prévue et
            # on continue la visite en cours.
            self._cancel_pending_end()
            self._pending_off_at = None
            self._notify()
            return

        if self.is_present:
            # Déjà présent, rien à faire (évite de redémarrer une visite).
            return

        self.is_present = True
        self.visit_started_at = dt_util.utcnow()
        self._notify()

    def _handle_raw_off(self) -> None:
        if not self.is_present or self._cancel_end_timer is not None:
            return

        self._pending_off_at = dt_util.utcnow()

        self._cancel_end_timer = async_call_later(
            self.hass, self.debounce_off, self._async_confirm_end_visit
        )

    def _cancel_pending_end(self) -> None:
        if self._cancel_end_timer is not None:
            self._cancel_end_timer()
            self._cancel_end_timer = None

    @callback
    def _async_confirm_end_visit(self, _now: datetime) -> None:
        self._cancel_end_timer = None
        self.is_present = False

        started_at = self.visit_started_at
        off_at = self._pending_off_at or dt_util.utcnow()
        self.visit_started_at = None
        self._pending_off_at = None

        if started_at is None:
            self._notify()
            return

        duration = max(0, int((off_at - started_at).total_seconds()))
        self.hass.async_create_task(self._async_finalize_visit(started_at, off_at, duration))

    async def _async_finalize_visit(
        self, started_at: datetime, ended_at: datetime, duration: int
    ) -> None:
        if duration < self.pipi_threshold:
            _LOGGER.debug(
                "Passage de %ss ignoré (en dessous du seuil pipi de %ss)",
                duration,
                self.pipi_threshold,
            )
            self._notify()
            return

        visit_type = (
            VISIT_TYPE_CACA if duration >= self.caca_threshold else VISIT_TYPE_PIPI
        )

        self._maybe_reset_daily_counters()
        self.counters["visits"] += 1
        self.counters[visit_type] += 1

        visit = {
            "type": visit_type,
            "duration_seconds": duration,
            "started_at": started_at.isoformat(),
            "ended_at": ended_at.isoformat(),
        }
        self.last_visit = visit
        self.history.insert(0, visit)
        del self.history[HISTORY_SIZE:]

        await self._async_save()

        self.hass.bus.async_fire(
            EVENT_VISIT_COMPLETED,
            {
                "device_id": self.entry.entry_id,
                "type": visit_type,
                "duration_seconds": duration,
                "started_at": visit["started_at"],
                "ended_at": visit["ended_at"],
            },
        )

        self._notify()

    def _notify(self) -> None:
        async_dispatcher_send(self.hass, self.signal)
