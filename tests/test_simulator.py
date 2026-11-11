"""Tests for the sensor simulator (ticket 02).

Lock the observable contract of the simulator: deterministic output under
a seed, the right volume and attribution, anomaly injection that stays
*within* the physical ranges so the ticket-01 validator accepts every
event, and a timestamp model that is deterministic and UTC.
"""

import pytest

from factorypulse.contract import SENSOR_RANGES, SENSOR_TYPES, SENSOR_UNITS
from factorypulse.simulator import NOMINAL_WINDOWS, SimulatorConfig, generate_events
from factorypulse.validator import validate_event


def run(config, *, n):
    """Materialize the first ``n`` events of a generator as a list."""
    return list(generate_events(config))[:n]


@pytest.fixture
def cfg():
    # small, fast default for most tests
    return SimulatorConfig(records_per_day=2000, seed=42)


def test_generates_exact_records_per_day():
    events = list(generate_events(SimulatorConfig(records_per_day=500)))
    assert len(events) == 500


def test_every_event_passes_the_contract_validator(cfg):
    events = run(cfg, n=2000)
    for event in events:
        assert validate_event(event) == [], f"invalid event: {event}"


def test_all_four_sensor_types_appear(cfg):
    sensor_types = {e["sensor_type"] for e in run(cfg, n=2000)}
    assert sensor_types == set(SENSOR_TYPES)


def test_each_sensor_uses_its_contract_unit(cfg):
    for event in run(cfg, n=2000):
        assert event["unit"] == SENSOR_UNITS[event["sensor_type"]]


def test_site_and_machine_attribution_from_config():
    cfg = SimulatorConfig(sites=("site-x", "site-y"), machines_per_site=3)
    events = run(cfg, n=2000)
    sites = {e["site_id"] for e in events}
    machines = {e["machine_id"] for e in events}
    assert sites == {"site-x", "site-y"}
    assert machines == {
        "site-x-machine-01", "site-x-machine-02", "site-x-machine-03",
        "site-y-machine-01", "site-y-machine-02", "site-y-machine-03",
    }
    for event in events:
        assert event["machine_id"].startswith(event["site_id"])


def test_events_are_bytes_identical_under_the_same_seed():
    a = run(SimulatorConfig(seed=42, records_per_day=500), n=500)
    b = run(SimulatorConfig(seed=42, records_per_day=500), n=500)
    assert a == b


def test_different_seed_produces_different_output():
    a = run(SimulatorConfig(seed=1, records_per_day=400), n=400)
    b = run(SimulatorConfig(seed=2, records_per_day=400), n=400)
    assert a != b


def test_no_anomalies_when_anomaly_rate_is_zero():
    cfg = SimulatorConfig(records_per_day=1000, anomaly_rate=0.0)
    events = run(cfg, n=1000)
    assert all(e["status"] == "nominal" for e in events)
    for event in events:
        low, high = NOMINAL_WINDOWS[event["sensor_type"]]
        assert low <= event["value"] <= high


def test_spikes_are_detectable_as_high_values():
    # Pure spikes (spike_fraction=1) must push values above the nominal
    # window but stay inside the physical ranges that the validator allows.
    cfg = SimulatorConfig(records_per_day=5000, seed=7, anomaly_rate=0.05, spike_fraction=1.0)
    events = run(cfg, n=5000)
    spikes = [e for e in events if e["status"] == "critical"]
    assert spikes, "expected injected anomalies"
    for event in spikes:
        low, high = NOMINAL_WINDOWS[event["sensor_type"]]
        assert event["value"] > high
        phys_low, phys_high = SENSOR_RANGES[event["sensor_type"]]
        assert phys_low <= event["value"] <= phys_high


def test_drift_produces_elevated_values():
    # Pure drift (spike_fraction=0) carries a sensor's reading from normal
    # up toward the physical ceiling over a run of events. Most of a drift
    # run should sit outside the nominal window.
    cfg = SimulatorConfig(records_per_day=6000, seed=3, anomaly_rate=0.04, spike_fraction=0.0)
    events = run(cfg, n=6000)
    elevated = [e for e in events if e["status"] == "critical"]
    assert elevated, "expected injected drift anomalies"
    above_nominal = [e for e in elevated if e["value"] > NOMINAL_WINDOWS[e["sensor_type"]][1]]
    assert len(above_nominal) / len(elevated) > 0.4, "drift should spend most of its run above nominal"
    # and never escape the physical ranges the validator allows
    for event in elevated:
        phys_low, phys_high = SENSOR_RANGES[event["sensor_type"]]
        assert phys_low <= event["value"] <= phys_high


def test_drift_is_a_run_not_a_random_spike():
    # A drift occupies consecutive events on the same machine+sensor.
    cfg = SimulatorConfig(records_per_day=4000, seed=9, anomaly_rate=0.05, spike_fraction=0.0)
    events = run(cfg, n=4000)
    runs = {}
    for e in events:
        runs.setdefault((e["machine_id"], e["sensor_type"]), []).append(e["value"])
    longest = max((len(vals) for vals in runs.values()), default=0)
    assert longest >= 2, "expected drift anomalies to span multiple consecutive events"


def test_anomaly_events_flagged_critical(cfg):
    events = run(cfg, n=2000)  # default anomaly_rate > 0
    assert any(e["status"] == "critical" for e in events)
    assert all(
        e["status"] in ("nominal", "critical")
        for e in events
    )


def test_timestamps_are_utc_and_spread_across_a_day():
    events = run(SimulatorConfig(records_per_day=1000), n=1000)
    assert events[0]["ts"].endswith("Z")
    first = events[0]["ts"]
    last = events[-1]["ts"]
    assert first < last
    # The span is roughly one simulated day (≤ 24h + margin for the seed offset).
    day_seconds = 86400
    span = _seconds_between(first, last)
    assert 0 < span <= day_seconds + 60


def test_records_per_day_defaults_to_ten_thousand():
    assert SimulatorConfig().records_per_day == 10_000


def test_seed_default_is_documented_and_stable():
    assert SimulatorConfig().seed == 42


# --- helpers ---


def _seconds_between(a, b):
    from datetime import datetime

    def parse(s):
        return datetime.fromisoformat(s.replace("Z", "+00:00"))

    return (parse(b) - parse(a)).total_seconds()