"""Rerunning the scheduled tasks leaves the lake unchanged (ticket 06).

This is the property that makes a failed Airflow task safe to clear and rerun:
batch ingestion merges by ``event_id``, and every dbt model is a table rebuilt
under a deterministic surrogate key. The test runs the DAGs' own write tasks
over the same range a second time, through Airflow, and asserts by the rows
per key (which also fixes the row counts) and by the uniqueness of the
surrogate keys, never by reading the merge statement.

It needs the running stack (MinIO, the Airflow services, a built lake) and
takes several minutes of Spark, so it is opt-in. The streamer must be stopped,
since it would append to the raw lake between the two snapshots:

    docker compose --profile airflow up -d airflow-webserver airflow-scheduler airflow-dag-processor
    FACTORYPULSE_STACK_TESTS=1 python -m pytest tests/test_pipeline_idempotency.py
"""

import os
import subprocess
from pathlib import Path

import pytest

from factorypulse import analytics, lake

pytestmark = pytest.mark.skipif(
    os.environ.get("FACTORYPULSE_STACK_TESTS") != "1",
    reason="needs the running Airflow stack; set FACTORYPULSE_STACK_TESTS=1",
)

ROOT = Path(__file__).resolve().parent.parent

# Every task that writes to the lake, in the order the DAGs run them.
WRITE_TASKS = [
    ("factorypulse_daily", "run_batch_ingestion"),
    ("factorypulse_daily", "run_dbt_transformations"),
    ("factorypulse_weekly", "build_weekly_mart"),
]

# The surrogate key of each table dbt builds: unique by construction, so a
# duplicated write shows up as a repeated key even when a count happens to match.
KEYS = {
    analytics.FCT_SENSOR_READINGS_CLEAN: "event_id",
    analytics.DIM_MACHINE: "machine_id",
    analytics.MRT_MACHINE_HOURLY: "machine_hour_key",
    analytics.MRT_MACHINE_WEEKLY: "machine_week_key",
}

# The raw lake is append-only from two directions: the streamer appends at
# least once, and the batch job MERGEs on event_id. It may therefore hold a
# replayed event twice, and the fact keeps one row per event
# (fct_sensor_readings_clean.sql). Its key is not unique; a rerun must add no
# copy of any event.
RAW_KEY = (analytics.RAW_EVENTS_TABLE, "event_id")


@pytest.fixture
def lake_env(env, monkeypatch):
    for name, value in env.items():
        monkeypatch.setenv(name, value)


def _run_task(dag_id, task_id):
    """Run one DAG task through Airflow, exactly as the scheduler would."""
    result = subprocess.run(
        ["docker", "compose", "--profile", "airflow", "exec", "-T", "airflow-scheduler",
         "airflow", "tasks", "test", dag_id, task_id],
        cwd=ROOT, capture_output=True, text=True, timeout=1200,
    )
    assert result.returncode == 0, f"{dag_id}.{task_id} failed:\n{result.stdout[-3000:]}"


def _copies(table, key):
    """How many rows hold each key value."""
    return lake.read_table(table)[key].value_counts().to_dict()


def _snapshot():
    copies = {table: _copies(table, key) for table, key in [*KEYS.items(), RAW_KEY]}
    for table in KEYS:
        repeated = [key for key, count in copies[table].items() if count > 1]
        assert not repeated, f"{table} repeats keys: {repeated[:5]}"
    return copies


def test_rerunning_every_write_task_duplicates_no_lake_record(lake_env):
    for dag_id, task_id in WRITE_TASKS:
        _run_task(dag_id, task_id)
    once = _snapshot()

    for dag_id, task_id in WRITE_TASKS:
        _run_task(dag_id, task_id)
    twice = _snapshot()

    assert all(once.values()), [table for table, copies in once.items() if not copies]
    # Same keys, same number of rows per key, in every table: the rerun added
    # no row, and no copy of any key.
    for table in once:
        assert twice[table] == once[table], f"the rerun changed {table}"
