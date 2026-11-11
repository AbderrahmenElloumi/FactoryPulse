"""Shared validator for the sensor-event contract.

The pipeline's single seam: every stage either produces or consumes
events shaped like the contract, and all of them use this validator at
their boundaries. It returns a list of human-readable, field-prefixed
errors (empty list = valid) so downstream stages can route bad rows
without raising.
"""

from __future__ import annotations  # PEP 563: the spark image runs Python 3.8

import datetime as _dt
import re
import uuid as _uuid
from typing import Dict, cast

from . import contract

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
# ISO-8601 UTC with millisecond precision: 2026-09-10T12:34:56.123Z or
# ...+00:00 / ...-00:00. Exactly three fractional digits.
_TS_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})T(?P<time>\d{2}:\d{2}:\d{2})"
    r"\.\d{3}(?P<tz>Z|[+-]00:00)$"
)
# dict keyed by contract field name; values are opaque JSON-decoded data.
# (typing.Dict, not dict[...]: builtin generics don't exist on Python 3.8,
# which is what the spark image runs.)
_Event = Dict[str, object]


def validate_event(event: object) -> list[str]:
    """Validate one event against the contract.

    Returns a list of error strings; an empty list means the event is
    contract-conforming. Never raises for malformed *input* (non-dicts
    produce an error entry rather than an exception).
    """
    if not isinstance(event, dict):
        return [f"event: expected a dict, got {type(event).__name__}"]

    errors = _check_missing(event)
    errors += _check_event_id(event.get("event_id"))
    errors += _check_ts(event.get("ts"))
    errors += _check_site(event.get("site_id"))
    errors += _check_machine(event.get("machine_id"))
    errors += _check_sensor(event)
    errors += _check_status(event.get("status"))
    return errors


def _check_missing(event: _Event) -> list[str]:
    errors = []
    for field in contract.EVENT_FIELDS:
        if field not in event or event[field] is None:
            errors.append(f"{field}: required field is missing or null")
    return errors


def _check_event_id(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, str) or not _UUID_RE.match(value):
        return [f"event_id: expected a UUID string (8-4-4-4-12), got {value!r}"]
    try:
        _uuid.UUID(value)
    except ValueError:
        return [f"event_id: not a valid UUID: {value!r}"]
    return []


def _check_ts(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, str):
        return [f"ts: expected an ISO-8601 UTC string, got {type(value).__name__}"]
    match = _TS_RE.match(value)
    if not match:
        return [
            "ts: expected ISO-8601 UTC with millisecond precision "
            f"(YYYY-MM-DDTHH:MM:SS.mmmZ), got {value!r}"
        ]
    try:
        # datetime.fromisoformat's shape coverage differs across Python
        # versions: Python 3.8 rejects the trailing 'Z' (and bare offsets)
        # that PEP 563-era images still run — e.g. the Spark 3.5 container
        # is on Python 3.8. Normalize to the '+'00:00' spell the contract
        # also allows, so the calendar check is version-identical.
        _dt.datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError:
        return [f"ts: not a real calendar timestamp: {value!r}"]
    return []


def _check_site(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, str) or not value.strip():
        return [f"site_id: expected a non-empty string, got {value!r}"]
    return []


def _check_machine(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, str) or not value.strip():
        return [f"machine_id: expected a non-empty string, got {value!r}"]
    return []


def _check_sensor(event: _Event) -> list[str]:
    sensor = event.get("sensor_type")
    unit = event.get("unit")
    value = event.get("value")
    errors = []

    if sensor not in contract.SENSOR_TYPES:
        return [f"sensor_type: expected one of {', '.join(contract.SENSOR_TYPES)}, got {sensor!r}"]

    sensor_name = cast(str, sensor)
    if unit != contract.SENSOR_UNITS[sensor_name]:
        errors.append(
            f"unit: sensor_type {sensor_name!r} must use unit "
            f"{contract.SENSOR_UNITS[sensor_name]!r}, got {unit!r}"
        )

    # bool is excluded explicitly: float(True) == 1.0 but a sensor never
    # reads "1.0" meaning "on".
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors.append(
            f"value: expected a number, got {value!r} ({type(value).__name__})"
        )
        return errors
    value_f = cast(float, value)

    low, high = contract.SENSOR_RANGES[sensor_name]
    if not (low <= value_f <= high):
        errors.append(
            f"value: {value} out of range for {sensor_name} "
            f"(allowed {low}..{high} {contract.SENSOR_UNITS[sensor_name]})"
        )
    return errors


def _check_status(value: object) -> list[str]:
    if value is None:
        return []
    if value not in contract.STATUSES:
        return [f"status: expected one of {', '.join(contract.STATUSES)}, got {value!r}"]
    return []