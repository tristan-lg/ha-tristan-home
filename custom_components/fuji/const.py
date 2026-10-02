"""Constantes pour l'intégration Fuji (litière)."""
from __future__ import annotations

DOMAIN = "fuji"

# Configuration (config entry data)
CONF_PRESENCE_SENSOR = "presence_sensor"

# Options
CONF_PIPI_THRESHOLD = "pipi_threshold_seconds"
CONF_CACA_THRESHOLD = "caca_threshold_seconds"
CONF_DEBOUNCE_OFF = "debounce_off_seconds"

DEFAULT_PIPI_THRESHOLD = 20
DEFAULT_CACA_THRESHOLD = 60
DEFAULT_DEBOUNCE_OFF = 10

DEFAULT_NAME = "Litière Fuji"

# Nombre maximum de passages conservés dans l'historique.
HISTORY_SIZE = 50

# Type de passage.
VISIT_TYPE_PIPI = "pipi"
VISIT_TYPE_CACA = "caca"

# Événement émis à chaque passage validé.
EVENT_VISIT_COMPLETED = "fuji_visit_completed"

# Signal interne (dispatcher) utilisé pour notifier les entités des mises à
# jour du coordinator, par entrée de configuration.
SIGNAL_UPDATE = "fuji_update_{entry_id}"
