"""Tests for the sensor-event contract validator (ticket 01).

The event contract is the single seam shared by every stage of the
pipeline, so these tests lock the *observable* behaviour of the validator:
a valid event passes, and each class of invalid event is rejected with a
field-prefixed error message.
"""

import pytest

from factorypulse.contract import (
    SENSOR_RANGES,
    SENSOR_TYPES,
    SENSOR_UNITS,
    STATUSES,
)
from factorypulse.validator import validate_event


def valid_event(**overrides):
    """Build a contract-conforming event, overriding any field."""
    event = {
        "event_id": "c8a2c6c1-0d4a-4b6a-9c1e-3a7f2b5d8e11",
        "ts": "2026-09-10T12:34:56.123Z",
        "site_id": "site-a",
        "machine_id": "machine-01",
        "sensor_type": "temperature",
        "value": 65.0,
        "unit": "celsius",
        "status": "nominal",
    }
    event.update(overrides)
    return event


@pytest.mark.parametrize("sensor_type", SENSOR_TYPES)
def test_valid_nominal_event_passes_for_every_sensor_type(sensor_type):
    event = valid_event(
        sensor_type=sensor_type,
        value=sum(SENSOR_RANGES[sensor_type]) / 2,
        unit=SENSOR_UNITS[sensor_type],
    )
    assert validate_event(event) == []


def test_missing_required_fields_are_rejected():
    for field in ("event_id", "ts", "site_id", "machine_id", "sensor_type", "value", "unit", "status"):
        event = valid_event()
        event.pop(field)
        errors = validate_event(event)
        assert errors, f"expected an error for missing field {field!r}"
        assert any(field in e for e in errors)


def test_ts_z_suffix_is_a_valid_calendar_timestamp():
    # Regression: the Spark 3.5 image runs Python 3.8, whose fromisoformat
    # rejects the trailing 'Z' this validator must still accept. The
    # calendar check must be identical across runtime versions.
    assert validate_event(valid_event(ts="2026-01-01T02:27:15.000Z")) == []
    assert validate_event(valid_event(ts="2026-01-01T20:10:42.000Z")) == []


def test_ts_z_suffix_rejects_a_nonexistent_calendar_date():
    assert "not a real calendar timestamp" in " ".join(
        validate_event(valid_event(ts="2026-02-30T02:27:15.000Z"))
    )
    assert "not a real calendar timestamp" in " ".join(
        validate_event(valid_event(ts="2026-02-30T02:27:15.000+00:00"))
    )


def test_null_required_fields_are_rejected():
    for field in ("event_id", "ts", "site_id", "machine_id", "sensor_type", "value", "unit", "status"):
        errors = validate_event(valid_event(**{field: None}))
        assert errors, f"expected an error for null field {field!r}"


@pytest.mark.parametrize(
    ("sensor_type", "unit", "bad_value"),
    [
        ("temperature", "celsius", -40.1),
        ("temperature", "celsius", 150.1),
        ("vibration", "g_pp", -0.1),
        ("vibration", "g_pp", 20.1),
        ("pressure", "psi", -0.1),
        ("pressure", "psi", 200.1),
        ("humidity", "percent", -0.1),
        ("humidity", "percent", 100.1),
    ],
)
def test_out_of_range_values_are_rejected(sensor_type, unit, bad_value):
    errors = validate_event(valid_event(sensor_type=sensor_type, unit=unit, value=bad_value))
    assert errors, f"expected an error for {sensor_type} value {bad_value}"


@pytest.mark.parametrize("bad_value", ["abc", [1, 2], {"v": 1}])
def test_non_numeric_value_is_rejected(bad_value):
    assert validate_event(valid_event(value=bad_value))


def test_unknown_sensor_type_is_rejected():
    assert validate_event(valid_event(sensor_type="magnetometer"))


def test_unit_mismatched_to_sensor_type_is_rejected():
    assert validate_event(valid_event(sensor_type="temperature", unit="psi"))


def test_unknown_unit_is_rejected():
    assert validate_event(valid_event(unit="fahrenheit"))


@pytest.mark.parametrize("bad_status", ["ok", "healthy", "unknown", 5])
def test_invalid_status_is_rejected(bad_status):
    assert validate_event(valid_event(status=bad_status))


@pytest.mark.parametrize("bad_id", ["not-a-uuid", "", "0123456789", "c8a2c6c1-0d4a-4b6a-9c1e-zzzz"])
def test_malformed_event_id_is_rejected(bad_id):
    assert validate_event(valid_event(event_id=bad_id))


@pytest.mark.parametrize(
    ("bad_ts", "why"),
    [
        ("2026-09-10T12:34:56.123", "missing timezone"),
        ("2026-09-10T12:34:56Z", "missing millisecond precision"),
        ("2026-09-10T12:34:56.123+05:00", "non-UTC offset"),
        ("2026-13-99T25:00:00.000Z", "garbage date"),
        ("not-a-timestamp", "not ISO at all"),
    ],
)
def test_invalid_timestamp_is_rejected(bad_ts, why):
    assert validate_event(valid_event(ts=bad_ts)), f"expected rejection: {why}"


@pytest.mark.parametrize("not_a_dict", [None, "string", [1, 2, 3], 42])
def test_non_dict_input_yields_error_not_exception(not_a_dict):
    assert validate_event(not_a_dict)


def test_extra_unknown_fields_are_allowed():
    """Documented decision: the validator is minimal-strict — it rejects
    missing/bad required fields but tolerates forward-compatible extras."""
    assert validate_event(valid_event(deployment_metadata={"batch": "x"})) == []


def test_error_messages_name_the_offending_field():
    errors = validate_event(valid_event(value=999))
    assert any("value" in e for e in errors)


def test_multiple_problems_reported_together():
    event = valid_event(value=-200.0, unit="psi")
    errors = validate_event(event)
    assert len(errors) >= 2, errors