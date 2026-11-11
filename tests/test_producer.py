"""Tests for the Kafka producer framing (ticket 04).

Lock the *observable* seam of the producer independent of Kafka or MinIO:
given simulator events, it must frame byte-exact Kafka records keyed by
``event_id`` so downstream consumers can partition/dedup on it, and the
JSON value must round-trip to the identical event. The network sinks are
lazy-imported behind this framing and are exercised end-to-end against the
live stack instead.
"""

import json

import pytest

from factorypulse.contract import EVENT_FIELDS
from factorypulse.producer import events_to_records


@pytest.fixture
def events():
    """Two contract-conforming events (shapes only — framing doesn't validate)."""
    return [
        {
            "event_id": "c8a2c6c1-0d4a-4b6a-9c1e-3a7f2b5d8e11",
            "ts": "2026-09-10T12:34:56.123Z",
            "site_id": "site-a",
            "machine_id": "site-a-machine-01",
            "sensor_type": "temperature",
            "value": 65.0,
            "unit": "celsius",
            "status": "nominal",
        },
        {
            "event_id": "9f4d2cbb-6e1a-4a2e-8f7c-1145e0b2a3dd",
            "ts": "2026-09-10T12:34:56.789Z",
            "site_id": "site-b",
            "machine_id": "site-b-machine-02",
            "sensor_type": "vibration",
            "value": 1.4,
            "unit": "g_pp",
            "status": "warning",
        },
    ]


def test_each_record_is_keyed_by_its_event_id(events):
    records = events_to_records(events)
    assert len(records) == len(events)
    assert [key.decode("utf-8") for key, _ in records] == [e["event_id"] for e in events]


def test_value_round_trips_to_the_identical_event(events):
    for (_, value), event in zip(events_to_records(events), events):
        assert json.loads(value.decode("utf-8")) == event


def test_value_serializes_fields_in_contract_order(events):
    # Field order is part of the contract (it documents serialization order),
    # so the bytes on the wire must keep it.
    _, value = events_to_records(events)[0]
    assert list(json.loads(value.decode("utf-8"))) == list(EVENT_FIELDS)


def test_framing_is_deterministic(events):
    assert events_to_records(events) == events_to_records(events)


def test_values_are_utf8_json_bytes(events):
    for key, value in events_to_records(events):
        assert isinstance(key, bytes) and isinstance(value, bytes)
        # round-trips cleanly through a decode(utf-8) → loads
        json.loads(value.decode("utf-8"))