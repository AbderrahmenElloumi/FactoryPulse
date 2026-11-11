"""Keep the JSON Schema mirror of the event contract in sync with the
authoritative Python constants in factorypulse.contract.

If a sensor, unit, status, or physical range changes, both representations
must change together — this test fails loudly otherwise.
"""

import importlib.resources
import json

from factorypulse.contract import SENSOR_RANGES, SENSOR_TYPES, SENSOR_UNITS, STATUSES


def _load_schema():
    ref = importlib.resources.files("factorypulse") / "schema" / "event_v1.json"
    with importlib.resources.as_file(ref) as path:
        return json.loads(path.read_text(encoding="utf-8"))


def test_schema_required_fields_match_contract():
    schema = _load_schema()
    assert schema["required"] == list(
        ("event_id", "ts", "site_id", "machine_id", "sensor_type", "value", "unit", "status")
    )


def test_schema_enums_match_contract():
    schema = _load_schema()
    assert schema["properties"]["sensor_type"]["enum"] == list(SENSOR_TYPES)
    assert schema["properties"]["status"]["enum"] == list(STATUSES)


def test_schema_sensor_units_and_ranges_match_contract():
    schema = _load_schema()
    units, ranges = {}, {}
    for branch in schema["allOf"]:
        sensor = branch["if"]["properties"]["sensor_type"]["const"]
        then_props = branch["then"]["properties"]
        units[sensor] = then_props["unit"]["const"]
        ranges[sensor] = (then_props["value"]["minimum"], then_props["value"]["maximum"])
    assert units == SENSOR_UNITS
    assert ranges == SENSOR_RANGES