"""The pure anomaly scoring core (ticket 08).

Thresholds come from the module, never from literals here, so the boundary
tests stay true when a threshold is tuned. The status vocabulary comes from
the event contract.
"""

import math
import random

import pytest

from factorypulse.anomaly_core import (
    BASELINE_HOURS,
    CRITICAL,
    MIN_BASELINE_WINDOWS,
    NOMINAL,
    WARNING,
    Z_CRITICAL,
    Z_WARNING,
    classify,
    machine_status,
    z_score,
)
from factorypulse.contract import STATUSES


FULL = MIN_BASELINE_WINDOWS  # a baseline just large enough to score against


def test_statuses_are_in_severity_order_mildest_first():
    # machine_status ranks severity by position in STATUSES.
    assert STATUSES == ("nominal", "warning", "critical")
    assert (NOMINAL, WARNING, CRITICAL) == STATUSES


def test_thresholds_are_ordered():
    assert 0 < Z_WARNING < Z_CRITICAL


def test_a_full_baseline_window_holds_enough_windows_to_score():
    # Two windows give a sample standard deviation, not a trustworthy one.
    assert 2 < MIN_BASELINE_WINDOWS <= BASELINE_HOURS


@pytest.mark.parametrize(
    "value, mean, stddev, expected",
    [
        (70.0, 70.0, 5.0, 0.0),
        (85.0, 70.0, 5.0, 3.0),
        (55.0, 70.0, 5.0, -3.0),
        (75.0, 70.0, 5.0, 1.0),
    ],
)
def test_z_score_measures_deviation_in_standard_deviations(value, mean, stddev, expected):
    assert z_score(value, mean, stddev, FULL) == expected


@pytest.mark.parametrize(
    "mean, stddev",
    [
        (70.0, 0.0),  # a flat baseline has no spread to measure against
        (70.0, None),  # one baseline window: no sample standard deviation
        (None, None),  # no baseline window at all
        (math.nan, 5.0),  # a NaN baseline mean
        (70.0, math.nan),  # a NaN baseline standard deviation
    ],
)
def test_z_score_is_none_without_a_usable_baseline(mean, stddev):
    assert z_score(90.0, mean, stddev, FULL) is None


@pytest.mark.parametrize("value", [None, math.nan])
def test_z_score_is_none_without_a_value(value):
    assert z_score(value, 70.0, 5.0, FULL) is None


def test_z_score_is_none_below_the_minimum_baseline_windows():
    assert z_score(90.0, 70.0, 5.0, MIN_BASELINE_WINDOWS - 1) is None
    assert z_score(90.0, 70.0, 5.0, MIN_BASELINE_WINDOWS) == 4.0


def _chance_critical_rate(baseline_windows, trials=10000):
    """The share of normal readings that z_score and classify call critical.

    Each trial draws a baseline of ``baseline_windows`` normal readings and one
    more normal reading, all from the same distribution, and scores the last.
    """
    rng = random.Random(14)
    criticals = 0
    for _ in range(trials):
        baseline = [rng.gauss(0.0, 1.0) for _ in range(baseline_windows)]
        mean = sum(baseline) / baseline_windows
        stddev = math.sqrt(sum((b - mean) ** 2 for b in baseline) / (baseline_windows - 1))
        z = z_score(rng.gauss(0.0, 1.0), mean, stddev, baseline_windows)
        criticals += classify(z) == CRITICAL
    return criticals / trials


def test_a_thinner_baseline_calls_more_normal_readings_critical(monkeypatch):
    # The reason for MIN_BASELINE_WINDOWS: a sample baseline makes a normal
    # reading critical by chance, and less often the more windows it holds.
    at_minimum = _chance_critical_rate(MIN_BASELINE_WINDOWS)
    half = MIN_BASELINE_WINDOWS // 2
    monkeypatch.setattr("factorypulse.anomaly_core.MIN_BASELINE_WINDOWS", half)

    assert at_minimum < _chance_critical_rate(half)


@pytest.mark.parametrize(
    "z, expected",
    [
        (0.0, NOMINAL),
        (Z_WARNING - 0.001, NOMINAL),
        (Z_WARNING, WARNING),
        (Z_CRITICAL - 0.001, WARNING),
        (Z_CRITICAL, CRITICAL),
        (Z_CRITICAL + 10, CRITICAL),
        (-(Z_WARNING - 0.001), NOMINAL),
        (-Z_WARNING, WARNING),
        (-Z_CRITICAL, CRITICAL),
    ],
)
def test_classify_maps_the_z_score_magnitude_to_a_contract_status(z, expected):
    assert classify(z) == expected


def test_classify_treats_a_window_without_a_score_as_nominal():
    assert classify(None) == NOMINAL


@pytest.mark.parametrize(
    "statuses, expected",
    [
        ([NOMINAL, NOMINAL], NOMINAL),
        ([NOMINAL, WARNING], WARNING),
        ([WARNING, NOMINAL], WARNING),
        ([CRITICAL, WARNING], CRITICAL),
        ([NOMINAL, CRITICAL], CRITICAL),
        ([WARNING], WARNING),
    ],
)
def test_machine_status_is_the_worst_sensor_status(statuses, expected):
    assert machine_status(statuses) == expected


def test_machine_status_accepts_any_iterable():
    assert machine_status(iter([NOMINAL, CRITICAL])) == CRITICAL


def test_machine_status_rejects_an_unknown_status():
    with pytest.raises(ValueError, match="alarm"):
        machine_status([NOMINAL, "alarm"])


def test_machine_status_rejects_no_sensor_statuses():
    with pytest.raises(ValueError, match="no sensor statuses"):
        machine_status([])
