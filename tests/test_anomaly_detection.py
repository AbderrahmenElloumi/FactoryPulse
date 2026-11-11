"""The anomaly scoring job, asserted through the table it writes (ticket 08).

The host tests lock the score table's declared shape to the registry. The
Spark tests build a seeded, labelled fixture lake in a temporary directory
(an hourly mart and a machine dimension, written with ``deltalake``), run the
real job on it in the Spark image, and read ``mrt_anomaly_scores`` back
through ``factorypulse.lake``. The fixture machines are labelled: some only
ever behave normally, some carry an injected spike at a known window, one
restarts after a gap longer than the baseline window. The fixture is built
from each of two seeds, and every Spark test runs on both.

The Spark tests need the Docker daemon and the ``factorypulse/spark:3.5``
image, and take about 100 s, so they are opt-in:

    FACTORYPULSE_DOCKER_TESTS=1 python -m pytest tests/test_anomaly_detection.py
"""

import math
import os
import random
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

import pytest

from factorypulse import analytics, lake
from factorypulse.anomaly_core import (
    BASELINE_HOURS,
    CRITICAL,
    MIN_BASELINE_WINDOWS,
    NOMINAL,
    SCORED_SENSORS,
    Z_CRITICAL,
)
from factorypulse.contract import SENSOR_TYPES, STATUSES

ROOT = Path(__file__).resolve().parent.parent
SCORES = analytics.MRT_ANOMALY_SCORES


# --- the declared shape (host) -------------------------------------------------


def test_scored_sensors_are_vibration_and_temperature_from_the_contract():
    assert set(SCORED_SENSORS) == {"temperature", "vibration"}
    assert set(SCORED_SENSORS) <= set(SENSOR_TYPES)


def test_every_scored_sensor_has_an_hourly_average_to_score():
    for sensor in SCORED_SENSORS:
        assert f"{sensor}_avg" in analytics.MACHINE_HOURLY_COLUMNS


def test_score_table_declares_its_columns_for_lake_readers():
    columns = analytics.TABLE_COLUMNS[SCORES]
    assert columns == analytics.ANOMALY_SCORE_COLUMNS
    for column in ("z_score", "sensor_status", "machine_status", "window_start", "window_end"):
        assert column in columns


def test_score_table_is_keyed_on_machine_window_and_sensor():
    assert analytics.ANOMALY_SCORE_KEYS == ("machine_id", "window_start", "sensor_type")
    assert set(analytics.ANOMALY_SCORE_KEYS) <= set(analytics.ANOMALY_SCORE_COLUMNS)


def test_analytics_path_resolves_a_table_under_an_explicit_root(env):
    assert analytics.analytics_path(env, SCORES, root="/fixture") == f"/fixture/{SCORES}"


def test_analytics_path_rejects_an_unregistered_table_under_an_explicit_root(env):
    with pytest.raises(ValueError, match="mrt_nothing"):
        analytics.analytics_path(env, "mrt_nothing", root="/fixture")


# --- the chance bar for "score low" (host) --------------------------------------


def _two_sided_t_tail(t, df):
    """P(|T| >= t) for Student's t with an integer ``df`` degrees of freedom.

    The exact finite series (Abramowitz and Stegun 26.7.3 and 26.7.4), so the
    bar needs no scipy.
    """
    theta = math.atan(t / math.sqrt(df))
    cos2 = math.cos(theta) ** 2
    if df % 2 == 1:
        term = math.cos(theta)
        total = term if df > 1 else 0.0
        for k in range(3, df - 1, 2):
            term *= cos2 * (k - 1) / k
            total += term
        inside = 2 / math.pi * (theta + math.sin(theta) * total)
    else:
        term = total = 1.0
        for k in range(2, df - 1, 2):
            term *= cos2 * (k - 1) / k
            total += term
        inside = math.sin(theta) * total
    return 1.0 - inside


def _poisson_quantile(mean, level):
    """The smallest count whose Poisson(``mean``) cumulative probability reaches ``level``."""
    count, probability = 0, math.exp(-mean)
    cumulative = probability
    while cumulative < level:
        count += 1
        probability *= mean / count
        cumulative += probability
    return count


def _expected_chance_criticals(baseline_counts):
    """The expected count of normal readings scored critical by chance.

    A normal reading's z-score against a sample baseline of n windows is
    Student's t with n - 1 degrees of freedom, scaled by sqrt(1 + 1/n).
    """
    return sum(
        _two_sided_t_tail(Z_CRITICAL / math.sqrt(1 + 1 / n), n - 1)
        for n in map(int, baseline_counts)
    )


def _t_tail_by_integration(t, df, steps=4000):
    # Simpson's rule over the t density on [0, t]; the density is symmetric.
    scale = math.gamma((df + 1) / 2) / (math.sqrt(df * math.pi) * math.gamma(df / 2))

    def density(x):
        return scale * (1 + x * x / df) ** (-(df + 1) / 2)

    width = t / steps
    weights = sum((4 if i % 2 else 2) * density(i * width) for i in range(1, steps))
    return 1.0 - 2 * width / 3 * (density(0.0) + density(t) + weights)


@pytest.mark.parametrize("df", [1, 2, 11, 23])
@pytest.mark.parametrize("t", [0.5, 2.0, 3.0])
def test_two_sided_t_tail_matches_the_integrated_density(t, df):
    assert _two_sided_t_tail(t, df) == pytest.approx(_t_tail_by_integration(t, df), abs=1e-9)


@pytest.mark.parametrize("mean, quantile", [(0.0, 0), (1.0, 5)])
def test_poisson_quantile_is_the_smallest_count_reaching_the_level(mean, quantile):
    assert _poisson_quantile(mean, 0.999) == quantile


# --- the labelled fixture lake -------------------------------------------------

START = datetime(2026, 1, 5, tzinfo=timezone.utc)
HOURS = BASELINE_HOURS + 8
SPIKE_HOUR = BASELINE_HOURS + 3
SEEDS = (8, 2026)

# Normal operating behaviour per scored sensor: (mean, standard deviation).
NORMAL = {"temperature": (70.0, 1.5), "vibration": (1.0, 0.08)}
SPIKE_SIGMAS = 12

NORMAL_MACHINES = ("M-NORMAL-1", "M-NORMAL-2", "M-NORMAL-3")
# Machine -> the sensor that spikes at SPIKE_HOUR.
SPIKED = {"M-TEMP-SPIKE": "temperature", "M-VIB-SPIKE": "vibration"}
# Runs for a few hours, stops for longer than the baseline window, runs again.
RESTART = "M-RESTART"
RESTART_HOURS = list(range(0, 8)) + list(range(8 + BASELINE_HOURS + 2, HOURS + BASELINE_HOURS))
# One hour without a vibration reading: nothing to score for that sensor.
GAP_MACHINE, GAP_HOUR = "M-NORMAL-1", BASELINE_HOURS + 1
# One hour whose temperature average is NaN: nothing to score either.
NAN_MACHINE, NAN_HOUR = "M-NORMAL-3", BASELINE_HOURS + 2


def _hourly_rows(seed):
    rng = random.Random(seed)
    hours = {machine: range(HOURS) for machine in (*NORMAL_MACHINES, *SPIKED)}
    hours[RESTART] = RESTART_HOURS
    rows = []
    for machine, machine_hours in hours.items():
        for hour in machine_hours:
            avg = {
                sensor: rng.gauss(mean, stddev) for sensor, (mean, stddev) in NORMAL.items()
            }
            if SPIKED.get(machine) and hour == SPIKE_HOUR:
                sensor = SPIKED[machine]
                avg[sensor] += SPIKE_SIGMAS * NORMAL[sensor][1]
            if (machine, hour) == (GAP_MACHINE, GAP_HOUR):
                avg["vibration"] = None
            if (machine, hour) == (NAN_MACHINE, NAN_HOUR):
                avg["temperature"] = math.nan
            hour_start = START + timedelta(hours=hour)
            rows.append(
                {
                    "machine_hour_key": f"{machine}|{hour_start.isoformat()}",
                    "machine_id": machine,
                    "site_id": "SITE-A",
                    "hour_start": hour_start,
                    "reading_count": 8,
                    "nominal_count": 8,
                    "warning_count": 0,
                    "critical_count": 0,
                    "temperature_avg": avg["temperature"],
                    "temperature_max": avg["temperature"],
                    "vibration_avg": avg["vibration"],
                    "vibration_max": avg["vibration"],
                    "pressure_avg": 100.0,
                    "pressure_max": 100.0,
                    "humidity_avg": 45.0,
                    "humidity_max": 45.0,
                }
            )
    return rows


def _dim_rows(hourly):
    rows = []
    for machine in sorted({row["machine_id"] for row in hourly}):
        starts = [row["hour_start"] for row in hourly if row["machine_id"] == machine]
        rows.append(
            {
                "machine_id": machine,
                "site_id": "SITE-A",
                "first_seen_at": min(starts),
                "last_seen_at": max(starts),
                "reading_count": 8 * len(starts),
                "sensor_type_count": 4,
            }
        )
    return rows


def _expected_score_rows(hourly):
    # One row per scored sensor average that is neither null nor NaN.
    averages = [row[f"{sensor}_avg"] for row in hourly for sensor in SCORED_SENSORS]
    return sum(1 for avg in averages if avg is not None and not math.isnan(avg))


def _write(root, table, rows):
    import pyarrow as pa
    from deltalake import write_deltalake

    # pyarrow, not pandas: pandas would store the NaN average as null.
    columns = analytics.TABLE_COLUMNS[table]
    frame = pa.Table.from_pylist([{column: row[column] for column in columns} for row in rows])
    write_deltalake(str(root / table), frame)


def _run_job(root):
    """Run the compose service on the fixture lake, as a hand run would."""
    result = subprocess.run(
        [
            "docker", "compose", "--profile", "lake-jobs", "run", "--rm", "--no-deps",
            "-v", f"{root}:/fixture",
            "-e", "ANOMALY_ARGS=--lake-root /fixture",
            "anomaly-detection",
        ],
        cwd=ROOT, capture_output=True, text=True, timeout=900,
    )
    assert result.returncode == 0, f"anomaly job failed:\n{result.stdout[-3000:]}\n{result.stderr[-3000:]}"
    return result.stdout


needs_spark = pytest.mark.skipif(
    os.environ.get("FACTORYPULSE_DOCKER_TESTS") != "1",
    reason="needs the Docker daemon and the Spark image; set FACTORYPULSE_DOCKER_TESTS=1",
)


class JobRun(NamedTuple):
    root: Path
    stdout: str


@pytest.fixture(scope="module", params=SEEDS, ids=lambda seed: f"seed{seed}")
def hourly(request):
    return _hourly_rows(request.param)


@pytest.fixture(scope="module")
def job_run(tmp_path_factory, hourly):
    """The fixture lake, and the job's stdout from its first run on it."""
    root = tmp_path_factory.mktemp("anomaly-lake")
    _write(root, analytics.MRT_MACHINE_HOURLY, hourly)
    _write(root, analytics.DIM_MACHINE, _dim_rows(hourly))
    return JobRun(root, _run_job(root))


@pytest.fixture(scope="module")
def scored_lake(job_run):
    return job_run.root


@pytest.fixture(scope="module")
def scores(scored_lake):
    return lake.read_table(SCORES, root=str(scored_lake))


def _window(hour):
    import pandas as pd

    return pd.Timestamp(START + timedelta(hours=hour))


@needs_spark
def test_known_normal_machines_score_low(scores):
    # "Score low" is a chance bar, not "never critical": a z-score against a
    # sample baseline is critical by chance for some normal readings. The
    # known-normal windows are the normal machines' windows and the spiked
    # machines' windows before the spike. Over them, the critical count is at
    # most the 99.9% Poisson quantile of the expected chance count, derived
    # from Z_CRITICAL and each row's baseline_count, so no threshold is fixed.
    before_spike = scores.machine_id.isin(list(SPIKED)) & (scores.window_start < _window(SPIKE_HOUR))
    known = scores[scores.machine_id.isin(NORMAL_MACHINES) | before_spike]
    scored = known.dropna(subset=["z_score"])
    expected = _expected_chance_criticals(scored.baseline_count)

    assert len(scored) > 0
    assert (known.sensor_status == CRITICAL).sum() <= _poisson_quantile(expected, 0.999)


@needs_spark
@pytest.mark.parametrize("machine, sensor", sorted(SPIKED.items()))
def test_injected_anomalies_score_high(scores, machine, sensor):
    at_spike = scores[(scores.machine_id == machine) & (scores.window_start == _window(SPIKE_HOUR))]
    spiked = at_spike[at_spike.sensor_type == sensor].iloc[0]

    assert spiked.z_score >= Z_CRITICAL
    assert spiked.sensor_status == CRITICAL
    # The machine's status is its worst sensor: every row of that window says so.
    assert set(at_spike.machine_status) == {CRITICAL}
    assert set(at_spike.sensor_type) == set(SCORED_SENSORS)


@needs_spark
def test_score_table_holds_one_row_per_machine_window_and_scored_sensor(hourly, scores):
    assert len(scores) == _expected_score_rows(hourly)
    assert not scores.duplicated(list(analytics.ANOMALY_SCORE_KEYS)).any()
    assert set(scores.sensor_type) == set(SCORED_SENSORS)
    assert set(scores.sensor_status) <= set(STATUSES)
    assert set(scores.machine_status) <= set(STATUSES)


@needs_spark
def test_a_window_without_a_reading_has_no_score_row(scores):
    window = scores[(scores.machine_id == GAP_MACHINE) & (scores.window_start == _window(GAP_HOUR))]

    assert list(window.sensor_type) == ["temperature"]


def _nan_hour_temperature(hourly, job_run):
    """The NaN hour's temperature average, read back from the fixture mart."""
    from deltalake import DeltaTable

    key = next(
        row["machine_hour_key"]
        for row in hourly
        if row["machine_id"] == NAN_MACHINE and row["hour_start"] == START + timedelta(hours=NAN_HOUR)
    )
    mart = DeltaTable(str(job_run.root / analytics.MRT_MACHINE_HOURLY)).to_pyarrow_table()
    return next(row for row in mart.to_pylist() if row["machine_hour_key"] == key)["temperature_avg"]


@needs_spark
def test_a_nan_hourly_average_has_no_score_row_and_leaves_the_baseline_usable(hourly, job_run, scores):
    # The job must read a NaN, not a null, or this test skips the NaN filter.
    nan_average = _nan_hour_temperature(hourly, job_run)
    machine = scores[scores.machine_id == NAN_MACHINE]
    window = machine[machine.window_start == _window(NAN_HOUR)]
    later = machine[
        (machine.sensor_type == "temperature") & (machine.window_start > _window(NAN_HOUR))
    ]

    assert nan_average is not None and math.isnan(nan_average)
    assert list(window.sensor_type) == ["vibration"]
    assert len(later) > 0
    assert later.z_score.notna().all()


@needs_spark
def test_job_logs_the_rows_its_merge_wrote(hourly, job_run):
    assert f"anomaly: merged {_expected_score_rows(hourly)} scores into" in job_run.stdout


@needs_spark
def test_each_window_is_one_hour_long(scores):
    assert ((scores.window_end - scores.window_start) == timedelta(hours=1)).all()


@needs_spark
def test_windows_without_enough_baseline_have_no_score(scores):
    first = scores[scores.machine_id == NORMAL_MACHINES[0]].sort_values("window_start")
    early = first[first.window_start < _window(MIN_BASELINE_WINDOWS)]
    later = first[first.window_start >= _window(MIN_BASELINE_WINDOWS)]

    assert early.z_score.isna().all()
    assert set(early.sensor_status) == {NOMINAL}
    assert later.z_score.notna().all()


@needs_spark
def test_baseline_covers_only_the_trailing_window_before_the_scored_one(scores):
    machine = scores[(scores.machine_id == "M-NORMAL-2") & (scores.sensor_type == "temperature")]
    full = machine[machine.window_start == _window(HOURS - 1)].iloc[0]
    second = machine[machine.window_start == _window(1)].iloc[0]

    assert full.baseline_count == BASELINE_HOURS
    assert second.baseline_count == 1


@needs_spark
def test_baseline_forgets_windows_older_than_the_baseline_hours(scores):
    machine = scores[(scores.machine_id == RESTART) & (scores.sensor_type == "temperature")]
    back = machine[machine.window_start == _window(RESTART_HOURS[8])].iloc[0]

    assert back.baseline_count == 0
    assert math.isnan(back.z_score)


@needs_spark
def test_scores_join_to_the_hourly_mart_and_the_machine_dimension(scored_lake, scores):
    root = str(scored_lake)
    hourly = lake.read_table(analytics.MRT_MACHINE_HOURLY, root=root)
    machines = lake.read_table(analytics.DIM_MACHINE, root=root)

    joined = scores.merge(
        hourly,
        left_on=["machine_id", "site_id", "window_start"],
        right_on=["machine_id", "site_id", "hour_start"],
        how="inner",
        validate="many_to_one",
    ).merge(machines[["machine_id"]], on="machine_id", how="inner", validate="many_to_one")

    assert len(joined) == len(scores)
    for sensor in SCORED_SENSORS:
        rows = joined[joined.sensor_type == sensor]
        assert (rows.value == rows[f"{sensor}_avg"]).all()


@needs_spark
def test_rerunning_the_job_leaves_the_same_rows(scored_lake, scores):
    log = _run_job(scored_lake)
    again = lake.read_table(SCORES, root=str(scored_lake))

    keys = list(analytics.ANOMALY_SCORE_KEYS)
    first = scores.sort_values(keys).reset_index(drop=True)
    second = again.sort_values(keys).reset_index(drop=True)
    assert len(second) == len(first)
    assert second.equals(first)
    # A re-run updates every row in place, and logs that count.
    assert f"anomaly: merged {len(first)} scores into" in log
