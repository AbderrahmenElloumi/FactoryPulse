"""FactoryPulse schedules (ticket 06): a daily DAG and a weekly DAG.

Airflow is a pure orchestrator here. Each task runs one step of a driver script
from the repository root, and each step runs one compose service with
``docker compose run --rm <service>``. A task is therefore the exact command a
human types to run that step by hand. The DAGs add the schedule, the order,
retries, and failure visibility, and nothing else.

- ``factorypulse_daily``: batch ingestion (an idempotent Delta MERGE on
  ``event_id``), the raw lake checks, the dbt build of every model except the
  weekly grain, then the checks of those models. A failed raw check stops dbt
  from building on bad data.
- ``factorypulse_weekly``: the weekly mart (``mrt_machine_weekly``, one row per
  machine per ISO week, rolled up from the hourly mart), then its checks.

A failed task can be cleared and rerun safely. Ingestion merges by key, and
every dbt model is a table rebuilt in full under a deterministic surrogate key
(``machine_hour_key``, ``machine_week_key``), so a rerun rewrites the same rows.
The quality checks then assert that those keys are unique.
"""

import os
from datetime import datetime, timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

# BashOperator runs each command in a temporary directory. The drivers and
# `docker compose` need the repository root, mounted in the Airflow containers
# at the path the Docker daemon knows it by (see compose.yaml). Without it the
# job services would bind empty directories and fail without naming the cause,
# so the file refuses to load and the UI shows this message instead.
PROJECT_DIR = os.environ.get("FACTORYPULSE_HOST_DIR", "")
if not PROJECT_DIR:
    raise RuntimeError(
        "FACTORYPULSE_HOST_DIR is not set: set it in .env to the repository's "
        "path as the Docker daemon sees it (see .env.example)"
    )

# Compose interpolates the task-token secret from .env and leaves it empty when
# unset. Each Airflow process would then sign with its own random secret, and
# every task would fail on an authentication error that does not name it.
if not os.environ.get("AIRFLOW__API_AUTH__JWT_SECRET", ""):
    raise RuntimeError("AIRFLOW_JWT_SECRET is not set: set it in .env (see .env.example)")

default_args = {
    "owner": "factorypulse",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

# Shared by both DAGs: one run at a time, because two runs at once would write
# the same Delta tables; no catchup, so unpausing does not queue one run per
# missed interval since start_date.
common = {
    "default_args": default_args,
    "start_date": datetime(2026, 1, 1),
    "catchup": False,
    "max_active_runs": 1,
    "tags": ["factorypulse"],
}


def step(task_id: str, command: str) -> BashOperator:
    """A task that runs one driver step from the repository root."""
    return BashOperator(task_id=task_id, bash_command=command, cwd=PROJECT_DIR)


with DAG(
    "factorypulse_daily",
    description="Batch ingestion, raw lake checks, daily dbt build, model checks",
    schedule="@daily",
    **common,
) as daily_dag:
    (
        step("run_batch_ingestion", "bash scripts/lake.sh batch")
        >> step("check_ingestion_quality", "bash scripts/quality.sh ingestion")
        >> step("run_dbt_transformations", "bash scripts/dbt.sh daily")
        >> step("check_post_dbt_quality", "bash scripts/quality.sh post-dbt")
    )


# Monday 02:00 UTC: the ISO week (Monday to Sunday) has closed, and the daily
# run at midnight has put Sunday's readings in the hourly mart.
with DAG(
    "factorypulse_weekly",
    description="Weekly mart (machine x ISO week) and its checks",
    schedule="0 2 * * 1",
    **common,
) as weekly_dag:
    (
        step("build_weekly_mart", "bash scripts/dbt.sh weekly")
        >> step("check_weekly_quality", "bash scripts/quality.sh weekly")
    )
