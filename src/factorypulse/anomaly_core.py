"""Anomaly scoring core (ticket 08): pure functions, no Spark.

A sensor's reading in one window is scored against that machine's own recent
behaviour: the z-score of the window's value against the mean and standard
deviation of the trailing baseline windows. The z-score's magnitude maps onto
the event contract's status vocabulary, and a machine's status in a window is
the worst status among its sensors.

``spark/anomaly_detection.py`` does the windowing and calls these functions,
so the thresholds and the severity order are stated here and nowhere else.
"""

from __future__ import annotations  # PEP 563: the spark image runs Python 3.8

import math
from typing import Iterable, Optional, Tuple

from factorypulse.contract import STATUSES

# The sensors whose readings are scored: the predictive-maintenance signals.
SCORED_SENSORS: Tuple[str, ...] = ("temperature", "vibration")

# |z| at or above these thresholds is a warning, then critical.
Z_WARNING = 2.0
Z_CRITICAL = 3.0

# The trailing baseline: the hourly windows before the scored one, at most
# BASELINE_HOURS back. A window with fewer than MIN_BASELINE_WINDOWS baseline
# windows gets no score: a machine's first few hours cannot say what is
# normal for it. A thin sample baseline calls normal readings critical by
# chance: at Z_CRITICAL = 3.0, 3.9% of them with 6 baseline windows, 1.5% with
# 12 and 0.7% with 24. Half the baseline window is the chosen trade-off.
BASELINE_HOURS = 24
MIN_BASELINE_WINDOWS = 12

NOMINAL, WARNING, CRITICAL = STATUSES

# Severity order, mildest first: STATUSES is spelled in that order.
_SEVERITY = {status: rank for rank, status in enumerate(STATUSES)}


def z_score(
    value: Optional[float],
    mean: Optional[float],
    stddev: Optional[float],
    baseline_count: int,
) -> Optional[float]:
    """How many baseline standard deviations ``value`` lies from the mean.

    ``None`` when there is no value or no usable baseline: a NaN value,
    fewer than ``MIN_BASELINE_WINDOWS`` baseline windows, no mean, no sample
    standard deviation, a NaN mean or standard deviation, or a flat baseline
    whose standard deviation is zero. Such a window has no score, not a score
    of 0.
    """
    if baseline_count < MIN_BASELINE_WINDOWS:
        return None
    if value is None or mean is None or stddev is None:
        return None
    # NaN fails every comparison, so `stddev <= 0.0` alone lets it through
    # and classify() would call the NaN score nominal.
    if math.isnan(value) or math.isnan(mean) or math.isnan(stddev) or stddev <= 0.0:
        return None
    return (value - mean) / stddev


def classify(z: Optional[float]) -> str:
    """The contract status for a z-score; a window without a score is nominal."""
    if z is None:
        return NOMINAL
    magnitude = abs(z)
    if magnitude >= Z_CRITICAL:
        return CRITICAL
    if magnitude >= Z_WARNING:
        return WARNING
    return NOMINAL


def machine_status(sensor_statuses: Iterable[str]) -> str:
    """A machine's status in one window: the worst of its sensors' statuses.

    Raises ``ValueError`` for a status outside the contract vocabulary and for
    a window with no sensor statuses at all.
    """
    statuses = list(sensor_statuses)
    unknown = [status for status in statuses if status not in _SEVERITY]
    if unknown:
        raise ValueError(f"unknown sensor status(es) {unknown}: expected one of {STATUSES}")
    if not statuses:
        raise ValueError("no sensor statuses to roll up into a machine status")
    return max(statuses, key=_SEVERITY.__getitem__)
