"""Sensor-event contract: the single seam shared by every stage.

This module is the authoritative, machine-readable definition of the event
contract agreed in spec.md. Non-Python stages (Spark/dbt) consume the
mirror JSON Schema at ``schema/event_v1.json``; a test keeps the two in
sync.

An event is a plain dict (JSON round-trip friendly):

    {
      "event_id":    UUID string,
      "ts":          ISO-8601 UTC, millisecond precision (.123Z),
      "site_id":     string,
      "machine_id":  string,
      "sensor_type": temperature | vibration | pressure | humidity,
      "value":       float (within the sensor's physical range),
      "unit":        celsius | g_pp | psi | percent (matches sensor_type),
      "status":      nominal | warning | critical,
    }
"""

# Order matters: it is both the canonical field list and the documented
# serialization order.
EVENT_FIELDS = (
    "event_id",
    "ts",
    "site_id",
    "machine_id",
    "sensor_type",
    "value",
    "unit",
    "status",
)

SENSOR_TYPES = ("temperature", "vibration", "pressure", "humidity")

# The single unit each sensor type is reported in. A value's unit must
# match the sensor it came from.
SENSOR_UNITS = {
    "temperature": "celsius",
    "vibration": "g_pp",
    "pressure": "psi",
    "humidity": "percent",
}

# Physically meaningful operating ranges (inclusive). Downstream anomaly
# detection works *within* these ranges; the validator rejects anything
# outside them as sensor error rather than machine drift.
SENSOR_RANGES = {
    "temperature": (-40.0, 150.0),
    "vibration": (0.0, 20.0),
    "pressure": (0.0, 200.0),
    "humidity": (0.0, 100.0),
}

ALLOWED_UNITS = frozenset(SENSOR_UNITS.values())

STATUSES = ("nominal", "warning", "critical")