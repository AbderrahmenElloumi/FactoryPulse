"""Analytics-layer contract (ticket 05): the dbt models' public surface.

dbt owns the transformation logic, but the *names* of the tables it builds —
and where they live in the lake — are a seam every later stage touches: the
verification query job, Airflow (ticket 06), Great Expectations (ticket 07),
the anomaly join (ticket 08) and the dashboard (ticket 09). None of them may
re-spell a model name or an S3a path, so this module is the single source of
truth for both. The dbt project reads the same var names (``lake_root`` and
``raw_sensor_events_path``); ``tests/test_dbt_project.py`` locks the two
views together on the host, with no JVM and no warehouse.

Layout: the raw lake and the analytics tables share one bucket and one
``delta/`` prefix, so ``raw_sensor_events`` and every model below are read
the same way — ``spark.read.format("delta").load(path)``.
"""

from __future__ import annotations  # PEP 563: the spark image runs Python 3.8

from typing import Any, Dict, Mapping, Optional, Tuple

from factorypulse.contract import EVENT_FIELDS, SENSOR_TYPES, STATUSES

# dbt model names == the Delta table names == the dbt var/path segments.
DIM_MACHINE = "dim_machine"
FCT_SENSOR_READINGS_CLEAN = "fct_sensor_readings_clean"
MRT_MACHINE_HOURLY = "mrt_machine_hourly"
MRT_MACHINE_WEEKLY = "mrt_machine_weekly"

ANALYTICS_MODELS: Tuple[str, ...] = (
    DIM_MACHINE,
    FCT_SENSOR_READINGS_CLEAN,
    MRT_MACHINE_HOURLY,
    MRT_MACHINE_WEEKLY,
)

# Which DAG advances each model (ticket 06). The weekly DAG builds the models
# tagged `weekly` in dbt (`--select tag:weekly`); the daily DAG builds the rest
# (`--exclude tag:weekly`). tests/test_dbt_project.py locks this to the tags.
WEEKLY_MODELS: Tuple[str, ...] = (MRT_MACHINE_WEEKLY,)
DAILY_MODELS: Tuple[str, ...] = tuple(
    model for model in ANALYTICS_MODELS if model not in WEEKLY_MODELS
)

# Written by Spark jobs rather than dbt, but still named here so no job spells
# a table name or a lake path on its own.
MRT_ANOMALY_SCORES = "mrt_anomaly_scores"

SPARK_WRITTEN_TABLES: Tuple[str, ...] = (MRT_ANOMALY_SCORES,)

REGISTERED_TABLES: Tuple[str, ...] = ANALYTICS_MODELS + SPARK_WRITTEN_TABLES

# The Delta table both ingestion paths write (spark/common.py); the analytics
# models read it and never write to it.
RAW_EVENTS_TABLE = "raw_sensor_events"

# dbt var names the project reads — see dbt/models/marts/*.sql.
LAKE_ROOT_VAR = "lake_root"
RAW_EVENTS_VAR = "raw_sensor_events_path"

# Column contracts of the built tables. The fixture seed in
# dbt/seeds/expected_mrt_machine_hourly.csv carries exactly the hourly
# columns, in this order, so a fixture run asserts the real column set.
MACHINE_DIM_COLUMNS: Tuple[str, ...] = (
    "machine_id",
    "site_id",
    "first_seen_at",
    "last_seen_at",
    "reading_count",
    "sensor_type_count",
)

FCT_READING_COLUMNS: Tuple[str, ...] = (
    "event_id",
    "event_ts",
    "site_id",
    "machine_id",
    "sensor_type",
    "value",
    "unit",
    "status",
)

MACHINE_HOURLY_COLUMNS: Tuple[str, ...] = (
    "machine_hour_key",
    "machine_id",
    "site_id",
    "hour_start",
    "reading_count",
    "nominal_count",
    "warning_count",
    "critical_count",
    "temperature_avg",
    "temperature_max",
    "vibration_avg",
    "vibration_max",
    "pressure_avg",
    "pressure_max",
    "humidity_avg",
    "humidity_max",
)

MACHINE_WEEKLY_COLUMNS: Tuple[str, ...] = (
    "machine_week_key",
    "machine_id",
    "site_id",
    "iso_year",
    "iso_week",
    "week_start",
    "reading_count",
    "nominal_count",
    "warning_count",
    "critical_count",
    "temperature_avg",
    "temperature_max",
    "vibration_avg",
    "vibration_max",
    "pressure_avg",
    "pressure_max",
    "humidity_avg",
    "humidity_max",
)

# mrt_anomaly_scores (written by spark/anomaly_detection.py): one row per
# machine, hourly window and scored sensor. `value` is the window's hourly
# average, scored against the trailing baseline windows of the same machine
# and sensor; `machine_status` is the worst `sensor_status` of the window.
ANOMALY_SCORE_COLUMNS: Tuple[str, ...] = (
    "machine_id",
    "site_id",
    "window_start",
    "window_end",
    "sensor_type",
    "value",
    "baseline_mean",
    "baseline_stddev",
    "baseline_count",
    "z_score",
    "sensor_status",
    "machine_status",
)

# The score table's grain, and the keys its idempotent write merges on.
ANOMALY_SCORE_KEYS: Tuple[str, ...] = ("machine_id", "window_start", "sensor_type")


# Every table a non-Spark reader may load, with the columns it is promised in
# order (factorypulse.lake reads through this). The raw lake holds exactly the
# contract fields: both ingestion paths select EVENT_SCHEMA_SPEC, which tracks
# EVENT_FIELDS.
TABLE_COLUMNS: Mapping[str, Tuple[str, ...]] = {
    RAW_EVENTS_TABLE: EVENT_FIELDS,
    DIM_MACHINE: MACHINE_DIM_COLUMNS,
    FCT_SENSOR_READINGS_CLEAN: FCT_READING_COLUMNS,
    MRT_MACHINE_HOURLY: MACHINE_HOURLY_COLUMNS,
    MRT_MACHINE_WEEKLY: MACHINE_WEEKLY_COLUMNS,
    MRT_ANOMALY_SCORES: ANOMALY_SCORE_COLUMNS,
}


def lake_root(env: Mapping[str, str]) -> str:
    """The Delta root every table in the lake lives under."""
    bucket = env.get("MINIO_BUCKET", "factorypulse")
    return f"s3a://{bucket}/delta"


def raw_events_path(env: Mapping[str, str]) -> str:
    """The raw event table the dbt models read."""
    return f"{lake_root(env)}/{RAW_EVENTS_TABLE}"


def analytics_path(
    env: Mapping[str, str], model: str, root: Optional[str] = None
) -> str:
    """The lake path of one registered table (``model`` is a table name).

    ``root`` defaults to the object-store lake named by ``env``; a local
    directory holding the same layout (a fixture lake) works too.
    """
    if model not in REGISTERED_TABLES:
        raise ValueError(f"{model!r} is not a registered table: {REGISTERED_TABLES}")
    return f"{root or lake_root(env)}/{model}"


# --- Machine health: pure functions over frames read from the lake ----------
# The dashboard renders these. They take pandas frames in the declared column
# order (factorypulse.lake) and never import pandas themselves: the Spark
# image imports this module and has no use for them.


def latest_machine_status(scores: Any) -> Any:
    """One row per machine: its status in its latest scored window.

    ``scores`` is ``mrt_anomaly_scores``. A scored window has a ``z_score`` on
    at least one sensor row; a machine with no scored window has no row.
    ``max_abs_z_score`` is the largest distance from baseline among the
    window's sensors, whatever its sign. Raises ``ValueError`` for a status
    outside the contract's vocabulary.
    """
    unknown = sorted(set(scores["machine_status"]) - set(STATUSES))
    if unknown:
        raise ValueError(f"unknown machine status(es) {unknown}: expected one of {STATUSES}")
    # The anomaly job calls a window without a baseline nominal (classify(None)),
    # so its status says nothing: only rows with a z_score count.
    scores = scores[scores["z_score"].notna()]
    latest_window = scores.groupby("machine_id")["window_start"].transform("max")
    latest = scores[scores["window_start"] == latest_window]
    return (
        latest.assign(abs_z_score=latest["z_score"].abs())
        .groupby(["machine_id", "site_id", "window_start", "machine_status"], as_index=False)
        .agg(max_abs_z_score=("abs_z_score", "max"))
        .sort_values("machine_id", ignore_index=True)
    )


def at_risk_machines(scores: Any) -> Any:
    """Machines whose latest status is not nominal, worst status first."""
    latest = latest_machine_status(scores)
    severity = latest["machine_status"].map(STATUSES.index)
    return (
        latest.assign(severity=severity)[severity > 0]
        .sort_values(["severity", "machine_id"], ascending=[False, True])
        .drop(columns="severity")
        .reset_index(drop=True)
    )


def machine_health_kpis(machines: Any, scores: Any) -> Dict[str, int]:
    """Machine counts: tracked, by latest status, and with no score yet.

    ``machines`` is ``dim_machine``; ``scores`` is ``mrt_anomaly_scores``.
    """
    latest = latest_machine_status(scores)
    by_status = latest["machine_status"].value_counts()
    kpis = {"machines": len(machines)}
    kpis.update({status: int(by_status.get(status, 0)) for status in STATUSES})
    kpis["unscored"] = int((~machines["machine_id"].isin(latest["machine_id"])).sum())
    return kpis


def sensor_trend(hourly: Any, sensor_type: str) -> Any:
    """One sensor's hourly average and maximum per machine, in time order.

    ``hourly`` is ``mrt_machine_hourly``. Raises ``ValueError`` for a sensor
    type outside the contract.
    """
    if sensor_type not in SENSOR_TYPES:
        raise ValueError(f"unknown sensor type {sensor_type!r}: expected one of {SENSOR_TYPES}")
    columns = ["machine_id", "hour_start", f"{sensor_type}_avg", f"{sensor_type}_max"]
    return hourly[columns].sort_values(["machine_id", "hour_start"], ignore_index=True)
