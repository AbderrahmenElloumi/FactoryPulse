"""Deterministic sensor simulator (ticket 02).

Emits contract-conforming sensor events (see ``factorypulse.contract``)
for a populating of machines, with occasional injected anomalies (spikes
and drift). Fully deterministic under a seed: all randomness flows from a
single ``random.Random(config.seed)`` stream and timestamps are derived
from the event index, never the wall clock — so two runs with the same
seed produce byte-identical output.

Every emitted value stays *inside* the physical range for its sensor, so
the ticket-01 validator accepts it; anomalies push readings outside the
narrow "nominal" operating window but never beyond physical limits.
"""

import json
import math
import random
import uuid as _uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterator

from .contract import SENSOR_RANGES, SENSOR_TYPES, SENSOR_UNITS

# Nominal operating windows (subset of each sensor's physical range).
# Values inside these look healthy; spikes/drift push readings above them.
NOMINAL_WINDOWS = {
    "temperature": (60.0, 80.0),
    "vibration": (0.2, 2.0),
    "pressure": (50.0, 120.0),
    "humidity": (40.0, 70.0),
}

# One simulated day worth of wall-clock span; the actual start-of-day is
# derived from the seed so different seeds see different first timestamps.
_DAY_SECONDS = 86400.0
_EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class SimulatorConfig:
    """Everything that shapes simulator output. Frozen + hashable ⇒ safe
    to pass around and compare in tests."""

    seed: int = 42
    records_per_day: int = 10_000
    sites: tuple[str, ...] = ("site-a", "site-b")
    machines_per_site: int = 4
    anomaly_rate: float = 0.03
    spike_fraction: float = 0.6  # of anomalies: 0.6 spikes, 0.4 drifts
    # drift length
    drift_min_events: int = 20
    drift_max_events: int = 40


@dataclass
class DriftState:
    """Immutable-ish state for an in-progress drift anomaly.

    Uses a dataclass to avoid Primitive Obsession — fields are explicit
    and type-checked rather than hidden in a generic dict.
    """

    machine_id: str
    site_id: str
    sensor: str
    value: float
    step: float
    left: int


def generate_events(config: SimulatorConfig) -> Iterator[dict]:
    """Yield exactly ``config.records_per_day`` contract-conforming events.

    Deterministic for a fixed config (same seed ⇒ identical output).
    """
    rng = random.Random(config.seed)
    machines = [
        (f"{site}-machine-{i:02d}", site)
        for site in config.sites
        for i in range(1, config.machines_per_site + 1)
    ]

    drift: DriftState | None = None
    for idx in range(config.records_per_day):
        ts = _timestamp(idx, config)
        hour = ts.hour + ts.minute / 60.0

        if drift is not None:
            machine_id, site_id = drift.machine_id, drift.site_id
            sensor = drift.sensor
            # Create a new DriftState with updated values (immutable-ish pattern)
            drift = DriftState(
                machine_id=drift.machine_id,
                site_id=drift.site_id,
                sensor=drift.sensor,
                value=drift.value + drift.step,
                step=drift.step,
                left=drift.left - 1,
            )
            value = drift.value
            status = "critical"
            if drift.left == 0:
                drift = None
        else:
            machine_id, site_id = rng.choice(machines)
            sensor = rng.choice(SENSOR_TYPES)
            roll = rng.random()
            if roll < config.anomaly_rate:
                if rng.random() < config.spike_fraction:
                    value = _spike_value(sensor, rng)
                    status = "critical"
                else:
                    value, drift = _start_drift(machine_id, site_id, sensor, rng, config)
                    status = "critical"
            else:
                value = _nominal_value(sensor, hour, rng)
                status = "nominal"

        yield _event(machine_id, site_id, sensor, value, unit=SENSOR_UNITS[sensor], status=status, ts=ts, rng=rng)


def _timestamp(idx: int, config: SimulatorConfig) -> datetime:
    """Deterministic wall-clock for event ``idx``: a fixed epoch plus the
    composite of a seed-derived start-of-day offset and the event's slot
    in the day."""
    start_of_day = (config.seed * 17) % _DAY_SECONDS
    slot = int(idx * _DAY_SECONDS / config.records_per_day)
    return _EPOCH + timedelta(seconds=start_of_day + slot)


def _event(machine_id, site_id, sensor, value, unit, status, ts, rng) -> dict:
    return {
        "event_id": str(_uuid.UUID(int=rng.getrandbits(128))),
        "ts": ts.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "site_id": site_id,
        "machine_id": machine_id,
        "sensor_type": sensor,
        "value": value,
        "unit": unit,
        "status": status,
    }


def _nominal_value(sensor: str, hour: float, rng: random.Random) -> float:
    """Realistic healthy reading for a sensor at a given UTC hour."""
    if sensor == "temperature":
        base = 70.0 + 6.0 * math.sin((hour - 9) / 24.0 * 2 * math.pi)
        value = rng.gauss(base, 2.5)
    elif sensor == "vibration":
        base = 1.1 + 0.2 * math.sin((hour - 7) / 24.0 * 2 * math.pi)
        value = rng.gauss(base, 0.25)
    elif sensor == "pressure":
        value = rng.gauss(85.0, 6.0)
    else:  # humidity
        value = rng.gauss(55.0, 4.0)
    low, high = NOMINAL_WINDOWS[sensor]
    return min(high, max(low, value))


def _spike_value(sensor: str, rng: random.Random) -> float:
    """One-off anomaly: a reading far above the nominal window but safely
    within the physical range (so the contract validator still accepts)."""
    _, high = NOMINAL_WINDOWS[sensor]
    _, phys_high = SENSOR_RANGES[sensor]
    return rng.uniform(high * 1.02, phys_high * 0.98)


def _start_drift(machine_id, site_id, sensor, rng, config) -> tuple[float, DriftState]:
    """Begin a drift: start near nominal, then climb toward the physical
    ceiling over ``drift_min..max`` consecutive events on the same
    machine+sensor. Returns the first value and the drift state
    consumed by the generator loop."""
    low, high = NOMINAL_WINDOWS[sensor]
    _, phys_high = SENSOR_RANGES[sensor]
    # The first drift sample deliberately stays inside the nominal window:
    # a drift begins looking healthy and climbs afterward, which is exactly
    # what a value-based anomaly detector must learn to spot. The event is
    # still flagged critical to mark that the drift run has begun.
    start = rng.gauss((low + high) / 2, 2.0)
    start = min(high, max(low, start))
    target = rng.uniform(phys_high * 0.9, phys_high * 0.98)
    left = rng.randint(config.drift_min_events, config.drift_max_events)
    step = (target - start) / left
    return start, DriftState(
        machine_id=machine_id,
        site_id=site_id,
        sensor=sensor,
        value=start,
        step=step,
        left=left,
    )


def main(argv=None) -> None:
    """CLI entry point: `python -m factorypulse.simulator`.

    Emits JSON Lines (one event per line) to stdout by default.
    """
    import argparse

    parser = argparse.ArgumentParser(description="FactoryPulse sensor event simulator")
    parser.add_argument("--records-per-day", type=int, default=SimulatorConfig.records_per_day)
    parser.add_argument("--seed", type=int, default=SimulatorConfig.seed)
    parser.add_argument("--anomaly-rate", type=float, default=SimulatorConfig.anomaly_rate)
    parser.add_argument("--spike-fraction", type=float, default=SimulatorConfig.spike_fraction)
    parser.add_argument("--sites", nargs="+", default=list(SimulatorConfig.sites))
    parser.add_argument("--machines-per-site", type=int, default=SimulatorConfig.machines_per_site)
    args = parser.parse_args(argv)

    config = SimulatorConfig(
        seed=args.seed,
        records_per_day=args.records_per_day,
        sites=tuple(args.sites),
        machines_per_site=args.machines_per_site,
        anomaly_rate=args.anomaly_rate,
        spike_fraction=args.spike_fraction,
    )
    for event in generate_events(config):
        print(json.dumps(event))


if __name__ == "__main__":
    main()